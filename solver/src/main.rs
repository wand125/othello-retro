mod board;
mod edge;
mod find;
mod fix;
mod optimize;
mod retro;
mod sat;
mod solver;

use board::*;
use solver::{replay, Outcome, Stats, PASS};
use std::time::Duration;

const USAGE: &str = "\
usage:
  othello-retro solve [FILE] [--time SEC | --no-time-limit] [--seed N]   盤面（FILE または標準入力）から棋譜を 1 つ復元
  othello-retro gen MOVES [--seed N] [--perturb K]     ランダム対局で MOVES 手進めた盤面を出力（K 個の石の色を反転）
  othello-retro bench MOVES COUNT [--time SEC] [--perturb K]

共通: --method sat|backward|forward（既定 sat）, --solver PATH（SAT ソルバー、既定 kissat）, --jobs N（各エンコードのシード数、既定 1）,
      --prepass-ms MS（SAT の前に DFS を試す時間、既定 300、0 で無効）, --book K（序盤表の手数、既定 9）

盤面: 8 行、1 行目が a1..h1。黒 X、白 O、空 -（空白は無視）";

struct Opts {
    pos: Vec<String>,
    time: f64,
    no_time_limit: bool,
    seed: u64,
    perturb: usize,
    method: String,
    book: u32,
    solver: String,
    jobs: usize,
    prepass_ms: u64,
    enc: String,
    json: bool,
    objective: String,
    moves: Option<String>,
    window: usize,
    solutions: usize,
    time_opt: f64,
    passes: bool,
    weights: String,
    fix_mode: String,
    k: usize,
    protect: String,
    each: f64,
    each_kissat: f64,
    first: f64,
}

fn parse_args() -> Result<Opts, String> {
    let mut o = Opts { pos: vec![], time: 10.0, no_time_limit: false, seed: 1, perturb: 0, method: "sat".into(), book: 9, solver: "kissat".into(), jobs: 1, prepass_ms: 300, enc: String::new(), json: false, objective: "last:1".into(), moves: None, window: 12, solutions: 5, time_opt: 60.0, passes: false, weights: String::new(), fix_mode: "nearest".into(), k: 3, protect: String::new(), each: 600.0, each_kissat: 600.0, first: 30.0 };
    let mut it = std::env::args().skip(1);
    while let Some(a) = it.next() {
        let mut val = |name: &str| it.next().ok_or(format!("{name} に値がありません"));
        match a.as_str() {
            "--no-time-limit" => o.no_time_limit = true,
            "--time" => o.time = val("--time")?.parse().map_err(|_| "--time が不正")?,
            "--seed" => o.seed = val("--seed")?.parse().map_err(|_| "--seed が不正")?,
            "--book" => o.book = val("--book")?.parse().map_err(|_| "--book が不正")?,
            "--method" => {
                o.method = val("--method")?;
                if !["sat", "backward", "forward"].contains(&o.method.as_str()) {
                    return Err(format!("不明な method: {}", o.method));
                }
            }
            "--solver" => o.solver = val("--solver")?,
            "--prepass-ms" => o.prepass_ms = val("--prepass-ms")?.parse().map_err(|_| "--prepass-ms が不正")?,
            "--json" => o.json = true,
            "--passes" => o.passes = true,
            "--weights" => o.weights = val("--weights")?,
            "--mode" => o.fix_mode = val("--mode")?,
            "--k" => o.k = val("--k")?.parse().map_err(|_| "--k が不正")?,
            "--protect" => o.protect = val("--protect")?,
            "--each" => o.each = val("--each")?.parse().map_err(|_| "--each が不正")?,
            "--first" => o.first = val("--first")?.parse().map_err(|_| "--first が不正")?,
            "--each-kissat" => o.each_kissat = val("--each-kissat")?.parse().map_err(|_| "--each-kissat が不正")?,
            "--objective" => o.objective = val("--objective")?,
            "--moves" => o.moves = Some(val("--moves")?),
            "--window" => o.window = val("--window")?.parse().map_err(|_| "--window が不正")?,
            "--solutions" => o.solutions = val("--solutions")?.parse().map_err(|_| "--solutions が不正")?,
            "--opt-time" => o.time_opt = val("--opt-time")?.parse().map_err(|_| "--opt-time が不正")?,
            "--enc" => o.enc = val("--enc")?,
            "--jobs" => o.jobs = val("--jobs")?.parse().map_err(|_| "--jobs が不正")?,
            "--perturb" => o.perturb = val("--perturb")?.parse().map_err(|_| "--perturb が不正")?,
            _ => o.pos.push(a),
        }
    }
    Ok(o)
}

pub struct Rng(u64);
impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        self.0
    }
    fn pick(&mut self, mut bits: u64) -> u32 {
        let k = self.next() % bits.count_ones() as u64;
        for _ in 0..k {
            bits &= bits - 1;
        }
        bits.trailing_zeros()
    }
}

fn generate(moves: usize, perturb: usize, seed: u64) -> (u64, u64) {
    let mut rng = Rng(seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
    let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
    let mut placed = 0;
    while placed < moves {
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, o);
        if legal == 0 {
            if legal_moves(o, p) == 0 {
                break;
            }
        } else {
            (b, w) = play(b, w, side, rng.pick(legal));
            placed += 1;
        }
        side = 1 - side;
    }
    for _ in 0..perturb {
        let m = 1u64 << rng.pick(b | w);
        if b & m != 0 {
            b &= !m;
            w |= m;
        } else {
            w &= !m;
            b |= m;
        }
    }
    (b, w)
}

/// パスなしで 60 手打ち切ったランダム対局の各局面（0..=60 手）。パスが起きたら None。
fn passfree_full_game(rng: &mut Rng) -> Option<Vec<(u64, u64)>> {
    let (mut b, mut w) = (INIT_BLACK, INIT_WHITE);
    let mut out = vec![(b, w)];
    for t in 0..60u8 {
        let side = t % 2;
        let (p, q) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, q);
        if legal == 0 {
            return None;
        }
        (b, w) = play(b, w, side, rng.pick(legal));
        out.push((b, w));
    }
    Some(out)
}

/// 終局まで打つ。greedy は「相手の着手可能数を減らす・隅を取る・隅の斜め隣を避ける」＋乱数。
fn full_game(rng: &mut Rng, greedy: bool) -> (u64, u64, u32) {
    let (mut b, mut w, mut side, mut passes) = (INIT_BLACK, INIT_WHITE, 0u8, 0u32);
    loop {
        let (p, q) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, q);
        if legal == 0 {
            if legal_moves(q, p) == 0 {
                return (b, w, passes);
            }
            passes += 1;
            side = 1 - side;
            continue;
        }
        let sq = if greedy {
            const CORNERS: u64 = 0x8100_0000_0000_0081;
            const XSQ: u64 = 0x0042_0000_0000_4200;
            let mut best = (i64::MIN, 0u32);
            let mut m = legal;
            while m != 0 {
                let s = m.trailing_zeros();
                m &= m - 1;
                let (nb, nw) = play(b, w, side, s);
                let (np, nq) = if side == 0 { (nb, nw) } else { (nw, nb) };
                let bit = 1u64 << s;
                let v = -(legal_moves(nq, np).count_ones() as i64) * 10
                    + if bit & CORNERS != 0 { 100 } else { 0 }
                    - if bit & XSQ != 0 { 50 } else { 0 }
                    + (rng.next() % 40) as i64;
                if v > best.0 {
                    best = (v, s);
                }
            }
            best.1
        } else {
            rng.pick(legal)
        };
        (b, w) = play(b, w, side, sq);
        side = 1 - side;
    }
}

/// 終局までの各局面（着手ごと）とパス回数。greedy は full_game と同じ評価。
fn game_path(rng: &mut Rng, greedy: bool) -> (Vec<(u64, u64)>, u32) {
    let (p, _, passes) = game_path_movers(rng, greedy);
    (p, passes)
}

/// 終局までの各局面・各着手を打った側・パス回数
fn game_path_movers(rng: &mut Rng, greedy: bool) -> (Vec<(u64, u64)>, Vec<u8>, u32) {
    let mut movers = vec![];
    let (path, passes) = game_path_inner(rng, greedy, &mut movers);
    (path, movers, passes)
}

fn game_path_inner(rng: &mut Rng, greedy: bool, movers: &mut Vec<u8>) -> (Vec<(u64, u64)>, u32) {
    let (mut b, mut w, mut side, mut passes) = (INIT_BLACK, INIT_WHITE, 0u8, 0u32);
    let mut path = vec![(b, w)];
    loop {
        let (p, q) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, q);
        if legal == 0 {
            if legal_moves(q, p) == 0 {
                return (path, passes);
            }
            passes += 1;
            side = 1 - side;
            continue;
        }
        let sq = if greedy { greedy_move(b, w, side, legal, rng) } else { rng.pick(legal) };
        (b, w) = play(b, w, side, sq);
        path.push((b, w));
        movers.push(side);
        side = 1 - side;
    }
}

fn greedy_move(b: u64, w: u64, side: u8, legal: u64, rng: &mut Rng) -> u32 {
    const CORNERS: u64 = 0x8100_0000_0000_0081;
    const XSQ: u64 = 0x0042_0000_0000_4200;
    let mut best = (i64::MIN, 0u32);
    let mut m = legal;
    while m != 0 {
        let s = m.trailing_zeros();
        m &= m - 1;
        let (nb, nw) = play(b, w, side, s);
        let (np, nq) = if side == 0 { (nb, nw) } else { (nw, nb) };
        let bit = 1u64 << s;
        let v = -(legal_moves(nq, np).count_ones() as i64) * 10 + if bit & CORNERS != 0 { 100 } else { 0 }
            - if bit & XSQ != 0 { 50 } else { 0 }
            + (rng.next() % 40) as i64;
        if v > best.0 {
            best = (v, s);
        }
    }
    best.1
}

/// 引数がファイルならその中身、"黒hex,白hex" ならそのまま、省略時は標準入力。
fn read_input(arg: Option<&String>) -> Result<String, String> {
    match arg {
        Some(a) if std::path::Path::new(a).exists() => std::fs::read_to_string(a).map_err(|e| format!("{a}: {e}")),
        Some(a) if a.contains(',') => Ok(a.clone()),
        Some(a) if a.chars().count() == 64 => Ok(a.clone()), // 64 文字の盤面
        Some(a) => Err(format!("{a}: ファイルが無い")),
        None => std::io::read_to_string(std::io::stdin()).map_err(|e| e.to_string()),
    }
}

/// 盤面テキストか "黒hex,白hex" を受け付ける。
fn parse_any(text: &str) -> Result<(u64, u64), String> {
    let t = text.trim();
    if let Some((a, b)) = t.split_once(',') {
        let h = |x: &str| u64::from_str_radix(x.trim().trim_start_matches("0x"), 16).map_err(|e| e.to_string());
        return Ok((h(a)?, h(b)?));
    }
    parse(t)
}

fn print_record(path: &[u8]) {
    let compact: String = path.iter().filter(|&&m| m != PASS).map(|&m| sq_name(m)).collect();
    println!("record: {compact}");
    let mut annotated = Vec::new();
    for (i, &m) in path.iter().enumerate() {
        let c = if i % 2 == 0 { 'B' } else { 'W' };
        annotated.push(if m == PASS { format!("{c}:pass") } else { format!("{c}:{}", sq_name(m)) });
    }
    println!("moves:  {}", annotated.join(" "));
}

struct Solver {
    method: String,
    k: u32,
    book: Option<retro::Book>,
    sat: String,
    jobs: usize,
    prepass: Duration,
}

impl Solver {
    fn new(o: &Opts) -> Self {
        let book = (o.method == "backward").then(|| retro::build_book(o.book));
        Solver { method: o.method.clone(), k: o.book, book, sat: o.solver.clone(), jobs: o.jobs, prepass: Duration::from_millis(o.prepass_ms) }
    }
    fn solve(&self, b: u64, w: u64, limit: Duration, seed: u64) -> (Outcome, Stats) {
        match (self.method.as_str(), &self.book) {
            ("sat", _) => sat::solve(b, w, limit, &self.sat, self.jobs, self.prepass),
            ("backward", Some(book)) => retro::solve(book, self.k, b, w, limit, seed),
            _ => solver::solve(b, w, limit, seed),
        }
    }
}

fn run() -> Result<(), String> {
    let o = parse_args()?;
    let cmd = o.pos.first().map(String::as_str).unwrap_or("");
    if o.no_time_limit && (cmd != "solve" || o.method != "sat") {
        return Err("--no-time-limit は solve --method sat で使用してください".into());
    }
    let limit = if o.no_time_limit { Duration::MAX } else { Duration::from_secs_f64(o.time) };
    match cmd {
        "solve" => {
            let text = read_input(o.pos.get(1))?;
            let (b, w) = parse_any(&text)?;
            let (out, st) = Solver::new(&o).solve(b, w, limit, o.seed);
            let info = format!(
                "nodes={} restarts={} time={:.3}s",
                st.nodes,
                st.restarts,
                st.elapsed.as_secs_f64()
            );
            if let Outcome::Found(path) = &out {
                let ok = replay(path).map(|r| r == (b, w));
                if ok != Ok(true) {
                    return Err(format!("内部エラー: 復元した棋譜が検証に失敗 ({ok:?})"));
                }
            }
            if o.json {
                // UI 用。moves は着手マス（"pass" を含む）、手番は黒から交互
                let esc = |x: &str| x.replace('\\', "\\\\").replace('"', "\\\"");
                let (status, reason, moves) = match &out {
                    Outcome::Found(path) => ("found", String::new(), path.clone()),
                    Outcome::Unreachable(why) => ("unreachable", why.clone(), vec![]),
                    Outcome::Unknown => ("unknown", String::new(), vec![]),
                };
                let mv: Vec<String> = moves
                    .iter()
                    .map(|&m| if m == PASS { "\"pass\"".to_string() } else { format!("\"{}\"", sq_name(m)) })
                    .collect();
                println!(
                    "{{\"status\":\"{status}\",\"reason\":\"{}\",\"moves\":[{}],\"time\":{:.3}}}",
                    esc(&reason),
                    mv.join(","),
                    st.elapsed.as_secs_f64()
                );
                return Ok(());
            }
            match out {
                Outcome::Found(path) => {
                    println!("status: found ({} plies, {info})", path.len());
                    print_record(&path);
                }
                Outcome::Unreachable(why) => println!("status: unreachable — {why} ({info})"),
                Outcome::Unknown => println!("status: unknown (time limit, {info})"),
            }
        }
        "gen" => {
            let n: usize = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "MOVES が不正")?;
            let (b, w) = generate(n, o.perturb, o.seed);
            print!("{}", format_board(b, w));
        }
        "bench" => {
            let n: usize = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "MOVES が不正")?;
            let count: u64 = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "COUNT が不正")?;
            let solver = Solver::new(&o);
            let (mut found, mut unr, mut unk) = (0, 0, 0);
            let mut times = Vec::new();
            for seed in 1..=count {
                let (b, w) = generate(n, o.perturb, seed);
                let (out, st) = solver.solve(b, w, limit, seed);
                let t = st.elapsed.as_secs_f64();
                times.push(t);
                let tag = match out {
                    Outcome::Found(path) => {
                        assert_eq!(replay(&path), Ok((b, w)));
                        found += 1;
                        "found".to_string()
                    }
                    Outcome::Unreachable(why) => {
                        unr += 1;
                        format!("unreachable ({why})")
                    }
                    Outcome::Unknown => {
                        unk += 1;
                        "unknown".to_string()
                    }
                };
                println!("seed {seed:>4}: {t:>8.3}s nodes={:>10} {tag}", st.nodes);
            }
            times.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let med = times[times.len() / 2];
            let max = times[times.len() - 1];
            println!("---\nfound={found} unreachable={unr} unknown={unk} median={med:.3}s max={max:.3}s");
        }
        "cnf" => {
            // 実験用: CNF を標準出力へ。--enc nopass,occ,noamo
            let text = read_input(o.pos.get(1))?;
            let (b, w) = parse_any(&text)?;
            let mut out = std::io::BufWriter::new(std::io::stdout().lock());
            sat::write_cnf(b, w, sat::EncOpts::parse(&o.enc), &mut out).map_err(|e| e.to_string())?;
        }
        "beam" => {
            // 見つける専用ビームサーチの評価: パスなし全マス対局の最終盤面から復元できるか
            let games: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            let width: usize = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "WIDTH が不正")?;
            let score = match o.pos.get(3).map(String::as_str).unwrap_or("kids") {
                "kids" => find::Score::Kids,
                "kids2" => find::Score::Kids2,
                "random" => find::Score::Random,
                x => return Err(format!("不明な score: {x}")),
            };
            let book = retro::build_book(9);
            let mut ok = 0;
            for g in 0..games {
                let mut rng = Rng((o.seed * 1_000_003 + g).wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                let truth = loop {
                    if let Some(p) = passfree_full_game(&mut rng) {
                        break p;
                    }
                };
                let t0 = std::time::Instant::now();
                let r = find::beam(truth[60], width, score, &book, g);
                let tag = match &r.path {
                    Some(path) => {
                        let sq = find::to_moves(path).ok_or("序盤手順が見つからない")?;
                        let rec = retro::with_passes(&sq);
                        assert_eq!(replay(&rec), Ok(truth[60]), "復元した棋譜が検証に失敗");
                        ok += 1;
                        "found".to_string()
                    }
                    None => format!("failed (reached {} moves)", r.reached),
                };
                println!("game {g:>3}: {:>7.2}s evals={:>9} {tag}", t0.elapsed().as_secs_f64(), r.evals);
            }
            println!("---\nfound {ok}/{games}");
        }
        "hybrid" => {
            // 案 A の評価: 後ろ向きに DEPTH 手戻した候補 K 個を SAT で並列に解く。DEPTH=0 は SAT 単独
            let games: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            let depth: u32 = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "DEPTH が不正")?;
            let k: usize = o.pos.get(3).map(|x| x.parse().unwrap_or(4)).unwrap_or(4);
            let mut times = vec![];
            for g in 0..games {
                let mut rng = Rng((o.seed * 1_000_003 + g).wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                let truth = loop {
                    if let Some(p) = passfree_full_game(&mut rng) {
                        break p;
                    }
                };
                let t0 = std::time::Instant::now();
                let paths = if depth == 0 { vec![vec![truth[60]]] } else { find::frontier(truth[60], k, 60 - depth, g) };
                let t_back = t0.elapsed().as_secs_f64();
                let starts: Vec<(u64, u64)> = paths.iter().map(|p| p[0]).collect();
                let tag = match sat::find_any_passfree(&starts, limit, &o.solver) {
                    Ok((i, mut sq)) => {
                        for win in paths[i].windows(2) {
                            let (a, b) = (win[0].0 | win[0].1, win[1].0 | win[1].1);
                            sq.push((b & !a).trailing_zeros() as u8);
                        }
                        let rec = retro::with_passes(&sq);
                        assert_eq!(replay(&rec), Ok(truth[60]), "復元した棋譜が検証に失敗");
                        format!("found (candidate {i})")
                    }
                    Err(_) => "not found".to_string(),
                };
                let t = t0.elapsed().as_secs_f64();
                times.push(t);
                println!("game {g:>3}: {t:>7.2}s (backward {t_back:.2}s, {} candidates) {tag}", starts.len());
            }
            times.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!("---\nmedian={:.2}s max={:.2}s", times[times.len() / 2], times[times.len() - 1]);
        }
        "fullset" => {
            // テスト用の全マス盤面: fullset COUNT STYLE(random|greedy) PASSES(none|some|any) → "黒hex,白hex passes=K"
            let count: usize = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "COUNT が不正")?;
            let style = o.pos.get(2).map(String::as_str).unwrap_or("random");
            let want = o.pos.get(3).map(String::as_str).unwrap_or("any");
            let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
            let mut got = 0;
            while got < count {
                let (b, w, passes) = full_game(&mut rng, style == "greedy");
                if (b | w) != u64::MAX {
                    continue;
                }
                let ok = match want { "none" => passes == 0, "some" => passes > 0, _ => true };
                if ok {
                    println!("{b:016x},{w:016x} passes={passes}");
                    got += 1;
                }
            }
        }
        "frontier" => {
            // 実験用: パスなし全マス対局 GAME の最終盤面から DEPTH 手戻した候補 K 個を hex で出す
            let g: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAME が不正")?;
            let depth: u32 = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "DEPTH が不正")?;
            let k: usize = o.pos.get(3).ok_or(USAGE)?.parse().map_err(|_| "K が不正")?;
            let mut rng = Rng((o.seed * 1_000_003 + g).wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
            let truth = loop {
                if let Some(p) = passfree_full_game(&mut rng) {
                    break p;
                }
            };
            for p in find::frontier(truth[60], k, 60 - depth, g) {
                println!("{:016x},{:016x}", p[0].0, p[0].1);
            }
        }
        "spine" if o.passes => {
            // 学習データ用（パスあり）: パスを含む全マス対局の正解経路に沿って戻し、各段の兄弟候補（局面＋次の手番）を出す。
            // 候補 c は「戻した局面で次に打つ側」。正解の子には t = 1
            let games: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            let style = o.pos.get(2).map(String::as_str).unwrap_or("mix");
            let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
            for g in 0..games {
                let greedy = style == "greedy" || (style == "mix" && g % 2 == 1);
                let (truth, movers) = loop {
                    let (p, mv, passes) = game_path_movers(&mut rng, greedy);
                    if passes > 0 && p.len() == 61 {
                        break (p, mv);
                    }
                };
                for n in (2..=60usize).rev() {
                    let (pb, pw) = truth[n];
                    let nxt = if n == 60 { retro::ANY } else { movers[n] };
                    let tc = (truth[n - 1], movers[n - 1]);
                    let mut kids: Vec<(u64, u64, u8)> = retro::undos_plain(pb, pw, nxt).into_iter().map(|k| (k.1, k.2, k.3)).collect();
                    kids.sort_unstable();
                    kids.dedup();
                    let items: Vec<String> = kids
                        .iter()
                        .map(|&(qb, qw, c)| format!("{{\"q\":\"{qb:016x},{qw:016x}\",\"c\":{c},\"t\":{}}}", ((qb, qw) == tc.0 && c == tc.1) as u8))
                        .collect();
                    println!(
                        "{{\"g\":{g},\"style\":\"{}\",\"n\":{n},\"parent\":\"{pb:016x},{pw:016x}\",\"children\":[{}]}}",
                        if greedy { "greedy" } else { "random" },
                        items.join(",")
                    );
                }
            }
        }
        "reach" => {
            // ラベル付け用: 局面 Q に、次に C が打つ状態で到達できるか（パスは直前 12 手の中だけ許す近似）。
            // reach 黒hex,白hex C --time 秒 → sat / unsat / unknown
            let (qb, qw) = parse_any(o.pos.get(1).ok_or(USAGE)?)?;
            let c: u8 = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "C が不正")?;
            println!("{}", sat::reach(qb, qw, c, limit, &o.solver));
        }
        "spine" => {
            // 学習データ用: パスなし全マス対局の正解経路に沿って戻し、各段の兄弟候補と特徴量を JSONL で出す
            // spine GAMES STYLE(random|greedy|mix)
            let games: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            let style = o.pos.get(2).map(String::as_str).unwrap_or("mix");
            let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
            for g in 0..games {
                let greedy = style == "greedy" || (style == "mix" && g % 2 == 1);
                let truth = loop {
                    let (p, passes) = game_path(&mut rng, greedy);
                    if passes == 0 && p.len() == 61 {
                        break p;
                    }
                };
                for n in (2..=60usize).rev() {
                    let (pb, pw) = truth[n];
                    let tc = truth[n - 1];
                    let mut kids = find::passfree_undos(pb, pw);
                    kids.sort_unstable();
                    kids.dedup();
                    let mut items = vec![];
                    for &(qb, qw) in &kids {
                        let sq = ((pb | pw) & !(qb | qw)).trailing_zeros();
                        let nf = ((qb ^ pb) & (qw ^ pw)).count_ones();
                        let k = find::passfree_undos(qb, qw).len();
                        let empty = !(qb | qw);
                        let fr = (DIRS.iter().fold(0, |a, &d| a | shift(empty, d)) & (qb | qw)).count_ones();
                        items.push(format!(
                            "{{\"q\":\"{qb:016x},{qw:016x}\",\"sq\":{sq},\"nf\":{nf},\"kids\":{k},\"mb\":{},\"mw\":{},\"fr\":{fr},\"t\":{}}}",
                            legal_moves(qb, qw).count_ones(),
                            legal_moves(qw, qb).count_ones(),
                            ((qb, qw) == tc) as u8
                        ));
                    }
                    println!(
                        "{{\"g\":{g},\"style\":\"{}\",\"n\":{n},\"parent\":\"{pb:016x},{pw:016x}\",\"children\":[{}]}}",
                        if greedy { "greedy" } else { "random" },
                        items.join(",")
                    );
                }
            }
        }
        "undo-server" => {
            // 探索用の常駐プロセス。1 行 1 局面を読み、1 手戻した候補を空白区切りで返す。
            //   "黒hex,白hex"        → パスなし仮定。候補は "黒hex,白hex"
            //   "黒hex,白hex 次の手番" → パスも扱う（0 黒 / 1 白 / 2 終局 / 3 不問）。候補は "黒hex,白hex:打った側"
            //     （戻した局面では、その「打った側」が次の手番になる）
            use std::io::{BufRead, Write};
            let stdin = std::io::stdin();
            let mut out = std::io::BufWriter::new(std::io::stdout().lock());
            for line in stdin.lock().lines() {
                let line = line.map_err(|e| e.to_string())?;
                let mut it = line.split_whitespace();
                let (b, w) = parse_any(it.next().unwrap_or(""))?;
                let s: Vec<String> = match it.next() {
                    None => {
                        let mut kids = find::passfree_undos(b, w);
                        kids.sort_unstable();
                        kids.dedup();
                        kids.iter().map(|(qb, qw)| format!("{qb:016x},{qw:016x}")).collect()
                    }
                    Some(n) => {
                        let nxt: u8 = n.parse().map_err(|_| "次の手番が不正")?;
                        let mut kids: Vec<(u64, u64, u8)> = retro::undos_plain(b, w, nxt).into_iter().map(|k| (k.1, k.2, k.3)).collect();
                        kids.sort_unstable();
                        kids.dedup();
                        kids.iter().map(|(qb, qw, c)| format!("{qb:016x},{qw:016x}:{c}")).collect()
                    }
                };
                writeln!(out, "{}", s.join(" ")).map_err(|e| e.to_string())?;
                out.flush().map_err(|e| e.to_string())?;
            }
        }
        "findany" => {
            // パスなし仮定で複数の局面を並列に SAT で解き、最初に解けたものの添字と着手を JSON で返す
            let targets: Vec<(u64, u64)> = o.pos[1..].iter().map(|h| parse_any(h)).collect::<Result<_, _>>()?;
            match sat::find_any_passfree(&targets, limit, &o.solver) {
                Ok((i, sq)) => {
                    let mv: Vec<String> = sq.iter().map(|&m| format!("\"{}\"", sq_name(m))).collect();
                    println!("{{\"index\":{i},\"moves\":[{}]}}", mv.join(","));
                }
                // unsat: どの局面もパスなしでは作れない（パスが必要か、到達不能）
                Err(all_unsat) => println!("{{\"index\":null,\"unsat\":{all_unsat}}}"),
            }
        }
        "optimize" => {
            // 棋譜の最適化と別解: optimize 盤面 [--moves 初めの棋譜] [--objective last:1|last:5|total]
            //   [--window 12] [--solutions 5] [--time 秒]。途中経過と結果を 1 行ずつ JSON で出す
            let (b, w) = parse_any(&read_input(o.pos.get(1))?)?;
            let obj = optimize::Objective::parse(&o.objective)?;
            let t0 = std::time::Instant::now();
            let initial: Vec<u8> = match &o.moves {
                Some(m) => {
                    let toks: Vec<u8> = m
                        .as_bytes()
                        .chunks(2)
                        .filter(|c| c.len() == 2 && (b'a'..=b'h').contains(&c[0].to_ascii_lowercase()) && (b'1'..=b'8').contains(&c[1]))
                        .map(|c| (c[1] - b'1') * 8 + (c[0].to_ascii_lowercase() - b'a'))
                        .collect();
                    toks
                }
                None => match Solver::new(&o).solve(b, w, limit, o.seed).0 {
                    Outcome::Found(path) => path.into_iter().filter(|&m| m != PASS).collect(),
                    Outcome::Unreachable(why) => return Err(format!("到達不能: {why}")),
                    Outcome::Unknown => return Err("最初の棋譜が時間内に見つからない".into()),
                },
            };
            let g0 = optimize::analyze(&initial)?;
            if *g0.positions.last().unwrap() != (b, w) {
                return Err("与えた棋譜が盤面と一致しない".into());
            }
            let fmt = |g: &optimize::Game| -> String {
                optimize::record(g)
                    .iter()
                    .map(|&m| if m == PASS { "\"pass\"".to_string() } else { format!("\"{}\"", sq_name(m)) })
                    .collect::<Vec<_>>()
                    .join(",")
            };
            let flips = |g: &optimize::Game| g.flips.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(",");
            // ASMR スコアと内訳
            let score = |b: &optimize::Breakdown| {
                format!(
                    "{{\"score\":{:.2},\"climax\":{},\"finale\":{},\"accents\":{},\"long\":{},\"dirs\":{},\"total\":{},\"boring\":{}}}",
                    b.score, b.climax, b.finale, b.accents, b.long, b.dirs, b.total, b.boring
                )
            };
            let mut progress = |ev: &str, f: &optimize::Found| {
                println!(
                    "{{\"event\":\"{ev}\",\"value\":{},\"time\":{:.3},\"moves\":[{}],\"flips\":[{}],\"asmr\":{}}}",
                    f.value,
                    t0.elapsed().as_secs_f64(),
                    fmt(&f.game),
                    flips(&f.game),
                    score(&f.score)
                );
            };
            let weights = optimize::Weights::parse(&o.weights)?;
            let rep = optimize::optimize(&initial, obj, &weights, o.window, o.solutions, std::time::Duration::from_secs_f64(o.time_opt), &o.solver, &mut progress)?;
            for f in &rep.solutions {
                assert_eq!(*f.game.positions.last().unwrap(), (b, w), "最適化した棋譜が盤面と一致しない");
            }
            let sols: Vec<String> = rep
                .solutions
                .iter()
                .map(|f| format!("{{\"value\":{},\"moves\":[{}],\"flips\":[{}],\"asmr\":{}}}", f.value, fmt(&f.game), flips(&f.game), score(&f.score)))
                .collect();
            println!(
                "{{\"event\":\"done\",\"objective\":\"{}\",\"initial\":{},\"best\":{},\"proven_optimal\":{},\"time\":{:.3},\"solutions\":[{}]}}",
                obj.name(),
                rep.initial_value,
                rep.best.value,
                rep.proven_optimal,
                t0.elapsed().as_secs_f64(),
                sols.join(",")
            );
        }
        "fix" => {
            // 到達不能な盤面の修正補助（CaDiCaL のインクリメンタル SAT）。1 行 1 イベントの JSON を出す
            //   fix 盤面 --mode nearest [--k 3] [--protect 保護するマスの hex] [--solutions 5] [--opt-time 秒]
            //   fix 盤面 --mode map [--each 1 回の上限秒] [--opt-time 秒]
            let (b, w) = parse_any(&read_input(o.pos.get(1))?)?;
            let t0 = std::time::Instant::now();
            let deadline = t0 + std::time::Duration::from_secs_f64(o.time_opt);
            if o.fix_mode == "candidates" {
                // 1 マスだけ裏返した候補と、事前チェック（辺・置き順・中央）の結果
                let occ = b | w;
                let mut ok = 0;
                let mut items = vec![];
                for s in 0..64u8 {
                    if occ >> s & 1 == 0 {
                        continue;
                    }
                    let (cb, cw) = (b ^ (1 << s), w ^ (1 << s));
                    let r = solver::preprocess(cb, cw);
                    ok += r.is_ok() as u32;
                    let why = r.err().unwrap_or_default().replace('"', "'");
                    items.push(format!("{{\"sq\":\"{}\",\"board\":\"{cb:016x},{cw:016x}\",\"ok\":{},\"why\":\"{why}\"}}", sq_name(s), why.is_empty()));
                }
                println!("{{\"event\":\"candidates\",\"total\":{},\"ok\":{ok},\"time\":{:.4},\"items\":[{}]}}", items.len(), t0.elapsed().as_secs_f64(), items.join(","));
                return Ok(());
            }
            // CaDiCaL（インクリメンタル）は nearest-cadical と map だけで使う
            let new_fixer = || {
                let fx = fix::Fixer::new(b, w);
                println!("{{\"event\":\"loaded\",\"time\":{:.3}}}", t0.elapsed().as_secs_f64());
                fx
            };
            match o.fix_mode.as_str() {
                "nearest-both" => {
                    // A（「k 個以下」を節で入れて kissat 3 本並列）と A'（1 マス裏返した候補を kissat 3 本並列で判定、jobs 並列）を
                    // 同時に走らせ、見つかった直し方をまとめる。A が「k 個以下では直せない」と証明したら A' も止める
                    use std::sync::atomic::{AtomicBool, Ordering::SeqCst};
                    let protect = u64::from_str_radix(o.protect.trim_start_matches("0x"), 16).unwrap_or(0);
                    let stop = AtomicBool::new(false);
                    let k1_done = AtomicBool::new(false); // 1 石の変更では直せないと分かった（A' は無駄）
                    let proved_none = AtomicBool::new(false);
                    let found: std::sync::Mutex<Vec<Vec<u8>>> = std::sync::Mutex::new(vec![]); // 見つけた変え方（禁止リストを兼ねる）
                    let emit = |k: usize, changed: Vec<u8>, squares: Vec<u8>, by: &str| -> bool {
                        let mut f = found.lock().unwrap();
                        let mut key = changed.clone();
                        key.sort_unstable();
                        if f.iter().any(|x| *x == key) {
                            return false; // 同じ変え方は報告済み
                        }
                        let (mut tb, mut tw) = (b, w);
                        for &s in &changed {
                            tb ^= 1 << s;
                            tw ^= 1 << s;
                        }
                        let rec = retro::with_passes(&squares);
                        assert_eq!(replay(&rec), Ok((tb, tw)), "修正した盤面への棋譜が検証に失敗");
                        let ch: Vec<String> = changed.iter().map(|&s| format!("\"{}\"", sq_name(s))).collect();
                        let mv: Vec<String> = rec.iter().map(|&m| if m == PASS { "\"pass\"".into() } else { format!("\"{}\"", sq_name(m)) }).collect();
                        println!(
                            "{{\"event\":\"fix\",\"k\":{k},\"by\":\"{by}\",\"time\":{:.3},\"changed\":[{}],\"board\":\"{tb:016x},{tw:016x}\",\"moves\":[{}]}}",
                            t0.elapsed().as_secs_f64(),
                            ch.join(","),
                            mv.join(",")
                        );
                        f.push(key);
                        if changed.is_empty() || f.len() >= o.solutions {
                            stop.store(true, SeqCst);
                        }
                        true
                    };
                    let occ = b | w;
                    let mut cands: Vec<u8> = (0..64u8)
                        .filter(|&s| occ >> s & 1 != 0 && protect >> s & 1 == 0 && solver::preprocess(b ^ (1 << s), w ^ (1 << s)).is_ok())
                        .collect();
                    let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                    for i in (1..cands.len()).rev() {
                        let j = (rng.next() % (i as u64 + 1)) as usize;
                        cands.swap(i, j);
                    }
                    let queue = std::sync::Mutex::new(cands.into_iter());
                    std::thread::scope(|sc| {
                        // A
                        sc.spawn(|| {
                            'ks: for k in 1..=o.k.max(1) {
                                loop {
                                    let left = deadline.saturating_duration_since(std::time::Instant::now());
                                    if left.is_zero() || stop.load(SeqCst) {
                                        break 'ks;
                                    }
                                    let blocks = found.lock().unwrap().clone();
                                    match sat::find_fix_cancel(b, w, k, protect, &blocks, left, &o.solver, Some(&stop)) {
                                        Ok(Some((changed, squares))) => {
                                            emit(k, changed, squares, "A");
                                        }
                                        Ok(None) => {
                                            if k == 1 {
                                                k1_done.store(true, SeqCst);
                                            }
                                            if !found.lock().unwrap().is_empty() {
                                                break 'ks; // 最小の k で見つかった分で終える
                                            }
                                            if k == o.k.max(1) {
                                                proved_none.store(true, SeqCst);
                                            }
                                            break; // k を増やす
                                        }
                                        Err(_) => break 'ks,
                                    }
                                }
                            }
                            stop.store(true, SeqCst); // A が終わったら A' も止める
                        });
                        // A'
                        for _ in 0..o.jobs.max(1) {
                            sc.spawn(|| loop {
                                if stop.load(SeqCst) || k1_done.load(SeqCst) {
                                    break;
                                }
                                let Some(s) = queue.lock().unwrap().next() else { break };
                                let left = deadline.saturating_duration_since(std::time::Instant::now());
                                if left.is_zero() {
                                    break;
                                }
                                let (cb, cw) = (b ^ (1 << s), w ^ (1 << s));
                                if let Some(Some(sq)) = sat::check_free_moves(cb, cw, 0, left.min(std::time::Duration::from_secs_f64(o.each_kissat)), &o.solver, Some(&stop)) {
                                    emit(1, vec![s], sq, "A'");
                                }
                            });
                        }
                    });
                    let n = found.into_inner().unwrap().len();
                    let status = if n > 0 { "found" } else if proved_none.load(SeqCst) { "none" } else { "timeout" };
                    println!("{{\"event\":\"done\",\"status\":\"{status}\",\"time\":{:.3}}}", t0.elapsed().as_secs_f64());
                }
                "nearest" | "nearest-a" => {
                    // A: 「色を変えるのは k 個以下」を節で入れて kissat 3 本並列（既定。ベンチマークで最も安定していた）
                    let protect = u64::from_str_radix(o.protect.trim_start_matches("0x"), 16).unwrap_or(0);
                    let mut blocks: Vec<Vec<u8>> = vec![];
                    let mut status = "none";
                    'ks: for k in 1..=o.k.max(1) {
                        loop {
                            let left = deadline.saturating_duration_since(std::time::Instant::now());
                            if left.is_zero() || blocks.len() >= o.solutions {
                                break 'ks;
                            }
                            match sat::find_fix(b, w, k, protect, &blocks, left, &o.solver) {
                                Ok(Some((changed, squares))) => {
                                    let (mut tb, mut tw) = (b, w);
                                    for &s in &changed {
                                        tb ^= 1 << s;
                                        tw ^= 1 << s;
                                    }
                                    let rec = retro::with_passes(&squares);
                                    assert_eq!(replay(&rec), Ok((tb, tw)), "修正した盤面への棋譜が検証に失敗");
                                    let ch: Vec<String> = changed.iter().map(|&s| format!("\"{}\"", sq_name(s))).collect();
                                    let mv: Vec<String> = rec.iter().map(|&m| if m == PASS { "\"pass\"".into() } else { format!("\"{}\"", sq_name(m)) }).collect();
                                    println!("{{\"event\":\"fix\",\"k\":{k},\"by\":\"A\",\"time\":{:.3},\"changed\":[{}],\"board\":\"{tb:016x},{tw:016x}\",\"moves\":[{}]}}", t0.elapsed().as_secs_f64(), ch.join(","), mv.join(","));
                                    status = "found";
                                    if changed.is_empty() {
                                        break 'ks;
                                    }
                                    blocks.push(changed);
                                }
                                Ok(None) => {
                                    if status == "found" {
                                        break 'ks;
                                    }
                                    break;
                                }
                                Err(_) => {
                                    if status != "found" {
                                        status = "timeout";
                                    }
                                    break 'ks;
                                }
                            }
                        }
                    }
                    println!("{{\"event\":\"done\",\"status\":\"{status}\",\"time\":{:.3}}}", t0.elapsed().as_secs_f64());
                }
                "nearest-cand" => {
                    let occ = b | w;
                    let mut cands: Vec<u8> = (0..64u8).filter(|&s| occ >> s & 1 != 0 && solver::preprocess(b ^ (1 << s), w ^ (1 << s)).is_ok()).collect();
                    let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                    for i in (1..cands.len()).rev() {
                        let j = (rng.next() % (i as u64 + 1)) as usize;
                        cands.swap(i, j);
                    }
                    println!("{{\"event\":\"candidates\",\"ok\":{},\"time\":{:.3}}}", cands.len(), t0.elapsed().as_secs_f64());
                    let queue = std::sync::Mutex::new(cands.into_iter());
                    let found = std::sync::atomic::AtomicUsize::new(0);
                    std::thread::scope(|sc| {
                        for _ in 0..o.jobs.max(1) {
                            sc.spawn(|| loop {
                                if found.load(std::sync::atomic::Ordering::SeqCst) >= o.solutions {
                                    break;
                                }
                                let Some(s) = queue.lock().unwrap().next() else { break };
                                let left = deadline.saturating_duration_since(std::time::Instant::now());
                                if left.is_zero() {
                                    break;
                                }
                                let (cb, cw) = (b ^ (1 << s), w ^ (1 << s));
                                let r = sat::check_free(cb, cw, 0, left.min(std::time::Duration::from_secs_f64(o.each_kissat)), &o.solver);
                                if r == Some(true) {
                                    found.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                                }
                                println!("{{\"event\":\"try\",\"sq\":\"{}\",\"result\":\"{}\",\"time\":{:.3}}}", sq_name(s), match r { Some(true) => "fix", Some(false) => "unreachable", None => "timeout" }, t0.elapsed().as_secs_f64());
                            });
                        }
                    });
                    println!("{{\"event\":\"done\",\"found\":{},\"time\":{:.3}}}", found.into_inner(), t0.elapsed().as_secs_f64());
                }
                "nearest-cadical" => {
                    let mut fx = new_fixer();
                    let protect = u64::from_str_radix(o.protect.trim_start_matches("0x"), 16).unwrap_or(0);
                    let mut report = |k: usize, f: &fix::Fix| {
                        // 検証: 着手を再生した最終盤面が、変えたマスだけ色が違う盤面と一致するか
                        let mut tb = b;
                        let mut tw = w;
                        for &s in &f.changed {
                            tb ^= 1 << s;
                            tw ^= 1 << s;
                        }
                        let rec = retro::with_passes(&f.squares);
                        assert_eq!(replay(&rec), Ok((tb, tw)), "修正した盤面への棋譜が検証に失敗");
                        let ch: Vec<String> = f.changed.iter().map(|&s| format!("\"{}\"", sq_name(s))).collect();
                        let mv: Vec<String> = rec.iter().map(|&m| if m == PASS { "\"pass\"".into() } else { format!("\"{}\"", sq_name(m)) }).collect();
                        println!(
                            "{{\"event\":\"fix\",\"k\":{k},\"time\":{:.3},\"changed\":[{}],\"board\":\"{tb:016x},{tw:016x}\",\"moves\":[{}]}}",
                            t0.elapsed().as_secs_f64(),
                            ch.join(","),
                            mv.join(",")
                        );
                    };
                    let r = fx.nearest(o.k, protect, o.solutions, deadline, &mut report);
                    println!("{{\"event\":\"done\",\"status\":\"{}\",\"time\":{:.3}}}", match r { Ok(f) if !f.is_empty() => "found", Ok(_) => "none", Err(_) => "timeout" }, t0.elapsed().as_secs_f64());
                }
                "map" => {
                    let mut fx = new_fixer();
                    let each = std::time::Duration::from_secs_f64(o.each);
                    let mut report = |s: u8, c: fix::Cell, why: &str| {
                        println!("{{\"event\":\"cell\",\"sq\":\"{}\",\"result\":\"{:?}\",\"why\":\"{why}\",\"time\":{:.3}}}", sq_name(s), c, t0.elapsed().as_secs_f64());
                    };
                    let mut res = fx.map(std::time::Duration::from_secs_f64(o.first), each, deadline, &mut report);
                    // 未判定のマス（主に「変えれば到達可能」側。棋譜を見つける必要があり重い）は、
                    // 速いエンコードの kissat を含む 3 本並列で判定する。jobs マスを同時に処理
                    let todo: Vec<u8> = (0..64u8).filter(|&s| (b | w) >> s & 1 != 0 && res[s as usize] == fix::Cell::Unknown).collect();
                    let queue = std::sync::Mutex::new(todo.into_iter());
                    let results = std::sync::Mutex::new(vec![]);
                    std::thread::scope(|sc| {
                        for _ in 0..o.jobs.max(1) {
                            sc.spawn(|| loop {
                                let Some(s) = queue.lock().unwrap().next() else { break };
                                let left = deadline.saturating_duration_since(std::time::Instant::now());
                                if left.is_zero() {
                                    break;
                                }
                                let r = sat::check_free(b, w, 1u64 << s, left.min(std::time::Duration::from_secs_f64(o.each_kissat)), &o.solver);
                                let cell = match r { Some(true) => fix::Cell::Reachable, Some(false) => fix::Cell::Unreachable, None => fix::Cell::Unknown };
                                println!("{{\"event\":\"cell\",\"sq\":\"{}\",\"result\":\"{:?}\",\"why\":\"kissat\",\"time\":{:.3}}}", sq_name(s), cell, t0.elapsed().as_secs_f64());
                                results.lock().unwrap().push((s, cell));
                            });
                        }
                    });
                    for (s, c) in results.into_inner().unwrap() {
                        res[s as usize] = c;
                    }
                    let grid: Vec<String> = (0..8)
                        .map(|r| {
                            (0..8)
                                .map(|c| {
                                    if (b | w) >> (r * 8 + c) & 1 == 0 {
                                        return '-'; // 石の無いマス
                                    }
                                    match res[r * 8 + c] { fix::Cell::Reachable => 'R', fix::Cell::Unreachable => '.', fix::Cell::Unknown => '?' }
                                })
                                .collect()
                        })
                        .collect();
                    println!("{{\"event\":\"done\",\"time\":{:.3},\"grid\":[{}]}}", t0.elapsed().as_secs_f64(), grid.iter().map(|g| format!("\"{g}\"")).collect::<Vec<_>>().join(","));
                }
                m => return Err(format!("不明な mode: {m}")),
            }
        }
        "walks" => {
            // 学習データ用: パスなしの全マス対局を作り、最終盤面からランダムに戻す経路を JSONL で出す
            let games: u64 = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            let per: usize = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "WALKS が不正")?;
            let book = retro::build_book(9);
            let hex = |p: &[(u64, u64)]| p.iter().map(|(b, w)| format!("\"{b:016x},{w:016x}\"")).collect::<Vec<_>>().join(",");
            for g in 0..games {
                let mut rng = Rng((o.seed * 1_000_003 + g).wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                let truth = loop {
                    if let Some(p) = passfree_full_game(&mut rng) {
                        break p;
                    }
                };
                let target = truth[60];
                println!("{{\"g\":{g},\"walk\":-1,\"end\":\"true\",\"path\":[{}]}}", hex(&truth.iter().rev().copied().collect::<Vec<_>>()));
                for k in 0..per {
                    let mut path = vec![target];
                    let end = loop {
                        let (b, w) = *path.last().unwrap();
                        let n = (b | w).count_ones() - 4;
                        if n == 9 {
                            break if book.contains(&(b, w, 1)) { "book" } else { "nobook" };
                        }
                        let kids = find::passfree_undos(b, w);
                        if kids.is_empty() {
                            break "dead";
                        }
                        let (qb, qw) = kids[(rng.next() % kids.len() as u64) as usize];
                        path.push((qb, qw));
                    };
                    println!("{{\"g\":{g},\"walk\":{k},\"end\":\"{end}\",\"path\":[{}]}}", hex(&path));
                }
            }
        }
        "trace" => {
            // 真の棋譜に沿って後ろ向きに戻し、各段の候補数と真の手の順位を出す
            let n: usize = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "MOVES が不正")?;
            let mut rng = Rng(o.seed.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
            let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
            let mut hist = vec![];
            while hist.len() < n {
                let (p, q) = if side == 0 { (b, w) } else { (w, b) };
                let legal = legal_moves(p, q);
                if legal == 0 {
                    if legal_moves(q, p) == 0 { break; }
                } else {
                    let sq = rng.pick(legal);
                    let prev = (b, w);
                    (b, w) = play(b, w, side, sq);
                    hist.push((prev, side, sq as u8, (b, w)));
                }
                side = 1 - side;
            }
            let mut nxt = retro::ANY;
            for (i, &(prev, c, sq, (cb, cw))) in hist.iter().enumerate().rev() {
                let mut r = 0u32;
                let kids = retro::undos(cb, cw, nxt, &mut || { r = r.wrapping_add(1); r });
                let mut sorted = kids.clone();
                sorted.sort_unstable_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
                let rank = sorted.iter().position(|k| k.2 == sq && (k.3, k.4) == prev && k.5 == c);
                let squares: std::collections::HashSet<u8> = kids.iter().map(|k| k.2).collect();
                println!("ply {:>2}: candidates={:>4} squares={:>3} true_rank={:?}", i + 1, kids.len(), squares.len(), rank);
                nxt = c;
            }
        }
        "features" => {
            // 学習用: 真の棋譜に沿って戻し、全候補の特徴量を CSV で出す
            let n: usize = o.pos.get(1).ok_or(USAGE)?.parse().map_err(|_| "MOVES が不正")?;
            let games: u64 = o.pos.get(2).ok_or(USAGE)?.parse().map_err(|_| "GAMES が不正")?;
            println!("game,ply,true,sq,c,free,nflips,ndirs,mob_c,mob_o,frontier_q,stable_corner");
            for g in 1..=games {
                let mut rng = Rng(g.wrapping_mul(0x2545_F491_4F6C_DD1D) | 1);
                let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
                let mut hist = vec![];
                while hist.len() < n {
                    let (p, q) = if side == 0 { (b, w) } else { (w, b) };
                    let legal = legal_moves(p, q);
                    if legal == 0 {
                        if legal_moves(q, p) == 0 { break; }
                    } else {
                        let sq = rng.pick(legal);
                        let prev = (b, w);
                        (b, w) = play(b, w, side, sq);
                        hist.push((prev, side, sq as u8, (b, w)));
                    }
                    side = 1 - side;
                }
                let mut nxt = retro::ANY;
                for (i, &(prev, c, sq, (cb, cw))) in hist.iter().enumerate().rev() {
                    let kids = retro::undos(cb, cw, nxt, &mut || 0);
                    for k in &kids {
                        let (qb, qw) = (k.3, k.4);
                        let (p, q) = if k.5 == 0 { (qb, qw) } else { (qw, qb) };
                        let nf = ((qb ^ cb) | (qw ^ cw)).count_ones() - 1;
                        let empty = !(qb | qw);
                        let mut nb = 0u64;
                        for &d in &DIRS { nb |= shift(empty, d); }
                        let frontier = (nb & (qb | qw)).count_ones();
                        let m = 1u64 << k.2;
                        let mut ndirs = 0;
                        for &d in &DIRS { let x = shift(m, d); if x & (qb ^ cb) != 0 { ndirs += 1; } }
                        let mut free = 0;
                        for &d in &DIRS { if shift(m, d) & !(cb | cw) != 0 { free += 1; } }
                        let corner = (m & 0x8100_0000_0000_0081 != 0) as u32;
                        let t = (k.2 == sq && (qb, qw) == prev && k.5 == c) as u32;
                        println!("{g},{},{t},{},{},{free},{nf},{ndirs},{},{},{frontier},{corner}", i + 1, k.2, k.5,
                            legal_moves(p, q).count_ones(), legal_moves(q, p).count_ones());
                    }
                    nxt = c;
                }
            }
        }
        _ => return Err(USAGE.into()),
    }
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        std::process::exit(1);
    }
}
