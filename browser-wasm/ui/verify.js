// SPDX-License-Identifier: MIT
// Copyright (c) 2026 wand125 and contributors.
/* Independent array-based Othello replay. No solver, model, DOM, or 64-bit math. */
(function (root, factory) {
  'use strict';
  const rules = factory();
  if (typeof module === 'object' && module.exports) module.exports = rules;
  if (root) root.RetroRules = rules;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const INITIAL = '---------------------------OX------XO---------------------------';
  const DIRECTIONS = [];
  for (let dr = -1; dr <= 1; dr++) {
    for (let dc = -1; dc <= 1; dc++) {
      if (dr || dc) DIRECTIONS.push([dr, dc]);
    }
  }
  class InvalidRecord extends Error {
    constructor(message) { super(message); this.name = 'InvalidRecord'; }
  }
  const other = color => color === 'X' ? 'O' : 'X';
  function validateBoard(board) {
    if (typeof board !== 'string' || board.length !== 64 || /[^XO-]/.test(board)) {
      throw new InvalidRecord('target must contain exactly 64 X/O/- cells');
    }
  }
  function flips(board, square, color) {
    if (board[square] !== '-') return [];
    const result = [], opponent = other(color);
    const row = Math.floor(square / 8), col = square % 8;
    for (const [dr, dc] of DIRECTIONS) {
      let r = row + dr, c = col + dc;
      const line = [];
      while (r >= 0 && r < 8 && c >= 0 && c < 8 && board[r * 8 + c] === opponent) {
        line.push(r * 8 + c); r += dr; c += dc;
      }
      if (line.length && r >= 0 && r < 8 && c >= 0 && c < 8 && board[r * 8 + c] === color) {
        result.push(...line);
      }
    }
    return result;
  }
  function canMove(board, color) {
    for (let square = 0; square < 64; square++) {
      if (flips(board, square, color).length) return true;
    }
    return false;
  }
  function ended(board) { return !canMove(board, 'X') && !canMove(board, 'O'); }

  function replay(moves, options) {
    if (!Array.isArray(moves) || moves.length > 120) {
      throw new InvalidRecord('moves must be an array of at most 120 coordinate/pass strings');
    }
    const includeStates = options && options.includeStates === true;
    const board = Array.from(INITIAL), normalized = [], states = [];
    let side = 'X', placements = 0, passes = 0;
    function snapshot(move) {
      if (includeStates) states.push({ board: board.join(''), next_player: side,
        move, placements, passes, terminal: ended(board) });
    }
    function pass() {
      normalized.push('pass'); passes++; side = other(side); snapshot('pass');
    }
    snapshot(null);
    for (let index = 0; index < moves.length; index++) {
      const move = moves[index];
      if (typeof move !== 'string' || (move !== 'pass' &&
          !(move.length === 2 && move[0] >= 'a' && move[0] <= 'h' && move[1] >= '1' && move[1] <= '8'))) {
        throw new InvalidRecord(`move ${index}: expected lower-case a1..h8 or pass`);
      }
      if (move === 'pass') {
        if (canMove(board, side)) throw new InvalidRecord(`move ${index}: voluntary pass is illegal`);
        if (!canMove(board, other(side))) throw new InvalidRecord(`move ${index}: game already ended`);
        pass();
        continue;
      }
      if (!canMove(board, side)) {
        if (!canMove(board, other(side))) throw new InvalidRecord(`move ${index}: game already ended`);
        pass();
      }
      const square = (move.charCodeAt(1) - 49) * 8 + move.charCodeAt(0) - 97;
      const changed = flips(board, square, side);
      if (!changed.length) throw new InvalidRecord(`move ${index}: placement is illegal`);
      board[square] = side;
      for (const position of changed) board[position] = side;
      normalized.push(move); placements++; side = other(side); snapshot(move);
    }
    const result = { moves: normalized, board: board.join(''), next_player: side,
      terminal: ended(board), placements, passes };
    if (includeStates) result.states = states;
    return result;
  }
  function verify(moves, target, options) {
    validateBoard(target);
    const result = replay(moves, options);
    if (result.board !== target) throw new InvalidRecord('replayed position differs from the 64-cell target');
    return result;
  }
  function boardFromMoves(moves) { return replay(moves).board; }
  return Object.freeze({ INITIAL, InvalidRecord, replay, verify, boardFromMoves });
});
