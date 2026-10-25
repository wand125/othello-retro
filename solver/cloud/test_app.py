"""Contract tests for validation, queued UI, cancellation and retry ownership."""
import datetime as dt
import json
import sys
import threading
import unittest
import types
import copy
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import app

class Document:
    def __init__(self):
        self.data = None

    def get(self, **kwargs):
        return types.SimpleNamespace(exists=self.data is not None, to_dict=lambda: copy.deepcopy(self.data))

    def update(self, fields):
        self.data.update(copy.deepcopy(fields))


class Database:
    def __init__(self):
        self.docs = {}

    def collection(self, name):
        from test_records import Query
        return Query(self, name)

    def transaction(self):
        return self

    def set(self, doc, data, merge=False):
        doc.data = {**(doc.data or {}), **copy.deepcopy(data)} if merge else copy.deepcopy(data)

    create = set

    def update(self, doc, data):
        doc.data.update(copy.deepcopy(data))


class StorageContractTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        firestore = types.SimpleNamespace(transactional=lambda f: f)
        google = types.ModuleType("google")
        cloud = types.ModuleType("google.cloud")
        cloud.firestore = firestore
        google.cloud = cloud
        self.patches = [patch.object(app, "database", return_value=self.db),
                        patch.dict(sys.modules, {"google": google, "google.cloud": cloud, "google.cloud.firestore": firestore})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def request(self, job="valid_id"):
        return {"id": job, "board": "X" * 64, "time": 10}

    def test_repeated_post_does_not_consume_quota_twice(self):
        first = app.reserve("solve", self.request(), "owner-a")
        second = app.reserve("solve", self.request(), "owner-a")
        self.assertEqual(first, second)
        counts = [v.data["count"] for (collection, _), v in self.db.docs.items() if collection == "othello_retro_limits"]
        self.assertEqual(counts, [1, 1])
        logs = [d for (collection, _), d in self.db.docs.items() if collection == "othello_retro_usage"]
        self.assertEqual(len(logs), 1)
        self.assertNotIn("expires_at", logs[0].data)

    def test_final_result_and_cancel_remain_in_usage_history(self):
        board = app.records.static_records()[0]["board"]
        moves = app.records.static_records()[0]["moves"]
        data = {**self.request(), "board": board}
        app.reserve("solve", data, "owner-a")
        app.claim("valid_id", "attempt-a")
        app.update_attempt("valid_id", "attempt-a", {"state": "done", "result": {"status": "found", "moves": moves, "time": .5, "method": "sat"}})
        entry = app.usage_ref("valid_id").data
        self.assertEqual((entry["browser_id"], entry["status"], entry["elapsed_seconds"], entry["moves"]), ("owner-a", "found", .5, sum(m != "pass" for m in moves)))
        app.reserve("solve", self.request("cancel_id"), "owner-a")
        self.assertTrue(app.cancel_owned("cancel_id", "owner-a"))
        self.assertEqual(app.usage_ref("cancel_id").data["status"], "cancelled")
        self.assertFalse(app.cancel_owned("valid_id", "owner-b"))

    def test_verified_success_is_permanent_and_non_success_is_not_published(self):
        import records
        example = records.static_records()[0]
        request = {"id":"public_success", "board":example["board"], "time":60}
        app.reserve("solve", request, "private-browser")
        app.claim(request["id"], "attempt-success")
        fields = {"state":"done", "finished_at":app.now(),
                  "result":{"status":"found", "moves":example["moves"], "time":1.25, "method":"sat"}}
        self.assertTrue(app.update_attempt(request["id"], "attempt-success", fields))
        saved = records.get_record(self.db, "record-public_success")
        self.assertEqual(saved["board"], example["board"])
        self.assertEqual(saved["moves"], example["moves"])
        self.assertEqual(saved["elapsed_seconds"], 1.25)
        self.assertEqual(app.ref(request["id"]).data["result"]["record_id"], saved["id"])
        self.assertNotIn("private-browser", json.dumps(saved))
        stored = records.record_ref(self.db, saved["id"]).data
        self.assertNotIn("expires_at", stored)
        self.assertFalse(app.update_attempt(request["id"], "attempt-success", fields))
        for status in ("unknown", "cancelled"):
            ident = "public_" + status
            app.reserve("solve", {**request, "id":ident}, "private-browser")
            app.claim(ident, "attempt-other")
            app.update_attempt(ident, "attempt-other", {"state":"done" if status == "unknown" else "cancelled",
                "result":{"status":status, "moves":example["moves"], "time":1}})
            self.assertIsNone(records.get_record(self.db, "record-" + ident))
        published = [doc for (name, _), doc in self.db.docs.items() if name == records.COLLECTION and doc.data]
        self.assertEqual(len(published), 1)

    def test_illegal_implicit_pass_never_returns_found(self):
        # d3 followed by f5 for Black skips a White turn despite three legal White moves.
        board = "-------------------X-------XX------XXX--------------------------"
        app.reserve("solve", {**self.request(), "board": board}, "owner-a")
        app.claim("valid_id", "attempt-a")
        app.update_attempt("valid_id", "attempt-a", {"state": "done", "result": {"status": "found", "moves": ["d3", "f5"], "time": .1}})
        self.assertEqual(app.ref("valid_id").data["state"], "failed")
        self.assertEqual(app.ref("valid_id").data["result"]["status"], "error")
        self.assertEqual(app.usage_ref("valid_id").data["status"], "error")
        self.assertIsNone(app.records.record_ref(self.db, "record-valid_id").get().to_dict())

    def test_global_limit_rejects_without_new_usage_entry(self):
        with patch.object(app, "GLOBAL_DAILY", 2):
            app.reserve("solve", self.request("global_a"), "owner-a")
            app.reserve("solve", self.request("global_b"), "owner-b")
            with self.assertRaises(ValueError):
                app.reserve("solve", self.request("global_c"), "owner-c")
        self.assertNotIn(("othello_retro_usage", "global_c"), self.db.docs)

    def test_another_session_cannot_reuse_job_id(self):
        app.reserve("solve", self.request(), "owner-a")
        with self.assertRaises(ValueError):
            app.reserve("solve", self.request(), "owner-b")

    def test_session_quota_is_enforced_before_creating_extra_job(self):
        for i in range(app.SESSION_DAILY):
            app.reserve("solve", self.request(f"valid_id_{i}"), "owner-a")
        with self.assertRaises(ValueError):
            app.reserve("solve", self.request("valid_id_over_limit"), "owner-a")
        self.assertIsNone(app.ref("valid_id_over_limit").data)

    def test_active_lease_blocks_duplicate_and_stale_attempt_cannot_finish(self):
        app.reserve("solve", self.request(), "owner-a")
        app.claim("valid_id", "attempt-a")
        with self.assertRaises(RuntimeError):
            app.claim("valid_id", "attempt-b")
        app.ref("valid_id").data["lease_until"] = app.now() - dt.timedelta(seconds=1)
        app.claim("valid_id", "attempt-b")
        self.assertFalse(app.update_attempt("valid_id", "attempt-a", {"state": "done"}))
        self.assertTrue(app.update_attempt("valid_id", "attempt-b", {"state": "done"}))

    def test_cancelled_queued_job_never_gets_executed(self):
        app.reserve("solve", self.request(), "owner-a")
        app.ref("valid_id").data["cancel"] = True
        self.assertIsNone(app.claim("valid_id", "attempt-a"))
        self.assertEqual(app.ref("valid_id").data["result"]["status"], "cancelled")


class ValidationTests(unittest.TestCase):
    def test_public_limits_are_applied_on_server(self):
        req = {"id": "valid_id", "board": "X" * 64, "time": 3600, "k": 99, "solutions": 50}
        result = app.validate("fix", req)
        self.assertEqual((result["time"], result["k"], result["solutions"]), (300, 3, 5))

    def test_invalid_requests_cannot_reach_subprocess(self):
        cases = [({}, "solve"), ({"id": "../escape", "board": "X" * 64}, "solve"),
                 ({"id": "valid_id", "board": "X" * 64, "time": "infinity"}, "solve"),
                 ({"id": "valid_id", "board": "X" * 64, "protect": [-1]}, "fix"),
                 ({"id": "valid_id", "board": "X" * 64, "moves": ["$(id)"]}, "optimize")]
        for data, kind in cases:
            with self.subTest(kind=kind, data=data), self.assertRaises(ValueError):
                app.validate(kind, data)


class ExecutionTests(unittest.TestCase):
    def execute_case(self, payload, cancel=False, solver_error=False):
        job = {"request": {"id": "valid_id", "board": "X" * 64, "time": 10}, "kind": "solve"}
        updates = []
        doc = MagicMock()
        doc.get.return_value.to_dict.return_value = {"cancel": cancel}
        def run(runner, req):
            if solver_error:
                raise RuntimeError("crash")
            runner.finish_job(req["id"], payload)
        with patch.object(app, "claim", return_value=job), patch.object(app, "ref", return_value=doc), \
             patch.object(app.Runner, "solve", run), patch.object(app, "stop_process") as stop, \
             patch.object(app, "update_attempt", side_effect=lambda *args: updates.append(args) or True):
            app.execute("valid_id")
        return updates[-1][2], stop

    def test_cancellation_wins_over_late_found_result(self):
        update, _ = self.execute_case({"status": "found", "moves": ["f5"]}, cancel=True)
        self.assertEqual(update["state"], "cancelled")
        self.assertEqual(update["result"], {"status": "cancelled"})

    def test_crashed_solver_is_stopped_and_records_error(self):
        update, stop = self.execute_case(None, solver_error=True)
        self.assertEqual(update["result"]["status"], "error")
        stop.assert_called_once_with("valid_id")

    def test_duplicate_completed_delivery_does_not_start_solver(self):
        with patch.object(app, "claim", return_value=None), patch.object(app.Runner, "solve") as solve:
            app.execute("valid_id")
            solve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
