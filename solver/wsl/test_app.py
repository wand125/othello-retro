import concurrent.futures
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('wsl_app',Path(__file__).with_name('app.py'))
app=importlib.util.module_from_spec(spec); spec.loader.exec_module(app)

class DurableStore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); app.DB=Path(self.tmp.name)/'jobs.sqlite3'; app.setup()
        self.req={'id':'test-job-123','board':'---------------------------OX------XO---------------------------','time':60}
    def tearDown(self): self.tmp.cleanup()
    def test_concurrent_retries_count_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:app.reserve(self.req,'owner'),range(4)))
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM usage').fetchone()[0],1)
            self.assertEqual([r[0] for r in db.execute('SELECT count FROM limits')],[1,1])
        with self.assertRaises(ValueError): app.reserve(self.req,'other')
    def test_browser_quota_boundary(self):
        app.reserve(self.req,'owner')
        with app.connect() as db: db.execute("UPDATE limits SET count=99 WHERE owner='owner'")
        app.reserve({**self.req,'id':'test-job-456'},'owner')
        with self.assertRaises(ValueError): app.reserve({**self.req,'id':'test-job-789'},'owner')
        with app.connect() as db: self.assertEqual(db.execute('SELECT count(*) FROM usage').fetchone()[0],2)
    def test_global_quota_boundary(self):
        app.reserve(self.req,'owner')
        with app.connect() as db: db.execute("UPDATE limits SET count=1000 WHERE owner='*'")
        with self.assertRaises(ValueError): app.reserve({**self.req,'id':'test-job-456'},'other')
    def test_restart_finishes_interrupted_job_and_retains_usage(self):
        app.reserve(self.req,'owner')
        with app.connect() as db: db.execute("UPDATE jobs SET state='running',started_at=?",(app.now(),))
        app.setup()
        with app.connect() as db:
            row=db.execute('SELECT * FROM jobs').fetchone()
            self.assertEqual(row['state'],'failed')
            usage=json.loads(db.execute('SELECT body FROM usage').fetchone()[0])
            self.assertEqual(usage['status'],'error'); self.assertNotIn('expires_at',usage)
    def test_only_independently_valid_record_is_public(self):
        app.reserve(self.req,'owner')
        with app.connect() as db:
            row=db.execute('SELECT * FROM jobs').fetchone()
            app.finalize(db,row,{'status':'found','moves':['a1'],'time':1})
            self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],0)
            self.assertEqual(json.loads(db.execute('SELECT result FROM jobs').fetchone()[0])['status'],'error')
            self.assertEqual(db.execute('SELECT state FROM jobs').fetchone()[0],'failed')
            app.finalize(db,row,{'status':'found','moves':[],'time':.001,'method':'sat'})
            record=json.loads(db.execute('SELECT body FROM records').fetchone()[0])
            public=app.records.public(record)
            self.assertFalse({'owner','browser_id','request','sort_key'} & public.keys())
            self.assertEqual(public['board'],self.req['board'])
            self.assertNotIn('expires_at',record)

    def test_illegal_color_switch_cannot_be_exposed_as_found(self):
        board=list(self.req['board'])
        for square in [19,27,36,37]: board[square]='X'
        request={**self.req,'board':''.join(board)}
        app.reserve(request,'owner')
        with app.connect() as db:
            row=db.execute('SELECT * FROM jobs').fetchone()
            app.finalize(db,row,{'status':'found','moves':['d3','f5'],'time':.1})
            result=json.loads(db.execute('SELECT result FROM jobs').fetchone()[0])
            usage=json.loads(db.execute('SELECT body FROM usage').fetchone()[0])
            self.assertEqual(result['status'],'error')
            self.assertEqual(usage['status'],'error')
            self.assertEqual(db.execute('SELECT state FROM jobs').fetchone()[0],'failed')
            self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],0)

    def test_valid_record_stays_found_at_api_boundary(self):
        board=list(self.req['board'])
        for square in [19,27]: board[square]='X'
        for square in [18,27]: board[square]='O'
        app.reserve({**self.req,'board':''.join(board)},'owner')
        with app.connect() as db:
            row=db.execute('SELECT * FROM jobs').fetchone()
            app.finalize(db,row,{'status':'found','moves':['d3','c3'],'time':.1})
            result=json.loads(db.execute('SELECT result FROM jobs').fetchone()[0])
            self.assertEqual(result['status'],'found')
            self.assertEqual(result['moves'],['d3','c3'])
            self.assertEqual(db.execute('SELECT count(*) FROM records').fetchone()[0],1)

if __name__=='__main__': unittest.main()
