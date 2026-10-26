// SPDX-License-Identifier: MIT
//! Browser-only raw ABI. Only preprocessing and CNF generation are called.
//! The unchanged native modules also define CLI helpers; those are dead code.
#![allow(dead_code)]
use std::cell::RefCell;

#[path = "../native/board.rs"] mod board;
#[path = "../native/edge.rs"] mod edge;
#[path = "../native/solver.rs"] mod solver;
#[path = "../native/retro.rs"] mod retro;
#[path = "../native/sat.rs"] mod sat;

#[derive(Default)]
struct Generated {
    literals: Vec<i32>,
    placements: Vec<i32>,
    variables: i32,
    clauses: usize,
    steps: usize,
    true_literal: i32,
    error: Vec<u8>,
}

thread_local! {
    static UNDOS: RefCell<Vec<u32>> = const { RefCell::new(Vec::new()) };
    static UNDO_SCORES: RefCell<Vec<i32>> = const { RefCell::new(Vec::new()) };
}

/// Enumerate legal one-placement predecessors. A candidate is only a heuristic;
/// its reachability is never asserted here. Records are six u32 words:
/// black low/high, white low/high, mover, removed square.
#[no_mangle]
pub extern "C" fn undo_board(bl: u32, bh: u32, wl: u32, wh: u32, next: u32, passfree: u32) -> i32 {
    let b = u64::from(bl) | (u64::from(bh) << 32);
    let w = u64::from(wl) | (u64::from(wh) << 32);
    UNDOS.with(|cell| {
        let mut out = cell.borrow_mut();
        out.clear();
        let stones = (b | w).count_ones();
        if b & w != 0 || stones < 4 || next > 3 { return -1; }
        if stones == 4 { return 0; }
        let n = stones - 4;
        let nxt = if passfree & 1 != 0 {
            if board::legal_moves(b, w) == 0 && board::legal_moves(w, b) == 0 {
                retro::ANY
            } else { (n % 2) as u8 }
        } else { next as u8 };
        let mut children: Vec<_> = if passfree & 2 != 0 {
            retro::undos(b, w, nxt, &mut || 0).into_iter().map(|c| ((c.2,c.3,c.4,c.5),c.0)).collect()
        } else { retro::undos_plain(b, w, nxt).into_iter().map(|c| (c,0)).collect() };
        if passfree & 1 != 0 { children.retain(|(c,_)| c.3 == ((n - 1) % 2) as u8); }
        children.sort_unstable_by_key(|(c,_)| (c.1, c.2, c.3));
        children.dedup_by_key(|(c,_)| (c.1, c.2, c.3));
        let mut scores=Vec::with_capacity(children.len());
        for ((square, qb, qw, mover), score) in children {
            out.extend_from_slice(&[qb as u32, (qb >> 32) as u32, qw as u32, (qw >> 32) as u32,
                u32::from(mover), u32::from(square)]);
            scores.push(score);
        }
        UNDO_SCORES.with(|cell| *cell.borrow_mut()=scores);
        (out.len() / 6) as i32
    })
}

#[no_mangle]
pub extern "C" fn undos_ptr() -> *const u32 { UNDOS.with(|v| v.borrow().as_ptr()) }
#[no_mangle]
pub extern "C" fn undo_scores_ptr() -> *const i32 { UNDO_SCORES.with(|v| v.borrow().as_ptr()) }
#[no_mangle]
pub extern "C" fn free_undos() {
    UNDOS.with(|v| *v.borrow_mut() = Vec::new());
    UNDO_SCORES.with(|v| *v.borrow_mut() = Vec::new());
}

thread_local! {
    static STATE: RefCell<Generated> = RefCell::new(Generated::default());
}

/// Return 0=encoded, 1=necessary condition disproves reachability,
/// -1=invalid overlap/mode. Modes 0/3 are general (with/without redundant
/// occupancy constraints); 1 is no-pass and 2 allows only late passes.
/// UNSAT for either restricted mode MUST NOT mean general unreachability.
#[no_mangle]
pub extern "C" fn encode_board(black_low: u32, black_high: u32, white_low: u32, white_high: u32, mode: u32) -> i32 {
    let black = u64::from(black_low) | (u64::from(black_high) << 32);
    let white = u64::from(white_low) | (u64::from(white_high) << 32);
    STATE.with(|state| {
        let mut value = state.borrow_mut();
        *value = Generated::default();
        if black & white != 0 || mode > 3 {
            value.error = b"invalid overlapping discs".to_vec();
            return -1;
        }
        if let Err(reason) = solver::preprocess(black, white) {
            value.error = reason.into_bytes();
            return 1;
        }
        let options = sat::EncOpts { occ: mode != 3, nopass: mode == 1,
            pass_window: if mode == 2 { 12 } else { 0 }, ..Default::default() };
        let (cnf, encoding) = sat::encode_window((board::INIT_BLACK, board::INIT_WHITE), 0, (black, white), None, options);
        *value = Generated {
            literals: cnf.lits,
            placements: encoding.m.into_iter().flatten().collect(),
            variables: cnf.nvars,
            clauses: cnf.nclauses,
            steps: encoding.n,
            true_literal: cnf.tru,
            error: Vec::new(),
        };
        0
    })
}

#[no_mangle]
pub extern "C" fn literals_ptr() -> *const i32 { STATE.with(|v| v.borrow().literals.as_ptr()) }
#[no_mangle]
pub extern "C" fn literals_len() -> usize { STATE.with(|v| v.borrow().literals.len()) }
#[no_mangle]
pub extern "C" fn placements_ptr() -> *const i32 { STATE.with(|v| v.borrow().placements.as_ptr()) }
#[no_mangle]
pub extern "C" fn placements_len() -> usize { STATE.with(|v| v.borrow().placements.len()) }
#[no_mangle]
pub extern "C" fn variables() -> i32 { STATE.with(|v| v.borrow().variables) }
#[no_mangle]
pub extern "C" fn clauses() -> usize { STATE.with(|v| v.borrow().clauses) }
#[no_mangle]
pub extern "C" fn steps() -> usize { STATE.with(|v| v.borrow().steps) }
#[no_mangle]
pub extern "C" fn true_literal() -> i32 { STATE.with(|v| v.borrow().true_literal) }
#[no_mangle]
pub extern "C" fn error_ptr() -> *const u8 { STATE.with(|v| v.borrow().error.as_ptr()) }
#[no_mangle]
pub extern "C" fn error_len() -> usize { STATE.with(|v| v.borrow().error.len()) }
#[no_mangle]
pub extern "C" fn free_encoding() { STATE.with(|v| *v.borrow_mut() = Generated::default()); }
