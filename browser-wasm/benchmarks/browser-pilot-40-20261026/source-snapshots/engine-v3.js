// SPDX-License-Identifier: MIT
// Shared browser/Node glue. The SAT model is accepted only after independent replay.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.RetroEngine = api;
})(globalThis, function () {
  'use strict';
  const POLICY = Object.freeze({name: 'extended-passfree-late-then-general-v3',
    probe_conflict_limit: 2000, probe_decision_limit: 20000,
    large_board_min_stones: 44, large_probe_conflict_limit: 100000,
    large_probe_decision_limit: 1000000,
    probe_encoding: 'nopass+occ', late_probe_encoding: 'late12+occ',
    late_probe_conflict_limit:100000, late_probe_decision_limit:1000000, fallback_encoding: 'general',
    final_solver_limit: null, limits_are_wall_seconds: false, machine_learning: false});
  function boardWords(board) {
    if (typeof board !== 'string' || board.length !== 64 || !/^[XO-]{64}$/.test(board)) throw Error('盤面の形式が正しくありません。');
    let black = 0n, white = 0n;
    for (let square = 0; square < 64; square++) {
      if (board[square] === 'X') black |= 1n << BigInt(square);
      if (board[square] === 'O') white |= 1n << BigInt(square);
    }
    const mask = 0xffffffffn;
    return [Number(black & mask), Number(black >> 32n), Number(white & mask), Number(white >> 32n)];
  }
  function createSearch(board, encoder, sat, rules, progress = () => {}) {
    const started = performance.now(), words = boardWords(board), attempts = [];
    function attempt(mode, limits = {}) {
      const restricted = mode === 1 || mode === 2;
      const attemptStarted = performance.now(), phase = mode === 1 ? 'probe' : mode === 2 ? 'late' : 'full';
      let solver = 0, buffer = 0;
      const stats = {phase, encoding: mode === 1 ? 'nopass+occ' : mode === 2 ? 'late12+occ' : mode === 0 ? 'general+occ' : 'general',
        general_pass_encoding: !restricted, solver: 'Kissat 4.0.3 / WebAssembly', single_thread: true,
        conflict_limit: limits.conflicts ?? null,
        decision_limit: limits.decisions ?? null};
      try {
        progress({stage: 'encoding', phase});
        const code = encoder.encode_board(...words, mode);
        if (code === 1) {
          // Both modes perform the same sound preprocessing, before encoding.
          const reason = new TextDecoder().decode(new Uint8Array(encoder.memory.buffer, encoder.error_ptr(), encoder.error_len()));
          stats.status = 'preprocess_rejection';
          return {status: 'unreachable', reason, preprocess_rejection: true, stats};
        }
        if (code !== 0) throw Error('盤面を解析できませんでした。');
        const placements = new Int32Array(encoder.memory.buffer, encoder.placements_ptr(), encoder.placements_len()).slice();
        const trueLiteral = encoder.true_literal();
        Object.assign(stats, {variables: encoder.variables(), clauses: encoder.clauses(), placements: encoder.steps(),
          literal_count: encoder.literals_len(), encoder_heap_bytes: encoder.memory.buffer.byteLength});
        solver = sat._kissat_init();
        if (!solver) throw Error('探索に必要なメモリを確保できませんでした。');
        sat._kissat_reserve(solver, stats.variables);
        const literals = new Int32Array(encoder.memory.buffer, encoder.literals_ptr(), encoder.literals_len());
        buffer = sat._malloc(Math.max(4, literals.byteLength));
        if (!buffer) throw Error('探索に必要なメモリを確保できませんでした。');
        sat.HEAP32.set(literals, buffer >>> 2);
        sat._kissat_add_buffer(solver, buffer, literals.length);
        sat._free(buffer); buffer = 0;
        encoder.free_encoding();
        if (limits.conflicts != null || limits.decisions != null) {
          // Work-unit limits, not elapsed-time promises. Preprocessing, CNF
          // construction and copying are also included in total wall time.
          if (limits.conflicts != null) sat._kissat_set_conflict_limit(solver, limits.conflicts);
          if (limits.decisions != null) sat._kissat_set_decision_limit(solver, limits.decisions);
        }
        progress({stage: 'solving', phase});
        const solvingStarted = performance.now(), result = sat._kissat_solve(solver);
        stats.solver_seconds = (performance.now() - solvingStarted) / 1000;
        stats.solver_heap_bytes = sat.HEAP32.buffer.byteLength;
        stats.solver_result = result;
        stats.status = result === 10 ? 'sat' : result === 20 ? 'unsat' : 'unknown';
        if (result === 20) return {status: restricted ? 'restricted_unsat' : 'unreachable', reason: restricted ? '制限したパス条件では解がありません。' : 'この盤面には初期配置から到達できません。', stats};
        if (result !== 10) return {status: 'unknown', reason: '探索を完了できませんでした。', stats};
        progress({stage: 'verifying', phase});
        const squares = [];
        for (let step = 0; step < stats.placements; step++) {
          let selected = -1;
          for (let square = 0; square < 64; square++) {
            const literal = placements[step * 64 + square];
            // The simplified constant variable may never have been sent to Kissat.
            const truth = literal === trueLiteral ? true : literal === -trueLiteral ? false : sat._kissat_value(solver, literal) > 0;
            if (truth) {
              if (selected >= 0) throw Error('探索結果を検証できませんでした。');
              selected = square;
            }
          }
          if (selected < 0) throw Error('探索結果を検証できませんでした。');
          squares.push('abcdefgh'[selected % 8] + String(Math.floor(selected / 8) + 1));
        }
        const checked = rules.verify(squares, board);
        return {status: 'found', moves: checked.moves, terminal: checked.terminal, stats};
      } finally {
        if (buffer) sat._free(buffer);
        if (solver) sat._kissat_release(solver);
        encoder.free_encoding();
        stats.wall_seconds = (performance.now() - attemptStarted) / 1000;
      }
    }
    return {
      attempt(mode, limits) {
        const result = attempt(mode, limits);
        attempts.push(result.stats);
        return result;
      },
      finish(result, extra = {}) {
        const {preprocess_rejection, ...output} = result;
        return {...output, stats: {...result.stats, policy: {...POLICY}, attempts,
          solved_by: preprocess_rejection ? 'preprocess' : result.stats.phase === 'probe' ? 'passfree_probe' : result.stats.phase === 'late' ? 'late_pass_probe' : 'general_sat', ...extra},
          wall_seconds: (performance.now() - started) / 1000};
      }
    };
  }
  function solve(board, encoder, sat, rules, progress = () => {}) {
    const search = createSearch(board, encoder, sat, rules, progress);
    const large = [...board].filter(c => c !== '-').length >= POLICY.large_board_min_stones;
    const limits = {conflicts: large ? POLICY.large_probe_conflict_limit : POLICY.probe_conflict_limit,
      decisions: large ? POLICY.large_probe_decision_limit : POLICY.probe_decision_limit};
    const probe = search.attempt(1, limits);
    if (probe.status === 'found' || probe.preprocess_rejection) return search.finish(probe);
    if (large) {
      const late = search.attempt(2, {conflicts: POLICY.late_probe_conflict_limit,
        decisions: POLICY.late_probe_decision_limit});
      if (late.status === 'found' || late.preprocess_rejection) return search.finish(late);
    }
    // Neither restricted probe can refute general reachability. A new solver is
    // required: Kissat 4.0.3 does not support a second solve on one instance.
    return search.finish(search.attempt(3));
  }
  return {boardWords, createSearch, solve, POLICY};
});
