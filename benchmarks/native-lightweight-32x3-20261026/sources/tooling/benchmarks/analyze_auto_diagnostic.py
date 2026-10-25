# SPDX-License-Identifier: MIT
"""Validate and summarize the separate auto diagnostic; standard library only.

Examples:
  python benchmarks/analyze_auto_diagnostic.py --input RESULTS --output ANALYSIS
Incomplete prefixes are validated but never imputed as completed finite costs.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
INITIAL = '---------------------------OX------XO---------------------------'
DIRECTIONS = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replay(moves, target):
    """Independent array-based replay, including omitted forced passes."""
    if not isinstance(target, str) or len(target) != 64 or set(target) - set('XO-'):
        raise ValueError('invalid target')
    if not isinstance(moves, list):
        raise ValueError('moves must be an array')
    board, side = list(INITIAL), 'X'
    def flips(pos, color):
        if board[pos] != '-': return []
        other, found = ('O' if color == 'X' else 'X'), []
        for dr, dc in DIRECTIONS:
            r, c = divmod(pos, 8); r += dr; c += dc; line = []
            while 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == other:
                line.append(8*r+c); r += dr; c += dc
            if line and 0 <= r < 8 and 0 <= c < 8 and board[8*r+c] == color:
                found += line
        return found
    def legal(color): return any(flips(i, color) for i in range(64))
    for move in moves:
        other = 'O' if side == 'X' else 'X'
        if move == 'pass':
            if legal(side) or not legal(other): raise ValueError('illegal pass')
            side = other; continue
        if not isinstance(move, str) or len(move) != 2 or move[0] not in 'abcdefgh' or move[1] not in '12345678':
            raise ValueError('invalid coordinate')
        pos = 8*(int(move[1])-1) + ord(move[0])-97
        changed = flips(pos, side)
        if not changed:
            if legal(side) or not legal(other): raise ValueError('illegal placement')
            side, other = other, side
            changed = flips(pos, side)
            if not changed: raise ValueError('illegal placement after forced pass')
        for i in [pos, *changed]: board[i] = side
        side = other
    if ''.join(board) != target: raise ValueError('target mismatch')
    return {'terminal': not legal('X') and not legal('O'), 'stones': 64-board.count('-')}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('invalid nonnegative finite ' + name)
    return float(value)


def load_run(directory, banks):
    directory = Path(directory)
    meta = json.loads((directory/'metadata.json').read_text())
    rows = [json.loads(line) for line in (directory/'runs.jsonl').read_text().splitlines() if line.strip()]
    cases = meta['selected_cases']; ids = [c['id'] for c in cases]
    if not cases or len(set(ids)) != len(ids): raise ValueError('empty/duplicate selected cases')
    split = meta['split']
    for suite in {c['suite'] for c in cases}:
        if digest(banks[suite]) != meta['banks_sha256'][suite]: raise ValueError('bank hash mismatch')
        bank = json.loads(Path(banks[suite]).read_text())
        originals = {c['id']: c for c in bank['splits'][split]['cases']}
        for c in (c for c in cases if c['suite'] == suite):
            if c['id'] not in originals or {k:v for k,v in c.items() if k != 'suite'} != originals[c['id']]:
                raise ValueError('selected case differs from hashed bank')
            proof = replay(c['reference_moves'], c['board'])
            if proof['stones'] != c['stones'] or ('terminal' in c and proof['terminal'] != c['terminal']):
                raise ValueError('reference metadata mismatch')
    schedule = meta['schedule']
    if not schedule: raise ValueError('empty schedule')
    variants = [s['variant'] for s in schedule if s['case'] == ids[0] and s['repeat'] == 1]
    if not variants or len(variants) != len(set(variants)): raise ValueError('duplicate/empty variants')
    repeats = max(s['repeat'] for s in schedule)
    if type(repeats) is not int or repeats < 1: raise ValueError('bad repeat')
    expected = []
    for repeat in range(1, repeats+1):
        for index, c in enumerate(cases):
            offset = (index+repeat-1) % len(variants)
            expected += [dict(case=c['id'], suite=c['suite'], repeat=repeat, variant=v) for v in variants[offset:]+variants[:offset]]
    if schedule != expected: raise ValueError('schedule differs from declared rotation/case-repeat coverage')
    if len(rows) > len(schedule): raise ValueError('extra rows')
    case_map = {c['id']: c for c in cases}
    for i, row in enumerate(rows):
        if any(row.get(k) != v for k,v in schedule[i].items()): raise ValueError('row order/schedule mismatch')
        if row.get('status') != 'found' or row.get('verified') is not True: raise ValueError('unverified/non-found row')
        c = case_map[row['case']]
        proof = replay(row['moves'], c['board'])
        if row['stones'] != c['stones']: raise ValueError('row stones mismatch')
        wall = finite(row['wall_seconds'], 'wall_seconds')
        guided = finite(row['guided_seconds'], 'guided_seconds')
        if guided > wall+1e-6: raise ValueError('guided time exceeds wall')
        metrics = row['metrics']
        for bucket in ['cnn_forward', 'score_pipeline', 'planes', 'undo']:
            if bucket in metrics:
                x = metrics[bucket]
                finite(x['seconds'], bucket)
                if type(x['calls']) is not int or x['calls'] < 0: raise ValueError('invalid timer calls')
        if row['cnn_used'] != (metrics.get('cnn_forward', {}).get('calls', 0) > 0): raise ValueError('CNN flag mismatch')
        if row['guided_hit'] != (row['stage'] in ['fast','careful','with-passes']): raise ValueError('guided hit mismatch')
        planned = row.get('planned_exact_route', False)
        if type(planned) is not bool: raise ValueError('invalid planned exact route flag')
        if planned != (row.get('guided_miss_reason') == 'incomplete_terminal_exact_route'):
            raise ValueError('planned exact route reason mismatch')
        if planned and (row['variant'] != 'lightweight' or not proof['terminal'] or proof['stones'] == 64
                        or row['cnn_used'] or row['guided_hit'] or metrics.get('sat_calls') or metrics.get('beams')):
            raise ValueError('planned exact route eligibility/work mismatch')
        final = 'final_sat_seconds' in metrics
        if final: finite(metrics['final_sat_seconds'], 'final SAT')
        if row['fallback'] != (row['variant'] != 'sat' and final): raise ValueError('fallback mismatch')
        if planned and not row['fallback']: raise ValueError('planned exact route missing final SAT')
        if row['variant'] == 'sat' and (row['cnn_used'] or row['guided_hit'] or guided != 0): raise ValueError('SAT row has guided work')
        for name in ['sat_calls', 'beams']:
            for call in metrics.get(name, []):
                finite(call['seconds'], name)
                if type(call['candidate_count']) is not int or call['candidate_count'] < 0: raise ValueError('bad candidate count')
                if name == 'sat_calls':
                    key = 'requested_per_solver_limit_seconds' if 'requested_per_solver_limit_seconds' in call else 'budget_seconds'
                    finite(call[key], 'requested per-solver limit')
                    if call['candidate_count'] != len(call['candidates_hex']): raise ValueError('candidate list count mismatch')
                    index = call.get('winning_index_in_chunk', call.get('index'))
                    if call['found'] and (type(index) is not int or not 0 <= index < call['candidate_count']): raise ValueError('winning index out of range')
    complete = len(rows) == len(schedule)
    if meta['status'] == 'complete' and not complete: raise ValueError('false complete metadata')
    if 'completed_trials' in meta and meta['completed_trials'] != len(rows): raise ValueError('completed count mismatch')
    return meta, rows, cases, variants, repeats, complete


def percentile(values, p):
    values = sorted(values); at = (len(values)-1)*p; lo = int(at); hi = min(lo+1,len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(at-lo)


def paired_ci(case_pairs, strata, count, seed):
    """Resample independent cases within strata, preserving all trial repeats."""
    groups = defaultdict(list)
    for key, pair in case_pairs.items(): groups[strata[key]].append(pair)
    rng = random.Random(seed); ratios, diffs = [], []
    for _ in range(count):
        sample = [rng.choice(group) for group in groups.values() for _ in range(len(group))]
        a = statistics.mean(p[0] for p in sample); b = statistics.mean(p[1] for p in sample)
        if b > 0: ratios.append(a/b)
        diffs.append(a-b)
    return {'ratio_ci95': [percentile(ratios,.025),percentile(ratios,.975)] if len(ratios)==count else None,
            'difference_seconds_ci95': [percentile(diffs,.025),percentile(diffs,.975)],
            'bootstrap_replicates':count,'seed':seed,'resampling_unit':'independent case; all repeats and variants kept together; within stratum'}


def route_category(row):
    if row.get('planned_exact_route'): return 'planned_exact_route'
    if row['variant'] == 'sat': return 'standalone_exact_sat'
    if row['fallback']:
        if row['metrics'].get('guided_exception_type'): return 'guided_exception_then_exact'
        if row['guided_candidate_rejected']: return 'rejected_guided_proof_then_exact'
        return 'model_miss_after_cnn_then_exact' if row['cnn_used'] else 'guided_miss_without_cnn_then_exact'
    return 'probe_hit_without_cnn' if row['stage'] == 'direct' else 'guided_' + row['stage']


def summarize(meta, rows, cases, variants, repeats, complete, bootstrap=5000, seed=20261026):
    case_map = {c['id']:c for c in cases}; grouped = defaultdict(list)
    for r in rows: grouped[(r['suite'],r['variant'])].append(r)
    output = {'schema':'auto-diagnostic-analysis-v1','status':'complete' if complete else 'incomplete',
              'independent_cases':len(cases),'planned_trials':len(meta['schedule']),'verified_trials':len(rows),
              'repeat_count':repeats,'variants':variants,'groups':{},'case_summaries':[],'comparisons':[],
              'limitations':[
                  'Exploratory selected cases; not a replacement for the frozen 400/20 benchmark. No precision threshold.',
                  'Conditional guided-hit rate is not candidate precision/recall or ranker accuracy; no ground-truth candidate labels exist.',
                  'Time is uncensored accepted-proof receipt wall; final independent replay is excluded. Missing trials are never assigned a finite cost.',
                  'score_pipeline includes planes and cnn_forward; beams include score and undo. Nested timers must not be added.',
                  'SAT call seconds include whole chunk wall/CNF/queue. requested_per_solver_limit_seconds (legacy budget_seconds) is not a chunk deadline.',
                  'Fusion/FP32 rounding can change rankings and search paths. Equal final boards or forward counts do not prove identical paths.',
                  'Per-case three-repeat means are independent-case summaries; repetitions do not increase independent sample size.',
                  'The declared incomplete-terminal exact route bypasses CNN by design; it is excluded from model-eligible and model-miss denominators. Mechanical final-SAT fallback counts also include this planned route.',
                  'Stage/reason metrics cannot distinguish all silent default scores or hidden internal failures. Typed guided exceptions are only observed where logged.'
              ]}
    slots = defaultdict(Counter)
    for index,s in enumerate(meta['schedule']): slots[(s['suite'],s['variant'])][str(index % len(variants))] += 1
    for (suite,variant), group in grouped.items():
        g = {'trials':len(group),'independent_cases':len({r['case'] for r in group}),
             'mean_trial_seconds':statistics.mean(r['wall_seconds'] for r in group),
             'stages':dict(Counter(r['stage'] for r in group)), 'cnn_trials':sum(r['cnn_used'] for r in group),
             'guided_hits':sum(r['guided_hit'] for r in group),'fallbacks':sum(r['fallback'] for r in group),
             'planned_exact_routes':sum(r.get('planned_exact_route',False) for r in group),
             'unplanned_fallbacks':sum(r['fallback'] and not r.get('planned_exact_route',False) for r in group),
             'model_misses_after_cnn':sum(route_category(r)=='model_miss_after_cnn_then_exact' for r in group),
             'unplanned_fallbacks_after_cnn':sum(r['fallback'] and r['cnn_used'] and not r.get('planned_exact_route',False) for r in group),
             'guided_miss_reasons':dict(Counter(r.get('guided_miss_reason') for r in group if r.get('guided_miss_reason'))),
             'route_categories':dict(Counter(route_category(r) for r in group)),
             'rejected_guided_proofs':sum(r['guided_candidate_rejected'] for r in group),
             'guided_exceptions':dict(Counter(r['metrics']['guided_exception_type'] for r in group if 'guided_exception_type' in r['metrics'])),
             'planned_order_slot_counts':dict(slots[(suite,variant)]),'timer_totals_seconds':{},'sat_chunks_by_stage':{}}
        cnn = [r for r in group if r['cnn_used']]
        g['guided_hit_rate_given_cnn'] = sum(r['guided_hit'] for r in cnn)/len(cnn) if cnn else None
        g['probe_hits'] = sum(r['stage']=='direct' for r in group)
        g['route_costs'] = {}
        for route in sorted({route_category(r) for r in group}):
            subset = [r for r in group if route_category(r) == route]
            g['route_costs'][route] = {'trials':len(subset),'independent_cases':len({r['case'] for r in subset}),
                                      'mean_wall_seconds':statistics.mean(r['wall_seconds'] for r in subset),
                                      'total_wall_seconds':sum(r['wall_seconds'] for r in subset)}
        g['timer_calls'] = {timer:sum(r['metrics'].get(timer,{}).get('calls',0) for r in group)
                            for timer in ['cnn_forward','score_pipeline','planes','undo']}
        eligible = [r for r in group if not r.get('planned_exact_route',False)] if variant != 'sat' else []
        g['cnn_eligible_trials'] = len(eligible) if variant != 'sat' else None
        g['actual_cnn_fraction'] = len(cnn)/len(group) if variant != 'sat' else None
        g['actual_cnn_fraction_given_eligible'] = len(cnn)/len(eligible) if eligible else None
        g['eligible_definition'] = 'Guided variant trial excluding the declared incomplete-terminal exact route. Actual CNN can still be skipped after a probe hit or empty candidates.'
        for timer in ['cnn_forward','score_pipeline','planes','undo']:
            g['timer_totals_seconds'][timer] = sum(r['metrics'].get(timer,{}).get('seconds',0) for r in group)
        g['timer_totals_seconds']['guided_wall'] = sum(r['guided_seconds'] for r in group)
        g['timer_totals_seconds']['final_sat_wall'] = sum(r['metrics'].get('final_sat_seconds',0) for r in group)
        g['timer_totals_seconds']['beams_inclusive'] = sum(b['seconds'] for r in group for b in r['metrics'].get('beams',[]))
        calls=defaultdict(list)
        for r in group:
            for call in r['metrics'].get('sat_calls',[]): calls[str(call.get('stage'))].append(call)
        for stage, cc in calls.items():
            g['sat_chunks_by_stage'][stage]={'calls':len(cc),'found_chunks':sum(c['found'] for c in cc),
                 'candidate_entries':sum(c['candidate_count'] for c in cc),'wall_seconds':sum(c['seconds'] for c in cc),
                 'found_chunk_fraction':sum(c['found'] for c in cc)/len(cc)}
        output['groups'][suite+':'+variant]=g
    by_case=defaultdict(lambda:defaultdict(list))
    for r in rows: by_case[r['case']][r['variant']].append(r)
    for c in cases:
        detail={'case':c['id'],'suite':c['suite'],'stratum':c.get('stratum'),'stones':c['stones'],'variants':{}}
        for variant in variants:
            group=by_case[c['id']][variant]
            detail['variants'][variant]={'trials':len(group),'complete':len(group)==repeats,
                'wall_seconds_by_repeat':{str(r['repeat']):r['wall_seconds'] for r in group},
                'mean_seconds':statistics.mean(r['wall_seconds'] for r in group) if len(group)==repeats else None,
                'stages_by_repeat':{str(r['repeat']):r['stage'] for r in group},
                'cnn_trials':sum(r['cnn_used'] for r in group),'guided_hits':sum(r['guided_hit'] for r in group),
                'fallbacks':sum(r['fallback'] for r in group),
                'planned_exact_routes':sum(r.get('planned_exact_route',False) for r in group),
                'unplanned_fallbacks':sum(r['fallback'] and not r.get('planned_exact_route',False) for r in group)}
        output['case_summaries'].append(detail)
    for suite in sorted({c['suite'] for c in cases}):
        for denominator,numerator in itertools.combinations(variants,2):
            selected=[c for c in cases if c['suite']==suite]
            full=[c for c in selected if all(len(by_case[c['id']][v])==repeats for v in variants)]
            comparison={'suite':suite,'numerator':numerator,'denominator':denominator,
                        'independent_cases':len(full),'selected_cases':len(selected),
                        'complete_all_variant_case_coverage':len(full)/len(selected),'all_selected_cases_complete':len(full)==len(selected)}
            if not full:
                comparison['status']='no complete case clusters';output['comparisons'].append(comparison);continue
            pairs={c['id']:(statistics.mean(r['wall_seconds'] for r in by_case[c['id']][numerator]),
                            statistics.mean(r['wall_seconds'] for r in by_case[c['id']][denominator])) for c in full}
            a=statistics.mean(p[0] for p in pairs.values());b=statistics.mean(p[1] for p in pairs.values())
            comparison.update(numerator_mean_seconds=a,denominator_mean_seconds=b,ratio=a/b if b else None,
                              difference_seconds=a-b,cases_numerator_faster=sum(p[0]<p[1] for p in pairs.values()))
            key=suite+':'+numerator+':'+denominator
            derived_seed=seed+int(hashlib.sha256(key.encode()).hexdigest()[:8],16)
            comparison.update(paired_ci(pairs,{c['id']:str(c.get('stratum',c['stones'])) for c in full},bootstrap,derived_seed))
            comparison['interpretation'] = ('native terminal-undo correction; inference unchanged' if (denominator,numerator)==('baseline','fixed_baseline') else
                'inference optimization; corrected native shared' if (denominator,numerator)==('fixed_baseline','fused_channels_last') else
                'native correction + inference optimization + narrower guided policy/exact routing; composite effect' if numerator=='lightweight' else
                'combined pipeline difference; inspect variant native/inference mapping')
            def native(v):
                kind='baseline' if v in ['sat','baseline'] else 'candidate'
                return meta.get('binaries_sha256',{}).get(kind,meta.get('source_sha256',{}).get('target/release/othello-retro'))
            comparison['native_binary_hashes_match']=native(numerator)==native(denominator)
            comparison['ranking_observation']={
                'same_sat_candidate_sequences_trials':sum(
                    [x.get('candidates_hex') for x in xrow['metrics'].get('sat_calls',[])] == [x.get('candidates_hex') for x in yrow['metrics'].get('sat_calls',[])]
                    for c in full for xrow,yrow in zip(by_case[c['id']][numerator],by_case[c['id']][denominator])),
                'paired_trials':len(full)*repeats,
                'scope':'Only submitted SAT candidate lists; beam-internal full rankings, score health and all pruned candidates are unobserved.'}
            output['comparisons'].append(comparison)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--midgame-bank',type=Path,default=ROOT/'benchmarks/study-midgame-cpu222-unbounded-v1.json')
    p.add_argument('--endgame-bank',type=Path,default=ROOT/'benchmarks/study-endgame-cpu222-unbounded-v1.json')
    p.add_argument('--bootstrap',type=int,default=5000);p.add_argument('--seed',type=int,default=20261026)
    args=p.parse_args()
    if args.bootstrap<1:p.error('bootstrap must be positive')
    try:
        values=load_run(args.input,{'midgame':args.midgame_bank,'endgame':args.endgame_bank})
        result=summarize(*values,args.bootstrap,args.seed)
        result['input_hashes']={n:digest(args.input/n) for n in ['metadata.json','runs.jsonl']}
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'verified_trials':result['verified_trials'],'independent_cases':result['independent_cases']}))
    except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError) as exc:
        p.exit(1,'validation failed: '+str(exc)+'\n')

if __name__=='__main__':main()
