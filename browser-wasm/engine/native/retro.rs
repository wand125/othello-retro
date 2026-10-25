//! 後ろ向き探索（目標から 1 手ずつ戻す）＋ 序盤表（ちょうど K 手の全局面）との突き合わせ。
//!
//! 戻す手の条件（c が s に置いた手を戻す場合）:
//! - s は c の石で、中央 4 マスではない
//! - どの方向にも「相手石の列の先に c の石」が残っていない（残っていればその列は返っていたはず）
//! - 各方向について、s の隣から続く c の石の列のうち先頭 k 個（その先も c）が返った石。少なくとも 1 方向で k ≥ 1

use crate::board::*;
use crate::edge;
use crate::solver::{self, placement_closure, preprocess, Mix, Outcome, Stats};
use std::collections::HashSet;
use std::hash::BuildHasherDefault;
use std::time::{Duration, Instant};

pub type Book = HashSet<(u64, u64, u8), BuildHasherDefault<Mix>>;
pub const TERMINAL: u8 = 2;
pub const ANY: u8 = 3;

/// c が着手した直後の局面で次に打つ側。相手に合法手がなければパスで c、両者なければ終局。
pub fn next_side(b: u64, w: u64, c: u8) -> u8 {
    let (p, o) = if c == 0 { (b, w) } else { (w, b) };
    if legal_moves(o, p) != 0 {
        1 - c
    } else if legal_moves(p, o) != 0 {
        c
    } else {
        TERMINAL
    }
}

/// ちょうど k 手の全局面（次の手番つき）。k = 9 で約 300 万局面。
pub fn build_book(k: u32) -> Book {
    let mut level = Book::default();
    level.insert((INIT_BLACK, INIT_WHITE, 0));
    for _ in 0..k {
        let mut next = Book::default();
        for &(b, w, side) in &level {
            if side == TERMINAL {
                continue;
            }
            let (p, o) = if side == 0 { (b, w) } else { (w, b) };
            let mut m = legal_moves(p, o);
            while m != 0 {
                let sq = m.trailing_zeros();
                m &= m - 1;
                let (nb, nw) = play(b, w, side, sq);
                next.insert((nb, nw, next_side(nb, nw, side)));
            }
        }
        level = next;
    }
    level
}

#[inline]
fn edges_from_empty(b: u64, w: u64) -> bool {
    let f = edge::from_empty();
    edge::EDGES.iter().all(|e| f[edge::index(b, w, e)])
}

#[inline]
fn neighbors(s: u32) -> u64 {
    let m = 1u64 << s;
    DIRS.iter().fold(0, |a, &d| a | shift(m, d))
}

/// (b, w)（次の手番 nxt）の直前の局面の候補: (優先度, 乱数, 戻したマス, 黒, 白, 着手した側)。
pub fn undos(b: u64, w: u64, nxt: u8, rand: &mut dyn FnMut() -> u32) -> Vec<(i32, u32, u8, u64, u64, u8)> {
    undos_with(b, w, nxt, rand, true)
}

/// 優先度の計算（着手可能数など）を省いた版。並べ替えを外でやるビームサーチ用。
pub fn undos_plain(b: u64, w: u64, nxt: u8) -> Vec<(u8, u64, u64, u8)> {
    undos_with(b, w, nxt, &mut || 0, false).into_iter().map(|k| (k.2, k.3, k.4, k.5)).collect()
}

fn undos_with(b: u64, w: u64, nxt: u8, rand: &mut dyn FnMut() -> u32, scored: bool) -> Vec<(i32, u32, u8, u64, u64, u8)> {
    let occ = b | w;
    let empty = !occ;
    let mut kids: Vec<(i32, u32, u8, u64, u64, u8)> = Vec::new();
    for c in 0..2u8 {
        if nxt != ANY && next_side(b, w, c) != nxt {
            continue;
        }
        let (own, opp) = if c == 0 { (b, w) } else { (w, b) };
        let mut cand = own & !CENTER;
        while cand != 0 {
            let s = cand.trailing_zeros();
            cand &= cand - 1;
            let sbit = 1u64 << s;
            let occ_q = occ & !sbit;
            if placement_closure(occ_q) != occ_q {
                continue;
            }
            // 方向ごとの「返った石」の候補。opts[d][0] = 返っていない
            let mut opts = [[0u64; 7]; 8];
            let mut nopt = [1usize; 8];
            let mut ok = true;
            for (di, &d) in DIRS.iter().enumerate() {
                let mut x = shift(sbit, d);
                if x & opp != 0 {
                    while x & opp != 0 {
                        x = shift(x, d);
                    }
                    if x & own != 0 {
                        ok = false;
                        break;
                    }
                } else if x & own != 0 {
                    let mut seg = 0;
                    loop {
                        seg |= x;
                        x = shift(x, d);
                        if x & own == 0 {
                            break;
                        }
                        opts[di][nopt[di]] = seg;
                        nopt[di] += 1;
                    }
                }
            }
            if !ok || nopt.iter().all(|&n| n == 1) {
                continue;
            }
            let free = (neighbors(s) & empty).count_ones() as f32;
            let empty_q = empty | sbit;
            let frontier = (DIRS.iter().fold(0, |a, &d| a | shift(empty_q, d)) & occ_q).count_ones() as f32;
            let corner = (sbit & 0x8100_0000_0000_0081 != 0) as u32 as f32;
            let mut idx = [0usize; 8];
            loop {
                // 全方向 0 を飛ばして混合基数で列挙
                let mut i = 0;
                while i < 8 {
                    idx[i] += 1;
                    if idx[i] < nopt[i] {
                        break;
                    }
                    idx[i] = 0;
                    i += 1;
                }
                if i == 8 {
                    break;
                }
                let f = (0..8).fold(0u64, |a, i| a | opts[i][idx[i]]);
                let q_own = own & !f & !sbit;
                let q_opp = opp | f;
                let (qb, qw) = if c == 0 { (q_own, q_opp) } else { (q_opp, q_own) };
                debug_assert_eq!(play(qb, qw, c, s), (b, w));
                if !edges_from_empty(qb, qw) {
                    continue;
                }
                if !scored {
                    kids.push((0, 0, s as u8, qb, qw, c));
                    continue;
                }
                // ランダム対局の真の手順から条件付きロジットで学習した重み（features サブコマンド参照）。
                // 戻した後の外周石と着手可能数が少ないほど、その局面から実際にこの手が打たれた可能性が高い
                let (p, o) = if c == 0 { (qb, qw) } else { (qw, qb) };
                let mob_c = legal_moves(p, o).count_ones() as f32;
                let mob_o = legal_moves(o, p).count_ones() as f32;
                let ndirs = idx.iter().filter(|&&i| i != 0).count() as f32;
                let nf = f.count_ones() as f32;
                let score = 0.1424 * free - 0.0159 * nf - 0.2147 * ndirs - 0.2891 * mob_c - 0.1843 * mob_o
                    - 0.35 * frontier
                    + 0.5617 * corner
                    - 0.716 * (mob_c + 1.0).ln()
                    - 0.191 * (mob_o + 1.0).ln();
                let score = (score * 1000.0) as i32;
                let r = rand();
                kids.push((score, r, s as u8, qb, qw, c));
            }
        }
    }
    kids
}

fn self_rand(rng: &mut u64) -> u32 {
    *rng ^= *rng << 13;
    *rng ^= *rng >> 7;
    *rng ^= *rng << 17;
    (*rng >> 32) as u32
}

enum R {
    Found,
    Fail,
    Abort,
}

struct Back<'a> {
    book: &'a Book,
    k: u32,
    fail: Book,
    rng: u64,
    nodes: u64,
    budget: u64,
    deadline: Instant,
    /// 戻した手（目標側から順に）
    path: Vec<u8>,
    hit: (u64, u64, u8),
}

impl Back<'_> {
    /// (b, w) で次に nxt が打つ（ANY は目標局面で手番不問）局面を、初期局面から作れるか。
    fn dfs(&mut self, b: u64, w: u64, nxt: u8) -> R {
        let occ = b | w;
        if occ.count_ones() - 4 == self.k {
            return if self.book.contains(&(b, w, nxt)) {
                self.hit = (b, w, nxt);
                R::Found
            } else {
                R::Fail
            };
        }
        self.nodes += 1;
        if self.nodes > self.budget || (self.nodes & 0xFFF == 0 && Instant::now() > self.deadline) {
            return R::Abort;
        }
        let key = (b, w, nxt);
        if self.fail.contains(&key) {
            return R::Fail;
        }

        let mut kids = undos(b, w, nxt, &mut || self_rand(&mut self.rng));
        kids.sort_unstable_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));

        let mut res = R::Fail;
        for &(_, _, s, qb, qw, c) in &kids {
            self.path.push(s);
            match self.dfs(qb, qw, c) {
                R::Found => return R::Found,
                R::Fail => {
                    self.path.pop();
                }
                R::Abort => {
                    self.path.pop();
                    res = R::Abort;
                    break;
                }
            }
        }
        if matches!(res, R::Fail) && self.fail.len() < 10_000_000 {
            self.fail.insert(key);
        }
        res
    }
}

/// 初期局面から (target, 手番) まで depth 手で行く手順（序盤表で到達可能と分かっている局面用）。
fn prefix(b: u64, w: u64, side: u8, target: (u64, u64, u8), depth: u32, out: &mut Vec<u8>) -> bool {
    if depth == 0 {
        return (b, w, side) == target;
    }
    if side == TERMINAL {
        return false;
    }
    let (p, o) = if side == 0 { (b, w) } else { (w, b) };
    let mut m = legal_moves(p, o) & (target.0 | target.1);
    while m != 0 {
        let sq = m.trailing_zeros();
        m &= m - 1;
        let (nb, nw) = play(b, w, side, sq);
        out.push(sq as u8);
        if prefix(nb, nw, next_side(nb, nw, side), target, depth - 1, out) {
            return true;
        }
        out.pop();
    }
    false
}

/// マスだけの着手列にパスを補う。
pub fn with_passes(squares: &[u8]) -> Vec<u8> {
    let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
    let mut out = Vec::with_capacity(squares.len() + 4);
    for &s in squares {
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        if legal_moves(p, o) == 0 {
            out.push(solver::PASS);
            side = 1 - side;
        }
        (b, w) = play(b, w, side, s as u32);
        out.push(s);
        side = 1 - side;
    }
    out
}

pub fn solve(book: &Book, k: u32, black: u64, white: u64, limit: Duration, seed: u64) -> (Outcome, Stats) {
    let start = Instant::now();
    let mut stats = Stats { nodes: 0, restarts: 0, elapsed: Duration::ZERO };
    if let Err(e) = preprocess(black, white) {
        stats.elapsed = start.elapsed();
        return (Outcome::Unreachable(e), stats);
    }
    if (black | white).count_ones() - 4 <= k {
        return solver::solve(black, white, limit, seed);
    }
    let mut s = Back {
        book,
        k,
        fail: Book::default(),
        rng: seed.wrapping_mul(0x9E37_79B9_7F4A_7C15) | 1,
        nodes: 0,
        budget: 0,
        deadline: start + limit,
        path: Vec::new(),
        hit: (0, 0, 0),
    };
    let mut budget = 20_000u64;
    loop {
        s.nodes = 0;
        s.budget = budget;
        s.path.clear();
        let r = s.dfs(black, white, ANY);
        stats.nodes += s.nodes;
        match r {
            R::Found => {
                let mut squares = Vec::new();
                let ok = prefix(INIT_BLACK, INIT_WHITE, 0, s.hit, k, &mut squares);
                assert!(ok, "序盤表にある局面への手順が見つからない");
                squares.extend(s.path.iter().rev());
                stats.elapsed = start.elapsed();
                return (Outcome::Found(with_passes(&squares)), stats);
            }
            R::Fail => {
                stats.elapsed = start.elapsed();
                return (Outcome::Unreachable("後ろ向き探索で全候補を否定".into()), stats);
            }
            R::Abort => {
                if Instant::now() > s.deadline {
                    stats.elapsed = start.elapsed();
                    return (Outcome::Unknown, stats);
                }
                stats.restarts += 1;
                budget = budget.saturating_mul(2);
            }
        }
    }
}
