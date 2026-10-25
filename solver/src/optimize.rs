//! 見つかった棋譜を起点に、目的（返す枚数など）を最大化した別の棋譜と、同じ値の別解を SAT で探す。
//!
//! 全手順を解き直すと重いので「窓」だけ作り直す（大近傍探索）。窓の前後の局面と手番は固定し、
//! 窓の中の手順を「目的の値 ≥ 今の値 + 1」「既に見つけた手順は禁止」という条件つきで SAT に解かせる。
//! 解があれば改善、無ければその窓ではこれ以上良くならないので窓を広げるか別の区間に移る。

use crate::board::*;
use crate::retro::{next_side, with_passes};
use crate::sat::{solve_window, WindowResult};
use std::time::{Duration, Instant};

#[derive(Clone, Copy, Debug)]
pub enum Objective {
    /// 最後の m 手で返す枚数の合計
    Last(usize),
    /// 全体で返す枚数の合計
    Total,
    /// 動画映え（ASMR）スコア: クライマックス・アクセント・長い一列などの重み付き合計
    Asmr,
}

/// ASMR スコアの重み。--weights "climax=1.5,accent=2" のように一部だけ変えられる
#[derive(Clone, Copy, Debug)]
pub struct Weights {
    pub climax: f64,
    pub finale: f64,
    pub accent: f64,
    pub long: f64,
    pub dirs: f64,
    pub total: f64,
    pub boring: f64,
}

impl Default for Weights {
    fn default() -> Self {
        Weights { climax: 1.0, finale: 0.3, accent: 2.0, long: 1.0, dirs: 0.5, total: 0.1, boring: 0.5 }
    }
}

impl Weights {
    pub fn parse(s: &str) -> Result<Self, String> {
        let mut w = Weights::default();
        for kv in s.split(',').map(str::trim).filter(|x| !x.is_empty()) {
            let (k, v) = kv.split_once('=').ok_or(format!("重みの書式が不正: {kv}"))?;
            let v: f64 = v.parse().map_err(|_| format!("重みの値が不正: {kv}"))?;
            match k {
                "climax" => w.climax = v,
                "finale" => w.finale = v,
                "accent" => w.accent = v,
                "long" => w.long = v,
                "dirs" => w.dirs = v,
                "total" => w.total = v,
                "boring" => w.boring = v,
                _ => return Err(format!("不明な重み: {k}")),
            }
        }
        Ok(w)
    }
}

/// ASMR スコアの内訳
#[derive(Clone, Copy, Debug, Default)]
pub struct Breakdown {
    pub climax: u32,
    pub finale: u32,
    pub accents: f64,
    pub long: u32,
    pub dirs: u32,
    pub total: u32,
    pub boring: u32,
    pub score: f64,
}

/// 小 → 小 → 中 → 小 → 大 のような緩急を点数にする
pub fn asmr(g: &Game, w: &Weights) -> Breakdown {
    let n = g.flips.len();
    let f = &g.flips;
    let mut b = Breakdown { climax: *f.last().unwrap_or(&0), finale: f[n.saturating_sub(5)..].iter().sum(), total: f.iter().sum(), ..Default::default() };
    // アクセント: 直前 3 手の平均の 2 倍以上かつ 4 枚以上。前のアクセントから 3 手以内なら半分に数える（詰まりすぎ）
    let mut last_acc: Option<usize> = None;
    for i in 0..n {
        let prev = &f[i.saturating_sub(3)..i];
        let avg = if prev.is_empty() { 1.0 } else { prev.iter().sum::<u32>() as f64 / prev.len() as f64 };
        if f[i] >= 4 && f[i] as f64 >= 2.0 * avg.max(1.0) {
            b.accents += if last_acc.is_some_and(|j| i - j <= 3) { 0.5 } else { 1.0 };
            last_acc = Some(i);
        }
    }
    b.long = g.runs.iter().filter(|&&r| r >= 4).count() as u32;
    b.dirs = g.dirs.iter().filter(|&&d| d >= 3).count() as u32;
    // 1 枚返しが 3 手以上続く区間の手数
    let mut streak = 0;
    for &x in f {
        if x == 1 {
            streak += 1;
            if streak == 3 {
                b.boring += 3;
            } else if streak > 3 {
                b.boring += 1;
            }
        } else {
            streak = 0;
        }
    }
    b.score = w.climax * b.climax as f64 + w.finale * b.finale as f64 + w.accent * b.accents + w.long * b.long as f64
        + w.dirs * b.dirs as f64 + w.total * b.total as f64 - w.boring * b.boring as f64;
    b
}

impl Objective {
    pub fn parse(s: &str) -> Result<Self, String> {
        match s {
            "total" => Ok(Objective::Total),
            "asmr" => Ok(Objective::Asmr),
            _ => {
                let m = s.strip_prefix("last").map(|x| x.trim_start_matches(':')).unwrap_or("");
                let m: usize = if m.is_empty() { 1 } else { m.parse().map_err(|_| format!("不明な目的: {s}"))? };
                Ok(Objective::Last(m.max(1)))
            }
        }
    }
    pub fn name(&self) -> String {
        match self {
            Objective::Last(1) => "最後の 1 手で返す枚数".into(),
            Objective::Last(m) => format!("最後の {m} 手で返す枚数の合計"),
            Objective::Total => "全体で返す枚数の合計".into(),
            Objective::Asmr => "ASMR スコア".into(),
        }
    }
    /// 値を数える手（着手の番号 0..n）の範囲
    fn steps(&self, n: usize) -> std::ops::Range<usize> {
        match *self {
            Objective::Last(m) => n.saturating_sub(m)..n,
            Objective::Total | Objective::Asmr => 0..n,
        }
    }
}

/// 棋譜（着手のマスだけ。パスは自動で補う）を再生した結果
#[derive(Clone)]
pub struct Game {
    pub squares: Vec<u8>,
    /// positions[i] = i 手置いた後の局面（positions[0] は初期局面）
    pub positions: Vec<(u64, u64)>,
    /// movers[i] = i 手目（0 始まり）を打った側
    pub movers: Vec<u8>,
    /// flips[i] = i 手目で返した枚数
    pub flips: Vec<u32>,
    /// runs[i] = i 手目で 1 方向に続けて返した最大の枚数（長い一列）
    pub runs: Vec<u32>,
    /// dirs[i] = i 手目で返した方向の数
    pub dirs: Vec<u32>,
}

/// 方向ごとに返る枚数
fn dir_flips(p: u64, o: u64, sq: u32) -> [u32; 8] {
    let mut out = [0u32; 8];
    for (k, &d) in DIRS.iter().enumerate() {
        let mut line = 0u64;
        let mut x = shift(1u64 << sq, d);
        while x & o != 0 {
            line |= x;
            x = shift(x, d);
        }
        if x & p != 0 {
            out[k] = line.count_ones();
        }
    }
    out
}

pub fn analyze(squares: &[u8]) -> Result<Game, String> {
    let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
    let mut g = Game { squares: squares.to_vec(), positions: vec![(b, w)], movers: vec![], flips: vec![], runs: vec![], dirs: vec![] };
    for (i, &s) in squares.iter().enumerate() {
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        if legal_moves(p, o) == 0 {
            side = 1 - side; // パス
        }
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        if legal_moves(p, o) >> s & 1 == 0 {
            return Err(format!("{} 手目 {} が非合法", i + 1, sq_name(s)));
        }
        let f = flips(p, o, s as u32);
        let df = dir_flips(p, o, s as u32);
        g.runs.push(*df.iter().max().unwrap());
        g.dirs.push(df.iter().filter(|&&x| x > 0).count() as u32);
        (b, w) = play(b, w, side, s as u32);
        g.positions.push((b, w));
        g.movers.push(side);
        g.flips.push(f.count_ones());
        side = 1 - side;
    }
    Ok(g)
}

fn value(g: &Game, obj: Objective) -> usize {
    obj.steps(g.squares.len()).map(|i| g.flips[i] as usize).sum()
}

fn found(g: &Game, obj: Objective, w: &Weights) -> Found {
    let score = asmr(g, w);
    let value = match obj {
        Objective::Asmr => (score.score * 10.0).round().max(0.0) as usize,
        _ => value(g, obj),
    };
    Found { game: g.clone(), value, score }
}

pub struct Found {
    pub game: Game,
    pub value: usize,
    /// ASMR スコア（目的にかかわらず計算する）
    pub score: Breakdown,
}

pub struct Report {
    pub best: Found,
    pub initial_value: usize,
    /// 同じ値の別解（best を含む）
    pub solutions: Vec<Found>,
    /// 最後の窓が棋譜全体を覆い、UNSAT でそれ以上が無いと示せた
    pub proven_optimal: bool,
}

/// 窓 [a, b)（着手番号）を作り直す。obj の手のうち窓に入る部分の合計 ≥ k、blocks の手順は禁止。
fn rebuild(g: &Game, a: usize, b: usize, obj: Objective, k: usize, blocks: &[Vec<u8>], limit: Duration, solver: &str) -> WindowResult {
    let n = g.squares.len();
    let start = g.positions[a];
    let start_side = g.movers[a];
    let target = g.positions[b];
    // 窓の後ろに元の手順を続けるには、窓の最後の手の後で元と同じ側が打つ必要がある
    let last_movers = (b < n).then(|| {
        let want = g.movers[b];
        [next_side(target.0, target.1, 0) == want, next_side(target.0, target.1, 1) == want]
    });
    let steps: Vec<usize> = obj.steps(n).filter(|&i| a <= i && i < b).map(|i| i - a).collect();
    solve_window(start, start_side, target, last_movers, &[(steps, k)], blocks, limit, solver)
}

/// 窓 [a, b) を、任意の条件（絶対の手番号の列, 下限）で作り直す
fn rebuild_with(g: &Game, a: usize, b: usize, cons: &[(Vec<usize>, usize)], blocks: &[Vec<u8>], limit: Duration, solver: &str) -> WindowResult {
    let n = g.squares.len();
    let target = g.positions[b];
    let last_movers = (b < n).then(|| {
        let want = g.movers[b];
        [next_side(target.0, target.1, 0) == want, next_side(target.0, target.1, 1) == want]
    });
    let rel: Vec<(Vec<usize>, usize)> =
        cons.iter().map(|(st, k)| (st.iter().filter(|&&i| a <= i && i < b).map(|&i| i - a).collect(), *k)).collect();
    solve_window(g.positions[a], g.movers[a], target, last_movers, &rel, blocks, limit, solver)
}

fn splice(g: &Game, a: usize, b: usize, window: &[u8]) -> Result<Game, String> {
    let mut sq = g.squares[..a].to_vec();
    sq.extend_from_slice(window);
    sq.extend_from_slice(&g.squares[b..]);
    analyze(&sq)
}

/// 進み具合の通知（改善のたびに呼ばれる）
pub type Progress<'a> = &'a mut dyn FnMut(&str, &Found);

pub fn optimize(
    initial: &[u8], obj: Objective, weights: &Weights, window: usize, n_solutions: usize, time: Duration, solver: &str,
    progress: Progress,
) -> Result<Report, String> {
    let start = Instant::now();
    let deadline = start + time;
    // 別解も頼まれていれば、制限時間の 1/4 は別解探しに残す（ASMR は探索中に集めた候補から選ぶので不要）
    let opt_deadline = if n_solutions > 1 && !matches!(obj, Objective::Asmr) { start + time.mul_f64(0.75) } else { deadline };
    let left = || opt_deadline.saturating_duration_since(Instant::now());
    let mut g = analyze(initial)?;
    let n = g.squares.len();
    let initial_value = found(&g, obj, weights).value;
    let mut proven = false;
    let w = weights;

    // 最後の m 手の枚数を、最後の窓を作り直しながら上げる（全体まで広げて UNSAT なら最適）
    let mut climb_last = |g: &mut Game, m: usize, until: Instant, proven: &mut bool, report: bool| -> Result<(), String> {
        let lobj = Objective::Last(m);
        let mut ws = window.max(m).min(n);
        loop {
            let rem = until.saturating_duration_since(Instant::now());
            if rem.is_zero() {
                return Ok(());
            }
            match rebuild(g, n - ws, n, lobj, value(g, lobj) + 1, &[], rem, solver) {
                WindowResult::Found(win) => {
                    *g = splice(g, n - ws, n, &win)?;
                    if report {
                        progress("improved", &found(g, obj, w));
                    }
                }
                WindowResult::Unsat if ws >= n => {
                    *proven = true;
                    return Ok(());
                }
                WindowResult::Unsat => ws = (ws + window.max(6) / 2).min(n),
                WindowResult::Timeout => return Ok(()),
            }
        }
    };

    // ASMR で途中に出会った棋譜（スコアで順位付けして別解として返す）
    let mut pool: Vec<Game> = vec![];
    let mut seen = std::collections::HashSet::new();
    let mut keep = |g: &Game, pool: &mut Vec<Game>| {
        if seen.insert(g.squares.clone()) {
            pool.push(g.clone());
        }
    };

    match obj {
        Objective::Last(m) => climb_last(&mut g, m, opt_deadline, &mut proven, true)?,
        Objective::Total => {
            // 窓をずらしながら、窓の中の返す枚数を増やす。1 周して改善が無ければ窓を広げる
            let mut ws = window.min(n);
            'outer: loop {
                let step = (ws / 2).max(1);
                let mut improved = false;
                let mut a = 0;
                while a < n {
                    let b = (a + ws).min(n);
                    loop {
                        if left().is_zero() {
                            break 'outer;
                        }
                        let k: usize = g.flips[a..b].iter().map(|&x| x as usize).sum::<usize>() + 1;
                        match rebuild(&g, a, b, Objective::Total, k, &[], left(), solver) {
                            WindowResult::Found(win) => {
                                g = splice(&g, a, b, &win)?;
                                improved = true;
                                progress("improved", &found(&g, obj, w));
                            }
                            WindowResult::Unsat => break,
                            WindowResult::Timeout => break 'outer,
                        }
                    }
                    if b == n {
                        break;
                    }
                    a += step;
                }
                if !improved {
                    if ws >= n {
                        proven = true;
                        break;
                    }
                    ws = (ws + window.max(6) / 2).min(n);
                }
            }
        }
        Objective::Asmr => {
            keep(&g, &mut pool);
            // 1) クライマックス: 最後の 1 手で返す枚数を上げる（最適化に使える時間の 4 割まで）
            let mut dummy = false;
            climb_last(&mut g, 1, start + (opt_deadline - start).mul_f64(0.4), &mut dummy, false)?;
            keep(&g, &mut pool);
            let mut best = asmr(&g, w).score;
            progress("improved", &found(&g, obj, w));
            // 2) 山登り: 窓（後ろから前へ）ごとに別の手順を SAT で出し、スコアが上がれば採用。
            //    窓の中の返し枚数は今の 85% 以上、最後の 1 手の枚数は下げない
            let ws = window.min(n);
            let step = (ws / 2).max(1);
            let mut starts: Vec<usize> = (0..=n - ws).step_by(step).collect();
            if *starts.last().unwrap() != n - ws {
                starts.push(n - ws);
            }
            starts.reverse();
            'climb: loop {
                let mut improved = false;
                for &a in &starts {
                    let b = a + ws;
                    let mut blocks = vec![g.squares[a..b].to_vec()];
                    for _ in 0..3 {
                        if left().is_zero() {
                            break 'climb;
                        }
                        let sum: usize = g.flips[a..b].iter().map(|&x| x as usize).sum();
                        let mut cons = vec![((a..b).collect::<Vec<_>>(), sum * 85 / 100)];
                        if b == n {
                            cons.push((vec![n - 1], g.flips[n - 1] as usize));
                        }
                        match rebuild_with(&g, a, b, &cons, &blocks, left(), solver) {
                            WindowResult::Found(win) => {
                                blocks.push(win.clone());
                                let alt = splice(&g, a, b, &win)?;
                                keep(&alt, &mut pool);
                                let s = asmr(&alt, w).score;
                                if s > best {
                                    best = s;
                                    g = alt;
                                    improved = true;
                                    progress("improved", &found(&g, obj, w));
                                    break;
                                }
                            }
                            WindowResult::Unsat => break,
                            WindowResult::Timeout => break 'climb,
                        }
                    }
                }
                if !improved {
                    break; // 1 周して改善なし（局所最適）
                }
            }
            // スコア順の上位を解として返す
            pool.sort_by(|x, y| asmr(y, w).score.total_cmp(&asmr(x, w).score));
            let solutions: Vec<Found> = pool.iter().take(n_solutions.max(1)).map(|x| found(x, obj, w)).collect();
            let best = found(&pool[0], obj, w);
            return Ok(Report { best, initial_value, solutions, proven_optimal: false });
        }
    }

    let left = || deadline.saturating_duration_since(Instant::now());
    // 同じ値の別解: 最後の窓の中だけ手順を変えたものを、既に見つけた手順を禁止しながら集める。
    // 窓の中で尽きたら窓を広げる（禁止する手順は、見つけた解それぞれの窓の部分）
    let best_value = value(&g, obj);
    let mut solutions = vec![found(&g, obj, w)];
    let mut ws = window.max(match obj { Objective::Last(m) => m, _ => 1 }).min(n);
    while solutions.len() < n_solutions && !left().is_zero() {
        let a = n - ws;
        let blocks: Vec<Vec<u8>> = solutions.iter().filter(|f| f.game.squares[..a] == g.squares[..a]).map(|f| f.game.squares[a..].to_vec()).collect();
        // 窓の外は g と同じなので、窓の中の値が g と同じ以上なら全体の値も best 以上
        let k = match obj {
            Objective::Last(_) => best_value,
            _ => g.flips[a..].iter().map(|&x| x as usize).sum(),
        };
        match rebuild(&g, a, n, obj, k, &blocks, left(), solver) {
            WindowResult::Found(win) => {
                let alt = splice(&g, a, n, &win)?;
                let f = found(&alt, obj, w);
                progress("alternative", &f);
                solutions.push(f);
            }
            WindowResult::Unsat if ws < n => ws = (ws + window.max(6) / 2).min(n),
            _ => break,
        }
    }
    Ok(Report { best: found(&g, obj, w), initial_value, solutions, proven_optimal: proven })
}

/// 棋譜をパスつきの着手列（PASS を含む）にする
pub fn record(g: &Game) -> Vec<u8> {
    with_passes(&g.squares)
}
