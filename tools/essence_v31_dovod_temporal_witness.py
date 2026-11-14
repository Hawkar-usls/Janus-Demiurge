#!/usr/bin/env python3
"""ESSENCE v3.1 DovoD temporal witness: source-bound, read-only microcore.

The historical DovoD family supplies research *designs*: hierarchical context
(DovoD.py), Physarum resource dynamics (DovoD2-4) and adaptive complexity
(DovoD5). This witness runs none of those legacy scripts. It inspects real
completed GitHub Actions observations, never modifies weights, never chooses
a neural PASS, and never consumes post-exam rows as training input.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

SCHEMA = "janus.essence.dovod_temporal_witness/3.1"
STATE_SCHEMA = "janus.essence.github_future_weights/2.6"
REPO = "Hawkar-usls/Janus-Demiurge"
ARCHIVES = (
    "Hawkar-usls/janus-meta-registry/DovoD.py",
    "Hawkar-usls/janus-meta-registry/DovoD2.py",
    "Hawkar-usls/janus-meta-registry/DovoD3.py",
    "Hawkar-usls/janus-meta-registry/DovoD4.py",
    "Hawkar-usls/janus-meta-registry/DovoD5.py",
    "Hawkar-usls/Janus-Fundamentum/archive/nas_dovod_sha_20261031/README.md",
)
MAX_RUNS = 500
MAX_STATE_BYTES = 250_000
MIN_NEW_AFTER_EXAM = 24
MIN_INDEPENDENT_FAMILIES = 8
MAX_FAMILY_SHARE = 0.40
EVENTS = frozenset(("push", "workflow_dispatch", "schedule",
                    "pull_request", "repository_dispatch"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("TIMESTAMP_TYPE")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("TIMESTAMP_FORMAT") from exc
    if dt.tzinfo is None:
        raise ValueError("TIMESTAMP_NO_TIMEZONE")
    return dt.astimezone(timezone.utc)


def state_gate(state):
    """Validate sealed *existing* ESSENCE research state; never load tensors."""
    if (not isinstance(state, dict) or state.get("schema") != STATE_SCHEMA
        or state.get("research_only") is not True
        or state.get("production_authority") is not False
        or type(state.get("generation")) is not int
        or not 0 <= state["generation"] <= 4):
        raise ValueError("INVALID_NEURAL_STATE_CONTRACT")
    expected = sha({k: v for k, v in state.items() if k != "state_sha256"})
    if state.get("state_sha256") != expected:
        raise ValueError("NEURAL_STATE_DIGEST_MISMATCH")
    history = state.get("history")
    if not isinstance(history, list) or len(history) > 24:
        raise ValueError("INVALID_HISTORY")
    for event in history:
        if not isinstance(event, dict) or type(event.get("accepted")) is not bool:
            raise ValueError("INVALID_GENERATION")
        proof = event.get("independent_future_verification")
        if not isinstance(proof, dict) or proof.get("receipt_sha256") != sha({
            k: v for k, v in proof.items() if k != "receipt_sha256"
        }):
            raise ValueError("UNSEALED_FUTURE_PROOF")
        if event["accepted"] and (
            proof.get("status") != "PASS_PROSPECTIVE_PAIRED_NEURAL_GAIN"
            or proof.get("improvement_proven_under_registered_internal_thresholds") is not True
            or proof.get("production_authority") is not False
        ):
            raise ValueError("UNVERIFIED_ACCEPTED_GENERATION")
    if state.get("pending") is not None:
        p = state["pending"]
        if not isinstance(p, dict) or p.get("challenger_sha256") != sha(p.get("challenger")):
            raise ValueError("UNSEALED_PENDING_CHALLENGER")
    return history


def observation_rows(raw, now):
    """Drop non-completed runs; reject eligible duplicate IDs, corrupt clocks."""
    if not isinstance(raw, list) or len(raw) > MAX_RUNS:
        raise ValueError("UNBOUNDED_ACTIONS_HISTORY")
    rows, seen = [], set()
    for run in raw:
        if not isinstance(run, dict):
            raise ValueError("INVALID_RUN")
        if (run.get("head_branch") != "main"
            or run.get("status") != "completed"
            or run.get("conclusion") not in ("success", "failure")
            or run.get("run_attempt") != 1):
            continue
        rid, wid = run.get("id"), run.get("workflow_id")
        if (type(rid) is not int or rid <= 0
            or type(wid) is not int or wid <= 0
            or rid in seen or run.get("event") not in EVENTS):
            raise ValueError("DUPLICATE_OR_INVALID_COMPLETED_RUN")
        seen.add(rid)
        created, started, updated = (stamp(run.get(k)) for k in
                                     ("created_at", "run_started_at", "updated_at"))
        if not (created <= started <= updated <= now):
            raise ValueError("RUN_CAUSAL_ORDER_INVALID")
        elapsed = (updated - started).total_seconds()
        if not 3 <= elapsed <= 7200:
            continue
        rows.append({"id": rid, "workflow_id": wid,
                     "created_at": created.isoformat(),
                     "event": run["event"],
                     "hour_bucket": created.hour // 6,
                     "duration_class": 0 if elapsed < 30 else 1 if elapsed < 120 else 2})
    return sorted(rows, key=lambda r: (r["created_at"], r["id"]))


def diversity(rows):
    families = Counter(r["workflow_id"] for r in rows)
    events = Counter(r["event"] for r in rows)
    windows = Counter(r["hour_bucket"] for r in rows)
    hidden = Counter(r["duration_class"] for r in rows)
    n = len(rows)
    if not n:
        return {"completed_runs": 0, "workflow_families": 0,
                "largest_family_share": None, "effective_family_count": 0.0,
                "workflow_entropy_bits": 0.0, "event_counts": {},
                "six_hour_windows": {}, "duration_proxy_classes": {}}
    probs = [c / n for c in families.values()]
    return {
        "completed_runs": n,
        "workflow_families": len(families),
        "largest_family_share": round(max(probs), 6),
        "effective_family_count": round(1 / sum(p*p for p in probs), 4),
        "workflow_entropy_bits": round(-sum(p * math.log2(p) for p in probs), 4),
        "event_counts": dict(sorted(events.items())),
        "six_hour_windows": {str(k): v for k, v in sorted(windows.items())},
        "duration_proxy_classes": {str(k): v for k, v in sorted(hidden.items())},
    }


def inspect(state, raw, now):
    """Three-level DovoD metadata audit, not training or proof of neural gain."""
    if now.tzinfo is None:
        raise ValueError("UNZONED_AUDIT_TIME")
    history = state_gate(state)
    rows = observation_rows(raw, now.astimezone(timezone.utc))
    if history:
        last_proof = history[-1]["independent_future_verification"]
        cutoff = stamp(last_proof.get("last_new_created_at"))
        before = [r for r in rows if stamp(r["created_at"]) <= cutoff]
        after = [r for r in rows if stamp(r["created_at"]) > cutoff]
    else:
        cutoff, before, after = None, rows, []
    baseline = diversity(before)
    new = diversity(after)
    novel_families = len({r["workflow_id"] for r in after} -
                         {r["workflow_id"] for r in before})
    ready = (cutoff is not None and len(after) >= MIN_NEW_AFTER_EXAM
             and new["workflow_families"] >= MIN_INDEPENDENT_FAMILIES
             and new["largest_family_share"] <= MAX_FAMILY_SHARE)
    # These are *design proposals* from archived source, not code activation.
    candidates = (
        {"family": "DOVOD_HIERARCHICAL_TEMPORAL_CONTEXT",
         "focus": "long_short_context_vs_workflow_family",
         "state": "PROPOSED_FOR_INDEPENDENT_TEST_ONLY"},
        {"family": "DOVOD_PHYSARUM_RESOURCE_MEMORY",
         "focus": "graph_resource_recovery_and_depletion",
         "state": "PROPOSED_FOR_INDEPENDENT_TEST_ONLY"},
        {"family": "DOVOD_ADAPTIVE_COMPLEXITY",
         "focus": "frozen_curriculum_heldout_difficulty_levels",
         "state": "PROPOSED_FOR_INDEPENDENT_TEST_ONLY"},
    )
    report = {
        "schema": SCHEMA, "repository": REPO, "observed_at_utc": now.isoformat(),
        "archival_sources": list(ARCHIVES),
        "research_state_sha256": state["state_sha256"],
        "raw_observations_sha256": sha(rows),
        "consumed_future_cutoff_utc": cutoff.isoformat() if cutoff else None,
        "before_consumed_cutoff": baseline, "new_since_consumed_exam": new,
        "new_workflow_families": novel_families,
        "observed_levels": {
            "meta_context": "workflow_family_concentration_and_entropy",
            "context": "event_and_6hour_window",
            "hidden_state": "completed_elapsed_time_proxy_only_not_future_label"},
        "candidate_test_designs": list(candidates),
        "status": ("RESEARCH_NEW_COHORT_STRUCTURALLY_DIVERSE_NOT_NEURAL_PASS"
                   if ready else "HOLD_TEMPORAL_EVIDENCE_INSUFFICIENT"),
        "separate_neural_prospective_exam_required": True,
        "independent_neural_gain_proven": False,
        "production_authority": False, "weights_updated": False,
        "source_code_executed_from_archives": False,
        "peer_input_executed": False, "automatic_module_activation": False,
        "next_generation_accepted_by_this_witness": False,
    }
    report["receipt_sha256"] = sha(report)
    return report


def api_runs(token):
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ValueError("MISSING_READONLY_GITHUB_TOKEN")
    out = []
    for page in range(1, 6):
        url = ("https://api.github.com/repos/" + REPO
               + "/actions/runs?branch=main&per_page=100&page=" + str(page))
        req = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": "Bearer " + token,
            "User-Agent": "JANUS-DovoD-TemporalWitness/3.1"})
        with urlopen(req, timeout=25) as response:
            packet = json.load(response)
        batch = packet.get("workflow_runs") if isinstance(packet, dict) else None
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError("GITHUB_RUNS_FORMAT_CHANGED")
        out.extend(batch)
        if len(batch) < 100:
            break
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--state", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--runs", help="Local offline fixture; production leaves unset")
    a = p.parse_args()
    state_path, out_path = Path(a.state), Path(a.out)
    if out_path.exists():
        raise ValueError("IMMUTABLE_WITNESS_RECEIPT_REQUIRED")
    if not state_path.is_file() or state_path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError("MISSING_OR_UNBOUNDED_NEURAL_STATE")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if a.runs:
        path = Path(a.runs)
        if path.stat().st_size > 2_000_000:
            raise ValueError("UNBOUNDED_FIXTURE")
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = api_runs(os.environ.get("GH_TOKEN"))
    report = inspect(state, raw, datetime.now(timezone.utc))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "new_since_exam": report["new_since_consumed_exam"]["completed_runs"],
                      "research_only": True, "receipt_sha256": report["receipt_sha256"]}))


if __name__ == "__main__":
    main()
