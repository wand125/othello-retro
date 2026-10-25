# SPDX-License-Identifier: MIT
"""Small synthetic replayable fixtures; these are never performance evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze
from verify import INITIAL


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


def toy_bank(root, repeats=3):
    # Four independently known legal first moves, plus the initial position.
    # The fixture is for accounting tests, not an independent-game sample.
    cases = [{"id": "initial", "board": INITIAL, "reference_moves": [],
              "stones": 4, "stratum": "four", "terminal": False}]
    for move, square, flipped in [("d3", 19, 27), ("c4", 26, 27),
                                  ("f5", 37, 36), ("e6", 44, 36)]:
        board = list(INITIAL)
        board[square] = board[flipped] = "X"
        cases.append({"id": move, "board": "".join(board), "reference_moves": [move],
                      "stones": 5, "stratum": "five", "terminal": False})
    schedule = [{"case": case["id"], "repeat": repeat, "method": method}
                for repeat in range(1, repeats + 1) for case in cases
                for method in ("sat", "auto")]
    protocol = {"title": "Synthetic unit-test fixture; no performance claims",
                "main_repeats": repeats, "trial_time_limit_seconds": None,
                "final_sat_time_limit_seconds": None}
    section = {"cases": cases, "schedule": schedule,
               "cases_sha256": analyze.digest(cases), "schedule_sha256": analyze.digest(schedule)}
    bank = {"protocol": protocol, "protocol_sha256": analyze.digest(protocol),
            "splits": {"main": section}}
    path = root / "bank.json"
    write_json(path, bank)
    return path, bank


def toy_run(root, bankpath, bank, label="host", methods=("sat", "auto"), fixture=True):
    directory = root / label
    directory.mkdir()
    section = bank["splits"]["main"]
    schedule = [x for x in section["schedule"] if x["method"] in methods]
    metadata = {"bank_sha256": analyze.sha(bankpath), "protocol_sha256": bank["protocol_sha256"],
                "cases_sha256": section["cases_sha256"], "schedule_sha256": analyze.digest(schedule),
                "derived_schedule_sha256": analyze.digest(schedule), "selected_methods": list(methods),
                "split": "main", "fixture": fixture, "status": "complete",
                "completed_trials": len(schedule), "planned_trials": len(schedule)}
    cases = {c["id"]: (i, c) for i, c in enumerate(section["cases"])}
    rows = []
    for index, item in enumerate(schedule):
        case_index, case = cases[item["case"]]
        # Repetitions deliberately differ; dropping any repeat changes the mean.
        seconds = (case_index + 1) * (1, 2, 9)[item["repeat"] - 1]
        seconds *= 2 if item["method"] == "auto" else 1
        rows.append({**item, "trial_index": index, "status": "found", "verified": True,
                     "moves": case["reference_moves"], "wall_seconds": seconds,
                     "interrupted_work_seconds": 0, "effective_wall_seconds": seconds,
                     "global_deadline": None, "final_sat_time_limit": None})
    save_run(directory, metadata, rows)
    return directory, metadata, rows


def save_run(directory, metadata, rows, suffix=b""):
    write_json(directory / "metadata.json", metadata)
    (directory / "runs.jsonl").write_bytes(
        b"".join((json.dumps(r) + "\n").encode() for r in rows) + suffix)


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bankpath, self.bank = toy_bank(self.root)
        self.run, self.meta, self.rows = toy_run(self.root, self.bankpath, self.bank)

    def analyze(self, **kwargs):
        return analyze.analyze({"host": self.run}, self.bankpath, replicates=200, **kwargs)

    def test_paired_case_bootstrap_keeps_all_repeats_and_degenerate_ci_is_not_precision(self):
        result = self.analyze()
        self.assertEqual(result["planned_independent_cases"], 5)
        self.assertEqual(result["sources"]["host"]["completed_trials"], 30)
        self.assertEqual(result["variants"]["host/sat"]["independent_common_cases"], 5)
        self.assertAlmostEqual(result["variants"]["host/sat"]["mean_seconds"], 12)
        self.assertAlmostEqual(result["variants"]["host/auto"]["mean_seconds"], 24)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["mean_ratio"], 2)
        self.assertEqual(comparison["ratio_ci95"], [2, 2])
        self.assertFalse(comparison["ratio_ci_target_met"])
        self.assertFalse(comparison["precision_established"])

    def test_fixture_cannot_establish_performance_or_environment_claim(self):
        other, _, _ = toy_run(self.root, self.bankpath, self.bank, "other")
        result = analyze.analyze({"host": self.run, "other": other}, self.bankpath, replicates=100)
        self.assertFalse(result["performance_claims_allowed"])
        self.assertFalse(result["cross_run_comparison_ready"])

    def test_incomplete_case_is_excluded_instead_of_assigned_finite_cost(self):
        self.meta["status"] = "running"
        self.meta["completed_trials"] = 29
        save_run(self.run, self.meta, self.rows[:-1])
        result = self.analyze()
        self.assertEqual(result["common_complete_cases"], 4)
        self.assertNotIn("e6", result["common_case_ids"])
        self.assertTrue(result["conditional_on_completed_subset"])
        self.assertFalse(result["all_planned_completed"])
        # The three completed repeats of other cases remain intact.
        self.assertAlmostEqual(result["variants"]["host/sat"]["mean_seconds"], 10.4)

    def test_no_complete_stratum_does_not_produce_a_cost_estimate(self):
        self.meta["status"] = "running"
        save_run(self.run, self.meta, self.rows[:2])
        result = self.analyze()
        self.assertEqual(result["variants"], {})
        self.assertEqual(result["comparisons"], [])
        self.assertFalse(result["cross_run_comparison_ready"])

    def test_single_method_uses_filtered_schedule_and_reindexed_rows(self):
        other, _, _ = toy_run(self.root, self.bankpath, self.bank, "single", methods=("auto",))
        loaded = analyze.load_run(other, self.bankpath)
        self.assertEqual(loaded["methods"], ["auto"])
        self.assertEqual(len(loaded["schedule"]), 15)
        result = analyze.analyze({"single": other}, self.bankpath, replicates=100)
        self.assertEqual(list(result["variants"]), ["single/auto"])
        self.assertEqual(result["comparisons"], [])

    def test_bootstrap_resamples_cases_not_repetitions(self):
        varied = copy.deepcopy(self.rows)
        case_ids = [c["id"] for c in self.bank["splits"]["main"]["cases"]]
        for row in varied:
            if row["method"] == "auto":
                row["wall_seconds"] *= 1 + case_ids.index(row["case"]) / 4
                row["effective_wall_seconds"] = row["wall_seconds"]
        save_run(self.run, self.meta, varied)
        original = self.analyze()
        smoothed = copy.deepcopy(varied)
        for row in smoothed:
            row["wall_seconds"] *= 4 / (1, 2, 9)[row["repeat"] - 1]
            row["effective_wall_seconds"] = row["wall_seconds"]
        save_run(self.run, self.meta, smoothed)
        averaged = self.analyze()
        # Removing within-case timing variation keeps every case mean intact.
        # Resampling repeats independently would incorrectly change this CI.
        self.assertEqual(original["comparisons"], averaged["comparisons"])
        self.assertNotEqual(original["comparisons"][0]["ratio_ci95"][0],
                            original["comparisons"][0]["ratio_ci95"][1])

    def test_required_labels_duplicate_inputs_and_timing_profiles_gate_readiness(self):
        self.meta["fixture"] = False
        save_run(self.run, self.meta, self.rows)
        required = ("m4", "m1", "intel", "wsl")
        aliases = analyze.analyze({label: self.run for label in required}, self.bankpath,
                                 replicates=100, required_labels=required)
        self.assertTrue(aliases["required_run_labels_present"])
        self.assertFalse(aliases["cross_run_comparison_ready"])
        other, meta, rows = toy_run(self.root, self.bankpath, self.bank, "second", fixture=False)
        for row in rows:
            row["wall_seconds"] *= 3
            row["effective_wall_seconds"] *= 3
        save_run(other, meta, rows)
        missing = analyze.analyze({"m4": self.run, "m1": other}, self.bankpath,
                                 replicates=100, required_labels=required)
        self.assertFalse(missing["required_run_labels_present"])
        self.assertFalse(missing["cross_run_comparison_ready"])
        matching = analyze.analyze({"m4": self.run, "m1": other}, self.bankpath, replicates=100)
        self.assertTrue(matching["cross_run_comparison_ready"])
        meta["timing_profile"] = "whole-program-wall"
        save_run(other, meta, rows)
        mismatch = analyze.analyze({"m4": self.run, "m1": other}, self.bankpath, replicates=100)
        self.assertTrue(mismatch["mixed_timing_profiles"])
        self.assertFalse(mismatch["cross_run_comparison_ready"])

    def test_same_bank_is_mandatory_even_when_rows_are_valid(self):
        self.meta["bank_sha256"] = "0" * 64
        save_run(self.run, self.meta, self.rows)
        with self.assertRaisesRegex(ValueError, "run/bank"):
            analyze.load_run(self.run, self.bankpath)

    def test_protocol_requires_both_explicit_uncapped_declarations(self):
        for key in ("trial_time_limit_seconds", "final_sat_time_limit_seconds"):
            for change in ("missing", 0, 60):
                with self.subTest(key=key, change=change):
                    bank = copy.deepcopy(self.bank)
                    if change == "missing":
                        del bank["protocol"][key]
                    else:
                        bank["protocol"][key] = change
                    # Rehash to establish that the policy, not corrupt bytes,
                    # rejects this otherwise correctly signed toy bank.
                    bank["protocol_sha256"] = analyze.digest(bank["protocol"])
                    write_json(self.bankpath, bank)
                    with self.assertRaisesRegex(ValueError, "uncapped benchmark protocol"):
                        analyze.read_bank(self.bankpath, "main")

    def test_finite_run_metadata_is_rejected_even_when_every_result_succeeded(self):
        for key in ("global_deadline", "final_sat_time_limit"):
            with self.subTest(key=key):
                metadata = copy.deepcopy(self.meta)
                metadata[key] = 60
                save_run(self.run, metadata, self.rows)
                with self.assertRaisesRegex(ValueError, "finite run deadline"):
                    analyze.load_run(self.run, self.bankpath)

    def test_each_result_requires_both_explicit_uncapped_flags(self):
        for key in ("global_deadline", "final_sat_time_limit"):
            for change in ("missing", 0, 60):
                with self.subTest(key=key, change=change):
                    rows = copy.deepcopy(self.rows)
                    if change == "missing":
                        del rows[0][key]
                    else:
                        rows[0][key] = change
                    save_run(self.run, self.meta, rows)
                    with self.assertRaisesRegex(ValueError, "finite timeout results"):
                        analyze.load_run(self.run, self.bankpath)

    def test_timing_profiles_are_matched_per_comparison_pair(self):
        programs = {"sat": {"timing_profile": "oneshot"},
                    "auto": {"timing_profile": "resident"}}
        self.meta.update(fixture=False, programs=programs)
        save_run(self.run, self.meta, self.rows)
        other, meta, rows = toy_run(self.root, self.bankpath, self.bank, "second", fixture=False)
        meta["programs"] = copy.deepcopy(programs)
        for row in rows:
            row["wall_seconds"] *= 3
            row["effective_wall_seconds"] *= 3
        save_run(other, meta, rows)
        result = analyze.analyze({"host": self.run, "second": other}, self.bankpath,
                                 replicates=100, required_labels=("host", "second"))
        self.assertTrue(result["mixed_timing_profiles"])
        self.assertTrue(result["cross_run_comparison_ready"])
        matching_cross_run = []
        rejected_mixed = []
        for pair in result["comparisons"]:
            same_method = pair["numerator"].split("/")[-1] == pair["denominator"].split("/")[-1]
            self.assertEqual(pair["timing_profiles_match"], same_method)
            self.assertEqual(pair["comparison_ready"], same_method)
            if pair["cross_run"] and same_method:
                matching_cross_run.append(pair)
            elif not same_method:
                rejected_mixed.append(pair)
        self.assertEqual(len(matching_cross_run), 2)  # SAT/SAT and auto/auto.
        self.assertEqual(len(rejected_mixed), 4)  # Both within-run and cross-run mixed pairs.

    def test_zero_cost_cannot_crash_or_establish_precision(self):
        for row in self.rows:
            if row["method"] == "auto":
                row["wall_seconds"] = row["effective_wall_seconds"] = 0
        save_run(self.run, self.meta, self.rows)
        try:
            result = self.analyze()
        except ValueError:
            # A clear rejection of zero timings is also a valid contract.
            return
        for comparison in result["comparisons"]:
            self.assertFalse(comparison["precision_established"])

    def test_zero_denominator_is_reported_without_an_infinite_ratio(self):
        for row in self.rows:
            if row["method"] == "sat":
                row["wall_seconds"] = row["effective_wall_seconds"] = 0
        save_run(self.run, self.meta, self.rows)
        result = self.analyze()
        self.assertEqual(result["comparisons"], [])
        self.assertTrue(result["skipped_comparisons"])
        self.assertTrue(result["skipped_comparisons"][0]["reason"])

    def test_reordered_results_and_illegal_move_sequences_are_rejected(self):
        bad = copy.deepcopy(self.rows)
        bad[0], bad[1] = bad[1], bad[0]
        save_run(self.run, self.meta, bad)
        with self.assertRaisesRegex(ValueError, "identity/order"):
            analyze.load_run(self.run, self.bankpath)
        bad = copy.deepcopy(self.rows)
        bad[2]["moves"] = ["a1"]
        save_run(self.run, self.meta, bad)
        with self.assertRaises(ValueError):
            analyze.load_run(self.run, self.bankpath)

    def test_claimed_complete_prefix_is_rejected_but_live_partial_line_is_not_a_trial(self):
        save_run(self.run, self.meta, self.rows[:-1])
        with self.assertRaisesRegex(ValueError, "claims completion"):
            analyze.load_run(self.run, self.bankpath)
        self.meta["status"] = "running"
        save_run(self.run, self.meta, self.rows[:-1], suffix=b'{"trial_index":29')
        loaded = analyze.load_run(self.run, self.bankpath)
        self.assertEqual(len(loaded["rows"]), 29)
        self.assertFalse(loaded["complete"])

    def test_interruption_cost_is_retained_and_bad_or_finite_times_rejected(self):
        good = copy.deepcopy(self.rows)
        good[0]["interrupted_work_seconds"] = 3
        good[0]["effective_wall_seconds"] += 3
        save_run(self.run, self.meta, good)
        self.assertEqual(analyze.load_run(self.run, self.bankpath)["rows"][0]["effective_wall_seconds"], 4)
        for field, value in [("effective_wall_seconds", 1), ("wall_seconds", float("nan")),
                             ("wall_seconds", True), ("final_sat_time_limit", 60)]:
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(good)
                bad[0][field] = value
                save_run(self.run, self.meta, bad)
                with self.assertRaises(ValueError):
                    analyze.load_run(self.run, self.bankpath)


if __name__ == "__main__":
    unittest.main()
