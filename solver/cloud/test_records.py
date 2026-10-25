"""Public record contract: replay, privacy, permanent storage and stable pagination."""
import copy
import datetime as dt
import json
import unittest
from pathlib import Path
from types import SimpleNamespace

import records


class Query:
    def __init__(self, db, name, after=None, maximum=None):
        self.db, self.name, self.after, self.maximum = db, name, after, maximum
    def document(self, key):
        return self.db.docs.setdefault((self.name, key), Document())
    def order_by(self, field, direction=None):
        assert (field, direction) == ('sort_key', 'DESCENDING')
        return self
    def where(self, field, operator, value):
        assert (field, operator) == ('sort_key', '<')
        return Query(self.db, self.name, value, self.maximum)
    def limit(self, maximum): return Query(self.db, self.name, self.after, maximum)
    def stream(self):
        rows = [doc for (name, _), doc in self.db.docs.items() if name == self.name and doc.data and (not self.after or doc.data['sort_key'] < self.after)]
        return [doc.get() for doc in sorted(rows, key=lambda doc:doc.data['sort_key'], reverse=True)[:self.maximum]]


class Document:
    def __init__(self): self.data = None
    def get(self, **kwargs): return SimpleNamespace(exists=self.data is not None, to_dict=lambda:copy.deepcopy(self.data))
    def set(self, value): self.data = copy.deepcopy(value)


class Database:
    def __init__(self): self.docs = {}
    def collection(self, name): return Query(self, name)


class RecordsTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.example = records.static_records()[0]
        self.date = dt.datetime(2026, 10, 25, 1, 2, 3, tzinfo=dt.timezone.utc)
        self.item = {'kind':'solve', 'owner':'never-publish', 'created_at':self.date,
                     'request':{'board':self.example['board'], 'time':60, 'id':'sample'}}
        self.result = {'status':'found','moves':self.example['moves'],'time':1.25,'method':'sat'}

    def make(self, ident='sample'):
        return records.make_record(ident, self.item, self.result, self.date)

    def test_success_is_replayed_and_safe(self):
        record = self.make()
        self.assertEqual(record['id'], 'record-sample')
        self.assertEqual(record['elapsed_seconds'], 1.25)
        self.assertEqual(record['finished_at'], '2026-10-25T01:02:03.000000Z')
        self.assertEqual(record['requested_seconds'], 60)
        self.assertNotIn('owner', record)
        self.assertNotIn('request', record)
        self.assertNotIn('expires_at', record)
        self.assertEqual(self.make(), record, 'same job/result must have the same document')
        self.result['moves'] = ['a1']
        self.assertIsNone(self.make())

    def test_non_success_and_inconsistent_board_not_published(self):
        self.result['status'] = 'unknown'; self.assertIsNone(self.make())
        self.result['status'] = 'found'; self.item['request']['board'] = 'X'*64
        self.assertIsNone(self.make())

    def test_dates_numeric_timing_and_whitelist(self):
        self.result['time'] = float('nan')
        record = self.make()
        self.assertIsNone(record['elapsed_seconds'])
        record.update(owner='private', browser_id='private', request={'private':'value'})
        self.assertNotIn('private', json.dumps(records.public(record)))
        self.assertNotIn('sort_key', records.public(record))

    def test_static_urls_and_timing_remain(self):
        rows = records.static_records()
        self.assertEqual(len(rows), 7)
        for row in rows:
            records.verify(row['moves'], row['board'])
            self.assertEqual(records.get_record(self.db, row['id'])['moves'], row['moves'])
        video = next(row for row in rows if row['source'] == 'saved-video-record')
        self.assertIsNone(video['elapsed_seconds'])
        self.assertEqual([row['elapsed_seconds'] for row in rows], [.046, 6.208, 28.116, 55.237, 31.46, 22.871, None])

    def test_cursor_pagination_no_duplicates_or_omissions(self):
        for index in range(25):
            record = self.make(f'sample-{index:02}')
            records.record_ref(self.db, record['id']).set(record)
        page, all_ids = records.list_records(self.db), []
        self.assertEqual(len(page['records']), 20)
        while True:
            all_ids.extend(row['id'] for row in page['records'])
            if not page['next_cursor']: break
            page = records.list_records(self.db, page['next_cursor'])
        self.assertEqual(len(all_ids), 32)
        self.assertEqual(len(set(all_ids)), 32)
        self.assertTrue(all(ident.startswith('record-') for ident in all_ids[:25]))
        for bad in ('!', 'YQ', 'a'*301):
            with self.assertRaises(ValueError): records.list_records(self.db, bad)
        self.assertIsNone(records.get_record(self.db, '../private'))

    def test_forced_pass_and_early_terminal(self):
        for example in records.static_records():
            if 'pass' not in example['moves']: continue
            normalized, terminal = records.verify([m for m in example['moves'] if m != 'pass'], example['board'])
            self.assertIn('pass', normalized)
            self.assertEqual(terminal, example['terminal'])


if __name__ == '__main__': unittest.main()
