//! SAT エンコーディング。N 手（パスは手番変数で表す）の対局を CNF にし、外部ソルバー（kissat 等）で解く。
//!
//! 変数（t = 局面番号 0..=N、手 t は局面 t → t+1）:
//! - B[t][s], W[t][s]: 局面 t でマス s が黒 / 白
//! - RB_X[t][d][s]: 局面 t で s から方向 d に「X の相手の石が続き、その先に X の石」（X が s-d に置けば挟める）
//! - side[t]: 手 t を打つのが黒か
//! - M[t][s]: 手 t で s に置く
//! - R[t][d][s] = side[t] ? RB_B : RB_W、FD[t][d][s]: 手 t で s が方向 d に返る、Flip[t][s]: s が返る
//!
//! パス: side[t] == side[t+1] なら、局面 t+1 で相手に合法手が無い。

use crate::board::*;
use crate::solver::{placement_closure, preprocess, Outcome, Stats};
use std::io::{Read, Write};
use std::sync::mpsc;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// 逆方向が d ^ 1 になるよう対で並べる
const D8: [(i32, i32); 8] = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)];

fn nb(s: usize, d: usize) -> Option<usize> {
    let (r, c) = ((s / 8) as i32 + D8[d].0, (s % 8) as i32 + D8[d].1);
    ((0..8).contains(&r) && (0..8).contains(&c)).then_some((r * 8 + c) as usize)
}

/// d の逆方向の添字
fn rev(d: usize) -> usize {
    d ^ 1
}

pub struct Cnf {
    pub nvars: i32,
    pub lits: Vec<i32>,
    pub nclauses: usize,
    pub tru: i32,
}

impl Cnf {
    fn new() -> Self {
        let mut c = Cnf { nvars: 0, lits: Vec::new(), nclauses: 0, tru: 0 };
        c.tru = c.var();
        c.add(&[c.tru]);
        c
    }
    pub fn var(&mut self) -> i32 {
        self.nvars += 1;
        self.nvars
    }
    pub fn add(&mut self, c: &[i32]) {
        // 定数リテラルを簡約
        if c.contains(&self.tru) {
            return;
        }
        for &l in c {
            if l != -self.tru {
                self.lits.push(l);
            }
        }
        self.lits.push(0);
        self.nclauses += 1;
    }
    /// lits のうち k 個以上が真（逐次カウンタ: r[i][j] =「先頭 i+1 個のうち j+1 個以上が真」）
    pub fn at_least(&mut self, lits: &[i32], k: usize) {
        if k == 0 {
            return;
        }
        if lits.len() < k {
            self.add(&[-self.tru]);
            return;
        }
        let n = lits.len();
        let mut prev: Vec<i32> = vec![];
        for (i, &x) in lits.iter().enumerate() {
            let width = k.min(i + 1);
            let cur: Vec<i32> = (0..width).map(|_| self.var()).collect();
            for j in 0..width {
                // r[i][j] → r[i-1][j] ∨ (x ∧ r[i-1][j-1])（j = 0 の r[i-1][-1] は真）
                let up = if j < prev.len() { Some(prev[j]) } else { None };
                let diag = if j == 0 { None } else { Some(prev[j - 1]) };
                let mut cl = vec![-cur[j]];
                if let Some(u) = up {
                    cl.push(u);
                }
                cl.push(x);
                self.add(&cl);
                if let Some(dg) = diag {
                    let mut cl2 = vec![-cur[j]];
                    if let Some(u) = up {
                        cl2.push(u);
                    }
                    cl2.push(dg);
                    self.add(&cl2);
                }
            }
            prev = cur;
            let _ = n;
        }
        self.add(&[prev[k - 1]]);
    }

    /// 高々 1 つ（逐次カウンタ）
    fn at_most_one(&mut self, xs: &[i32]) {
        if xs.len() <= 1 {
            return;
        }
        let mut prev = xs[0];
        for (i, &x) in xs.iter().enumerate().skip(1) {
            self.add(&[-prev, -x]);
            if i + 1 < xs.len() {
                let s = self.var();
                self.add(&[-prev, s]);
                self.add(&[-x, s]);
                prev = s;
            }
        }
    }
}

pub struct Enc {
    pub n: usize,
    pub m: Vec<[i32; 64]>,
    /// flips[t][s]: 手 t で s が返る（変数が無いマスは偽の定数）
    flips: Vec<[i32; 64]>,
    /// selectors のとき、sel[s] が真なら最終盤面の s は目標の色（石の無いマスは 0）
    pub sel: [i32; 64],
}

/// 目標で埋まるマスに対し、いずれの軸でも両隣が目標で埋まらない（= 一度置いたら返らない）マス。
fn never_flipped(occ: u64) -> u64 {
    let mut f = 0u64;
    for s in 0..64 {
        if occ >> s & 1 == 0 {
            continue;
        }
        let flippable = (0..8).step_by(2).any(|d| {
            matches!((nb(s, d), nb(s, rev(d))), (Some(a), Some(b)) if occ >> a & 1 != 0 && occ >> b & 1 != 0)
        });
        if !flippable {
            f |= 1 << s;
        }
    }
    f
}

/// 置き順の閉包の段数（開始局面から数えて、そのマスに置けるのは早くとも何手目か）。
fn earliest(start_occ: u64, occ: u64) -> [usize; 64] {
    let mut e = [0usize; 64];
    let mut placed = start_occ;
    let mut round = 0;
    while placed != occ {
        round += 1;
        let mut add = 0;
        for &d in &DIRS {
            let n1 = shift(placed, -d);
            add |= n1 & shift(n1, -d);
        }
        add &= occ & !placed;
        if add == 0 {
            break;
        }
        for s in 0..64 {
            if add >> s & 1 != 0 {
                e[s] = round - 1;
            }
        }
        placed |= add;
    }
    e
}

/// エンコードの変種（実験用）。
#[derive(Clone, Copy, Default, Debug)]
pub struct EncOpts {
    /// パスが無いと仮定する（手番が定数になる）。充足不能でも到達不能とは限らない
    pub nopass: bool,
    /// 占有の層（O[t][s]）と置き順の前提を冗長制約として加える
    pub occ: bool,
    /// マスごとの「高々 1 回置く」を省く
    pub noamo: bool,
    /// 0 以外なら、パスを最後の pass_window 手の中でだけ許す（それ以前の手番は交互の定数）
    pub pass_window: usize,
    /// 最終盤面で色を問わない（石があることだけを求める）マス。到達不能の原因の絞り込み用
    pub free_colors: u64,
    /// 最終盤面の各マスの色を「仮定」で切り替えられるようにする（sel[s] が真のとき目標の色）。修正補助用
    pub selectors: bool,
}

impl EncOpts {
    pub fn parse(s: &str) -> Self {
        let mut o = EncOpts::default();
        for t in s.split(',').map(str::trim) {
            match t {
                "nopass" => o.nopass = true,
                "occ" => o.occ = true,
                "noamo" => o.noamo = true,
                t if t.starts_with("late") => o.pass_window = t[4..].parse().unwrap_or(12),
                t if t.starts_with("free=") => o.free_colors = u64::from_str_radix(&t[5..], 16).unwrap_or(0),
                _ => {}
            }
        }
        o
    }
}

fn encode(black: u64, white: u64, opts: EncOpts) -> (Cnf, Enc) {
    encode_window((INIT_BLACK, INIT_WHITE), 0, (black, white), None, opts)
}

/// 局面 start（次に start_side が打つ）から局面 (black, white) までの手順を CNF にする。
/// last_movers が Some([黒可, 白可]) なら、最後の手を打つ側をそれに限る（窓の後ろに元の手順を続けるため）。
pub fn encode_window(start: (u64, u64), start_side: u8, (black, white): (u64, u64), last_movers: Option<[bool; 2]>, opts: EncOpts) -> (Cnf, Enc) {
    let occ = black | white;
    let start_occ = start.0 | start.1;
    let n = (occ.count_ones() - start_occ.count_ones()) as usize;
    // 返らないマス。目標の色で固定するのは、色を仮定で切り替えない・外さないときだけ
    let never = never_flipped(occ) & !start_occ;
    let fixed = if opts.selectors { 0 } else { never & !opts.free_colors };
    let early = earliest(start_occ, occ);
    let mut c = Cnf::new();
    let f = -c.tru;
    // 手 t の手番が定数なら Some(黒か)。パスが無ければ開始の手番から交互
    let const_side = |t: usize| {
        (opts.nopass || (opts.pass_window > 0 && t + opts.pass_window < n)).then_some((t % 2 == 0) == (start_side == 0))
    };

    // 盤面
    let mut b = vec![[0i32; 64]; n + 1];
    let mut w = vec![[0i32; 64]; n + 1];
    for t in 0..=n {
        for s in 0..64 {
            if occ >> s & 1 == 0 {
                b[t][s] = f;
                w[t][s] = f;
            } else {
                b[t][s] = c.var();
                w[t][s] = c.var();
                c.add(&[-b[t][s], -w[t][s]]);
                if start_occ >> s & 1 != 0 {
                    c.add(&[b[t][s], w[t][s]]);
                }
                // 返らない石は置いた時点から目標の色
                if fixed >> s & 1 != 0 {
                    c.add(&[if black >> s & 1 != 0 { -w[t][s] } else { -b[t][s] }]);
                }
            }
        }
    }
    let mut sel = [0i32; 64];
    if opts.selectors {
        // 返らないマスは、置かれてから最後まで同じ色（目標の色に依らない形で書く）
        for s in 0..64 {
            if never >> s & 1 != 0 {
                for t in 0..n {
                    c.add(&[-b[t][s], b[n][s]]);
                    c.add(&[-w[t][s], w[n][s]]);
                }
            }
        }
    }
    for s in 0..64 {
        let (ib, iw) = (start.0 >> s & 1 != 0, start.1 >> s & 1 != 0);
        c.add(&[if ib { b[0][s] } else { -b[0][s] }]);
        c.add(&[if iw { w[0][s] } else { -w[0][s] }]);
        if opts.free_colors >> s & 1 != 0 || (opts.selectors && occ >> s & 1 != 0) {
            if occ >> s & 1 != 0 {
                c.add(&[b[n][s], w[n][s]]); // 色は問わないが石はある
            }
            if opts.selectors && opts.free_colors >> s & 1 == 0 {
                let a = c.var();
                c.add(&[-a, if black >> s & 1 != 0 { b[n][s] } else { w[n][s] }]);
                sel[s] = a;
            }
            continue;
        }
        c.add(&[if black >> s & 1 != 0 { b[n][s] } else { -b[n][s] }]);
        c.add(&[if white >> s & 1 != 0 { w[n][s] } else { -w[n][s] }]);
    }

    // 挟み線 RB_X[t][d][s]（X = 0 黒, 1 白）
    let mut rb = vec![[[[f; 64]; 8]; 2]; n + 1];
    for t in 0..=n {
        for x in 0..2 {
            for d in 0..8 {
                for s in 0..64 {
                    if occ >> s & 1 != 0 && nb(s, d).is_some_and(|q| occ >> q & 1 != 0) {
                        rb[t][x][d][s] = c.var();
                    }
                }
            }
        }
        for x in 0..2 {
            let (own, opp) = if x == 0 { (&b[t], &w[t]) } else { (&w[t], &b[t]) };
            for d in 0..8 {
                for s in 0..64 {
                    let r = rb[t][x][d][s];
                    if r == f {
                        continue;
                    }
                    let q = nb(s, d).unwrap();
                    let rq = rb[t][x][d][q];
                    c.add(&[-r, opp[s]]);
                    c.add(&[-r, own[q], rq]);
                    c.add(&[-opp[s], -own[q], r]);
                    c.add(&[-opp[s], -rq, r]);
                }
            }
        }
    }

    // 手
    let mut side = vec![0i32; n];
    let mut m = vec![[f; 64]; n];
    for t in 0..n {
        side[t] = match const_side(t) {
            Some(true) => c.tru,
            Some(false) => -c.tru,
            None => c.var(),
        };
        for s in 0..64 {
            if occ >> s & 1 != 0 && start_occ >> s & 1 == 0 && t >= early[s] {
                m[t][s] = c.var();
            }
        }
        let ms: Vec<i32> = m[t].iter().copied().filter(|&l| l != f).collect();
        c.add(&ms);
        c.at_most_one(&ms);
    }
    if n > 0 {
        c.add(&[if start_side == 0 { side[0] } else { -side[0] }]);
        if let Some([bl, wh]) = last_movers {
            if !bl {
                c.add(&[-side[n - 1]]);
            }
            if !wh {
                c.add(&[side[n - 1]]);
            }
        }
    }
    for s in 0..64 {
        let ms: Vec<i32> = (0..n).map(|t| m[t][s]).filter(|&l| l != f).collect();
        if !ms.is_empty() {
            c.add(&ms);
            if !opts.noamo {
                c.at_most_one(&ms);
            }
        }
    }

    if opts.occ {
        // O[t][s] = B ∨ W。単調に増え、増えたマスがその手の着手。置くには隣とその先が埋まっている
        let mut o = vec![[f; 64]; n + 1];
        for t in 0..=n {
            for s in 0..64 {
                if occ >> s & 1 == 0 {
                    continue;
                }
                if start_occ >> s & 1 != 0 {
                    o[t][s] = c.tru;
                    continue;
                }
                let v = c.var();
                c.add(&[-v, b[t][s], w[t][s]]);
                c.add(&[v, -b[t][s]]);
                c.add(&[v, -w[t][s]]);
                o[t][s] = v;
            }
        }
        for t in 0..n {
            for s in 0..64 {
                if occ >> s & 1 == 0 || start_occ >> s & 1 != 0 {
                    continue;
                }
                let (o0, o1, mv) = (o[t][s], o[t + 1][s], m[t][s]);
                c.add(&[-o0, o1]);
                c.add(&[-mv, o1]);
                c.add(&[-mv, -o0]);
                c.add(&[mv, o0, -o1]);
                if mv == f {
                    continue;
                }
                let mut pre = vec![-mv];
                for d in 0..8 {
                    if let Some(q1) = nb(s, d) {
                        if let Some(q2) = nb(q1, d) {
                            if occ >> q1 & 1 != 0 && occ >> q2 & 1 != 0 {
                                let a = c.var();
                                c.add(&[-a, o[t][q1]]);
                                c.add(&[-a, o[t][q2]]);
                                pre.push(a);
                            }
                        }
                    }
                }
                c.add(&pre);
            }
        }
    }

    let mut flips = Vec::with_capacity(n);
    for t in 0..n {
        let sd = side[t];
        // 合法性
        for s in 0..64 {
            let mv = m[t][s];
            if mv == f {
                continue;
            }
            c.add(&[-mv, -b[t][s]]);
            c.add(&[-mv, -w[t][s]]);
            let mut cb = vec![-mv, -sd];
            let mut cw = vec![-mv, sd];
            for d in 0..8 {
                if let Some(q) = nb(s, d) {
                    cb.push(rb[t][0][d][q]);
                    cw.push(rb[t][1][d][q]);
                }
            }
            c.add(&cb);
            c.add(&cw);
            if fixed >> s & 1 != 0 {
                c.add(&[-mv, if black >> s & 1 != 0 { sd } else { -sd }]);
            }
        }
        // 返り
        let mut fd = [[f; 64]; 8];
        let mut rr = [[f; 64]; 8];
        for d in 0..8 {
            for s in 0..64 {
                let (rbb, rbw) = (rb[t][0][d][s], rb[t][1][d][s]);
                if rbb == f && rbw == f {
                    continue;
                }
                let cs = const_side(t);
                if cs.is_some_and(|bl| (if bl { rbb } else { rbw }) == f) {
                    continue;
                }
                let r = if let Some(bl) = cs {
                    if bl { rbb } else { rbw }
                } else {
                    let r = c.var();
                    c.add(&[-sd, -rbb, r]);
                    c.add(&[-sd, rbb, -r]);
                    c.add(&[sd, -rbw, r]);
                    c.add(&[sd, rbw, -r]);
                    r
                };
                rr[d][s] = r;
                if nb(s, rev(d)).is_some() {
                    fd[d][s] = c.var();
                }
            }
        }
        let mut flip = [f; 64];
        for s in 0..64 {
            let mut any = vec![];
            for d in 0..8 {
                let x = fd[d][s];
                if x == f {
                    continue;
                }
                let p = nb(s, rev(d)).unwrap();
                let (mp, fp) = (m[t][p], fd[d][p]);
                c.add(&[-x, rr[d][s]]);
                c.add(&[-x, mp, fp]);
                c.add(&[-rr[d][s], -mp, x]);
                c.add(&[-rr[d][s], -fp, x]);
                any.push(x);
            }
            if any.is_empty() {
                continue;
            }
            let fl = c.var();
            let mut cl = vec![-fl];
            cl.extend(&any);
            c.add(&cl);
            for &x in &any {
                c.add(&[fl, -x]);
            }
            flip[s] = fl;
        }
        flips.push(flip);
        // 遷移
        for s in 0..64 {
            if occ >> s & 1 == 0 {
                continue;
            }
            let (b0, w0, b1, w1, mv, fl) = (b[t][s], w[t][s], b[t + 1][s], w[t + 1][s], m[t][s], flip[s]);
            // 黒番: B' = B ∨ Flip ∨ M, W' = W ∧ ¬Flip
            c.add(&[-sd, -b0, b1]);
            c.add(&[-sd, -fl, b1]);
            c.add(&[-sd, -mv, b1]);
            c.add(&[-sd, b0, fl, mv, -b1]);
            c.add(&[-sd, -w0, fl, w1]);
            c.add(&[-sd, w0, -w1]);
            c.add(&[-sd, -fl, -w1]);
            // 白番: 対称
            c.add(&[sd, -w0, w1]);
            c.add(&[sd, -fl, w1]);
            c.add(&[sd, -mv, w1]);
            c.add(&[sd, w0, fl, mv, -w1]);
            c.add(&[sd, -b0, fl, b1]);
            c.add(&[sd, b0, -b1]);
            c.add(&[sd, -fl, -b1]);
        }
    }

    // パス: 同じ側が続けて打つなら（nopass では手番が交互の定数なので全節が自明に充足され消える）、その間の局面で相手に合法手が無い
    for t in 0..n.saturating_sub(1) {
        let (s0, s1) = (side[t], side[t + 1]);
        let u = t + 1;
        // 目標で空のマスも相手の合法手になり得るので除外しない
        for s in 0..64 {
            for d in 0..8 {
                if let Some(q) = nb(s, d) {
                    // 黒が連続 → 白に合法手なし
                    c.add(&[-s0, -s1, b[u][s], w[u][s], -rb[u][1][d][q]]);
                    c.add(&[s0, s1, b[u][s], w[u][s], -rb[u][0][d][q]]);
                }
            }
        }
    }
    (c, Enc { n, m, flips, sel })
}

/// パスなし仮定で複数の目標局面を並列に SAT で解き、最初に解けたものの (添字, 着手マス列) を返す。
/// 結果: Ok((添字, 着手)) / Err(true) = すべての局面がパスなしでは作れない / Err(false) = 時間切れ
pub fn find_any_passfree(targets: &[(u64, u64)], limit: Duration, solver: &str) -> Result<(usize, Vec<u8>), bool> {
    let encs: Vec<(Cnf, Enc)> = targets
        .iter()
        .map(|&(b, w)| encode(b, w, EncOpts { nopass: true, occ: true, ..Default::default() }))
        .collect();
    let insts: Vec<(&Cnf, bool)> = encs.iter().map(|(c, _)| (c, false)).collect();
    let (i, model) = run_portfolio(&insts, solver, limit, 1).map_err(|e| e == "allunsat")?;
    let model = model.ok_or(false)?;
    let enc = &encs[i].1;
    let val = |l: i32| if l > 0 { model[l as usize] } else { !model[(-l) as usize] };
    let squares = (0..enc.n).map(|t| (0..64).find(|&s| val(enc.m[t][s])).unwrap() as u8).collect();
    Ok((i, squares))
}

/// 局面 Q に「次に c が打つ」状態で到達できるか（パスは直前 12 手の中だけ許す近似）。sat / unsat / unknown
pub fn reach(qb: u64, qw: u64, c: u8, limit: Duration, solver: &str) -> &'static str {
    if (qb, qw) == (INIT_BLACK, INIT_WHITE) {
        return if c == 0 { "sat" } else { "unsat" };
    }
    // 最後の手を打った側 L は、L が打った後に c の番になる側
    let last = [crate::retro::next_side(qb, qw, 0) == c, crate::retro::next_side(qb, qw, 1) == c];
    if !last[0] && !last[1] {
        return "unsat";
    }
    let (cnf, _) = encode_window((INIT_BLACK, INIT_WHITE), 0, (qb, qw), Some(last), EncOpts { occ: true, pass_window: 12, ..Default::default() });
    match run_portfolio(&[(&cnf, false)], solver, limit, 1) {
        Ok((_, Some(_))) => "sat",
        Err(e) if e == "allunsat" => "unsat",
        _ => "unknown",
    }
}

/// 色の条件を外したマス（free）を持つ盤面に到達できるか。棋譜を探す 2 本（パスなし・終盤パス許可）と
/// 証明用の一般版の 3 本を並列に解く。Some(true) = 到達可能 / Some(false) = 到達不能（証明） / None = 時間切れ
pub fn check_free(black: u64, white: u64, free: u64, limit: Duration, solver: &str) -> Option<bool> {
    match check_free_moves(black, white, free, limit, solver, None) {
        Some(Some(_)) => Some(true),
        Some(None) => Some(false),
        None => None,
    }
}

/// check_free の着手つき版。Some(Some(着手)) = 到達可能 / Some(None) = 到達不能（証明） / None = 時間切れ・中止
pub fn check_free_moves(
    black: u64, white: u64, free: u64, limit: Duration, solver: &str, cancel: Option<&std::sync::atomic::AtomicBool>,
) -> Option<Option<Vec<u8>>> {
    let fast = encode(black, white, EncOpts { nopass: true, occ: true, free_colors: free, ..Default::default() });
    let late = encode(black, white, EncOpts { occ: true, pass_window: 12, free_colors: free, ..Default::default() });
    let full = encode(black, white, EncOpts { free_colors: free, ..Default::default() });
    let encs = [&fast.1, &late.1, &full.1];
    match run_portfolio_cancel(&[(&fast.0, false), (&late.0, false), (&full.0, true)], solver, limit, 1, cancel) {
        Ok((i, Some(model))) => {
            let enc = encs[i];
            let val = |l: i32| if l > 0 { model[l as usize] } else { !model[(-l) as usize] };
            Some(Some((0..enc.n).map(|t| (0..64).find(|&s| val(enc.m[t][s])).unwrap() as u8).collect()))
        }
        Ok((_, None)) => Some(None),
        Err(_) => None,
    }
}

/// 修正補助（kissat 版）: 目標の盤面から色を変えるマスを k 個以下にして到達可能にする直し方を 1 つ探す。
/// protect のマスは変えない。blocks の変え方（変えたマスの集合）は使わない。
/// パスなし・終盤パス許可・一般版の 3 本を並列に解く（一般版の UNSAT は「k 個以下では直せない」の証明）。
/// 戻り値: Ok(Some((変えたマス, 着手))) / Ok(None) = k 個以下では直せない / Err = 時間切れ
pub fn find_fix(black: u64, white: u64, k: usize, protect: u64, blocks: &[Vec<u8>], limit: Duration, solver: &str) -> Result<Option<(Vec<u8>, Vec<u8>)>, String> {
    find_fix_cancel(black, white, k, protect, blocks, limit, solver, None)
}

pub fn find_fix_cancel(
    black: u64, white: u64, k: usize, protect: u64, blocks: &[Vec<u8>], limit: Duration, solver: &str,
    cancel: Option<&std::sync::atomic::AtomicBool>,
) -> Result<Option<(Vec<u8>, Vec<u8>)>, String> {
    let build = |opts: EncOpts| {
        let (mut cnf, enc) = encode_window((INIT_BLACK, INIT_WHITE), 0, (black, white), None, EncOpts { selectors: true, ..opts });
        let sel: Vec<i32> = enc.sel.iter().copied().filter(|&a| a != 0).collect();
        // sel が真 = 目標の色のまま。変えるのは k 個以下 ⇔ 目標の色のままのマスが (全体 - k) 個以上
        cnf.at_least(&sel, sel.len().saturating_sub(k));
        for s in 0..64 {
            if protect >> s & 1 != 0 && enc.sel[s] != 0 {
                cnf.add(&[enc.sel[s]]);
            }
        }
        for blk in blocks {
            let cl: Vec<i32> = blk.iter().map(|&s| enc.sel[s as usize]).filter(|&a| a != 0).collect();
            if !cl.is_empty() {
                cnf.add(&cl); // この変え方そのものは使わない（どれかは元の色のまま）
            }
        }
        (cnf, enc)
    };
    let fast = build(EncOpts { nopass: true, occ: true, ..Default::default() });
    let late = build(EncOpts { occ: true, pass_window: 12, ..Default::default() });
    let full = build(EncOpts::default());
    let insts = [(&fast.0, false), (&late.0, false), (&full.0, true)];
    let encs = [&fast.1, &late.1, &full.1];
    match run_portfolio_cancel(&insts, solver, limit, 1, cancel) {
        Ok((i, Some(model))) => {
            let enc = encs[i];
            let val = |l: i32| if l > 0 { model[l as usize] } else { !model[(-l) as usize] };
            let changed = (0..64u8).filter(|&s| enc.sel[s as usize] != 0 && !val(enc.sel[s as usize])).collect();
            let squares = (0..enc.n).map(|t| (0..64).find(|&s| val(enc.m[t][s])).unwrap() as u8).collect();
            Ok(Some((changed, squares)))
        }
        Ok((_, None)) => Ok(None),
        Err(e) => Err(e),
    }
}

pub enum WindowResult {
    /// 窓の中の着手（マス）
    Found(Vec<u8>),
    Unsat,
    Timeout,
}

/// 局面 start（次は start_side）から target までの手順を、条件つきで 1 つ探す（棋譜の最適化用）。
/// - constraints の各 (手の番号の列, k) について、それらの手（窓の中の番号）で返す枚数の合計 ≥ k
/// - blocks にある手順（窓の中の着手列）は禁止
/// - last_movers で最後の手を打つ側を限る（窓の後ろに元の手順を続けるため）
pub fn solve_window(
    start: (u64, u64), start_side: u8, target: (u64, u64), last_movers: Option<[bool; 2]>, constraints: &[(Vec<usize>, usize)],
    blocks: &[Vec<u8>], limit: Duration, solver: &str,
) -> WindowResult {
    let (mut cnf, enc) = encode_window(start, start_side, target, last_movers, EncOpts::default());
    let f = -cnf.tru;
    for (steps, k) in constraints {
        if *k > 0 {
            let lits: Vec<i32> = steps.iter().flat_map(|&t| enc.flips[t].iter().copied()).filter(|&l| l != f).collect();
            cnf.at_least(&lits, *k);
        }
    }
    for seq in blocks {
        if seq.len() != enc.n {
            continue;
        }
        // この手順が使う着手変数のどれかが偽（その手順はもう使えない）。存在しない着手を含む手順は元から不可能
        let cl: Option<Vec<i32>> = seq.iter().enumerate().map(|(t, &s)| {
            let l = enc.m[t][s as usize];
            (l != f).then_some(-l)
        }).collect();
        if let Some(cl) = cl {
            cnf.add(&cl);
        }
    }
    match run_portfolio(&[(&cnf, true)], solver, limit, 1) {
        Ok((_, Some(model))) => {
            let val = |l: i32| if l > 0 { model[l as usize] } else { !model[(-l) as usize] };
            WindowResult::Found((0..enc.n).map(|t| (0..64).find(|&s| val(enc.m[t][s])).unwrap() as u8).collect())
        }
        Ok((_, None)) => WindowResult::Unsat,
        Err(_) => WindowResult::Timeout,
    }
}

/// DIMACS を書き出す（実験用）。
pub fn write_cnf(black: u64, white: u64, opts: EncOpts, out: &mut dyn Write) -> std::io::Result<()> {
    let (cnf, _) = encode(black, white, opts);
    write_dimacs(&cnf, out)
}

fn write_dimacs(cnf: &Cnf, f: &mut dyn Write) -> std::io::Result<()> {
    writeln!(f, "p cnf {} {}", cnf.nvars, cnf.nclauses)?;
    let mut line = String::new();
    for &l in &cnf.lits {
        line.push_str(&l.to_string());
        if l == 0 {
            line.push('\n');
            f.write_all(line.as_bytes())?;
            line.clear();
        } else {
            line.push(' ');
        }
    }
    Ok(())
}

/// 解の出力を解釈する。Some(Some(model)) = SAT、Some(None) = UNSAT、None = 判定なし。
fn parse_output(out: &str, nvars: i32) -> Option<Option<Vec<bool>>> {
    let mut status = "";
    let mut model = vec![false; nvars as usize + 1];
    for line in out.lines() {
        if let Some(st) = line.strip_prefix("s ") {
            status = st.trim();
        } else if let Some(vs) = line.strip_prefix("v ") {
            for v in vs.split_whitespace().filter_map(|t| t.parse::<i32>().ok()) {
                if v > 0 && v <= nvars {
                    model[v as usize] = true;
                }
            }
        }
    }
    match status {
        "SATISFIABLE" => Some(Some(model)),
        "UNSATISFIABLE" => Some(None),
        _ => None,
    }
}

/// 複数の CNF を並列に解く。各インスタンスは「UNSAT が到達不能の証明になるか」を持つ。
/// 戻り値: (インスタンス番号, Some(model) = SAT / None = 証明つき UNSAT)。
/// Duration::MAX is the explicit no-time-limit sentinel. Elapsed-time subtraction
/// preserves this classification; ordinary finite CLI budgets are far below it.
fn is_unbounded(limit: Duration) -> bool {
    limit.as_secs() >= u64::MAX / 2
}

fn run_portfolio(insts: &[(&Cnf, bool)], solver: &str, limit: Duration, seeds: usize) -> Result<(usize, Option<Vec<bool>>), String> {
    run_portfolio_cancel(insts, solver, limit, seeds, None)
}

/// cancel が立ったら途中でも全ソルバーを止めて Err("cancelled") を返す版
fn run_portfolio_cancel(
    insts: &[(&Cnf, bool)], solver: &str, limit: Duration, seeds: usize, cancel: Option<&std::sync::atomic::AtomicBool>,
) -> Result<(usize, Option<Vec<bool>>), String> {
    let tag = format!("{}-{:?}", std::process::id(), std::thread::current().id());
    let mut paths = Vec::new();
    for (i, (cnf, _)) in insts.iter().enumerate() {
        let path = std::env::temp_dir().join(format!("othello-retro-{tag}-{i}.cnf"));
        let mut f = std::io::BufWriter::new(std::fs::File::create(&path).map_err(|e| e.to_string())?);
        write_dimacs(cnf, &mut f).map_err(|e| e.to_string())?;
        paths.push(path);
    }
    let (tx, rx) = mpsc::channel();
    let mut children = Vec::new();
    for (i, path) in paths.iter().enumerate() {
        for seed in 0..seeds.max(1) {
            let mut command = Command::new(solver);
            command.arg("-q");
            if !is_unbounded(limit) {
                command.arg(format!("--time={}", limit.as_secs().max(1)));
            }
            let mut child = command
                .arg(format!("--seed={seed}"))
                .arg(path)
                .stdout(Stdio::piped())
                .stderr(Stdio::null())
                .spawn()
                .map_err(|e| format!("{solver} を起動できない: {e}"))?;
            let mut stdout = child.stdout.take().unwrap();
            let tx = tx.clone();
            std::thread::spawn(move || {
                let mut out = String::new();
                let _ = stdout.read_to_string(&mut out);
                let _ = tx.send((i, out));
            });
            children.push(child);
        }
    }
    drop(tx);
    // 証明にならない UNSAT しか返らなかった場合は "allunsat"（時間切れの "timeout" と区別する）
    let mut result = Err("timeout".to_string());
    let (mut unsat, total) = (0, children.len());
    loop {
        let (i, out) = match rx.recv_timeout(Duration::from_millis(200)) {
            Ok(x) => x,
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if cancel.is_some_and(|c| c.load(std::sync::atomic::Ordering::SeqCst)) {
                    result = Err("cancelled".to_string());
                    break;
                }
                continue;
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        };
        match parse_output(&out, insts[i].0.nvars) {
            Some(Some(model)) => {
                result = Ok((i, Some(model)));
                break;
            }
            Some(None) if insts[i].1 => {
                result = Ok((i, None));
                break;
            }
            Some(None) => {
                unsat += 1;
                if unsat == total {
                    result = Err("allunsat".to_string());
                }
            }
            None => {}
        }
    }
    for c in &mut children {
        let _ = c.kill();
        let _ = c.wait();
    }
    for p in &paths {
        let _ = std::fs::remove_file(p);
    }
    result
}

pub fn solve(black: u64, white: u64, limit: Duration, solver: &str, jobs: usize, prepass: Duration) -> (Outcome, Stats) {
    let start = Instant::now();
    let mut stats = Stats { nodes: 0, restarts: 0, elapsed: Duration::ZERO };
    let done = |o: Outcome, mut st: Stats| {
        st.elapsed = start.elapsed();
        (o, st)
    };
    if let Err(e) = preprocess(black, white) {
        return done(Outcome::Unreachable(e), stats);
    }
    if (black, white) == (INIT_BLACK, INIT_WHITE) {
        return done(Outcome::Found(vec![]), stats);
    }
    debug_assert_eq!(placement_closure(black | white), black | white);
    // 手数の少ない盤面は DFS が一瞬で解くので先に短時間だけ試す
    if !prepass.is_zero() {
        let (o, st) = crate::solver::solve(black, white, limit.min(prepass), 1);
        stats.nodes = st.nodes;
        if !matches!(o, Outcome::Unknown) {
            return done(o, stats);
        }
    }
    // 3 本を並列に走らせる（全マス盤面での比較実験に基づく）:
    // パスなし（最速。UNSAT は証明にならないが、パス必須の盤面ではすぐ UNSAT になる）、
    // 終盤 12 手だけパス許可（パスを含む盤面の解を見つける）、一般版（UNSAT が到達不能の証明）
    let fast = encode(black, white, EncOpts { nopass: true, occ: true, ..Default::default() });
    let late = encode(black, white, EncOpts { occ: true, pass_window: 12, ..Default::default() });
    let full = encode(black, white, EncOpts::default());
    let insts = [(&fast.0, false), (&late.0, false), (&full.0, true)];
    let encs = [&fast.1, &late.1, &full.1];
    match run_portfolio(&insts, solver, limit.saturating_sub(start.elapsed()), jobs).map(|(i, r)| (encs[i], r)) {
        Ok((enc, Some(model))) => {
            let val = |l: i32| if l > 0 { model[l as usize] } else { !model[(-l) as usize] };
            let mut squares = Vec::with_capacity(enc.n);
            for t in 0..enc.n {
                let s = (0..64).find(|&s| val(enc.m[t][s])).expect("各手に着手マスがある");
                squares.push(s as u8);
            }
            done(Outcome::Found(crate::retro::with_passes(&squares)), stats)
        }
        Ok((_, None)) => done(Outcome::Unreachable("SAT ソルバーが充足不能を証明".into()), stats),
        Err(e) if e == "timeout" => done(Outcome::Unknown, stats),
        Err(e) => {
            eprintln!("SAT ソルバーのエラー: {e}");
            done(Outcome::Unknown, stats)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn has_kissat() -> bool {
        Command::new("kissat").arg("--version").output().is_ok()
    }

    #[test]
    fn unbounded_sentinel_survives_elapsed_time() {
        assert!(is_unbounded(Duration::MAX));
        assert!(is_unbounded(Duration::MAX.saturating_sub(Duration::from_secs(86_400))));
        assert!(!is_unbounded(Duration::from_secs(3_600)));
        assert!(!is_unbounded(Duration::ZERO));
    }

    #[test]
    fn opposite_pairs() {
        for d in 0..8 {
            assert_eq!((D8[d].0 + D8[rev(d)].0, D8[d].1 + D8[rev(d)].1), (0, 0));
        }
    }

    #[test]
    fn sat_solves_and_rejects() {
        if !has_kissat() {
            eprintln!("kissat が無いのでスキップ");
            return;
        }
        // f5 d6 c3 d3 c4（白番で終わる 5 手）を SAT のみで復元
        let mut path = vec![];
        for sq in ["f5", "d6", "c3", "d3", "c4"] {
            let b = sq.as_bytes();
            path.push((b[1] - b'1') * 8 + (b[0] - b'a'));
        }
        let (b, w) = crate::solver::replay(&path).unwrap();
        match solve(b, w, Duration::from_secs(10), "kissat", 1, Duration::ZERO).0 {
            Outcome::Found(p) => assert_eq!(crate::solver::replay(&p).unwrap(), (b, w)),
            _ => panic!("到達可能な局面を解けなかった"),
        }
        // 同じ石配置で、返らないマス以外の 1 石の色を変えたものは到達不能のはず（DFS と照合）
        let flip = 1u64 << 27; // d4
        let (b2, w2) = if b & flip != 0 { (b & !flip, w | flip) } else { (b | flip, w & !flip) };
        let dfs = crate::solver::solve(b2, w2, Duration::from_secs(10), 1).0;
        let sat = solve(b2, w2, Duration::from_secs(10), "kissat", 1, Duration::ZERO).0;
        assert_eq!(matches!(dfs, Outcome::Found(_)), matches!(sat, Outcome::Found(_)));
    }
}
