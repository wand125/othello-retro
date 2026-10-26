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
    static STATE: RefCell<Generated> = RefCell::new(Generated::default());
}

/// Return 0=encoded, 1=necessary condition disproves reachability,
/// -1=invalid overlap. Mode 0 is general, 1 is the restricted no-pass heuristic.
/// An UNSAT result for mode 1 MUST NOT be exposed as general unreachability.
#[no_mangle]
pub extern "C" fn encode_board(black_low: u32, black_high: u32, white_low: u32, white_high: u32, mode: u32) -> i32 {
    let black = u64::from(black_low) | (u64::from(black_high) << 32);
    let white = u64::from(white_low) | (u64::from(white_high) << 32);
    STATE.with(|state| {
        let mut value = state.borrow_mut();
        *value = Generated::default();
        if black & white != 0 {
            value.error = b"invalid overlapping discs".to_vec();
            return -1;
        }
        if let Err(reason) = solver::preprocess(black, white) {
            value.error = reason.into_bytes();
            return 1;
        }
        let options = sat::EncOpts { occ: mode != 3, nopass: mode == 1 || mode == 4, pass_window: if mode == 2 { 12 } else { 0 }, noamo: mode == 4, ..Default::default() };
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
