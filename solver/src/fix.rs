//! 到達不能な盤面の修正補助（CaDiCaL のインクリメンタル SAT）。
//!
//! 最終盤面の各マスの色の条件を「仮定」（セレクタ変数）にした CNF を 1 度だけ読み込み、
//! 仮定を変えながら繰り返し解く。学習した節が使い回されるので、毎回ゼロから解くより速い。
//! - nearest: 「色を変えるマスは k 個以下」を k = 0, 1, 2, … と変えて、最小の直し方を探す（保護したいマスは変えない）
//! - map: 各マスについて「そのマスだけ色の条件を外すと到達可能か」を調べる。
//!   UNSAT のときに矛盾に関わった仮定（コア）に入らないマスは、1 回の解でまとめて「変えても直らない」と分かる

use crate::board::*;
use crate::sat::{encode_window, Enc, EncOpts};
use std::time::{Duration, Instant};

pub struct Fixer {
    solver: cadical::Solver,
    enc: Enc,
    /// out[j] = 「色を変えたマスが j+1 個以上」
    out: Vec<i32>,
}

pub const K_MAX: usize = 8;

#[derive(Clone, Copy, PartialEq, Debug)]
pub enum Cell {
    /// そのマスを裏返すだけで到達可能になる
    Reachable,
    /// そのマスを変えても到達不能
    Unreachable,
    Unknown,
}

pub struct Fix {
    /// 色を変えたマス
    pub changed: Vec<u8>,
    /// 変えた後の盤面に至る着手（マス。パスは含めない）
    pub squares: Vec<u8>,
}

impl Fixer {
    pub fn new(black: u64, white: u64) -> Self {
        let opts = EncOpts { selectors: true, ..Default::default() };
        let (mut cnf, enc) = encode_window((INIT_BLACK, INIT_WHITE), 0, (black, white), None, opts);
        // 色を変えたマス（セレクタが偽）を数える逐次カウンタ。上向きの含意だけで「≤ k」を仮定で表せる
        let xs: Vec<i32> = enc.sel.iter().filter(|&&a| a != 0).map(|&a| -a).collect();
        let mut prev: Vec<i32> = vec![];
        for &x in &xs {
            let cur: Vec<i32> = (0..K_MAX).map(|_| cnf.var()).collect();
            for j in 0..K_MAX {
                if j < prev.len() {
                    cnf.add(&[-prev[j], cur[j]]); // 前までに j+1 個 → 今も j+1 個以上
                }
                if j == 0 {
                    cnf.add(&[-x, cur[0]]);
                } else if j - 1 < prev.len() {
                    cnf.add(&[-x, -prev[j - 1], cur[j]]);
                }
            }
            prev = cur;
        }
        // CaDiCaL の設定（環境変数 RETRO_CADICAL_CONFIG: default / unsat / sat / plain）
        let mut solver: cadical::Solver = match std::env::var("RETRO_CADICAL_CONFIG") {
            Ok(cfg) if cfg != "default" => cadical::Solver::with_config(&cfg).unwrap_or_default(),
            _ => Default::default(),
        };
        let mut clause = vec![];
        for &l in &cnf.lits {
            if l == 0 {
                solver.add_clause(clause.drain(..));
            } else {
                clause.push(l);
            }
        }
        Fixer { solver, enc, out: prev }
    }

    fn solve(&mut self, assumptions: &[i32], limit: Duration) -> Option<bool> {
        self.solver.set_callbacks(Some(cadical::Timeout::new(limit.as_secs_f32().max(0.01))));
        self.solver.solve_with(assumptions.iter().copied())
    }

    fn all_sel(&self) -> Vec<i32> {
        self.enc.sel.iter().copied().filter(|&a| a != 0).collect()
    }

    fn squares(&self) -> Vec<u8> {
        (0..self.enc.n)
            .map(|t| (0..64).find(|&s| self.enc.m[t][s] > 0 && self.solver.value(self.enc.m[t][s]) == Some(true)).unwrap() as u8)
            .collect()
    }

    fn changed(&self) -> Vec<u8> {
        (0..64u8).filter(|&s| self.enc.sel[s as usize] != 0 && self.solver.value(self.enc.sel[s as usize]) == Some(false)).collect()
    }

    /// 最小の直し方を探す。protect のマスは変えない。k_max 個まで、fixes 通りまで集める
    pub fn nearest(&mut self, k_max: usize, protect: u64, fixes: usize, deadline: Instant, on_fix: &mut dyn FnMut(usize, &Fix)) -> Result<Vec<Fix>, &'static str> {
        let protected: Vec<i32> = (0..64).filter(|&s| protect >> s & 1 != 0 && self.enc.sel[s] != 0).map(|s| self.enc.sel[s]).collect();
        let mut found = vec![];
        // k = 0（変えずに到達可能か）を先に証明するのは重いので飛ばし、k = 1 から始める。
        // 「k 個以下」には 0 個も含まれるので、実は到達可能なら変更 0 個の解が返る
        for k in 1..=k_max.min(K_MAX - 1) {
            loop {
                let left = deadline.saturating_duration_since(Instant::now());
                if left.is_zero() {
                    return if found.is_empty() { Err("timeout") } else { Ok(found) };
                }
                let mut asm = protected.clone();
                asm.push(-self.out[k]); // 変えるマスは k 個以下
                match self.solve(&asm, left) {
                    Some(true) => {
                        let fix = Fix { changed: self.changed(), squares: self.squares() };
                        on_fix(k, &fix);
                        if fix.changed.is_empty() {
                            found.push(fix);
                            return Ok(found); // そもそも到達可能
                        }
                        // 同じ変え方は二度と出さない（変えたマスのどれかは元の色のまま）
                        let block: Vec<i32> = fix.changed.iter().map(|&s| self.enc.sel[s as usize]).collect();
                        self.solver.add_clause(block);
                        found.push(fix);
                        if found.len() >= fixes {
                            return Ok(found);
                        }
                    }
                    Some(false) => break, // k 個以下では（もう）直せない
                    None => return if found.is_empty() { Err("timeout") } else { Ok(found) },
                }
            }
            if !found.is_empty() {
                return Ok(found); // 最小の k で見つかった分だけ返す
            }
        }
        Ok(found)
    }

    /// 各マスについて、そのマスだけ色の条件を外すと到達可能か。each は 1 回の解の上限
    /// first は最初の「全マスを仮定して解く」求解の上限。これが解ければコアで多くのマスが一度に決まるので、長めに与える
    pub fn map(&mut self, first: Duration, each: Duration, deadline: Instant, on_cell: &mut dyn FnMut(u8, Cell, &str)) -> [Cell; 64] {
        let mut res = [Cell::Unknown; 64];
        let all = self.all_sel();
        let lim = |d: Instant| deadline.saturating_duration_since(Instant::now()).min(each).min(d.saturating_duration_since(Instant::now()));
        let first_lim = deadline.saturating_duration_since(Instant::now()).min(first);
        match self.solve(&all, first_lim) {
            Some(true) => {
                // そもそも到達可能: どのマスを外しても到達可能
                for s in 0..64u8 {
                    if self.enc.sel[s as usize] != 0 {
                        res[s as usize] = Cell::Reachable;
                        on_cell(s, Cell::Reachable, "盤面がそもそも到達可能");
                    }
                }
                return res;
            }
            None => return res,
            Some(false) => {}
        }
        // コアに入らないマスは、外しても残りの仮定だけで矛盾するので「変えても直らない」
        let core: Vec<u8> = (0..64u8).filter(|&s| self.enc.sel[s as usize] != 0 && self.solver.failed(self.enc.sel[s as usize])).collect();
        for s in 0..64u8 {
            if self.enc.sel[s as usize] != 0 && !core.contains(&s) {
                res[s as usize] = Cell::Unreachable;
                on_cell(s, Cell::Unreachable, "最初のコアの外");
            }
        }
        for &s in &core {
            if res[s as usize] != Cell::Unknown {
                continue;
            }
            if deadline <= Instant::now() {
                break;
            }
            let asm: Vec<i32> = all.iter().copied().filter(|&a| a != self.enc.sel[s as usize]).collect();
            match self.solve(&asm, lim(deadline)) {
                Some(true) => {
                    res[s as usize] = Cell::Reachable;
                    on_cell(s, Cell::Reachable, "解いて確認");
                }
                Some(false) => {
                    res[s as usize] = Cell::Unreachable;
                    on_cell(s, Cell::Unreachable, "解いて確認");
                    // このときのコアに入らない未判定のマスも、外しても直らない
                    for t in 0..64u8 {
                        let a = self.enc.sel[t as usize];
                        if a != 0 && res[t as usize] == Cell::Unknown && t != s && !self.solver.failed(a) {
                            res[t as usize] = Cell::Unreachable;
                            on_cell(t, Cell::Unreachable, "別のコアの外");
                        }
                    }
                }
                None => on_cell(s, Cell::Unknown, "時間切れ"),
            }
        }
        res
    }
}
