#!/usr/bin/env python3
"""Rex v2.4 independent executable functionality check against a prior organ.

This verifies a *specific missing capability*, not broad AI self-improvement:
a newly generated ledger_health organ must preserve the previous ledger_summary
contract while correctly reporting status distributions on real extra records.
Both programs are deterministic, SHA-bound Rex templates and run in scrubbed,
bounded isolated Python subprocesses. No admission, merge or model writes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tools import demiurge_rex as rex
from tools import demiurge_rex_need_discovery as need

SCHEMA = "janus.rex.module_functional_gain/2.4"
MAX_LEDGER_RECORDS = 10000
MAX_RECORD_BYTES = 100000
MAX_TEST_ROWS = 64
MIN_EXTRA_RECORDS = 12


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_generated(candidate_dir, spec_path, expected_template):
    folder = Path(candidate_dir)
    spec = rex.load(Path(spec_path))
    meta = rex.load(folder / "candidate.json")
    audit = rex.load(folder / "audit.json")
    path = folder / "module.py"
    if any(p.is_symlink() for p in (folder, path)):
        raise ValueError("MODULE_SYMLINK_DENIED")
    source = path.read_bytes()
    if (meta.get("template") != expected_template or
        spec.get("template") != expected_template or
        meta.get("module_id") != spec.get("module_id") or
        meta.get("source_sha256") != sha(source) or
        audit.get("status") != "PASS" or
        audit.get("source_sha256") != sha(source) or
        audit.get("authority_delta") != 0 or
        source != rex.render(spec).encode("utf-8") or
        rex.audit_ast(__import__("ast").parse(source))):
        raise ValueError("REX_GENERATED_MODULE_INTEGRITY_FAILED")
    return spec, path, sha(source)


def safe_ledger_rows(root, observed):
    if not isinstance(observed, str) or not observed.startswith(
        ("rex/lifecycle_runs/", "rex/runs/")
    ) or ".." in Path(observed).parts:
        raise ValueError("FORBIDDEN_LEDGER_ROOT")
    repo = Path(root).resolve(strict=True)
    ledger = (repo / observed).resolve(strict=True)
    if not ledger.is_dir() or not ledger.is_relative_to(repo):
        raise ValueError("UNSAFE_LEDGER_PATH")
    paths = sorted(ledger.glob("*.json"))
    if len(paths) > MAX_LEDGER_RECORDS:
        raise ValueError("UNBOUNDED_REAL_LEDGER")
    rows = []
    for path in paths:
        if path.is_symlink() or path.stat().st_size > MAX_RECORD_BYTES:
            raise ValueError("UNTRUSTED_REAL_LEDGER_FILE")
        value = need.load(path)
        if value.get("authority_delta", 0) != 0:
            continue
        rows.append((path.name, need.sha256_file(path), need.compact_row(value)))
    return rows


def isolate_run(path, rows):
    # Reuse the exact Rex runner with an isolated interpreter, no imports in
    # candidate source, no network code, scrubbed env, and bounded wall time.
    payload = {"rows": rows}
    with tempfile.TemporaryDirectory() as td:
        folder = Path(td)
        input_file = folder / "input.json"
        runner = folder / "runner.py"
        input_file.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        if input_file.stat().st_size > 100000:
            raise ValueError("UNBOUNDED_TEST_PACKET")
        runner.write_text(rex.runner_source(), encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""),
               "PYTHONIOENCODING": "utf-8",
               "PYTHONDONTWRITEBYTECODE": "1"}
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-B", str(runner),
             str(path.resolve()), str(input_file)],
            cwd=td, env=env, text=True, capture_output=True, timeout=8
        )
        if completed.returncode or len(completed.stdout) > 30000:
            raise ValueError("BOUNDED_GENERATED_ORGAN_EXECUTION_FAILED")
        result = json.loads(completed.stdout)
        if not isinstance(result, dict) or result.get("authority_delta") != 0:
            raise ValueError("UNTRUSTED_ORGAN_RESULT")
        return result


def evaluate(root, candidate_dir, candidate_spec, baseline_dir, baseline_spec):
    descendant, child_path, child_sha = validate_generated(
        candidate_dir, candidate_spec, "ledger_health")
    parent, parent_path, parent_sha = validate_generated(
        baseline_dir, baseline_spec, "ledger_summary")
    source = ((descendant.get("nexus") or {}).get("input") or {}).get("observed_path")
    old = ((parent.get("nexus") or {}).get("input") or {})
    if source != old.get("observed_path"):
        raise ValueError("UNMATCHED_SOURCE_LEDGER")
    old_count = old.get("observed_record_count")
    if type(old_count) is not int or old_count < 1:
        raise ValueError("UNTRUSTED_PARENT_OBSERVATION")
    rows = safe_ledger_rows(root, source)
    if len(rows) - old_count < MIN_EXTRA_RECORDS:
        raise ValueError("INSUFFICIENT_ADDITIONAL_REAL_RECORDS")
    # The original proposal freezes its count, not its complete dated
    # identities. Therefore this is a retrospective additional-record test,
    # not an independent external future holdout.
    extras = rows[old_count:]
    chosen = (extras[:MAX_TEST_ROWS//2] + extras[-MAX_TEST_ROWS//2:]
              if len(extras) > MAX_TEST_ROWS else extras)
    checks = []
    for sample in (chosen[::2], chosen[1::2]):
        context = [row[2] for row in sample]
        if len(context) < MIN_EXTRA_RECORDS//2:
            raise ValueError("INSUFFICIENT_EVALUATION_ROWS")
        baseline = isolate_run(parent_path, context)
        candidate = isolate_run(child_path, context)
        expected = {}
        for row in context:
            state = row.get("result_status", row.get("status", row.get("state", "UNKNOWN")))
            if not isinstance(state, str):
                state = "UNKNOWN"
            state = state[:64]
            expected[state] = expected.get(state, 0) + 1
        preserved = all(candidate.get(k) == baseline.get(k) for k in
                        ("status", "row_count", "dict_row_count", "keys", "authority_delta"))
        new_signal = ("status_counts" not in baseline and
                      candidate.get("status_counts") == expected)
        checks.append({"rows": len(context), "preserved_legacy_contract": preserved,
                       "new_status_distribution_correct": new_signal})
    passed = all(c["preserved_legacy_contract"] and
                 c["new_status_distribution_correct"] for c in checks)
    report = {
        "schema": SCHEMA,
        "status": "RESEARCH_FUNCTIONAL_GAIN" if passed else "HOLD_NO_FUNCTIONAL_GAIN",
        "candidate_module": descendant["module_id"],
        "parent_module": parent["module_id"],
        "candidate_source_sha256": child_sha,
        "parent_source_sha256": parent_sha,
        "ledger_family": source,
        "ledger_records_now": len(rows),
        "parent_snapshot_count": old_count,
        "retrospective_extra_records": len(extras),
        "evaluation_set_sha256": sha(json.dumps([(r[0],r[1]) for r in chosen]).encode()),
        "checks": checks,
        "prior_capability": "ROW_COUNT_AND_KEYS",
        "added_capability": "STATUS_DISTRIBUTION",
        "new_functional_capability_proven": passed,
        "quality_on_external_future_tasks_proven": False,
        "continuous_neural_weight_gain_proven": False,
        "training_data_used_for_independent_blind_assessment": False,
        "production_authority": False,
        "automatic_main_merge": False,
        "authority_delta": 0,
    }
    report["receipt_sha256"] = sha(json.dumps(report, sort_keys=True,
                                             separators=(",", ":")).encode())
    return report


def main():
    ap = argparse.ArgumentParser()
    for arg in ("root", "candidate-dir", "candidate-spec",
                "baseline-dir", "baseline-spec", "out"):
        ap.add_argument("--" + arg, required=True)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        raise FileExistsError("IMMUTABLE_RESEARCH_FITNESS_RECEIPT")
    result = evaluate(a.root, a.candidate_dir, a.candidate_spec,
                      a.baseline_dir, a.baseline_spec)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status":result["status"],"real_extra_records":result["retrospective_extra_records"],
                      "functional_gain":result["new_functional_capability_proven"],
                      "production_authority":False}))
    if result["status"] != "RESEARCH_FUNCTIONAL_GAIN":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
