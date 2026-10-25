# SPDX-License-Identifier: MIT
"""Public bundle validation and privacy tests using synthetic legal records."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import export as public_export
from analyze import analyze, load_run
from test_analyze import save_run, toy_bank, toy_run


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bankpath, self.bank = toy_bank(self.root)
        self.source, self.meta, self.rows = toy_run(self.root, self.bankpath, self.bank)
        self.output = self.root / "public"

    def export(self):
        return public_export.export(self.source, self.bankpath, self.output, split="main")

    def test_complete_dataset_is_verified_and_summary_is_recomputed(self):
        self.meta["fixture"] = False  # Exercise the contract; still only a unit-test fixture.
        save_run(self.source, self.meta, self.rows)
        (self.source / "summary.json").write_text('{"invented": "untrusted input summary"}')
        manifest = self.export()
        self.assertEqual(manifest["status"], "complete")
        self.assertTrue(manifest["completed_formal_dataset"])
        self.assertFalse(manifest["cross_environment_comparison_ready"])
        for name in ["metadata.json", "runs.jsonl", "verification.json", "manifest.json", "summary.json"]:
            self.assertTrue((self.output / name).is_file(), name)
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertNotIn("invented", summary)
        self.assertEqual(summary["common_complete_cases"], 5)
        self.assertTrue(summary["all_planned_completed"])
        self.assertEqual(len((self.output / "runs.jsonl").read_text().splitlines()), 30)
        self.assertEqual(summary["metadata"], json.loads((self.output / "metadata.json").read_text()))
        for name, expected in manifest["files_sha256"].items():
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), expected)

    def test_fixture_complete_is_never_formal_or_performance_evidence(self):
        manifest = self.export()
        self.assertEqual(manifest["status"], "fixture-complete")
        self.assertFalse(manifest["completed_formal_dataset"])
        self.assertFalse(manifest["cross_environment_comparison_ready"])
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertFalse(summary["performance_claims_allowed"])
        # An exported fixture remains complete when reloaded, without becoming
        # reconstruction-performance evidence or an unfinished result.
        self.assertTrue(load_run(self.output, self.bankpath)["complete"])
        rechecked = analyze({"published": self.output}, self.bankpath, replicates=100)
        self.assertTrue(rechecked["all_planned_completed"])
        self.assertFalse(rechecked["performance_claims_allowed"])

    def test_row_fixture_marker_also_blocks_summary_claims(self):
        self.meta["fixture"] = False
        self.rows[0]["fixture"] = True
        save_run(self.source, self.meta, self.rows)
        manifest = self.export()
        self.assertEqual(manifest["status"], "fixture-complete")
        self.assertFalse(manifest["completed_formal_dataset"])
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertFalse(summary["performance_claims_allowed"])
        self.assertTrue(summary["sources"]["program"]["fixture"])

    def test_incomplete_export_has_no_summary_or_completion_claim(self):
        self.meta.update(status="running", completed_trials=29)
        save_run(self.source, self.meta, self.rows[:-1])
        manifest = self.export()
        self.assertEqual(manifest["status"], "incomplete")
        self.assertFalse(manifest["completed_formal_dataset"])
        self.assertFalse(manifest["cross_environment_comparison_ready"])
        self.assertFalse((self.output / "summary.json").exists())
        self.assertEqual(len((self.output / "runs.jsonl").read_text().splitlines()), 29)

    def test_live_reexport_removes_obsolete_complete_summary(self):
        self.export()
        self.assertTrue((self.output / "summary.json").exists())
        self.meta.update(status="running", completed_trials=29)
        save_run(self.source, self.meta, self.rows[:-1])
        self.export()
        self.assertFalse((self.output / "summary.json").exists())

    def test_existing_unrelated_private_output_cannot_be_published_by_accident(self):
        self.output.mkdir()
        private = self.output / "credentials.txt"
        private.write_text("SYNTHETIC_PRIVATE_OLD_OUTPUT")
        try:
            self.export()
        except ValueError:
            # Rejecting an unrecognized populated destination is safe.
            return
        self.assertFalse(private.exists(), "a successful export must not retain untracked private files")

    def test_false_completion_and_illegal_moves_do_not_produce_summary(self):
        save_run(self.source, self.meta, self.rows[:-1])
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.output / "summary.json").exists())
        self.rows[2]["moves"] = ["a1"]
        save_run(self.source, self.meta, self.rows)
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse((self.output / "summary.json").exists())

    def test_mismatched_bank_is_rejected(self):
        self.meta["bank_sha256"] = "f" * 64
        save_run(self.source, self.meta, self.rows)
        with self.assertRaises(ValueError):
            self.export()

    def test_export_excludes_private_files_absolute_paths_and_secret_keys(self):
        sentinel = "SYNTHETIC_SECRET_DO_NOT_EXPORT"
        absolute = "/Users/private-test-person/private/project"
        self.meta.update({"gate_directory": absolute, "api_key": sentinel,
                          "private_runtime": {"token": sentinel},
                          "host_descriptor": {"home": absolute, "hostname": "private-host", "secret": sentinel},
                          "programs": {"sat": {"label": "SAT", "command": [absolute + "/solver"],
                                               "api_key": sentinel}}})
        self.rows[0].update({"private_notes": sentinel, "working_directory": absolute})
        save_run(self.source, self.meta, self.rows)
        for name in ["private-runtime", ".private-logs"]:
            (self.source / name).mkdir()
            (self.source / name / "credentials.txt").write_text(sentinel)
        (self.source / "unrelated-secret.log").write_text(sentinel)
        self.export()
        self.assertFalse((self.output / "private-runtime").exists())
        self.assertFalse((self.output / ".private-logs").exists())
        self.assertFalse((self.output / "unrelated-secret.log").exists())
        for path in self.output.rglob("*"):
            if path.is_file():
                text = path.read_text()
                self.assertNotIn(sentinel, text, path.name)
                self.assertNotIn(absolute, text, path.name)
                self.assertNotIn('"api_key"', text, path.name)

    def test_unusual_absolute_root_paths_are_also_excluded(self):
        self.meta["host_descriptor"] = {"filesystem": "/data/private-unit-test/work",
                                        "other_location": "/etc/private-unit-test/config",
                                        "windows": "C:\\private-unit-test\\work",
                                        "network": "\\\\private-unit-test-server\\private-share"}
        self.meta["documentation"] = "https://example.test/public-document"
        save_run(self.source, self.meta, self.rows)
        self.export()
        for path in self.output.rglob("*.json"):
            text = path.read_text()
            self.assertNotIn("private-unit-test", text)
        meta = json.loads((self.output / "metadata.json").read_text())
        self.assertEqual(meta["documentation"], "https://example.test/public-document")

    def test_auxiliary_records_are_sanitized_and_stale_copies_are_removed(self):
        for name in ["preparation.jsonl", "resource-pauses.jsonl"]:
            (self.source / name).write_text(json.dumps({"elapsed_seconds": 2, "env": {"secret": "SYNTHETIC_AUX_SECRET"},
                                                       "location": "/data/private-aux-test"}) + "\n")
        manifest = self.export()
        for name in ["preparation.jsonl", "resource-pauses.jsonl"]:
            self.assertIn(name, manifest["files_sha256"])
            text = (self.output / name).read_text()
            self.assertNotIn("SYNTHETIC_AUX_SECRET", text)
            self.assertNotIn("/data/private-aux-test", text)
            self.assertEqual(json.loads(text)["elapsed_seconds"], 2)
            (self.source / name).unlink()
        self.export()
        for name in ["preparation.jsonl", "resource-pauses.jsonl"]:
            self.assertFalse((self.output / name).exists())


if __name__ == "__main__":
    unittest.main()
