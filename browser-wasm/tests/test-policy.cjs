// SPDX-License-Identifier: MIT
// Control-flow regression tests with mock SAT results. These do not measure
// solver performance or replace the real-WASM acceptance/replay tests.
'use strict';
const assert = require('node:assert/strict');
const {test, after} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const {solve} = require('../ui/engine.js');
const board = '---------------------------OX------XO---------------------------';
const results = [];

function fixture(codes, {preprocess = false, badVerify = false, target = board} = {}) {
  const pending = codes.slice(), modes = [], limits = [], released = [], events = [];
  let solver = 0, checks = 0;
  const encoder = {
    memory: {buffer: new ArrayBuffer(1024)},
    encode_board: (...args) => { modes.push(args[4]); return preprocess ? 1 : 0; },
    error_ptr: () => 0, error_len: () => 0,
    placements_ptr: () => 0, placements_len: () => 0,
    true_literal: () => 1, variables: () => 1, clauses: () => 0, steps: () => 0,
    literals_ptr: () => 0, literals_len: () => 0, free_encoding: () => {}
  };
  const sat = {
    HEAP32: new Int32Array(1024), _kissat_init: () => ++solver,
    _kissat_reserve: () => {}, _malloc: () => 4, _free: () => {},
    _kissat_add_buffer: () => {},
    _kissat_set_conflict_limit: (id, limit) => limits.push([id, 'conflicts', limit]),
    _kissat_set_decision_limit: (id, limit) => limits.push([id, 'decisions', limit]),
    _kissat_solve: () => {
      assert(pending.length > 0, 'unexpected extra solver attempt');
      return pending.shift();
    },
    _kissat_release: id => released.push(id)
  };
  const rules = {verify: moves => {
    checks++;
    if (badVerify) throw Error('invalid witness');
    return {moves, terminal: false};
  }};
  return {
    run: () => solve(target, encoder, sat, rules, event => events.push(event)),
    modes, limits, released, events, checks: () => checks
  };
}
function check(name, fn) {
  test(name, () => {
    try { fn(); results.push({name, status: 'passed'}); }
    catch (error) { results.push({name, status: 'failed', reason: error.message}); throw error; }
  });
}

for (const code of [20, 0]) {
  check(`probe ${code === 20 ? 'UNSAT' : 'unknown'} falls through to verified full SAT`, () => {
    const f = fixture([code, 10]), result = f.run();
    assert.equal(result.status, 'found');
    assert.deepEqual(f.modes, [1, 3]);
    assert.equal(result.stats.attempts.length, 2);
    assert.deepEqual(f.released, [1, 2]);
    assert.deepEqual(f.limits, [[1, 'conflicts', 2000], [1, 'decisions', 20000]]);
    assert.equal(f.checks(), 1);
    assert.equal(result.stats.solved_by, 'general_sat');
    assert(result.wall_seconds >= result.stats.attempts.reduce((n, attempt) => n + attempt.wall_seconds, 0));
  });
}
check('probe SAT is independently verified and released', () => {
  const f = fixture([10]), result = f.run();
  assert.equal(result.status, 'found');
  assert.deepEqual(f.modes, [1]);
  assert.equal(f.checks(), 1);
  assert.deepEqual(f.released, [1]);
  assert.equal(result.stats.solved_by, 'passfree_probe');
});
check('only full UNSAT gives final unreachability', () => {
  const f = fixture([0, 20]), result = f.run();
  assert.equal(result.status, 'unreachable');
  assert.deepEqual(f.modes, [1, 3]);
  assert.equal(result.stats.attempts[1].general_pass_encoding, true);
});
check('restricted UNSAT plus full unknown stays unknown', () => {
  const f = fixture([20, 0]), result = f.run();
  assert.equal(result.status, 'unknown');
  assert.deepEqual(f.modes, [1, 3]);
  assert.equal(result.stats.attempts[0].status, 'unsat');
});
check('common preprocessing rejection is authoritative', () => {
  const f = fixture([], {preprocess: true}), result = f.run();
  assert.equal(result.status, 'unreachable');
  assert.deepEqual(f.modes, [1]);
  assert.equal(f.released.length, 0);
  assert.equal(result.stats.solved_by, 'preprocess');
});
check('invalid SAT witness is rejected and the solver is released', () => {
  const f = fixture([10], {badVerify: true});
  assert.throws(f.run, /invalid witness/);
  assert.deepEqual(f.released, [1]);
});
check('policy records SAT-only work limits and an unlimited full stage', () => {
  const f = fixture([10]), result = f.run();
  assert.equal(result.stats.policy.machine_learning, false);
  assert.equal(result.stats.policy.limits_are_wall_seconds, false);
  assert.equal(result.stats.policy.final_solver_limit, null);
  assert.deepEqual(f.events.map(event => event.phase), ['probe', 'probe', 'probe']);
});

const largeBoard = JSON.parse(fs.readFileSync(path.join(__dirname,'cases.json'))).cases.find(c=>c.id.startsWith('main-n44-')).board;
check('neither restricted UNSAT is a general refutation on a large board',()=>{
  const f=fixture([20,20,10],{target:largeBoard}), result=f.run();
  assert.equal(result.status,'found');assert.deepEqual(f.modes,[1,2,3]);
  assert.equal(result.stats.attempts[1].general_pass_encoding,false);
  assert.equal(result.stats.attempts[2].general_pass_encoding,true);
  assert.equal(f.checks(),1);
});
check('late-pass work-limit exhaustion continues to the unlimited general formula',()=>{
  const f=fixture([0,0,20],{target:largeBoard}), result=f.run();
  assert.equal(result.status,'unreachable');assert.deepEqual(f.modes,[1,2,3]);
  assert.deepEqual(f.limits,[[1,'conflicts',100000],[1,'decisions',1000000],[2,'conflicts',100000],[2,'decisions',1000000]]);
  assert.equal(result.stats.attempts[2].conflict_limit,null);
});
check('a late-pass SAT witness is independently replayed and stops the search',()=>{
  const f=fixture([0,10],{target:largeBoard}), result=f.run();
  assert.equal(result.status,'found');assert.deepEqual(f.modes,[1,2]);
  assert.equal(result.stats.solved_by,'late_pass_probe');assert.equal(f.checks(),1);
  assert.deepEqual(f.released,[1,2]);
});

after(() => {
  const directory = path.join(__dirname, '../validation');
  fs.mkdirSync(directory, {recursive: true});
  fs.writeFileSync(path.join(directory, 'policy-regression.json'), JSON.stringify({
    status: results.length === 11 && results.every(row => row.status === 'passed') ? 'passed' : 'failed',
    purpose: 'Mock encoder/SAT control-flow regression; real solver acceptance is separate',
    runtime: process.version,
    tests: results
  }, null, 2) + '\n');
});
