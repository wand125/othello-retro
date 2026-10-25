#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent, standard-library checks of banks, records and published data.

Reports identify inputs by ordinal or supplied label, never by private path.
Hashes establish file consistency, not authorship or solver correctness.
"""
import argparse
import collections
import itertools
import json
import math
from pathlib import Path, PurePosixPath
import statistics

from analyze import analyze, digest, load_run, quantile, read_bank, sha
from export import LOCAL_PATH, PRIVATE_KEYS, SECRET_KEY, sanitize
from verify import verify


class CheckError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise CheckError(code)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _constant(_):
    raise CheckError("nonfinite_json_number")


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=_pairs, parse_constant=_constant)


def stratum(case):
    return str(case.get("stratum", case["stones"]))


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def check_bank(path):
    bank = read_json(path)
    require(isinstance(bank.get("splits"), dict) and bool(bank["splits"]), "missing_splits")
    protocol = bank["protocol"]
    ids, seeds, boards, references = set(), set(), collections.Counter(), collections.Counter()
    reports = {}
    for split in bank["splits"]:
        _, section, cases = read_bank(path, split)
        require(bool(cases), "empty_case_set")
        for case in cases.values():
            require(isinstance(case["id"], str) and bool(case["id"]) and case["id"] not in ids,
                    "duplicate_or_invalid_case_id")
            ids.add(case["id"])
            seed = case.get("seed")
            require(_integer(seed) and seed not in seeds, "missing_invalid_or_reused_game_seed")
            seeds.add(seed)
            replay = verify(case["reference_moves"], case["board"])
            stones = 64 - case["board"].count("-")
            require(_integer(case["stones"]) and case["stones"] == stones, "stone_count_mismatch")
            require(isinstance(case["terminal"], bool) and replay["terminal"] == case["terminal"],
                    "terminal_mismatch")
            require(case.get("actualstones", stones) == stones, "actual_stones_mismatch")
            require(case.get("expected", "reachable") == "reachable", "unproved_expected_label")
            reference_hash = digest({"board": case["board"], "moves": case["reference_moves"]})
            require(case.get("reference_sha256") == reference_hash, "reference_hash_mismatch")
            require(case.get("reference_passes", replay["passes"]) == replay["passes"],
                    "reference_pass_count_mismatch")
            boards[case["board"]] += 1
            references[reference_hash] += 1
        require(section.get("independent_games", len(cases)) == len(cases), "independent_case_count_mismatch")
        require(protocol.get(split + "_independent_games", len(cases)) == len(cases), "protocol_case_count_mismatch")
        strata = collections.Counter(stratum(case) for case in cases.values())
        if split + "_cases_per_stratum" in protocol:
            require(all(n == protocol[split + "_cases_per_stratum"] for n in strata.values()), "stratum_case_count_mismatch")
        for spec in protocol.get("strata", []):
            group = [c for c in cases.values() if stratum(c) == str(spec["id"])]
            if split + "_cases" in spec:
                require(len(group) == spec[split + "_cases"], "stratum_case_count_mismatch")
            for case in group:
                require(spec.get("target_stones") is None or case["stones"] == spec["target_stones"], "stratum_stone_mismatch")
                require("terminal" not in spec or case["terminal"] == spec["terminal"], "stratum_terminal_mismatch")
                passes = verify(case["reference_moves"], case["board"])["passes"]
                require(spec.get("reference_passes") != "zero" or passes == 0, "stratum_reference_pass_mismatch")
                require(spec.get("reference_passes") != "positive" or passes > 0, "stratum_reference_pass_mismatch")
                require(spec["id"] != "early-terminal" or case["stones"] < 64, "stratum_early_terminal_mismatch")
        schedule = section["schedule"]
        require(bool(schedule), "empty_schedule")
        methods = protocol.get("methods", sorted({r["method"] for r in schedule}))
        require(isinstance(methods, list) and len(methods) == len(set(methods)) and bool(methods), "invalid_slots")
        repeats = protocol.get(split + "_repeats")
        require(_integer(repeats) and repeats > 0, "missing_or_invalid_repeat_count")
        expected = set(itertools.product(cases, methods, range(1, repeats + 1)))
        actual = []
        for row in schedule:
            require(row["case"] in cases and row["method"] in methods and _integer(row["repeat"]),
                    "invalid_schedule_identity")
            actual.append((row["case"], row["method"], row["repeat"]))
        require(len(actual) == len(set(actual)) and set(actual) == expected, "schedule_not_complete_cartesian_product")
        first_declared = ["first_method" in r for r in schedule]
        require(all(first_declared) or not any(first_declared), "partial_first_method_declaration")
        balance = {}
        if all(first_declared):
            firsts = collections.defaultdict(collections.Counter)
            for offset in range(0, len(schedule), len(methods)):
                block = schedule[offset:offset + len(methods)]
                first = block[0]
                require(all((r["case"], r["repeat"]) == (first["case"], first["repeat"]) for r in block),
                        "noncontiguous_case_pair")
                require(all(r["first_method"] == first["method"] for r in block), "first_method_order_mismatch")
                firsts[first["repeat"], stratum(cases[first["case"]])][first["method"]] += 1
            for (repeat, group), counts in firsts.items():
                values = [counts[m] for m in methods]
                require(max(values) - min(values) <= 1, "first_method_imbalance")
                balance[f"repeat{repeat}:{group}"] = dict(counts)
        reports[split] = {"cases": len(cases), "trials": len(schedule), "slots": methods, "repeats": repeats,
                          "first_method_balance": "passed" if all(first_declared) else "not_declared",
                          "balance_counts": balance}
    return {"status": "passed", "bank_sha256": sha(path), "splits": reports,
            "independent_seed_count": len(seeds), "duplicate_board_groups": sum(n > 1 for n in boards.values()),
            "duplicate_reference_groups": sum(n > 1 for n in references.values()),
            "duplicate_board_policy": "reported; independent seeds can produce the same position",
            "checks": ["protocol_cases_schedule_reference_hashes", "legal_reference_replay", "terminal_and_stones",
                       "unique_case_ids_and_game_seeds", "complete_case_slot_repeat_product", "declared_first_method_balance"]}


def check_banks(paths, require_disjoint=()):
    reports = [check_bank(path) for path in paths]
    indexes = []
    for path in paths:
        cases = [c for s in read_json(path)["splits"].values() for c in s["cases"]]
        indexes.append({"seed": {c["seed"] for c in cases}, "id": {c["id"] for c in cases},
                        "board": {c["board"] for c in cases}, "reference": {c["reference_sha256"] for c in cases}})
    overlaps = []
    for left, right in itertools.combinations(range(len(paths)), 2):
        counts = {key: len(indexes[left][key] & indexes[right][key]) for key in indexes[left]}
        require(not any(counts[key] for key in require_disjoint), "explicit_cross_bank_disjointness_policy_failed")
        overlaps.append({"banks": [left + 1, right + 1], "overlapping_distinct_values": counts})
    return {"status": "passed", "banks": reports, "cross_bank_overlap": overlaps,
            "required_disjoint_fields": list(require_disjoint)}


def check_record(bankpath, case_id, movespath):
    check_bank(bankpath)
    bank = read_json(bankpath)
    cases = [c for s in bank["splits"].values() for c in s["cases"] if c["id"] == case_id]
    require(len(cases) == 1, "case_id_not_unique_or_missing")
    value = read_json(movespath)
    if isinstance(value, dict):
        value = value.get("payload", value)
        require(isinstance(value, dict) and value.get("status", "found") == "found", "record_not_found")
        value = value.get("moves")
    result = verify(value, cases[0]["board"])
    return {"status": "passed", "bank_sha256": sha(bankpath), "legal": True, "target_matches": True,
            "terminal": result["terminal"], "placements": result["placements"], "passes": result["passes"]}


def _validated_run(source, bankpath, split):
    # Strict JSON parsing complements load_run's prefix/replay/clock validation.
    read_json(Path(source) / "metadata.json")
    rows_file = Path(source) / "runs.jsonl"
    if rows_file.exists():
        for line in rows_file.read_bytes().splitlines(keepends=True):
            if not line.endswith(b"\n"):
                break
            json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
    loaded = load_run(source, bankpath, split)
    for row, planned in zip(loaded["rows"], loaded["schedule"]):
        require(_integer(row["trial_index"]) and _integer(row["repeat"]), "invalid_result_index_type")
        if "first_method" in row:
            require(row["first_method"] == planned.get("first_method", row["first_method"]), "result_first_method_mismatch")
        case = loaded["cases"][row["case"]]
        require(row.get("stones", case["stones"]) == case["stones"], "result_stone_count_mismatch")
    meta = loaded["metadata"]
    complete = len(loaded["rows"]) == len(loaded["schedule"]) and meta.get("status") in ("complete", "fixture-complete")
    require(meta.get("status") not in ("complete", "fixture-complete") or complete, "false_completion_claim")
    return loaded, complete


def check_run(source, bankpath, split="main"):
    check_bank(bankpath)
    loaded, complete = _validated_run(source, bankpath, split)
    fixture = bool(loaded["metadata"].get("fixture"))
    return {"status": "passed", "bank_sha256": sha(bankpath), "split": split,
            "state": ("fixture-complete" if fixture else "complete") if complete else "incomplete",
            "fixture": fixture, "completed_trials": len(loaded["rows"]), "planned_trials": len(loaded["schedule"]),
            "completed_formal_dataset": complete and not fixture and split == "main",
            "checks": ["run_bank_hash", "fixed_or_derived_order", "every_completed_record_replayed",
                       "uncapped_flags", "finite_nonnegative_effective_cost_and_retained_interruption"]}


def _private(value):
    if isinstance(value, dict):
        for key, child in value.items():
            require(key not in PRIVATE_KEYS and not SECRET_KEY.search(key) and not key.startswith(("_", "/")),
                    "private_or_secret_field_in_public_data")
            _private(child)
    elif isinstance(value, list):
        for child in value:
            _private(child)
    elif isinstance(value, str):
        require(not LOCAL_PATH.search(value), "absolute_local_path_in_public_data")


def _near(actual, expected, code="summary_arithmetic_mismatch"):
    require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual), code)
    require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-10), code)


def _check_summary(summary, source, bankpath, split, loaded, complete):
    if "variants" in summary and "sources" in summary:
        require(len(summary["sources"]) == 1, "single_bundle_summary_has_multiple_inputs")
        label = next(iter(summary["sources"]))
        settings = summary["bootstrap"]
        require(_integer(settings["replicates"]) and 100 <= settings["replicates"] <= 100000, "invalid_bootstrap_count")
        expected = analyze({label: source}, bankpath, split, settings["replicates"], settings["seed"])
        require(summary["bank_sha256"] == sha(bankpath) and summary["split"] == split, "summary_bank_or_split_mismatch")
        for key in ("planned_independent_cases", "common_complete_cases", "performance_claims_allowed"):
            require(summary[key] == expected[key], "summary_coverage_or_claim_mismatch")
        require(summary["all_planned_completed"] == complete, "summary_false_completion")
        require(set(summary["variants"]) == set(expected["variants"]), "summary_variant_set_mismatch")
        for name, variant in expected["variants"].items():
            _near(summary["variants"][name]["mean_seconds"], variant["mean_seconds"])
            require(summary["variants"][name]["independent_common_cases"] == variant["independent_common_cases"],
                    "summary_independent_n_mismatch")
        comparisons = {(x["numerator"], x["denominator"]): x for x in summary["comparisons"]}
        require(len(comparisons) == len(summary["comparisons"]) == len(expected["comparisons"]), "summary_comparison_set_mismatch")
        for item in expected["comparisons"]:
            actual = comparisons[item["numerator"], item["denominator"]]
            _near(actual["mean_ratio"], item["mean_ratio"])
            require(len(actual["ratio_ci95"]) == 2, "invalid_summary_ci_shape")
            for a, b in zip(actual["ratio_ci95"], item["ratio_ci95"]):
                _near(a, b, "summary_stdlib_bootstrap_ci_mismatch")
            for key in ("ratio_ci_target_met", "precision_established", "timing_profiles_match"):
                require(actual[key] == item[key], "summary_precision_or_profile_claim_mismatch")
            if "comparison_ready" in actual:
                require(actual["comparison_ready"] == item["comparison_ready"], "summary_comparison_readiness_mismatch")
        return {"schema": "stdlib_runner", "arithmetic": "passed", "ci": "stdlib_paired_bootstrap_recomputed"}
    require("counts" in summary and "estimates" in summary, "unsupported_summary_schema")
    rows = loaded["rows"]
    cases = loaded["cases"]
    means = {}
    for method in loaded["methods"]:
        subset = [r for r in rows if r["method"] == method]
        report = summary["counts"][method]
        require(report["completed_found"] == len(subset), "summary_completed_count_mismatch")
        _near(report["mean_seconds"], statistics.mean(r["effective_wall_seconds"] for r in subset))
        values = [r["effective_wall_seconds"] for r in subset]
        for field, value in (("median_seconds", statistics.median(values)), ("p95_seconds", quantile(values, .95))):
            if field in report:
                _near(report[field], value)
        means[method] = {c: statistics.mean(r["effective_wall_seconds"] for r in subset if r["case"] == c) for c in cases}
        require(report["independent_cases"] == len(cases), "summary_independent_n_mismatch")
    groups = collections.defaultdict(list)
    for case in cases.values():
        groups[stratum(case)].append(case["id"])
    expected_names = set(groups) | {"fixed_stratum_overall"}
    require(set(summary["estimates"]) == expected_names, "summary_stratum_set_mismatch")
    for group, ids in list(groups.items()) + [("fixed_stratum_overall", list(cases))]:
        report = summary["estimates"][group]
        sat, auto = (statistics.mean(means[m][c] for c in ids) for m in ("sat", "auto"))
        _near(report["sat_mean_seconds"], sat)
        _near(report["auto_mean_seconds"], auto)
        _near(report["auto_div_sat"], auto / sat)
        if "auto_minus_sat_seconds" in report:
            _near(report["auto_minus_sat_seconds"], auto - sat)
        require(report["independent_cases"] == len(ids), "summary_independent_n_mismatch")
    require(summary.get("global_deadline") is None and summary.get("timeout_count", 0) == 0, "summary_finite_deadline_or_timeout")
    return {"schema": "original_numpy_study", "arithmetic": "passed",
            "ci": "not_checked_here; use check_numpy_ci.py for NumPy PCG bootstrap and Wilson intervals"}


def check_published(source, bankpath, split="main"):
    root = Path(source)
    require(root.is_dir() and not root.is_symlink(), "unsafe_public_directory")
    manifest = read_json(root / "manifest.json")
    files = manifest["files_sha256"]
    allowed = {"metadata.json", "runs.jsonl", "verification.json", "summary.json", "preparation.jsonl", "resource-pauses.jsonl"}
    require(isinstance(files, dict) and {"metadata.json", "runs.jsonl", "verification.json"}.issubset(files), "missing_manifest_core_files")
    for name, expected in files.items():
        require(isinstance(name, str) and name in allowed and not PurePosixPath(name).is_absolute()
                and ".." not in PurePosixPath(name).parts and "\\" not in name, "unsafe_manifest_member")
        path = root / name
        require(path.is_file() and not path.is_symlink(), "unsafe_or_missing_public_file")
        require(sha(path) == expected, "manifest_file_hash_mismatch")
    require({p.name for p in root.iterdir()} == set(files) | {"manifest.json"}, "untracked_public_file_or_directory")
    for path in root.iterdir():
        require(path.is_file() and not path.is_symlink(), "public_symlink_or_directory")
        if path.suffix == ".json":
            _private(read_json(path))
        else:
            data = path.read_bytes()
            require(not data or data.endswith(b"\n"), "incomplete_public_jsonl_line")
            for line in data.splitlines():
                _private(json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant))
    check_bank(bankpath)
    loaded, complete = _validated_run(source, bankpath, split)
    fixture = bool(loaded["metadata"].get("fixture"))
    expected_state = ("fixture-complete" if fixture else "complete") if complete else "incomplete"
    require(manifest["status"] == expected_state, "manifest_state_mismatch")
    require(manifest.get("fixture", fixture) == fixture, "manifest_fixture_mismatch")
    require(manifest.get("split", split) == split, "manifest_split_mismatch")
    require(manifest["completed_trials"] == len(loaded["rows"]) and manifest["planned_trials"] == len(loaded["schedule"]), "manifest_trial_count_mismatch")
    require(manifest["completed_formal_dataset"] == (complete and not fixture and split == "main"), "manifest_false_formal_claim")
    require(manifest.get("cross_environment_comparison_ready") is False, "single_bundle_cannot_certify_multiple_environments")
    verification = read_json(root / "verification.json")
    require(verification["bank_sha256"] == sha(bankpath), "verification_bank_mismatch")
    for key in ("completed_prefix_trials", "computed_records_independently_replayed"):
        require(verification[key] == len(loaded["rows"]), "verification_count_mismatch")
    require(verification["planned_trials"] == len(loaded["schedule"]), "verification_plan_count_mismatch")
    if complete:
        require("summary.json" in files, "missing_complete_summary")
        summary = _check_summary(read_json(root / "summary.json"), source, bankpath, split, loaded, complete)
    else:
        require("summary.json" not in files, "incomplete_bundle_contains_summary")
        summary = {"status": "not_applicable_incomplete"}
    return {"status": "passed", "state": expected_state, "bank_sha256": sha(bankpath),
            "manifest_files_verified": len(files), "completed_trials": len(loaded["rows"]),
            "planned_trials": len(loaded["schedule"]), "summary": summary,
            "checks": ["manifest_hashes", "no_untracked_files_or_symlinks", "no_private_fields_or_local_paths",
                       "independent_replay_and_order", "completion_and_fixture_claims"]}


def _attempt(action):
    try:
        return action()
    except CheckError as exc:
        return {"status": "failed", "error": str(exc)}
    except (ValueError, KeyError, TypeError, IndexError, OSError, ZeroDivisionError):
        # Parser/OS errors can contain private paths, input text or credentials.
        return {"status": "failed", "error": "input_or_validation_error"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("bank", "record", "run", "published", "all"):
        sub = subs.add_parser(command)
        sub.add_argument("--bank", required=True, type=Path, action="append" if command in ("bank", "all") else "store")
        if command in ("bank", "all"):
            sub.add_argument("--require-disjoint", action="append", default=[], choices=("seed", "id", "board", "reference"))
        if command == "record":
            sub.add_argument("--case", required=True)
            sub.add_argument("--moves", required=True, type=Path)
        if command in ("run", "published"):
            sub.add_argument("--input", required=True, type=Path)
            sub.add_argument("--split", default="main")
        if command == "all":
            sub.add_argument("--run", action="append", default=[], metavar="LABEL=DIR")
            sub.add_argument("--published", action="append", default=[], metavar="LABEL=DIR")
    args = parser.parse_args(argv)
    if args.command == "bank":
        result = _attempt(lambda: check_banks(args.bank, args.require_disjoint))
    elif args.command == "record":
        result = _attempt(lambda: check_record(args.bank, args.case, args.moves))
    elif args.command in ("run", "published"):
        function = check_run if args.command == "run" else check_published
        result = _attempt(lambda: function(args.input, args.bank, args.split))
    else:
        result = {"banks": _attempt(lambda: check_banks(args.bank, args.require_disjoint)), "runs": {}, "published": {}}
        if result["banks"]["status"] != "passed":
            result["status"] = "failed"
            print(json.dumps(sanitize(result), ensure_ascii=False, indent=2, allow_nan=False))
            return 1
        banks = {sha(path): path for path in args.bank if path.is_file()}
        for kind in ("run", "published"):
            for item in getattr(args, kind):
                label, sep, directory = item.partition("=")
                if not sep or not label or label in result[kind + ("s" if kind == "run" else "")]:
                    parser.error("use unique LABEL=DIR arguments")
                def inspect(directory=directory, kind=kind):
                    metadata = read_json(Path(directory) / "metadata.json")
                    require(metadata["bank_sha256"] in banks, "run_bank_not_supplied")
                    function = check_run if kind == "run" else check_published
                    return function(directory, banks[metadata["bank_sha256"]], metadata.get("split", "main"))
                result[kind + ("s" if kind == "run" else "")][label] = _attempt(inspect)
        result["status"] = "passed" if result["banks"]["status"] == "passed" and all(r["status"] == "passed" for group in (result["runs"], result["published"]) for r in group.values()) else "failed"
    print(json.dumps(sanitize(result), ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
