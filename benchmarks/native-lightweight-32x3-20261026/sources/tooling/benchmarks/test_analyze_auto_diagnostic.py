# SPDX-License-Identifier: MIT
"""Small synthetic records test validation/statistics, not solver performance."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('diagnostic_analysis',Path(__file__).with_name('analyze_auto_diagnostic.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        board=list(a.INITIAL);board[19]=board[27]='X'
        self.cases=[{'id':'toy0','seed':1,'board':a.INITIAL,'reference_moves':[],'stones':4,'stratum':'toy'},
                    {'id':'toy1','seed':2,'board':''.join(board),'reference_moves':['d3'],'stones':5,'stratum':'toy'}]
        self.bank=self.root/'bank.json';self.bank.write_text(json.dumps({'splits':{'main':{'cases':self.cases}}}))
        self.meta={'split':'main','status':'complete','banks_sha256':{'midgame':a.digest(self.bank)},
                   'selected_cases':[dict(c,suite='midgame') for c in self.cases], 'schedule':[]}
        self.rows=[];variants=['sat','baseline','fixed_baseline','fused_channels_last']
        for rep in range(1,4):
            for i,c in enumerate(self.cases):
                offset=(i+rep-1)%4
                for v in variants[offset:]+variants[:offset]:
                    s=dict(case=c['id'],suite='midgame',repeat=rep,variant=v);self.meta['schedule'].append(s)
                    cost=(i+1)*{'sat':1,'baseline':2,'fixed_baseline':3,'fused_channels_last':4}[v]
                    metrics={'final_sat_seconds':cost} if v=='sat' else {}
                    self.rows.append(dict(s,stones=c['stones'],status='found',verified=True,
                        wall_seconds=cost,guided_seconds=0 if v=='sat' else cost,
                        stage='final_exact_sat' if v=='sat' else 'direct',cnn_used=False,guided_hit=False,
                        guided_candidate_rejected=False,fallback=False,moves=c['reference_moves'],metrics=metrics))
        self.save()
    def save(self):
        (self.root/'metadata.json').write_text(json.dumps(self.meta))
        (self.root/'runs.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
    def load(self):return a.load_run(self.root,{'midgame':self.bank})
    def test_case_cluster_ratio_and_repeats(self):
        result=a.summarize(*self.load(),bootstrap=100,seed=4)
        item=next(c for c in result['comparisons'] if c['denominator']=='sat' and c['numerator']=='baseline')
        self.assertEqual(item['ratio'],2);self.assertEqual(item['ratio_ci95'],[2,2])
        self.assertEqual(item['independent_cases'],2);self.assertEqual(item['ranking_observation']['paired_trials'],6)
    def test_incomplete_prefix_not_imputed(self):
        self.rows=self.rows[:4];self.meta['status']='interrupted';self.save()
        result=a.summarize(*self.load(),bootstrap=10,seed=1)
        self.assertEqual(result['status'],'incomplete')
        self.assertTrue(all(c['independent_cases']==0 for c in result['comparisons']))
        self.assertTrue(all('ratio' not in c for c in result['comparisons']))
    def test_order_and_false_completion_rejected(self):
        self.rows[0],self.rows[1]=self.rows[1],self.rows[0];self.save()
        with self.assertRaisesRegex(ValueError,'order'):self.load()
        self.rows[0],self.rows[1]=self.rows[1],self.rows[0];self.rows.pop();self.save()
        with self.assertRaisesRegex(ValueError,'false complete'):self.load()
    def test_illegal_proof_and_illegal_pass_rejected(self):
        self.rows[0]['moves']=['pass'];self.save()
        with self.assertRaisesRegex(ValueError,'illegal pass'):self.load()
        with self.assertRaisesRegex(ValueError,'illegal placement'):a.replay(['a1'],a.INITIAL)
    def test_bank_and_timer_integrity(self):
        self.bank.write_text(self.bank.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'bank hash'):self.load()
        self.meta['banks_sha256']['midgame']=a.digest(self.bank)
        self.rows[0]['wall_seconds']=float('nan');self.save()
        with self.assertRaisesRegex(ValueError,'finite'):self.load()
    def test_candidate_and_boolean_flags(self):
        self.rows[1]['cnn_used']=True;self.save()
        with self.assertRaisesRegex(ValueError,'CNN flag'):self.load()
    def test_planned_terminal_exact_is_not_model_failure(self):
        bank=Path(__file__).with_name('study-endgame-cpu222-unbounded-v1.json')
        c=next(c for c in json.loads(bank.read_text())['splits']['main']['cases'] if c['stones']<64)
        self.bank.write_text(json.dumps({'splits':{'main':{'cases':[c]}}}))
        self.meta['selected_cases']=[dict(c,suite='midgame')]
        self.meta['banks_sha256']['midgame']=a.digest(self.bank)
        self.meta['schedule']=[];self.rows=[]
        variants=['sat','baseline','lightweight']
        for rep in range(1,4):
            offset=(rep-1)%3
            for v in variants[offset:]+variants[:offset]:
                item=dict(case=c['id'],suite='midgame',repeat=rep,variant=v)
                self.meta['schedule'].append(item)
                planned=v=='lightweight';cnn=v=='baseline'
                metrics={'final_sat_seconds':1.0}
                if cnn:metrics['cnn_forward']={'calls':1,'seconds':0.1}
                self.rows.append(dict(item,stones=c['stones'],status='found',verified=True,
                    wall_seconds=2.0,guided_seconds=0 if v=='sat' else 0.5,
                    stage='final_exact_sat',cnn_used=cnn,guided_hit=False,guided_candidate_rejected=False,
                    fallback=v!='sat',planned_exact_route=planned,
                    guided_miss_reason='incomplete_terminal_exact_route' if planned else ('exhausted' if cnn else None),
                    moves=c['reference_moves'],metrics=metrics))
        self.save()
        result=a.summarize(*self.load(),bootstrap=10,seed=1)
        light=result['groups']['midgame:lightweight'];baseline=result['groups']['midgame:baseline']
        self.assertEqual(light['planned_exact_routes'],3)
        self.assertEqual(light['cnn_eligible_trials'],0)
        self.assertEqual(light['unplanned_fallbacks'],0)
        self.assertEqual(light['model_misses_after_cnn'],0)
        self.assertIsNone(light['actual_cnn_fraction_given_eligible'])
        self.assertEqual(baseline['model_misses_after_cnn'],3)
        self.rows[-1]['planned_exact_route']=False;self.save()
        # Last rotation ends in baseline, so corrupt whichever planned row exists.
        row=next(r for r in self.rows if r['planned_exact_route'])
        row['cnn_used']=True;row['metrics']['cnn_forward']={'calls':1,'seconds':0.1};self.save()
        with self.assertRaisesRegex(ValueError,'eligibility/work'):self.load()

    def test_planned_route_reason_cannot_be_forged(self):
        self.rows[0]['planned_exact_route']=True
        self.save()
        with self.assertRaisesRegex(ValueError,'reason mismatch'):self.load()

    def test_reference_and_row_forced_passes(self):
        # Genuine stored references include forced passes; independent replay must
        # agree with the already-published full terminal reference record.
        bank=Path(__file__).with_name('study-endgame-cpu222-unbounded-v1.json')
        if not bank.exists():self.skipTest('real reference bank absent')
        cases=json.loads(bank.read_text())['splits']['main']['cases']
        passed=next(c for c in cases if 'pass' in c['reference_moves'])
        self.assertTrue(a.replay(passed['reference_moves'],passed['board'])['terminal'])
        self.assertTrue(a.replay([m for m in passed['reference_moves'] if m!='pass'],passed['board'])['terminal'])

if __name__=='__main__':unittest.main()
