//! 前処理（即時棄却・辺テーブル）＋ 前向き DFS（置換表・ランダム再始動）。

use crate::board::*;
use crate::edge;
use std::collections::HashSet;
use std::hash::{BuildHasherDefault, Hasher};
use std::time::{Duration, Instant};

pub const PASS: u8 = 255;
const FAIL_TABLE_CAP: usize = 10_000_000;

pub enum Outcome {
    /// 着手列（PASS を含む）
    Found(Vec<u8>),
    /// 到達不能が証明された（理由）
    Unreachable(String),
    /// 時間切れ
    Unknown,
}

pub struct Stats {
    pub nodes: u64,
    pub restarts: u32,
    pub elapsed: Duration,
}

pub struct Target {
    pub black: u64,
    pub white: u64,
    pub occ: u64,
    edge_ok: [Vec<bool>; 4],
}

/// 前処理 A-2: 置き順の閉包。
/// s に置くには、ある方向 d で s+d, s+2d が既に埋まっている必要がある（石は消えないので目標でも埋まっている）。
pub fn placement_closure(occ: u64) -> u64 {
    let mut placed = CENTER & occ;
    loop {
        let mut add = 0;
        for &d in &DIRS {
            let n1 = shift(placed, -d);
            let n2 = shift(n1, -d);
            add |= n1 & n2;
        }
        add &= occ & !placed;
        if add == 0 {
            return placed;
        }
        placed |= add;
    }
}

/// 前処理。到達不能が即座に分かれば Err(理由)。
pub fn preprocess(black: u64, white: u64) -> Result<Target, String> {
    if black & white != 0 {
        return Err("黒と白が重なっている".into());
    }
    let occ = black | white;
    if occ & CENTER != CENTER {
        return Err("中央 4 マスが埋まっていない".into());
    }
    let closure = placement_closure(occ);
    if closure != occ {
        let bad: Vec<String> = (0..64u8)
            .filter(|&s| (occ & !closure) >> s & 1 != 0)
            .map(sq_name)
            .collect();
        return Err(format!("置き順の閉包に入らないマスがある: {}", bad.join(" ")));
    }
    let edge_ok: [Vec<bool>; 4] =
        std::array::from_fn(|i| edge::can_reach(edge::index(black, white, &edge::EDGES[i])));
    for (i, ok) in edge_ok.iter().enumerate() {
        if !ok[edge::index(INIT_BLACK, INIT_WHITE, &edge::EDGES[i])] {
            return Err(format!("辺 {} のパターンが作れない", ["1段目", "8段目", "a列", "h列"][i]));
        }
    }
    Ok(Target { black, white, occ, edge_ok })
}

impl Target {
    /// 局面 (b, w) から目標に届き得るかの必要条件チェック。
    #[inline]
    fn viable(&self, b: u64, w: u64) -> bool {
        for i in 0..4 {
            if !self.edge_ok[i][edge::index(b, w, &edge::EDGES[i])] {
                return false;
            }
        }
        let mism = (b & self.white) | (w & self.black);
        if mism == 0 {
            return true;
        }
        mism & !self.flippable(b | w) == 0
    }

    /// 今後まだ返り得るマス。s が返るには、ある方向で
    /// 「今は空で将来置かれるマス p から s まで目標で埋まるマスが連続し、s の反対隣も目標で埋まる」必要がある。
    #[inline]
    fn flippable(&self, occ_now: u64) -> u64 {
        let t = self.occ;
        let future = t & !occ_now;
        let mut f = 0;
        for &d in &DIRS {
            let mut x = shift(future, d) & t;
            for _ in 0..5 {
                x |= shift(x, d) & t;
            }
            f |= x & shift(t, -d);
        }
        f
    }
}

#[derive(Default)]
pub(crate) struct Mix(u64);
impl Hasher for Mix {
    fn finish(&self) -> u64 {
        self.0
    }
    fn write(&mut self, bytes: &[u8]) {
        for &b in bytes {
            self.write_u64(b as u64);
        }
    }
    #[inline]
    fn write_u64(&mut self, x: u64) {
        self.0 = (self.0 ^ x).wrapping_mul(0x9E37_79B9_7F4A_7C15).rotate_left(31);
    }
    #[inline]
    fn write_u8(&mut self, x: u8) {
        self.write_u64(x as u64);
    }
}

enum R {
    Found,
    Fail,
    Abort,
}

struct Search<'a> {
    t: &'a Target,
    /// 完全に調べ尽くして失敗した局面。必要条件による枝刈りしかしないので、再始動をまたいで有効。
    fail: HashSet<(u64, u64, u8), BuildHasherDefault<Mix>>,
    rng: u64,
    nodes: u64,
    budget: u64,
    deadline: Instant,
    path: Vec<u8>,
}

impl Search<'_> {
    fn rand(&mut self) -> u32 {
        self.rng ^= self.rng << 13;
        self.rng ^= self.rng >> 7;
        self.rng ^= self.rng << 17;
        (self.rng >> 32) as u32
    }

    fn dfs(&mut self, b: u64, w: u64, side: u8) -> R {
        if b == self.t.black && w == self.t.white {
            return R::Found;
        }
        self.nodes += 1;
        if self.nodes > self.budget || (self.nodes & 0xFFF == 0 && Instant::now() > self.deadline) {
            return R::Abort;
        }
        let key = (b, w, side);
        if self.fail.contains(&key) {
            return R::Fail;
        }
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, o);
        let res = if legal == 0 {
            if legal_moves(o, p) == 0 {
                R::Fail // 終局
            } else {
                self.path.push(PASS);
                match self.dfs(b, w, 1 - side) {
                    R::Found => return R::Found,
                    r => {
                        self.path.pop();
                        r
                    }
                }
            }
        } else {
            // 目標で空のマスには置けない。合法手が全部そこなら（パスできないので）行き止まり
            let mut cand = legal & self.t.occ;
            let mut kids: Vec<(u32, u32, u8, u64, u64)> = Vec::with_capacity(cand.count_ones() as usize);
            while cand != 0 {
                let sq = cand.trailing_zeros();
                cand &= cand - 1;
                let (nb, nw) = play(b, w, side, sq);
                if !self.t.viable(nb, nw) {
                    continue;
                }
                let score = ((nb & self.t.black) | (nw & self.t.white)).count_ones();
                let r = self.rand();
                kids.push((score, r, sq as u8, nb, nw));
            }
            kids.sort_unstable_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));
            let mut res = R::Fail;
            for &(_, _, sq, nb, nw) in &kids {
                self.path.push(sq);
                match self.dfs(nb, nw, 1 - side) {
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
            res
        };
        if matches!(res, R::Fail) && self.fail.len() < FAIL_TABLE_CAP {
            self.fail.insert(key);
        }
        res
    }
}

pub fn solve(black: u64, white: u64, time_limit: Duration, seed: u64) -> (Outcome, Stats) {
    let start = Instant::now();
    let mut stats = Stats { nodes: 0, restarts: 0, elapsed: Duration::ZERO };
    let t = match preprocess(black, white) {
        Ok(t) => t,
        Err(e) => {
            stats.elapsed = start.elapsed();
            return (Outcome::Unreachable(e), stats);
        }
    };
    if !t.viable(INIT_BLACK, INIT_WHITE) {
        stats.elapsed = start.elapsed();
        return (Outcome::Unreachable("初期局面が必要条件を満たさない".into()), stats);
    }
    let mut s = Search {
        t: &t,
        fail: HashSet::default(),
        rng: seed.wrapping_mul(0x9E37_79B9_7F4A_7C15) | 1,
        nodes: 0,
        budget: 0,
        deadline: start + time_limit,
        path: Vec::new(),
    };
    // 再始動ごとにノード予算を倍にする。失敗表は引き継ぐ
    let mut budget = 20_000u64;
    loop {
        s.nodes = 0;
        s.budget = budget;
        s.path.clear();
        let r = s.dfs(INIT_BLACK, INIT_WHITE, 0);
        stats.nodes += s.nodes;
        match r {
            R::Found => {
                stats.elapsed = start.elapsed();
                return (Outcome::Found(s.path), stats);
            }
            R::Fail => {
                stats.elapsed = start.elapsed();
                return (Outcome::Unreachable("探索で全候補を否定".into()), stats);
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

/// 着手列を初期局面から再生して検証し、最終局面を返す。
pub fn replay(path: &[u8]) -> Result<(u64, u64), String> {
    let (mut b, mut w, mut side) = (INIT_BLACK, INIT_WHITE, 0u8);
    for (i, &m) in path.iter().enumerate() {
        let (p, o) = if side == 0 { (b, w) } else { (w, b) };
        let legal = legal_moves(p, o);
        if m == PASS {
            if legal != 0 {
                return Err(format!("{} 手目: 合法手があるのにパス", i + 1));
            }
        } else {
            if legal >> m & 1 == 0 {
                return Err(format!("{} 手目: {} は非合法", i + 1, sq_name(m)));
            }
            (b, w) = play(b, w, side, m as u32);
        }
        side = 1 - side;
    }
    Ok((b, w))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn random_position(moves: usize, seed: u64) -> (u64, u64) {
        let mut rng = seed | 1;
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
                rng ^= rng << 13;
                rng ^= rng >> 7;
                rng ^= rng << 17;
                let k = (rng % legal.count_ones() as u64) as u32;
                let mut l = legal;
                for _ in 0..k {
                    l &= l - 1;
                }
                (b, w) = play(b, w, side, l.trailing_zeros());
                placed += 1;
            }
            side = 1 - side;
        }
        (b, w)
    }

    #[test]
    fn solves_random_reachable_positions() {
        for seed in 1..30 {
            let (b, w) = random_position(20, seed);
            match solve(b, w, Duration::from_secs(10), seed).0 {
                Outcome::Found(path) => assert_eq!(replay(&path).unwrap(), (b, w)),
                _ => panic!("seed {seed}: 到達可能な局面を解けなかった"),
            }
        }
    }

    #[test]
    fn initial_position_is_empty_record() {
        match solve(INIT_BLACK, INIT_WHITE, Duration::from_secs(1), 1).0 {
            Outcome::Found(path) => assert!(path.is_empty()),
            _ => panic!(),
        }
    }

    #[test]
    fn rejects_isolated_disc() {
        let b = INIT_BLACK | 1; // a1 に孤立した石
        assert!(preprocess(b, INIT_WHITE).is_err());
    }

    #[test]
    fn rejects_swapped_center() {
        // 中央の色を入れ替えた初期配置（0 手で作れず、1 手以上なら石が増える）
        assert!(matches!(
            solve(INIT_WHITE, INIT_BLACK, Duration::from_secs(5), 1).0,
            Outcome::Unreachable(_)
        ));
    }
}
