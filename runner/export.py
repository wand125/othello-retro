#!/usr/bin/env python3
"""Export verified data without private commands, logs, environment or local paths."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re

from analyze import analyze, load_run, sha

PRIVATE_KEYS = {"command", "args", "argv", "env", "cwd", "root", "working_directory",
                "gate_directory", "gate_dir", "real_kissat", "python_executable",
                "private_runtime", "runtime_config", "pid", "pgid", "controller_pid",
                "processes", "groups", "stdout", "stderr", "output_directory"}
SECRET_KEY = re.compile(r"token|password|secret|credential|authorization|cookie|api.?key", re.I)
LOCAL_PATH = re.compile(r"(?:^|[\s'\"(=])(?:/(?!/)[^\s'\"<>),;]+|[A-Za-z]:[\\/]|~[\\/]|\\\\)")
ROW_FIELDS = ("trial_index", "original_trial_index", "case", "repeat", "method", "label",
              "first_method", "stones", "stratum", "status", "success", "verified", "moves",
              "wall_seconds", "interrupted_work_seconds", "effective_wall_seconds",
              "global_deadline", "final_sat_time_limit", "host_before", "host_after",
              "fixture", "timing_profile", "guided_diagnostic", "guided_candidate_rejected",
              "fallback_observed")


def sanitize(value):
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()
                if k not in PRIVATE_KEYS and not SECRET_KEY.search(k) and not k.startswith(("_", "/"))
                and not (isinstance(v, str) and LOCAL_PATH.search(v))}
    if isinstance(value, list):
        return [sanitize(v) for v in value if not (isinstance(v, str) and LOCAL_PATH.search(v))]
    if isinstance(value, str) and LOCAL_PATH.search(value):
        return "[local path omitted]"
    return value


def write(path, data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if LOCAL_PATH.search(text):
        raise ValueError("absolute local path remains in export")
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text)
    temp.replace(path)


def export(source, bankpath, output, split="main"):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError("public output must be outside private input directory")
    allowed_files = {"metadata.json", "runs.jsonl", "preparation.jsonl", "resource-pauses.jsonl",
                     "summary.json", "verification.json", "manifest.json"}
    if output.exists() and any(not item.is_file() or item.name not in allowed_files for item in output.iterdir()):
        raise ValueError("output contains unrelated files; use a new public directory")
    run = load_run(source, bankpath, split)
    rows = [sanitize({k: row[k] for k in ROW_FIELDS if k in row}) for row in run["rows"]]
    meta = sanitize(run["metadata"])
    fixture = bool(meta.get("fixture", False)) or any(r.get("fixture", False) for r in rows)
    state = ("fixture-complete" if fixture else "complete") if run["complete"] else "incomplete"
    meta.update(status=state, completed_trials=len(rows), planned_trials=len(run["schedule"]),
                publication_state=state, fixture=fixture,
                performance_claims_allowed=run["complete"] and not fixture and split == "main")
    output.mkdir(parents=True, exist_ok=True)
    write(output / "metadata.json", meta)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if LOCAL_PATH.search(text):
        raise ValueError("local path remains in result rows")
    (output / "runs.jsonl").write_text(text)
    names = ["metadata.json", "runs.jsonl"]
    for name in ("preparation.jsonl", "resource-pauses.jsonl"):
        path = source / name
        if not path.exists():
            if (output / name).exists():
                (output / name).unlink()
            continue
        records = []
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b"\n"):
                break
            records.append(sanitize(json.loads(line)))
        (output / name).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
        names.append(name)
    if "resource-pauses.jsonl" in names:
        meta["program_wall_comparison_note"] = "Whole-program wall includes between-trial pauses; per-trial costs exclude waiting between trials."
        write(output / "metadata.json", meta)
    summary = output / "summary.json"
    if run["complete"]:
        report = analyze({"program": source}, bankpath, split)
        report["metadata"] = meta
        write(summary, sanitize(report))
        names.append("summary.json")
    elif summary.exists():
        summary.unlink()
    verification = {"bank_sha256": sha(bankpath), "completed_prefix_trials": len(rows),
                    "planned_trials": len(run["schedule"]), "computed_records_independently_replayed": len(rows),
                    "reference_records_independently_replayed": len(run["cases"]),
                    "trial_order_and_uniqueness": "passed", "strict_legal_replay_and_target": "passed",
                    "source_metadata_sha256": sha(source / "metadata.json"),
                    "privacy": "private commands, runtime files, logs, secret-named fields and absolute local paths excluded"}
    write(output / "verification.json", verification)
    names.append("verification.json")
    manifest = {"exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "status": state, "split": split, "fixture": fixture,
                "completed_trials": len(rows), "planned_trials": len(run["schedule"]),
                "completed_formal_dataset": run["complete"] and not fixture and split == "main",
                "cross_environment_comparison_ready": False,
                "comparison_note": "One exported dataset does not establish cross-environment coverage or matched timing profiles. Fixtures test the harness only.",
                "files_sha256": {name: sha(output / name) for name in names}}
    write(output / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("main", "pilot"), default="main")
    args = parser.parse_args()
    print(json.dumps(export(args.input, args.bank, args.output, args.split)))


if __name__ == "__main__":
    main()
