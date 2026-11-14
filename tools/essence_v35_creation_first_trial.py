#!/usr/bin/env python3
"""ESSENCE v3.5: memory-derived microkernel blueprints and prospective paired witness.

Reads sealed, append-preserving v3.3/Keymaster v3.2 research memories. Selects
reviewed *data-only* research blueprints from past negative results. A single
pre-registered executable microkernel (workflow-family shrinkage) is compared
with a frozen global-frequency control on the FIRST 64 completed eligible
GitHub Actions workflow runs CREATED strictly after the frozen Git commit.
No source-code generation, imported donor code, production model/weight changes,
automatic promotion, retrospective sample reselection or hidden retuning.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from tools import essence_v32_keymaster_memory as km
from tools import essence_v33_epistemic_exchange as spi

SCHEMA = "janus.essence.memory_guided_research_proposals/3.5"
FREEZE_SCHEMA = "janus.essence.memory_guided_prospective_freeze/3.5"
EXAM_SCHEMA = "janus.essence.memory_guided_prospective_exam/3.5"
REPO = "Hawkar-usls/Janus-Demiurge"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")
MAX_STATE_BYTES = 150_000
MAX_API_RUNS = 800
MIN_TRAIN = 180
MIN_TRAIN_FAMILIES = 8
FUTURE_COHORT = 64
MIN_FUTURE_FAMILIES = 8
MAX_FAMILY_SHARE = 0.40
MIN_POSITIVE_FAMILIES = 0.625
CLUSTER_T = 2.0
SHRINKAGE_ALPHA = 12  # source-reviewed, fixed before prospective outcomes
MAX_NLL = 30.0
ROOT = "0" * 64
EVENTS = frozenset(("push", "workflow_dispatch", "schedule", "workflow_run",
                    "pull_request", "repository_dispatch"))
NEGATIVE = {
    "DOVOD_SHA_25_OF_50_TEST_LEAKAGE": "temporal_train_test_firewall",
    "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114": "workflow_family_shrinkage_duration",
    "KEYMASTER_R2_REPLICATED_ABLATIONS": "unresolved_donor_authority_veto",
}
# Full API snapshots can repeat exact runs across unstable paginated pages.
FIELDS = ("id", "workflow_id", "head_branch", "event", "status", "conclusion",
          "run_attempt", "created_at", "run_started_at", "updated_at")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def source_engine_sha():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def at(value):
    if not isinstance(value, str):
        raise ValueError("UNTRUSTED_UNZONED_TIME")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("UNTRUSTED_TIME_FORMAT") from exc
    if dt.tzinfo is None:
        raise ValueError("UNTRUSTED_UNZONED_TIME")
    return dt.astimezone(timezone.utc)


def read_state(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or not 2 <= p.stat().st_size <= MAX_STATE_BYTES:
        raise ValueError("MISSING_OR_UNBOUNDED_RESEARCH_STATE")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def source_memory(epistemic, keymaster):
    spi.verify_state(epistemic)
    km.verify_state(keymaster)
    if not epistemic["history"] or not keymaster["history"]:
        raise ValueError("MISSING_VERIFIED_EXPERIENCE")
    last = epistemic["history"][-1]
    neg = last.get("negative_evidence")
    if not isinstance(neg, list) or len(neg) != len(NEGATIVE):
        raise ValueError("NEGATIVE_LESSON_SET_CHANGED")
    if {(x.get("id"), x.get("status")) for x in neg if isinstance(x, dict)} != {
        ("DOVOD_SHA_25_OF_50_TEST_LEAKAGE", "NEGATIVE_CONTROL_CONTAMINATED"),
        ("ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114", "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN"),
        ("KEYMASTER_R2_REPLICATED_ABLATIONS", "UNRESOLVED_EIGHT_CONTRIBUTORS")
    }:
        raise ValueError("NEGATIVE_CONTROL_SILENTLY_REWRITTEN")
    if len(last["scout_identities"]) != 17 or (
        keymaster["history"][-1].get("keymaster_guard")
        != "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION"):
        raise ValueError("UNVERIFIED_KEYMASTER_OR_SCOUT_STATE")
    if keymaster["history"][-1].get("verified_local_lessons", 0) < 1:
        raise ValueError("NO_TARGET_LOCAL_VERIFIED_LESSONS")
    return {
        "epistemic_state_sha256": epistemic["state_sha256"],
        "keymaster_state_sha256": keymaster["state_sha256"],
        "epistemic_last_receipt_sha256": last["receipt_sha256"],
        "keymaster_last_receipt_sha256": keymaster["history"][-1]["receipt_sha256"],
        "scout_count": len(last["scout_identities"]),
        "negative_result_ids": sorted(x["id"] for x in neg),
        "source_evidence_status": "INTERNAL_HASH_LINKED_RESEARCH_NOT_EXTERNAL_ATTESTATION",
    }


def propose(memory):
    if sorted(memory.get("negative_result_ids", [])) != sorted(NEGATIVE):
        raise ValueError("NO_SOURCE_BOUND_LESSON")
    if memory.get("scout_count") != 17:
        raise ValueError("SCOUT_INHERITANCE_INCOMPLETE")
    definitions = (
        ("temporal_train_test_firewall", "NO_TRAIN_TEST_OVERLAP",
         "DOVOD_SHA_25_OF_50_TEST_LEAKAGE", "RESEARCH_GATE_ONLY"),
        ("workflow_family_shrinkage_duration", "WORKFLOW_CONDITIONAL_DURATION_PRIOR",
         "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114", "EXECUTABLE_STDLIB_PROSPECTIVE"),
        ("unresolved_donor_authority_veto", "HOLD_UNKNOWN_DONOR_CAUSALITY",
         "KEYMASTER_R2_REPLICATED_ABLATIONS", "RESEARCH_GATE_ONLY"),
    )
    blueprints = []
    for ident, op, source_id, mode in definitions:
        body = {
            "id": ident, "generation": 0, "parent_microkernel": "ESSENCE_V33_EPISTEMIC_EXCHANGE",
            "source_negative_result": source_id,
            "source_memory_sha256": memory["epistemic_state_sha256"],
            "operator": op, "mode": mode,
            "lesson_preserved": True, "review_required": True,
            "tested_for_generalization": False,
            "auto_code_execution": False, "production_authority": False,
        }
        blueprints.append(dict(body, candidate_sha256=sha(body)))
    return blueprints


def api_runs(token):
    if not token or len(token) > 4096:
        raise ValueError("GITHUB_READ_TOKEN_MISSING")
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "JANUS-Essence-MemoryGuided-3.4",
    }
    seen = {}
    for page in range(1, 9):
        url = (f"https://api.github.com/repos/{REPO}/actions/runs"
               f"?branch=main&per_page=100&page={page}")
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            raw = json.load(response)
        batch = raw.get("workflow_runs") if isinstance(raw, dict) else None
        if not isinstance(batch, list) or len(batch) > 100:
            raise ValueError("UNTRUSTED_GITHUB_API_PAGE")
        for x in batch:
            if not isinstance(x, dict):
                raise ValueError("GITHUB_RUN_NOT_OBJECT")
            ident = x.get("id")
            if type(ident) is not int or ident < 1:
                raise ValueError("GITHUB_RUN_ID_INVALID")
            fields = {k: x.get(k) for k in FIELDS}
            if ident in seen and fields != seen[ident]:
                raise ValueError("CONFLICTING_PAGINATED_RUN")
            seen[ident] = fields
        if len(batch) < 100:
            break
    if len(seen) > MAX_API_RUNS:
        raise ValueError("UNBOUNDED_GITHUB_RUNS")
    return list(seen.values())


def source_rows(runs, observed_at):
    now = at(observed_at)
    if not isinstance(runs, list) or len(runs) > MAX_API_RUNS:
        raise ValueError("UNTRUSTED_GITHUB_RUN_SET")
    ids = {}
    out = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("GITHUB_ROW_OBJECT_REQUIRED")
        rid = run.get("id")
        wid = run.get("workflow_id")
        if type(rid) is not int or rid <= 0:
            raise ValueError("GITHUB_RUN_ID_INVALID")
        if rid in ids:
            if ids[rid] != {k: run.get(k) for k in FIELDS}:
                raise ValueError("CONFLICTING_DUPLICATE_RUN")
            continue
        ids[rid] = {k: run.get(k) for k in FIELDS}
        if not (type(wid) is int and wid > 0 and
                run.get("status") == "completed" and
                run.get("conclusion") in ("success", "failure") and
                run.get("head_branch") == "main" and
                run.get("run_attempt") == 1 and
                run.get("event") in EVENTS):
            continue
        created, started, updated = (at(run.get(k)) for k in
                                    ("created_at", "run_started_at", "updated_at"))
        duration = (updated - started).total_seconds()
        if not (created <= started <= updated <= now and 3 <= duration <= 7200):
            continue
        label = 0 if duration < 30 else 1 if duration < 120 else 2
        out.append({
            "run_id": rid, "workflow_id": wid, "created_at": created.isoformat(),
            "updated_at": updated.isoformat(), "class": label,
        })
    return sorted(out, key=lambda x: (x["created_at"], x["run_id"]))



def future_slots(runs, observed_at):
    """Pre-outcome cohort eligibility: a run slot exists even if still queued.

    Every attempt-1 main-branch workflow is eligible by its *created_at* and
    pre-run identity, not by duration/terminal success. Missing, cancelled,
    failed or delayed outcomes cannot be replaced by more convenient runs.
    """
    now = at(observed_at)
    if not isinstance(runs, list) or len(runs) > MAX_API_RUNS:
        raise ValueError("UNTRUSTED_FUTURE_SOURCE_ROWS")
    seen = {}
    rows = []
    known_status = {"queued", "requested", "waiting", "pending", "in_progress",
                    "completed"}
    for x in runs:
        if not isinstance(x, dict) or type(x.get("id")) is not int or x["id"] <= 0:
            raise ValueError("FUTURE_RUN_ID_INVALID")
        meta = {key: x.get(key) for key in FIELDS}
        if x["id"] in seen:
            if seen[x["id"]] != meta:
                raise ValueError("FUTURE_RUN_DUPLICATE_CONFLICT")
            continue
        seen[x["id"]] = meta
        if not (type(x.get("workflow_id")) is int and x["workflow_id"] > 0
                and x.get("head_branch") == "main"
                and x.get("run_attempt") == 1
                and x.get("event") in EVENTS):
            continue
        created = at(x.get("created_at"))
        if created > now or x.get("status") not in known_status:
            raise ValueError("FUTURE_SOURCE_TIMESTAMP_OR_STATUS_UNTRUSTED")
        value = {
            "run_id": x["id"], "workflow_id": x["workflow_id"],
            "created_at": created.isoformat(),
            "status": x["status"], "class": None,
            "terminal_invalid": False,
        }
        if x["status"] == "completed":
            if x.get("conclusion") not in ("success", "failure"):
                value["terminal_invalid"] = True
            else:
                try:
                    started = at(x.get("run_started_at"))
                    updated = at(x.get("updated_at"))
                    duration = (updated - started).total_seconds()
                    if not (created <= started <= updated <= now
                            and 3 <= duration <= 7200):
                        value["terminal_invalid"] = True
                    else:
                        value["class"] = 0 if duration < 30 else 1 if duration < 120 else 2
                except ValueError:
                    value["terminal_invalid"] = True
        rows.append(value)
    return sorted(rows, key=lambda x: (x["created_at"], x["run_id"]))


def cohort_key(row):
    return {"run_id": row["run_id"], "workflow_id": row["workflow_id"],
            "created_at": row["created_at"]}


def cohort_manifest(target, packet):
    if len(target) != FUTURE_COHORT:
        raise ValueError("FUTURE_COHORT_NOT_FULL")
    body = {
        "schema": "janus.essence.creation_first_immutable_cohort/3.5",
        "freeze_sha256": packet["freeze_sha256"],
        "cohort_size": FUTURE_COHORT,
        "run_keys": [cohort_key(row) for row in target],
        "frozen_without_outcomes": True,
        "source_is_not_independent_lab": True,
    }
    return dict(body, cohort_sha256=sha(body))


def check_cohort(cohort, packet):
    if (not isinstance(cohort, dict) or
        cohort.get("schema") != "janus.essence.creation_first_immutable_cohort/3.5" or
        cohort.get("freeze_sha256") != packet["freeze_sha256"] or
        cohort.get("cohort_size") != FUTURE_COHORT or
        cohort.get("frozen_without_outcomes") is not True or
        cohort.get("source_is_not_independent_lab") is not True or
        cohort.get("cohort_sha256") != sha({
            k: v for k, v in cohort.items() if k != "cohort_sha256"})):
        raise ValueError("TAMPERED_IMMUTABLE_COHORT")
    keys = cohort.get("run_keys")
    if (not isinstance(keys, list) or len(keys) != FUTURE_COHORT
        or len({x.get("run_id") for x in keys if isinstance(x, dict)}) != FUTURE_COHORT):
        raise ValueError("INVALID_FROZEN_RUN_IDS")
    for x in keys:
        if (not isinstance(x, dict) or set(x) != {"run_id", "workflow_id", "created_at"}
            or type(x["run_id"]) is not int or x["run_id"] <= 0
            or type(x["workflow_id"]) is not int or x["workflow_id"] <= 0):
            raise ValueError("INVALID_FROZEN_RUN_KEY")
        at(x["created_at"])
    return True


def counts(rows):
    count = [1, 1, 1]  # reviewed, fixed Dirichlet(1) baseline
    for row in rows:
        count[row["class"]] += 1
    total = sum(count)
    return [n / total for n in count]


def build_models(training):
    if len(training) < MIN_TRAIN:
        raise ValueError("HOLD_TOO_FEW_PRE_FREEZE_REAL_EVENTS")
    by = defaultdict(list)
    for row in training:
        by[row["workflow_id"]].append(row)
    if len(by) < MIN_TRAIN_FAMILIES:
        raise ValueError("HOLD_TOO_FEW_TRAIN_FAMILIES")
    global_prior = counts(training)
    local = {str(wid): [sum(r["class"] == cat for r in rows)
                        for cat in range(3)] for wid, rows in by.items()}
    return {
        "baseline": {"operator": "global_laplace_frequency", "prior": global_prior},
        "candidate": {"operator": "workflow_family_shrinkage_duration",
                      "prior": global_prior, "alpha": SHRINKAGE_ALPHA,
                      "workflow_counts": local},
        "train_count": len(training), "train_workflow_families": len(by),
    }


def probabilities(model, wid):
    p = model["prior"]
    if model["operator"] == "global_laplace_frequency":
        return p
    if model["operator"] != "workflow_family_shrinkage_duration" or (
        model.get("alpha") != SHRINKAGE_ALPHA):
        raise ValueError("UNREVIEWED_CANDIDATE_OPERATOR")
    local = model["workflow_counts"].get(str(wid), (0, 0, 0))
    if len(local) != 3 or any(type(x) is not int or x < 0 for x in local):
        raise ValueError("UNTRUSTED_LOCAL_COUNTS")
    total = sum(local) + SHRINKAGE_ALPHA
    return [(local[k] + SHRINKAGE_ALPHA * p[k]) / total for k in range(3)]


def validate_freeze(packet):
    if not isinstance(packet, dict) or packet.get("schema") != FREEZE_SCHEMA:
        raise ValueError("FROZEN_CANDIDATE_SCHEMA")
    if packet.get("freeze_sha256") != sha({
        k: v for k, v in packet.items() if k != "freeze_sha256"
    }):
        raise ValueError("FROZEN_CANDIDATE_TAMPERED")
    if packet.get("engine_sha256") != source_engine_sha():
        raise ValueError("ENGINE_CHANGED_AFTER_FREEZE_REVIEW_REQUIRED")
    if packet.get("production_authority") is not False or packet.get(
            "future_labels_used_in_training") is not False:
        raise ValueError("FROZEN_AUTHORITY_ESCALATION")
    if packet.get("fixed_future_cohort_size") != FUTURE_COHORT or (
            packet.get("selected_candidate_id") != "workflow_family_shrinkage_duration"):
        raise ValueError("FROZEN_PROPOSAL_OR_COHORT_DRIFT")
    if packet.get("research_only") is not True:
        raise ValueError("FROZEN_RESEARCH_MODE_REQUIRED")
    models = packet.get("models") or {}
    baseline = models.get("baseline") or {}
    candidate = models.get("candidate") or {}
    if (baseline.get("operator") != "global_laplace_frequency"
        or candidate.get("operator") != "workflow_family_shrinkage_duration"
        or candidate.get("alpha") != SHRINKAGE_ALPHA
        or baseline.get("prior") != candidate.get("prior")):
        raise ValueError("FROZEN_MODEL_DRIFT")
    for p in (baseline.get("prior"), candidate.get("prior")):
        if (not isinstance(p, list) or len(p) != 3
            or any(type(x) is not float or not 0 < x < 1 for x in p)
            or abs(sum(p) - 1.0) > 1e-10):
            raise ValueError("FROZEN_PROBABILITIES_INVALID")
    for k, value in (candidate.get("workflow_counts") or {}).items():
        if (not k.isdigit() or len(value) != 3
            or any(type(x) is not int or x < 0 for x in value)):
            raise ValueError("FROZEN_WORKFLOW_COUNTS_INVALID")
    if models.get("train_count", 0) < MIN_TRAIN or models.get(
            "train_workflow_families", 0) < MIN_TRAIN_FAMILIES:
        raise ValueError("FROZEN_TRAIN_COHORT_INVALID")
    return True


def freeze(epistemic, keymaster, runs, *, observed_at, source_commits):
    current = at(observed_at)
    if (not isinstance(source_commits, dict) or
        set(source_commits) != {"epistemic", "keymaster"} or
        not all(SHA40.fullmatch(str(v)) for v in source_commits.values())):
        raise ValueError("SOURCE_MEMORY_GIT_COMMITS_REQUIRED")
    memory = source_memory(epistemic, keymaster)
    blueprints = propose(memory)
    rows = source_rows(runs, observed_at)
    history = [r for r in rows if at(r["updated_at"]) < current]
    models = build_models(history)
    baseline = models["baseline"]
    cand = models["candidate"]
    # Frozen candidate and baseline are *not* tuned using a known future
    # validation loss. The first 64 future run IDs are the registered target.
    packet = {
        "schema": FREEZE_SCHEMA, "status": "FROZEN_AWAITING_FUTURE_EVENTS",
        "repository": REPO, "research_only": True,
        "engine_sha256": source_engine_sha(),
        "memory_evidence": memory, "memory_source_commits": source_commits,
        "candidate_blueprints": blueprints,
        "selected_candidate_id": "workflow_family_shrinkage_duration",
        "models": models, "sealed_at": observed_at,
        "latest_training_updated_at": max(r["updated_at"] for r in history),
        "training_rows_sha256": sha(history),
        "fixed_future_cohort_size": FUTURE_COHORT,
        "fixed_future_diversity_min_families": MIN_FUTURE_FAMILIES,
        "fixed_future_largest_family_share_max": MAX_FAMILY_SHARE,
        "paired_cluster_t_multiplier": CLUSTER_T,
        "minimum_mean_nll_gain": 0.02,
        "minimum_positive_workflow_family_fraction": MIN_POSITIVE_FAMILIES,
        "baseline_does_not_read_memory": True,
        "future_labels_used_in_training": False,
        "neural_weights_changed": False,
        "production_authority": False, "automatic_module_activation": False,
        "scientific_independence_claimed": False,
    }
    packet["freeze_sha256"] = sha(packet)
    validate_freeze(packet)
    receipt = {
        "schema": SCHEMA, "status": "FROZEN_BLUEPRINTS_NO_FUTURE_TEST",
        "frozen_packet_sha256": packet["freeze_sha256"],
        "proposed_microkernel_count": len(blueprints),
        "prospective_tested_count": 0, "prior_completed_runs": len(history),
        "training_workflow_families": models["train_workflow_families"],
        "model_weights_updated": False, "production_authority": False,
    }
    receipt["receipt_sha256"] = sha(receipt)
    return packet, receipt


def mean_sd_lower(values):
    n = len(values)
    if n < 2:
        raise ValueError("PAIRED_SAMPLE_TOO_SMALL")
    avg = sum(values) / n
    sd = math.sqrt(sum((x - avg) ** 2 for x in values) / (n - 1))
    return avg, avg - CLUSTER_T * sd / math.sqrt(n)


def evaluate(packet, runs, *, observed_at, published_at, cohort=None):
    validate_freeze(packet)
    now, freeze_date, published = (at(x) for x in
                                   (observed_at, packet["sealed_at"], published_at))
    if not (freeze_date <= published <= now):
        raise ValueError("INVALID_FUTURE_GIT_PUBLICATION_TIMESTAMP")
    if at(packet["latest_training_updated_at"]) >= freeze_date:
        raise ValueError("TRAINING_OUTCOME_AFTER_FREEZE")
    # Select by *creation* before consulting any outcome. The first 64
    # eligible run identities are precommitted; slow/cancelled runs cannot
    # disappear to make the candidate look better.
    slots = future_slots(runs, observed_at)
    future = [r for r in slots if at(r["created_at"]) > published]
    first = future[:FUTURE_COHORT]
    report = {
        "schema": EXAM_SCHEMA, "freeze_sha256": packet["freeze_sha256"],
        "frozen_git_published_at": published.isoformat(),
        "observed_at": now.isoformat(), "research_only": True,
        "precommitted_first_n_future_events": FUTURE_COHORT,
        "future_records_observed": len(first),
        "cohort_eligibility": "CREATED_AFTER_FREEZE_REGARDLESS_OF_OUTCOME_STATUS",
        "future_created_strictly_after_git_freeze": True,
        "future_labels_visible_to_candidate_training": False,
        "scientific_independence_claimed": False,
        "production_authority": False, "model_weights_updated": False,
        "candidate_code_changed_after_freeze": False,
    }
    if (len(runs) >= MAX_API_RUNS and slots
        and min(at(r["created_at"]) for r in slots) > published):
        report["status"] = "HOLD_FUTURE_API_LOOKBACK_CANNOT_PROVE_FIRST_RUNS"
    elif len(first) < FUTURE_COHORT:
        report["status"] = "HOLD_AWAITING_FIRST_64_CREATED_RUNS"
        report["remaining"] = FUTURE_COHORT - len(first)
    else:
        observed_manifest = cohort_manifest(first, packet)
        if cohort is not None:
            check_cohort(cohort, packet)
            if cohort["run_keys"] != observed_manifest["run_keys"]:
                report["status"] = "HOLD_GITHUB_FROZEN_COHORT_IDENTITY_DRIFT"
        else:
            cohort = observed_manifest
        if "status" not in report:
            report["frozen_cohort_sha256"] = cohort["cohort_sha256"]
            report["cohort_manifest"] = cohort
            report["first_future_run_id"] = first[0]["run_id"]
            report["last_future_run_id"] = first[-1]["run_id"]
            pending = sum(row["status"] != "completed" for row in first)
            invalid = sum(row["terminal_invalid"] for row in first)
            report["pending_future_outcomes"] = pending
            report["invalid_terminal_future_outcomes"] = invalid
            if invalid:
                report["status"] = "HOLD_FIXED_COHORT_UNSCORABLE_TERMINAL"
                report["candidate_gain_proven"] = False
            elif pending:
                report["status"] = "HOLD_AWAITING_64_FIXED_COHORT_OUTCOMES"
            else:
                by = defaultdict(list)
                for idx, row in enumerate(first):
                    by[row["workflow_id"]].append(idx)
                family_share = max(len(indices) for indices in by.values()) / FUTURE_COHORT
                report["workflow_families"] = len(by)
                report["largest_workflow_share"] = family_share
                if (len(by) < MIN_FUTURE_FAMILIES or
                    family_share > MAX_FAMILY_SHARE):
                    report["status"] = "HOLD_FIXED_FUTURE_FAMILY_CONCENTRATION"
                    report["candidate_gain_proven"] = False
                else:
                    base, child = packet["models"]["baseline"], packet["models"]["candidate"]
                    base_losses, child_losses = [], []
                    bacc = cacc = 0
                    for row in first:
                        b = probabilities(base, row["workflow_id"])
                        c = probabilities(child, row["workflow_id"])
                        label = row["class"]
                        base_losses.append(-math.log(max(b[label], 1e-12)))
                        child_losses.append(-math.log(max(c[label], 1e-12)))
                        bacc += (max(range(3), key=lambda k: b[k]) == label)
                        cacc += (max(range(3), key=lambda k: c[k]) == label)
                    differences = [b-c for b,c in zip(base_losses, child_losses)]
                    run_mean, run_lower = mean_sd_lower(differences)
                    family_means = [sum(differences[i] for i in indices) / len(indices)
                                    for _, indices in sorted(by.items())]
                    family_mean, family_lower = mean_sd_lower(family_means)
                    positive_share = sum(x > 0 for x in family_means) / len(family_means)
                    base_acc, child_acc = bacc/FUTURE_COHORT, cacc/FUTURE_COHORT
                    passed = (run_mean >= 0.02 and run_lower > 0
                              and family_mean >= 0.02 and family_lower > 0
                              and positive_share >= MIN_POSITIVE_FAMILIES
                              and child_acc >= base_acc - 0.01)
                    report.update({
                        "status": "RESEARCH_PASS_INTERNAL_PROSPECTIVE_PAIRED"
                        if passed else "HOLD_NO_PROSPECTIVE_MEMORY_GAIN",
                        "baseline_nll": sum(base_losses)/FUTURE_COHORT,
                        "candidate_nll": sum(child_losses)/FUTURE_COHORT,
                        "baseline_accuracy": base_acc, "candidate_accuracy": child_acc,
                        "paired_run_nll_gain": run_mean,
                        "paired_run_conservative_lower_bound": run_lower,
                        "paired_workflow_family_mean_gain": family_mean,
                        "paired_workflow_family_lower_bound": family_lower,
                        "positive_workflow_fraction": positive_share,
                        "candidate_gain_proven": passed,
                        "source_of_targets": "GH_ACTIONS_FIRST_64_CREATED_AFTER_GIT_FREEZE",
                        "evaluation_subset_selected_after_scoring": False,
                        "automatic_production_promotion": False,
                    })
    report["receipt_sha256"] = sha(report)
    return report


def immutable_write(path, obj):
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise ValueError("IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, sort_keys=True, indent=2,
                                 ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("freeze", "evaluate"))
    p.add_argument("--epistemic")
    p.add_argument("--keymaster")
    p.add_argument("--epistemic-commit")
    p.add_argument("--keymaster-commit")
    p.add_argument("--freeze")
    p.add_argument("--freeze-out")
    p.add_argument("--published-at")
    p.add_argument("--cohort")
    p.add_argument("--cohort-out")
    p.add_argument("--receipt", required=True)
    a = p.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    runs = api_runs(os.environ.get("GH_TOKEN"))
    if a.mode == "freeze":
        data, receipt = freeze(
            read_state(a.epistemic), read_state(a.keymaster), runs,
            observed_at=now,
            source_commits={"epistemic": a.epistemic_commit,
                            "keymaster": a.keymaster_commit},
        )
        immutable_write(a.freeze_out, data)
    else:
        old_cohort = read_state(a.cohort) if a.cohort and Path(a.cohort).exists() else None
        receipt = evaluate(read_state(a.freeze), runs, observed_at=now,
                           published_at=a.published_at, cohort=old_cohort)
        if old_cohort is None and receipt.get("cohort_manifest") is not None:
            immutable_write(a.cohort_out, receipt["cohort_manifest"])
    immutable_write(a.receipt, receipt)
    print(json.dumps({
        "status": receipt["status"],
        "memory_generated_blueprints": receipt.get("proposed_microkernel_count", 3),
        "future_evaluated": receipt.get("future_records_observed", 0),
        "production_authority": False,
        "receipt_sha256": receipt["receipt_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
