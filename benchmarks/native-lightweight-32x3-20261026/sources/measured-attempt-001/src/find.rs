//! 「見つける専用」の後ろ向きビームサーチ（パスなし仮定）。
//! 最終盤面から 1 手ずつ戻し、各段で評価の高い上位 width 局面だけを残して序盤表（9 手）まで届かせる。
//! 完全性は無い（見つからなくても到達不能とは言えない）。

use crate::board::*;
use crate::retro::{self, Book};
use std::collections::HashMap;

pub fn mix64(mut x: u64) -> u64 {
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    x = x.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    x ^ (x >> 33)
}

/// パスなし仮定での 1 手戻しの候補（n 手目を打ったのは n-1 の偶奇で決まる側）。
pub fn passfree_undos(b: u64, w: u64) -> Vec<(u64, u64)> {
    let n = (b | w).count_ones() - 4;
    if n == 0 {
        return vec![];
    }
    let mover = ((n - 1) % 2) as u8;
    // A terminal target has no next player, even when empty squares remain.
    // Only relax that terminal marker: retain the no-pass last-mover parity below.
    let nxt = if n == 60 || (legal_moves(b, w) == 0 && legal_moves(w, b) == 0) {
        retro::ANY
    } else {
        (n % 2) as u8
    };
    retro::undos_plain(b, w, nxt).into_iter().filter(|k| k.3 == mover).map(|k| (k.1, k.2)).collect()
}

#[derive(Clone, Copy, Debug)]
pub enum Score {
    /// 戻せる手の数（生存力）
    Kids,
    /// 2 手先まで生き残る子の数
    Kids2,
    /// 乱数（行き止まりだけ除く）
    Random,
}

pub struct BeamResult {
    /// 見つかった局面列（9 手の局面 → 目標）
    pub path: Option<Vec<(u64, u64)>>,
    /// 生き残った最小手数
    pub reached: u32,
    pub evals: u64,
}

fn eval(b: u64, w: u64, score: Score, salt: u64) -> Option<i64> {
    let kids = passfree_undos(b, w);
    if kids.is_empty() && (b | w).count_ones() - 4 > 9 {
        return None;
    }
    let r = (mix64(b ^ mix64(w) ^ salt) >> 44) as i64; // 同点の並び替え用
    Some(match score {
        Score::Kids => (kids.len() as i64) << 20 | r,
        Score::Kids2 => {
            let alive = kids.iter().filter(|&&(qb, qw)| !passfree_undos(qb, qw).is_empty()).count();
            if alive == 0 && (b | w).count_ones() - 4 > 10 {
                return None;
            }
            (alive as i64) << 20 | r
        }
        Score::Random => r,
    })
}

pub fn beam(target: (u64, u64), width: usize, score: Score, book: &Book, salt: u64) -> BeamResult {
    // levels[i] = (局面, 親の添字)
    let mut levels: Vec<Vec<((u64, u64), usize)>> = vec![vec![(target, usize::MAX)]];
    let mut evals = 0u64;
    loop {
        let cur = levels.last().unwrap();
        let n = { let (b, w) = cur[0].0; (b | w).count_ones() - 4 };
        if n == 9 {
            // 序盤表との突き合わせ（9 手後は白番）
            for (i, &((b, w), _)) in cur.iter().enumerate() {
                if book.contains(&(b, w, 1)) {
                    let mut path = vec![];
                    let mut idx = i;
                    for lv in levels.iter().rev() {
                        let (p, parent) = lv[idx];
                        path.push(p);
                        idx = parent;
                    }
                    return BeamResult { path: Some(path), reached: 9, evals };
                }
            }
            return BeamResult { path: None, reached: 9, evals };
        }
        let mut seen: HashMap<(u64, u64), ()> = HashMap::new();
        let mut cand: Vec<(i64, (u64, u64), usize)> = Vec::new();
        for (pi, &((b, w), _)) in cur.iter().enumerate() {
            for q in passfree_undos(b, w) {
                if seen.insert(q, ()).is_some() {
                    continue;
                }
                evals += 1;
                if let Some(s) = eval(q.0, q.1, score, salt) {
                    cand.push((s, q, pi));
                }
            }
        }
        if cand.is_empty() {
            return BeamResult { path: None, reached: n, evals };
        }
        cand.sort_unstable_by(|a, b| b.0.cmp(&a.0));
        cand.truncate(width);
        levels.push(cand.into_iter().map(|(_, q, pi)| (q, pi)).collect());
    }
}

/// 9 手の局面から目標までの局面列を、序盤の手順と合わせて着手列にする。
pub fn to_moves(path: &[(u64, u64)]) -> Option<Vec<u8>> {
    let (b9, w9) = path[0];
    let mut squares = vec![];
    if !prefix9(INIT_BLACK, INIT_WHITE, 0, (b9, w9), &mut squares) {
        return None;
    }
    for win in path.windows(2) {
        let (a, b) = (win[0].0 | win[0].1, win[1].0 | win[1].1);
        squares.push((b & !a).trailing_zeros() as u8);
    }
    Some(squares)
}

fn prefix9(b: u64, w: u64, depth: u32, target: (u64, u64), out: &mut Vec<u8>) -> bool {
    if depth == 9 {
        return (b, w) == target;
    }
    let side = (depth % 2) as u8;
    let (p, o) = if side == 0 { (b, w) } else { (w, b) };
    let mut m = legal_moves(p, o) & (target.0 | target.1);
    while m != 0 {
        let sq = m.trailing_zeros();
        m &= m - 1;
        let (nb, nw) = play(b, w, side, sq);
        out.push(sq as u8);
        if prefix9(nb, nw, depth + 1, target, out) {
            return true;
        }
        out.pop();
    }
    false
}

/// 目標から (目標の手数 - stop_n) 手戻した局面の候補を、ビームサーチで最大 width 個集める。
/// 各要素は「その局面 → 目標」の局面列。
pub fn frontier(target: (u64, u64), width: usize, stop_n: u32, salt: u64) -> Vec<Vec<(u64, u64)>> {
    let mut levels: Vec<Vec<((u64, u64), usize)>> = vec![vec![(target, usize::MAX)]];
    loop {
        let cur = levels.last().unwrap();
        let n = { let (b, w) = cur[0].0; (b | w).count_ones() - 4 };
        if n <= stop_n {
            return (0..cur.len())
                .map(|i| {
                    let mut path = vec![];
                    let mut idx = i;
                    for lv in levels.iter().rev() {
                        let (p, parent) = lv[idx];
                        path.push(p);
                        idx = parent;
                    }
                    path
                })
                .collect();
        }
        let mut seen: HashMap<(u64, u64), ()> = HashMap::new();
        let mut cand: Vec<(i64, (u64, u64), usize)> = Vec::new();
        for (pi, &((b, w), _)) in cur.iter().enumerate() {
            for q in passfree_undos(b, w) {
                if seen.insert(q, ()).is_some() {
                    continue;
                }
                if let Some(s) = eval(q.0, q.1, Score::Kids, salt) {
                    cand.push((s, q, pi));
                }
            }
        }
        if cand.is_empty() {
            return vec![];
        }
        cand.sort_unstable_by(|a, b| b.0.cmp(&a.0));
        cand.truncate(width);
        levels.push(cand.into_iter().map(|(_, q, pi)| (q, pi)).collect());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Frozen terminal-bank cases, selected independently of solver results.
    // endgame-early-terminal-s202610255401016 has 59 placements and no passes.
    const NO_PASS_RECORD: &str = "d3 c5 f6 e3 c4 b3 d6 e6 f4 c3 c6 g6 b4 d7 c7 a4 d2 b6 b7 b5 b2 g3 e7 a2 g4 b1 g5 c8 g2 c2 b8 g7 a3 f5 d1 g1 h8 g8 d8 a5 a1 f8 c1 f7 h4 h3 a6 e8 h7 f3 f2 h5 h1 h6 f1 a7 a8 e2 h2";
    const NO_PASS_TARGET: &str = "XXXX-XXXXXXXOXXXXXXOOOXXXXOXOOOXXOOXOOOXXOXOOOOXXXOOOOOXXXXXOOOX";
    // endgame-early-terminal-s202610255406852 has one forced pass before h5.
    const PASS_RECORD: &str = "e6 f6 c4 c5 b6 f3 g6 b5 b4 a5 a6 f7 e8 e3 a4 h6 d6 d7 f5 g8 e2 g7 g4 a7 d3 d2 c8 e7 c1 c7 f8 g5 c2 g2 g3 h3 h1 b3 a2 f2 h8 f4 h7 c6 h4 e1 d1 c3 b2 g1 d8 a3 h2 a1 b1 f1 b7 pass h5";
    const PASS_TARGET: &str = "OXXXOOOXOXXOOXXXOXOOOXXXOXOXXXXXOXOXXXXXOXXXOXXXOXXXXXXX--XXXXXX";

    fn replay_record(record: &str) -> (Vec<(u64, u64)>, Vec<u8>, usize) {
        let mut states = vec![(INIT_BLACK, INIT_WHITE)];
        let mut movers = Vec::new();
        let (mut side, mut passes) = (0u8, 0usize);
        for token in record.split_whitespace() {
            let (b, w) = *states.last().unwrap();
            let (p, o) = if side == 0 { (b, w) } else { (w, b) };
            if token == "pass" {
                assert_eq!(legal_moves(p, o), 0, "pass while a placement exists");
                assert_ne!(legal_moves(o, p), 0, "pass after termination");
                passes += 1;
                side ^= 1;
                continue;
            }
            let bytes = token.as_bytes();
            assert_eq!(bytes.len(), 2);
            let square = u32::from(bytes[0] - b'a') + 8 * u32::from(bytes[1] - b'1');
            assert_ne!(legal_moves(p, o) & (1 << square), 0, "illegal {token}");
            states.push(play(b, w, side, square));
            movers.push(side);
            side ^= 1;
        }
        (states, movers, passes)
    }

    #[test]
    fn incomplete_terminal_preserves_a_known_passfree_predecessor() {
        let (states, movers, passes) = replay_record(NO_PASS_RECORD);
        assert_eq!(passes, 0);
        let target = *states.last().unwrap();
        assert_eq!(target, parse(NO_PASS_TARGET).unwrap());
        assert_eq!((target.0 | target.1).count_ones(), 63);
        assert_eq!(legal_moves(target.0, target.1), 0);
        assert_eq!(legal_moves(target.1, target.0), 0);
        let n = (target.0 | target.1).count_ones() - 4;
        let mover = ((n - 1) % 2) as u8;
        assert_eq!(*movers.last().unwrap(), mover);
        let previous = states[states.len() - 2];
        let candidates = passfree_undos(target.0, target.1);
        assert!(candidates.contains(&previous), "lost the legal no-pass reference prefix");
        // Every returned candidate must still be one legal placement of the
        // no-pass parity mover away from this exact target, not an arbitrary color.
        for (b, w) in candidates {
            let removed = (target.0 | target.1) & !(b | w);
            assert_eq!(removed.count_ones(), 1);
            assert_eq!((b | w).count_ones() + 1, 63);
            let square = removed.trailing_zeros();
            let (p, o) = if mover == 0 { (b, w) } else { (w, b) };
            assert_ne!(legal_moves(p, o) & removed, 0);
            assert_eq!(play(b, w, mover, square), target);
        }
    }

    #[test]
    fn terminal_fix_keeps_the_no_pass_mover_and_nonterminal_policy() {
        let (states, movers, passes) = replay_record(PASS_RECORD);
        assert_eq!(passes, 1);
        let target = *states.last().unwrap();
        assert_eq!(target, parse(PASS_TARGET).unwrap());
        assert_eq!((target.0 | target.1).count_ones(), 62);
        assert_eq!(legal_moves(target.0, target.1) | legal_moves(target.1, target.0), 0);
        let mover = (((target.0 | target.1).count_ones() - 5) % 2) as u8;
        assert_ne!(*movers.last().unwrap(), mover);
        let before_final = states[states.len() - 2];
        assert!(!passfree_undos(target.0, target.1).contains(&before_final),
                "terminal handling must not admit the opposite-parity last mover");
        // Immediately before the explicit pass White has no move but Black does.
        // This change must not broaden the existing no-pass nonterminal policy.
        assert_eq!(legal_moves(before_final.1, before_final.0), 0);
        assert_ne!(legal_moves(before_final.0, before_final.1), 0);
        assert!(passfree_undos(before_final.0, before_final.1).is_empty());
    }
}
