//! 辺テーブル。辺の石は辺方向にしか挟まれないので、各辺を 8 マスの 1 次元オセロとして独立に扱える。
//! 合法性は緩和し（どこに何色を置いてもよい）、辺方向の返しだけ規則どおり行う。
//! よって「目標の辺パターンへ到達可能な辺パターン集合」は到達性の必要条件になる。

use std::sync::OnceLock;

pub const NSTATES: usize = 6561;
pub const EDGES: [[u32; 8]; 4] = [
    [0, 1, 2, 3, 4, 5, 6, 7],
    [56, 57, 58, 59, 60, 61, 62, 63],
    [0, 8, 16, 24, 32, 40, 48, 56],
    [7, 15, 23, 31, 39, 47, 55, 63],
];
const POW3: [usize; 8] = [1, 3, 9, 27, 81, 243, 729, 2187];

fn decode(mut s: usize) -> [u8; 8] {
    let mut a = [0u8; 8];
    for v in a.iter_mut() {
        *v = (s % 3) as u8;
        s /= 3;
    }
    a
}

fn encode(a: &[u8; 8]) -> usize {
    a.iter().enumerate().map(|(i, &v)| v as usize * POW3[i]).sum()
}

/// 0 = 空, 1 = 黒, 2 = 白
#[inline]
pub fn index(black: u64, white: u64, edge: &[u32; 8]) -> usize {
    let mut s = 0;
    for (i, &sq) in edge.iter().enumerate() {
        let m = 1u64 << sq;
        if black & m != 0 {
            s += POW3[i];
        } else if white & m != 0 {
            s += 2 * POW3[i];
        }
    }
    s
}

fn place(a: &[u8; 8], i: usize, c: u8) -> [u8; 8] {
    let mut r = *a;
    r[i] = c;
    let opp = 3 - c;
    for dir in [-1i32, 1] {
        let mut j = i as i32 + dir;
        while (0..8).contains(&j) && r[j as usize] == opp {
            j += dir;
        }
        if (0..8).contains(&j) && r[j as usize] == c {
            let mut k = i as i32 + dir;
            while k != j {
                r[k as usize] = c;
                k += dir;
            }
        }
    }
    r
}

fn predecessors() -> &'static [Vec<u16>] {
    static P: OnceLock<Vec<Vec<u16>>> = OnceLock::new();
    P.get_or_init(|| {
        let mut p = vec![Vec::new(); NSTATES];
        for s in 0..NSTATES {
            let a = decode(s);
            for i in 0..8 {
                if a[i] != 0 {
                    continue;
                }
                for c in 1..=2 {
                    p[encode(&place(&a, i, c))].push(s as u16);
                }
            }
        }
        p
    })
}

/// 空の辺から到達可能な辺パターンの集合（後ろ向き探索で戻した局面の必要条件）。
pub fn from_empty() -> &'static [bool] {
    static F: OnceLock<Vec<bool>> = OnceLock::new();
    F.get_or_init(|| {
        let mut seen = vec![false; NSTATES];
        let mut queue = vec![0usize];
        seen[0] = true;
        while let Some(s) = queue.pop() {
            let a = decode(s);
            for i in 0..8 {
                if a[i] != 0 {
                    continue;
                }
                for c in 1..=2 {
                    let t = encode(&place(&a, i, c));
                    if !seen[t] {
                        seen[t] = true;
                        queue.push(t);
                    }
                }
            }
        }
        seen
    })
}

/// target へ到達可能な辺パターンの集合（逆向き BFS）。
pub fn can_reach(target: usize) -> Vec<bool> {
    let preds = predecessors();
    let mut seen = vec![false; NSTATES];
    let mut queue = vec![target];
    seen[target] = true;
    while let Some(s) = queue.pop() {
        for &q in &preds[s] {
            if !seen[q as usize] {
                seen[q as usize] = true;
                queue.push(q as usize);
            }
        }
    }
    seen
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn corner_never_flips() {
        // 隅が白の辺パターンへは、隅が黒の状態から到達できない
        let mut t = [0u8; 8];
        t[0] = 2;
        t[1] = 2;
        let r = can_reach(encode(&t));
        let mut s = [0u8; 8];
        s[0] = 1;
        assert!(!r[encode(&s)]);
        assert!(r[0]);
    }

    #[test]
    fn sandwiched_forces_flip() {
        // X O X は「O を後から真ん中に置く」以外に作れない。X X X からは作れない
        let t = [1, 2, 1, 0, 0, 0, 0, 0];
        let r = can_reach(encode(&t));
        assert!(r[0]);
        assert!(!r[encode(&[1, 1, 1, 0, 0, 0, 0, 0])]);
    }
}
