# SPDX-License-Identifier: MIT
"""Independent validation CLI tests; all timings and samples are synthetic."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze
import check
import export as public_export
from test_analyze import save_run, toy_bank, toy_run, write_json


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bankpath, self.bank = toy_bank(self.root)
        for index, case in enumerate(self.bank["splits"]["main"]["cases"]):
            case["seed"] = 1000 + index
            case["reference_sha256"] = analyze.digest({"board": case["board"], "moves": case["reference_moves"]})
        self.save_bank()
        self.source, self.meta, self.rows = toy_run(self.root, self.bankpath, self.bank)
        self.public = self.root / "public"

    def save_bank(self):
        self.bank["protocol_sha256"] = analyze.digest(self.bank["protocol"])
        for section in self.bank["splits"].values():
            for key in ("cases", "schedule"):
                section[key + "_sha256"] = analyze.digest(section[key])
        write_json(self.bankpath, self.bank)

    def bundle(self):
        return public_export.export(self.source, self.bankpath, self.public)

    def rehash_public(self, name):
        manifest = check.read_json(self.public / "manifest.json")
        manifest["files_sha256"][name] = analyze.sha(self.public / name)
        write_json(self.public / "manifest.json", manifest)

    def cli(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = check.main(list(map(str, argv)))
        return code, json.loads(output.getvalue()), output.getvalue()

    def test_bank_and_cli_report_without_disclosing_input_paths(self):
        report = check.check_bank(self.bankpath)
        self.assertEqual(report["independent_seed_count"], 5)
        self.assertEqual(report["splits"]["main"]["trials"], 30)
        self.assertEqual(report["splits"]["main"]["first_method_balance"], "not_declared")
        code, output, raw = self.cli("bank", "--bank", self.bankpath)
        self.assertEqual(code, 0)
        self.assertEqual(output["status"], "passed")
        self.assertNotIn(str(self.root), raw)

    def test_missing_reference_hash_wrong_stones_terminal_and_seed_are_rejected(self):
        original = copy.deepcopy(self.bank)
        for key, value in [("reference_sha256", "0" * 64), ("stones", 60),
                           ("terminal", True), ("seed", None)]:
            with self.subTest(key=key):
                self.bank = copy.deepcopy(original)
                self.bank["splits"]["main"]["cases"][0][key] = value
                self.save_bank()
                with self.assertRaises(ValueError):
                    check.check_bank(self.bankpath)

    def test_all_splits_are_checked(self):
        section = copy.deepcopy(self.bank["splits"]["main"])
        case = section["cases"][0]
        case.update(id="pilot-only", seed=9000, reference_sha256="0" * 64)
        section["cases"] = [case]
        section["schedule"] = [{"case": case["id"], "repeat": 1, "method": m} for m in ("sat", "auto")]
        self.bank["protocol"]["pilot_repeats"] = 1
        self.bank["splits"]["pilot"] = section
        self.save_bank()
        with self.assertRaisesRegex(ValueError, "reference_hash_mismatch"):
            check.check_bank(self.bankpath)

    def test_reused_seed_and_missing_schedule_cell_are_rejected_even_after_rehash(self):
        original = copy.deepcopy(self.bank)
        cases = self.bank["splits"]["main"]["cases"]
        cases[1]["seed"] = cases[0]["seed"]
        self.save_bank()
        with self.assertRaisesRegex(ValueError, "reused_game_seed"):
            check.check_bank(self.bankpath)
        self.bank = original
        self.bank["splits"]["main"]["schedule"].pop()
        self.save_bank()
        with self.assertRaisesRegex(ValueError, "complete_cartesian_product"):
            check.check_bank(self.bankpath)

    def test_identical_boards_from_distinct_seeds_are_reported_not_rejected(self):
        section = self.bank["splits"]["main"]
        case = copy.deepcopy(section["cases"][0])
        case.update(id="other-independent-seed", seed=2000)
        section["cases"].append(case)
        section["schedule"] += [{"case": case["id"], "repeat": r, "method": m}
                                for r in (1, 2, 3) for m in ("sat", "auto")]
        self.save_bank()
        report = check.check_bank(self.bankpath)
        self.assertEqual(report["duplicate_board_groups"], 1)

    def test_declared_balanced_first_methods_and_pair_order_are_verified(self):
        section = self.bank["splits"]["main"]
        schedule = []
        for repeat in (1, 2, 3):
            for index, case in enumerate(section["cases"]):
                methods = ("sat", "auto") if index % 2 else ("auto", "sat")
                schedule += [{"case": case["id"], "repeat": repeat, "method": method, "first_method": methods[0]}
                             for method in methods]
        section["schedule"] = schedule
        self.save_bank()
        self.assertEqual(check.check_bank(self.bankpath)["splits"]["main"]["first_method_balance"], "passed")
        schedule[0]["first_method"] = schedule[1]["method"]
        self.save_bank()
        with self.assertRaisesRegex(ValueError, "first_method_order_mismatch"):
            check.check_bank(self.bankpath)

    def test_cross_bank_overlap_is_only_fatal_with_explicit_policy(self):
        other = self.root / "other-bank.json"
        write_json(other, self.bank)
        report = check.check_banks([self.bankpath, other])
        self.assertEqual(report["cross_bank_overlap"][0]["overlapping_distinct_values"]["seed"], 5)
        with self.assertRaisesRegex(ValueError, "explicit_cross_bank"):
            check.check_banks([self.bankpath, other], ("seed",))

    def test_record_array_and_result_object_require_legal_full_target_match(self):
        moves = self.root / "moves.json"
        for value in (["d3"], {"status": "found", "moves": ["d3"]},
                      {"event": "result", "payload": {"status": "found", "moves": ["d3"]}}):
            write_json(moves, value)
            self.assertTrue(check.check_record(self.bankpath, "d3", moves)["target_matches"])
        write_json(moves, ["a1"])
        with self.assertRaises(ValueError):
            check.check_record(self.bankpath, "d3", moves)

    def test_run_distinguishes_complete_incomplete_and_fixture(self):
        self.assertEqual(check.check_run(self.source, self.bankpath)["state"], "fixture-complete")
        self.meta["fixture"] = False
        save_run(self.source, self.meta, self.rows)
        self.assertTrue(check.check_run(self.source, self.bankpath)["completed_formal_dataset"])
        self.meta["status"] = "running"
        save_run(self.source, self.meta, self.rows[:-1])
        result = check.check_run(self.source, self.bankpath)
        self.assertEqual(result["state"], "incomplete")
        self.assertFalse(result["completed_formal_dataset"])

    def test_published_fixture_and_generic_summary_are_independently_checked(self):
        self.bundle()
        result = check.check_published(self.public, self.bankpath)
        self.assertEqual(result["state"], "fixture-complete")
        self.assertEqual(result["summary"]["ci"], "stdlib_paired_bootstrap_recomputed")
        summary = check.read_json(self.public / "summary.json")
        summary["variants"]["program/sat"]["mean_seconds"] *= 2
        write_json(self.public / "summary.json", summary)
        self.rehash_public("summary.json")
        with self.assertRaisesRegex(ValueError, "summary_arithmetic_mismatch"):
            check.check_published(self.public, self.bankpath)

    def test_manifest_hash_and_record_replay_both_detect_tampering(self):
        self.bundle()
        rows = copy.deepcopy(self.rows)
        rows[2]["moves"] = ["a1"]
        (self.public / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        with self.assertRaisesRegex(ValueError, "manifest_file_hash_mismatch"):
            check.check_published(self.public, self.bankpath)
        self.rehash_public("runs.jsonl")
        with self.assertRaises(ValueError):
            check.check_published(self.public, self.bankpath)

    def test_rehashed_summary_cannot_falsely_claim_precision(self):
        self.bundle()
        summary = check.read_json(self.public / "summary.json")
        summary["comparisons"][0]["precision_established"] = True
        write_json(self.public / "summary.json", summary)
        self.rehash_public("summary.json")
        with self.assertRaisesRegex(ValueError, "summary_precision_or_profile_claim"):
            check.check_published(self.public, self.bankpath)

    def test_duplicate_json_fields_are_not_silently_accepted(self):
        first = json.dumps(self.rows[0])[:-1] + ',"verified":true}\n'
        (self.source / "runs.jsonl").write_text(first)
        self.meta["status"] = "running"
        write_json(self.source / "metadata.json", self.meta)
        with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            check.check_run(self.source, self.bankpath)

    def test_manifest_traversal_absolute_members_symlinks_and_private_logs_are_rejected(self):
        self.bundle()
        manifest = check.read_json(self.public / "manifest.json")
        for name in ("../escape.json", "/tmp/escape.json", "C:\\escape.json"):
            with self.subTest(name=name):
                value = copy.deepcopy(manifest)
                value["files_sha256"][name] = "0" * 64
                write_json(self.public / "manifest.json", value)
                with self.assertRaisesRegex(ValueError, "unsafe_manifest_member"):
                    check.check_published(self.public, self.bankpath)
        write_json(self.public / "manifest.json", manifest)
        metadata = self.public / "metadata.json"
        content = metadata.read_bytes()
        metadata.unlink()
        metadata.symlink_to(self.source / "metadata.json")
        with self.assertRaisesRegex(ValueError, "unsafe_or_missing_public_file"):
            check.check_published(self.public, self.bankpath)
        metadata.unlink()
        metadata.write_bytes(content)
        (self.public / ".private-logs").mkdir()
        with self.assertRaisesRegex(ValueError, "untracked_public_file"):
            check.check_published(self.public, self.bankpath)

    def test_rehashed_secrets_and_absolute_paths_are_still_rejected(self):
        self.bundle()
        original = check.read_json(self.public / "metadata.json")
        for field in ({"api_key": "SYNTHETIC_SECRET"}, {"location": "/data/private-test-location"}):
            metadata = {**original, **field}
            write_json(self.public / "metadata.json", metadata)
            self.rehash_public("metadata.json")
            with self.assertRaises(check.CheckError):
                check.check_published(self.public, self.bankpath)

    def test_incomplete_public_bundle_cannot_contain_a_summary(self):
        self.meta["status"] = "running"
        save_run(self.source, self.meta, self.rows[:-1])
        self.bundle()
        self.assertEqual(check.check_published(self.public, self.bankpath)["state"], "incomplete")
        write_json(self.public / "summary.json", {})
        self.rehash_public("summary.json")
        with self.assertRaisesRegex(ValueError, "incomplete_bundle_contains_summary"):
            check.check_published(self.public, self.bankpath)

    def test_cli_all_and_failures_are_structured_and_do_not_disclose_private_paths(self):
        self.bundle()
        code, result, raw = self.cli("all", "--bank", self.bankpath, "--run", "local=" + str(self.source),
                                     "--published", "public=" + str(self.public))
        self.assertEqual(code, 0)
        self.assertEqual(result["runs"]["local"]["status"], "passed")
        self.assertNotIn(str(self.root), raw)
        private = self.root / "SYNTHETIC_PRIVATE_INPUT" / "missing.json"
        code, result, raw = self.cli("bank", "--bank", private)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("SYNTHETIC_PRIVATE_INPUT", raw)


if __name__ == "__main__":
    unittest.main()
