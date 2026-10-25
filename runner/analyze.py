#!/usr/bin/env python3
"""Paired analysis of frozen Othello benchmark data (Python standard library)."""
import argparse
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import statistics

from verify import verify


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_bank(path, split):
    bank = json.loads(Path(path).read_text())
    if digest(bank["protocol"]) != bank["protocol_sha256"]:
        raise ValueError("bank protocol hash mismatch")
    for key in ("trial_time_limit_seconds", "final_sat_time_limit_seconds"):
        if key not in bank["protocol"] or bank["protocol"][key] is not None:
            raise ValueError("an uncapped benchmark protocol is required")
    section = bank["splits"][split]
    for key in ("cases", "schedule"):
        if digest(section[key]) != section[key + "_sha256"]:
            raise ValueError("bank " + key + " hash mismatch")
    cases = {c["id"]: c for c in section["cases"]}
    if len(cases) != len(section["cases"]):
        raise ValueError("duplicate input case ID")
    for case in cases.values():
        if verify(case["reference_moves"], case["board"])["terminal"] != case["terminal"]:
            raise ValueError("reference terminal mismatch")
    return bank, section, cases


def load_run(directory, bankpath, split="main"):
    """Validate a completed prefix, including every move, before using times."""
    directory = Path(directory)
    bank, section, cases = read_bank(bankpath, split)
    meta = json.loads((directory / "metadata.json").read_text())
    if meta["bank_sha256"] != sha(bankpath):
        raise ValueError("run/bank hash mismatch")
    if meta.get("protocol_sha256", bank["protocol_sha256"]) != bank["protocol_sha256"]:
        raise ValueError("run/protocol mismatch")
    if meta.get("split", split) != split:
        raise ValueError("run/split mismatch")
    if meta.get("global_deadline") is not None or meta.get("final_sat_time_limit") is not None:
        raise ValueError("finite run deadline mixed into uncapped data")
    if meta.get("cases_sha256", section["cases_sha256"]) != section["cases_sha256"]:
        raise ValueError("run/cases mismatch")
    methods = meta.get("selected_methods") or sorted({x["method"] for x in section["schedule"]})
    if not set(methods).issubset({x["method"] for x in section["schedule"]}):
        raise ValueError("selected method is absent from the fixed schedule")
    schedule = [x for x in section["schedule"] if x["method"] in methods]
    if not schedule or len(set(methods)) != len(methods):
        raise ValueError("invalid selected methods")
    if meta.get("schedule_sha256") not in (section["schedule_sha256"], digest(schedule)):
        raise ValueError("run/schedule mismatch")
    if meta.get("derived_schedule_sha256", digest(schedule)) != digest(schedule):
        raise ValueError("derived schedule mismatch")
    data = (directory / "runs.jsonl").read_bytes() if (directory / "runs.jsonl").exists() else b""
    rows = []
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            break  # A live writer's unfinished last line is never a completed trial.
        row = json.loads(line)
        if len(rows) >= len(schedule):
            raise ValueError("extra result row")
        expected = schedule[len(rows)]
        if any(row[k] != expected[k] for k in ("case", "repeat", "method")):
            raise ValueError("result identity/order mismatch")
        if row["trial_index"] != len(rows):
            raise ValueError("result index mismatch")
        if row["status"] != "found" or row.get("verified") is not True:
            raise ValueError("result is not an independently verified success")
        verify(row["moves"], cases[row["case"]]["board"])
        for field in ("wall_seconds", "interrupted_work_seconds", "effective_wall_seconds"):
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError("invalid timing: " + field)
        if abs(row["effective_wall_seconds"] - row["wall_seconds"] - row["interrupted_work_seconds"]) > 1e-6:
            raise ValueError("effective time does not retain interrupted work")
        if "global_deadline" not in row or "final_sat_time_limit" not in row or row["global_deadline"] is not None or row["final_sat_time_limit"] is not None:
            raise ValueError("finite timeout results mixed into the uncapped benchmark")
        rows.append(row)
    if meta.get("status") in ("complete", "fixture-complete") and len(rows) != len(schedule):
        raise ValueError("metadata claims completion without the whole schedule")
    meta["fixture"] = bool(meta.get("fixture", False)) or meta.get("status") == "fixture-complete" or any(row.get("fixture", False) for row in rows)
    return {"metadata": meta, "rows": rows, "schedule": schedule, "methods": methods,
            "cases": cases, "bank": bank, "section": section,
            "complete": meta.get("status") in ("complete", "fixture-complete") and len(rows) == len(schedule)}


def quantile(values, p):
    values = sorted(values)
    position = (len(values) - 1) * p
    lo = math.floor(position)
    hi = math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def analyze(runs, bankpath, split="main", replicates=3000, seed=730253, required_labels=()):
    if replicates < 100:
        raise ValueError("at least 100 bootstrap replicates required")
    loaded = {label: load_run(path, bankpath, split) for label, path in runs.items()}
    if not loaded:
        raise ValueError("no runs supplied")
    first = next(iter(loaded.values()))
    cases = first["cases"]
    all_strata = collections.defaultdict(list)
    for case in cases.values():
        all_strata[str(case.get("stratum", case["stones"]))].append(case["id"])
    variants = {}
    sources = {}
    for label, run in loaded.items():
        by_key = {(r["case"], r["method"], r["repeat"]): r for r in run["rows"]}
        expected = collections.defaultdict(list)
        for item in run["schedule"]:
            expected[item["case"], item["method"]].append(item["repeat"])
        program_meta = run["metadata"].get("programs", {})
        for method in run["methods"]:
            values = {}
            for case_id in cases:
                repeats = expected[case_id, method]
                if repeats and all((case_id, method, repeat) in by_key for repeat in repeats):
                    values[case_id] = statistics.mean(by_key[case_id, method, repeat]["effective_wall_seconds"] for repeat in repeats)
            info = program_meta.get(method, {})
            variants[label + "/" + method] = {"case_means": values, "label": info.get("label", method), "run_label": label,
                "timing_profile": info.get("timing_profile", info.get("mode", run["metadata"].get("timing_profile", "legacy-resident-model-final-sat")))}
        sources[label] = {"completed_trials": len(run["rows"]), "planned_trials": len(run["schedule"]),
                          "complete": run["complete"], "fixture": bool(run["metadata"].get("fixture", False)),
                          "rows_sha256": sha(Path(runs[label]) / "runs.jsonl") if (Path(runs[label]) / "runs.jsonl").exists() else None,
                          "methods": run["methods"]}
    common = set(cases)
    for variant in variants.values():
        common.intersection_update(variant["case_means"])
    coverage = len(common) / len(cases)
    fixture = any(x["fixture"] for x in sources.values())
    result = {"bank_sha256": sha(bankpath), "split": split, "sources": sources,
        "planned_independent_cases": len(cases), "common_complete_cases": len(common),
        "common_case_ids": sorted(common), "common_coverage": coverage,
        "all_planned_completed": all(x["complete"] for x in sources.values()),
        "conditional_on_completed_subset": len(common) != len(cases),
        "performance_claims_allowed": not fixture and split == "main" and coverage >= .9,
        "cross_run_comparison_ready": len({s["rows_sha256"] for s in sources.values()}) > 1 and coverage >= .9 and not fixture and split == "main" and set(required_labels).issubset(runs),
        "required_run_labels": list(required_labels),
        "required_run_labels_present": set(required_labels).issubset(runs),
        "comparison_scope": "Same validated input bank; timing profiles and declared controls must also be checked. No CPU-only causal claim.",
        "cost": "case mean of effective_wall_seconds over all planned repeats; fixed original stratum weights",
        "bootstrap": {"replicates": replicates, "seed": seed, "rng": "Python random.Random (MT19937)",
                      "unit": "independent case; all variants and all repeats remain paired within stratum", "interval": "95% percentile, linear quantiles"},
        "variants": {}, "comparisons": [], "skipped_comparisons": []}
    groups = {name: [c for c in ids if c in common] for name, ids in all_strata.items()}
    result["strata"] = {name: {"planned": len(all_strata[name]), "complete_common": len(ids)} for name, ids in groups.items()}
    if not common or any(not ids for ids in groups.values()):
        result["analysis_status"] = "insufficient common cases in every stratum"
        result["cross_run_comparison_ready"] = False
        result["performance_claims_allowed"] = False
        return result
    weights = {name: len(all_strata[name]) / len(cases) for name in groups}
    samples = {name: [] for name in variants}
    means = {name: sum(weights[s] * statistics.mean(v["case_means"][c] for c in ids) for s, ids in groups.items()) for name, v in variants.items()}
    rng = random.Random(seed)
    for _ in range(replicates):
        totals = dict.fromkeys(variants, 0.0)
        for stratum, ids in groups.items():
            selected = [ids[rng.randrange(len(ids))] for _ in ids]
            for name, variant in variants.items():
                totals[name] += weights[stratum] * sum(variant["case_means"][c] for c in selected) / len(selected)
        for name in variants:
            samples[name].append(totals[name])
    for name, variant in variants.items():
        result["variants"][name] = {"label": variant["label"], "timing_profile": variant["timing_profile"],
                                   "mean_seconds": means[name], "independent_common_cases": len(common)}
    for denominator, numerator in itertools.combinations(variants, 2):
        if means[denominator] <= 0:
            result["skipped_comparisons"].append({"numerator": numerator, "denominator": denominator, "reason": "zero denominator time"})
            continue
        ratios = [n / d for n, d in zip(samples[numerator], samples[denominator]) if d > 0]
        if len(ratios) != replicates:
            continue
        point = means[numerator] / means[denominator]
        ci = [quantile(ratios, .025), quantile(ratios, .975)]
        radius = max(abs(v - point) for v in ci) / abs(point) if point != 0 else None
        profile_match = variants[numerator]["timing_profile"] == variants[denominator]["timing_profile"]
        result["comparisons"].append({"numerator": numerator, "denominator": denominator,
            "cross_run": variants[numerator]["run_label"] != variants[denominator]["run_label"],
            "comparison_ready": result["performance_claims_allowed"] and profile_match and set(required_labels).issubset(runs),
            "mean_ratio": point, "ratio_ci95": ci, "relative_ci_radius": radius,
            "ci_includes_one": ci[0] <= 1 <= ci[1],
            "ratio_ci_target_met": radius is not None and radius <= .05 and ci[0] != ci[1],
            "precision_established": len(common) >= 400 and radius is not None and radius <= .05 and ci[0] != ci[1],
            "timing_profiles_match": profile_match})
    result["analysis_status"] = "descriptive completed-case analysis"
    profiles = {json.dumps(v["timing_profile"], sort_keys=True) for v in variants.values()}
    result["mixed_timing_profiles"] = len(profiles) > 1
    if len(profiles) > 1:
        result["timing_profile_note"] = "Different clocks/startup profiles must not be treated as a matched timing comparison. Descriptive statistics are retained."
    result["cross_run_comparison_ready"] = result["cross_run_comparison_ready"] and any(c["cross_run"] and c["comparison_ready"] for c in result["comparisons"])
    result["note"] = "90% coverage is not a precision guarantee or permission to stop early. N20 is auxiliary. The full frozen schedule remains the completion goal."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--run", action="append", required=True, metavar="LABEL=DIR")
    parser.add_argument("--split", choices=("main", "pilot"), default="main")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=3000)
    parser.add_argument("--bootstrap-seed", type=int, default=730253)
    parser.add_argument("--require-label", action="append", default=[], help="Require every named run before declaring a cross-run comparison ready")
    args = parser.parse_args()
    runs = {}
    for item in args.run:
        label, sep, directory = item.partition("=")
        if not sep or not label or label in runs:
            parser.error("use unique LABEL=DIR arguments")
        runs[label] = directory
    output = analyze(runs, args.bank, args.split, args.bootstrap_replicates, args.bootstrap_seed, args.require_label)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: output[k] for k in ("common_complete_cases", "common_coverage", "all_planned_completed", "cross_run_comparison_ready")}))


if __name__ == "__main__":
    main()
