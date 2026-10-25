// SPDX-License-Identifier: MIT
// Copyright (c) 2026 wand125 and contributors.
'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const rules = require('../ui/verify.js');
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'cases.json'), 'utf8'));
const successes = fixtures.cases.filter(c => c.expected === 'reachable');
const passCase = successes.find(c => c.id === 'game-2c8b678b7c02');
const sha = text => crypto.createHash('sha256').update(text).digest('hex');
const rejects = fn => assert.throws(fn, {name: 'InvalidRecord'});

test('all11 reference records independently replay to every target cell', () => {
  assert.equal(successes.length, 11);
  for (const c of successes) {
    const original = JSON.stringify(c.reference_moves);
    const result = rules.verify(c.reference_moves, c.board);
    assert.equal(result.board, c.board, c.id);
    assert.equal(result.placements, c.placements, c.id);
    assert.equal(result.passes, c.passes, c.id);
    assert.equal(result.terminal, c.terminal, c.id);
    assert.equal(c.stones, 4 + result.placements, c.id);
    assert.equal(rules.boardFromMoves(c.reference_moves), c.board, c.id);
    assert.equal(JSON.stringify(c.reference_moves), original, 'input array must not be mutated');
    assert.equal(sha(c.board), c.board_sha256);
    assert.equal(sha(JSON.stringify(c.reference_moves)), c.reference_moves_sha256);
  }
});

test('initial board, black first, coordinates and optional snapshots', () => {
  const initial = rules.verify([], rules.INITIAL, {includeStates: true});
  assert.equal(initial.next_player, 'X');
  assert.equal(initial.states.length, 1);
  assert.equal(initial.states[0].move, null);
  assert.equal(initial.terminal, false);
  const c = successes.find(c => c.id === 'one-move');
  const result = rules.verify(['d3'], c.board, {includeStates:true});
  assert.equal(result.board[19], 'X');
  assert.equal(result.board[27], 'X');
  assert.equal(result.board[36], 'O');
  assert.equal(result.next_player, 'O');
  assert.equal(result.states.length, 2);
  assert.equal(result.states[1].board, c.board);
  assert.ok(!Object.hasOwn(rules.verify(['d3'], c.board), 'states'));
});

test('explicit and omitted forced passes normalize identically', () => {
  for (const c of successes.filter(c => c.passes > 0)) {
    const explicit = rules.verify(c.reference_moves, c.board, {includeStates:true});
    const omitted = rules.verify(c.reference_moves.filter(m => m !== 'pass'), c.board, {includeStates:true});
    assert.deepEqual(explicit, omitted, c.id);
    assert.equal(explicit.states.length, explicit.moves.length+1);
    for (let i=1; i<explicit.states.length; i++) {
      const before=explicit.states[i-1], after=explicit.states[i];
      assert.notEqual(after.next_player,before.next_player);
      if (after.move === 'pass') {
        assert.equal(after.board,before.board);
        assert.equal(after.placements,before.placements);
        assert.equal(after.passes,before.passes+1);
      }
    }
  }
  assert.equal(rules.verify(passCase.reference_moves,passCase.board).terminal,true);
  assert.ok(passCase.board.includes('-'), 'terminal need not mean full board');
});

test('voluntary pass and an illegal switch to the other color are rejected', () => {
  rejects(() => rules.verify(['pass'],rules.INITIAL));
  rejects(() => rules.replay(['e3'])); // Legal for white, but black must start.
  rejects(() => rules.replay(['d3','f5']));
  rejects(() => rules.replay(['d3','pass']));
  rejects(() => rules.replay(['d3','d3']));
});

test('no placement or terminal pass may be added after the game ended', () => {
  const full=successes.find(c => c.stones===64);
  for (const c of [full,passCase]) {
    rejects(() => rules.verify([...c.reference_moves,'pass'],c.board));
    rejects(() => rules.verify([...c.reference_moves,'pass','pass'],c.board));
    rejects(() => rules.verify([...c.reference_moves,'a1'],c.board));
  }
});

test('a legal forced pass at an intermediate target can end the record', () => {
  const i=passCase.reference_moves.indexOf('pass');
  const before=rules.replay(passCase.reference_moves.slice(0,i));
  const after=rules.verify(passCase.reference_moves.slice(0,i+1),before.board);
  assert.equal(after.placements,before.placements);
  assert.equal(after.passes,before.passes+1);
  assert.notEqual(after.next_player,before.next_player);
  assert.equal(after.terminal,false);
});

test('wrong target cells are rejected even when the move sequence is legal', () => {
  for (const c of [successes[0],passCase]) {
    for (const square of [0,7,27,36,56,63]) {
      const wrong=Array.from(c.board);
      wrong[square]=wrong[square]==='X'?'O':'X';
      rejects(() => rules.verify(c.reference_moves,wrong.join('')));
    }
  }
});

test('strict input types, bounds and trailing newlines cannot bypass parsing', () => {
  for (const moves of [null,undefined,'d3',{},[19],['D3'],['a0'],['i1'],[' pass '],['a1\n'],['pass\n'],Array(121).fill('pass'),new Array(1)]) {
    rejects(() => rules.verify(moves,rules.INITIAL));
  }
  for (const board of [null,undefined,Array.from(rules.INITIAL),rules.INITIAL.slice(1),rules.INITIAL+'\n','?'.repeat(64), ' '.repeat(64)]) {
    rejects(() => rules.verify([],board));
  }
});

test('browser/worker global and CommonJS expose the same pure API', () => {
  assert.equal(globalThis.RetroRules,rules);
  const context=vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../ui/verify.js'),'utf8'),context);
  assert.equal(typeof context.RetroRules.verify,'function');
  const c=passCase;
  const result=context.RetroRules.verify(c.reference_moves,c.board);
  assert.deepEqual(JSON.parse(JSON.stringify(result)),rules.verify(c.reference_moves,c.board));
});

test('small6-stone impossible board is absent from all12 two-placement boards', () => {
  // Four legal black openings and their three legal white replies exhaust the
  // first two placements; no forced pass occurs at this depth.
  const replies={d3:['c3','e3','c5'],c4:['c3','e3','c5'],f5:['d6','f4','f6'],e6:['d6','f4','f6']};
  const boards=[];
  for (const [first,seconds] of Object.entries(replies)) {
    for (const second of seconds) boards.push(rules.boardFromMoves([first,second]));
  }
  assert.equal(new Set(boards).size,12);
  const c=fixtures.cases.find(c=>c.id==='paper-two-placement-unreachable');
  assert.equal(Array.from(c.board).filter(cell=>cell!=='-').length,6);
  assert.equal(boards.includes(c.board),false);
});

test('impossible fixtures preserve distinct evidence strength and scope', () => {
  const immediate=fixtures.cases.find(c=>c.id==='missing-center');
  assert.equal(immediate.board[27],'-');
  const deep=fixtures.cases.find(c=>c.id==='paper-deep-root-61');
  assert.equal(deep.stones,61);
  assert.equal(deep.proof.kind,'general-pass board-only CNF');
  assert.equal(deep.proof.target_next_side,'unrestricted');
  assert.equal(deep.proof.nopass,false);
  assert.equal(deep.proof.solver_exit_code,20);
  assert.equal(deep.proof.drat_independently_checked,false);
  assert.equal(deep.proof.drat_trace_generated,false);
  // Replay tests do not execute a solver or establish a new UNSAT certificate.
});

test('optional public-source provenance audit', {skip:!process.env.RETRO_FIXTURE_SOURCE_REPO}, () => {
  const root=path.resolve(process.env.RETRO_FIXTURE_SOURCE_REPO);
  for (const [rel,entry] of Object.entries(fixtures.sources)) {
    assert.ok(!path.isAbsolute(rel) && !rel.split('/').includes('..'));
    assert.equal(sha(fs.readFileSync(path.join(root,rel))),entry.sha256,rel);
  }
});
