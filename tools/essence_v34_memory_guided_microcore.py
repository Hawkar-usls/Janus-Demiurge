#!/usr/bin/env python3
"""ESSENCE v3.4: memory-guided *research* microkernel, frozen prospective pair.

Consumes existing sealed ESSENCE v3.2 and v3.3 memory, proposes bounded
blueprints, and executes one deterministic DovoD-inspired temporal microkernel
against a frozen global-prior baseline. Labels come only from real GitHub
Actions runs CREATED AFTER the candidate state was committed on GitHub.

The candidate is a conventional smoothed frequency estimator, not original
mathematics or a neural model. No auto-merge, training on holdout, production
model promotion, or claim of external independent replication.
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
from urllib.request import Request, urlopen

from tools import essence_v32_keymaster_memory as keymaster
from tools import essence_v33_epistemic_exchange as epistemic

SCHEMA = "janus.essence.memory_guided_prospective_microcore/3.4"
REPO = "Hawkar-usls/Janus-Demiurge"
SOURCE_URL = "https://api.github.com/repos/" + REPO + "/actions/runs"
MAX_API_PAGES = 8
MAX_ROWS = MAX_API_PAGES * 100
MAX_WORKFLOWS = 160
MIN_HISTORICAL = 160
MIN_HISTORICAL_FAMILIES = 8
MIN_FUTURE = 48
MIN_FUTURE_FAMILIES = 8
MAX_FAMILY_SHARE = 0.40
MIN_FAMILY_POSITIVE = 0.625
MIN_MEAN_GAIN = 0.02
CLUSTER_MULTIPLIER = 2.0
ALLOWED_EVENTS = frozenset((
    "push", "workflow_dispatch", "schedule", "pull_request",
    "workflow_run", "repository_dispatch",
))
SHA40 = __import__("re").compile(r"^[a-f0-9]{40}$")
SHA64 = __import__("re").compile(r"^[a-f0-9]{64}$")
LABELS = 3
CONFIG = {"operator": "dovod_hierarchical_duration_prior_v1",
          "alpha_workflow": 8, "alpha_event": 16,
          "workflow_weight": 0.70, "event_weight": 0.20,
          "global_weight": 0.10, "required_workflow_examples": 5}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=False).encode("utf-8")


def seal(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def utc(value):
    if not isinstance(value, str):
        raise ValueError("TIME_NOT_STRING")
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("TIME_FORMAT_HOLD") from exc
    if t.tzinfo is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return t.astimezone(timezone.utc)


def require(cond, code):
    if not cond:
        raise ValueError(code)


def rows_from_api(runs, now):
    require(isinstance(runs, list) and len(runs) <= MAX_ROWS,
            "UNTRUSTED_ACTIONS_HISTORY_LIMIT")
    if isinstance(now, str):
        now = utc(now)
    require(now.tzinfo is not None, "NOW_UNZONED")
    seen = {}
    for item in runs:
        if not isinstance(item, dict) or item.get("head_branch") != "main":
            continue
        ident, family = item.get("id"), item.get("workflow_id")
        if (type(ident) is not int or type(family) is not int
                or ident <= 0 or family <= 0
                or item.get("status") != "completed"
                or item.get("run_attempt") != 1
                or item.get("conclusion") not in ("success", "failure")
                or item.get("event") not in ALLOWED_EVENTS):
            continue
        created, started, updated = (
            utc(item.get(k)) for k in ("created_at", "run_started_at", "updated_at"))
        duration = (updated - started).total_seconds()
        if (created > now or updated > now or started < created
                or not 3 <= duration <= 7200):
            continue
        label = 0 if duration < 30 else (1 if duration < 120 else 2)
        row = {
            "id": ident, "workflow_id": family, "event": item["event"],
            "created_at": created.isoformat(), "label": label,
            "duration_proxy": int(duration),
        }
        if ident in seen and seen[ident] != row:
            raise ValueError("DUPLICATE_RUN_MUTATED_DURING_PAGINATION")
        seen[ident] = row
    return sorted(seen.values(), key=lambda x: (x["created_at"], x["id"]))


def api_runs(token):
    require(isinstance(token, str) and 1 <= len(token) <= 4096,
            "GITHUB_READ_TOKEN_REQUIRED")
    output = []
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ESSENCE-Memory-Guided-Prospective-v3.4",
    }
    for n in range(1, MAX_API_PAGES + 1):
        req = Request(SOURCE_URL +
                      "?branch=main&per_page=100&page=" + str(n), headers=headers)
        with urlopen(req, timeout=30) as response:
            page = json.load(response)
        batch = page.get("workflow_runs") if isinstance(page, dict) else None
        require(isinstance(batch, list) and len(batch) <= 100,
                "INVALID_GITHUB_RUNS_RESPONSE")
        output.extend(batch)
        if len(batch) < 100:
            break
    return output


def verified_memories(v32, v33, outcomes):
    # Fail closed: separate memory contracts are not proof of scientific gain.
    keymaster.verify_state(v32)
    epistemic.verify_state(v33)
    lessons = keymaster.check_outcomes(outcomes)
    require(bool(v32["history"]) and bool(v33["history"]),
            "EMPTY_VERIFIED_MEMORIES")
    k = v32["history"][-1]
    e = v33["history"][-1]
    negatives = {x.get("id"): x.get("status")
                 for x in e.get("negative_evidence", []) if isinstance(x, dict)}
    expected = {
        "DOVOD_SHA_25_OF_50_TEST_LEAKAGE": "NEGATIVE_CONTROL_CONTAMINATED",
        "ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114":
            "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN",
        "KEYMASTER_R2_REPLICATED_ABLATIONS":
            "UNRESOLVED_EIGHT_CONTRIBUTORS",
    }
    require(all(negatives.get(a) == b for a, b in expected.items()),
            "MEMORY_NEGATIVE_CONTROLS_MISSING")
    require(k.get("donor_count") == 8
            and k.get("keymaster_guard") == "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION"
            and k.get("verified_local_lessons") == len(lessons)
            and k.get("training_admission") is False
            and k.get("authority_delta") == 0
            and e.get("decision") == "INTEGRATED_LESSON_NOT_ASCENDED"
            and len(e.get("scout_identities", [])) == 17,
            "MEMORY_INHERITED_AUTHORITY_HOLD")
    require(bool(lessons), "NO_VERIFIED_LOCAL_LESSON_FOR_CANDIDATE")
    return {
        "keymaster_state_sha256": v32["state_sha256"],
        "epistemic_state_sha256": v33["state_sha256"],
        "source_lesson_record_sha256": lessons[0]["record_sha256"],
        "source_lesson_proposal_sha256": lessons[0]["proposal_sha256"],
        "negative_controls": sorted(expected),
        "scout_identities": list(e["scout_identities"]),
    }


def blueprints(mem):
    # These are *actual proposals selected from provenance-bound memory*.
    # Only the duration operator is implemented and compared in research.
    return [
        {"id": "dovod_hierarchical_duration_prior_v1",
         "kind": "EXECUTABLE_RESEARCH_MICROKERNEL",
         "operator": CONFIG["operator"],
         "source_control": "DOVOD_SHA_25_OF_50_TEST_LEAKAGE",
         "development_only": False,
         "training_requires_postfreeze_targets": False,
         "model_weights_modified": False},
        {"id": "keymaster_unresolved_donor_veto_v1",
         "kind": "DATA_ONLY_BLUEPRINT_NOT_EXECUTED",
         "source_control": "KEYMASTER_R2_REPLICATED_ABLATIONS",
         "development_only": True,
         "production_authority": False},
        {"id": "verified_repair_lineage_memory_v1",
         "kind": "DATA_ONLY_BLUEPRINT_NOT_EXECUTED",
         "source_control": mem["source_lesson_record_sha256"],
         "development_only": True,
         "production_authority": False},
    ]


def count_priors(rows):
    require(len(rows) >= MIN_HISTORICAL, "INSUFFICIENT_HISTORICAL_TRAINING_RUNS")
    families = {x["workflow_id"] for x in rows}
    require(len(families) >= MIN_HISTORICAL_FAMILIES,
            "INSUFFICIENT_HISTORICAL_WORKFLOW_FAMILIES")
    require(len(rows) == len({x["id"] for x in rows}),
            "DUPLICATE_TRAINING_RUNS")
    counts = [0] * LABELS
    workflow, event = {}, {}
    for row in rows:
        label = row["label"]
        require(type(label) is int and 0 <= label < LABELS, "INVALID_TRAIN_LABEL")
        counts[label] += 1
        k = str(row["workflow_id"])
        if k not in workflow:
            workflow[k] = [0] * LABELS
        if row["event"] not in event:
            event[row["event"]] = [0] * LABELS
        workflow[k][label] += 1
        event[row["event"]][label] += 1
    require(len(workflow) <= MAX_WORKFLOWS, "UNBOUNDED_WORKFLOW_FAMILY")
    require(sum(1 for a in counts if a >= 5) >= 2,
            "LOW_INFORMATION_TRAINING_LABELS")
    return {"global": counts, "workflow": dict(sorted(workflow.items())),
            "event": dict(sorted(event.items()))}


def global_prior(counts):
    n = sum(counts)
    return [(v + 1) / (n + LABELS) for v in counts]


def smoothed(counts, prior, alpha):
    n = sum(counts)
    return [(counts[i] + alpha * prior[i]) / (n + alpha)
            for i in range(LABELS)]


def predict(model, row, *, use_memory):
    global_p = global_prior(model["global"])
    if not use_memory:
        return global_p
    wf = model["workflow"].get(str(row["workflow_id"]), [0] * LABELS)
    if sum(wf) < CONFIG["required_workflow_examples"]:
        wf_p = global_p
    else:
        wf_p = smoothed(wf, global_p, CONFIG["alpha_workflow"])
    ev = model["event"].get(row["event"], [0] * LABELS)
    ev_p = smoothed(ev, global_p, CONFIG["alpha_event"])
    out = [CONFIG["workflow_weight"] * wf_p[i]
           + CONFIG["event_weight"] * ev_p[i]
           + CONFIG["global_weight"] * global_p[i]
           for i in range(LABELS)]
    require(abs(sum(out) - 1.0) < 1e-9 and all(0 < p < 1 for p in out),
            "PREDICTION_INVALID_PROBABILITIES")
    return out


def scored_pair(model, rows):
    diffs = []
    old_losses, new_losses = [], []
    by_family = defaultdict(list)
    base_correct = child_correct = 0
    for row in rows:
        old, new = predict(model, row, use_memory=False), predict(
            model, row, use_memory=True)
        y = row["label"]
        a, b = -math.log(old[y]), -math.log(new[y])
        old_losses.append(a)
        new_losses.append(b)
        diffs.append(a - b)
        by_family[row["workflow_id"]].append(a - b)
        base_correct += max(range(LABELS), key=lambda i: old[i]) == y
        child_correct += max(range(LABELS), key=lambda i: new[i]) == y
    n = len(rows)
    mean = sum(diffs) / n
    var = sum((x - mean) ** 2 for x in diffs) / (n - 1)
    lower = mean - 1.645 * math.sqrt(var / n)
    means = [sum(items) / len(items) for _, items in sorted(by_family.items())]
    k = len(means)
    cl_mean = sum(means) / k
    cl_var = sum((x - cl_mean) ** 2 for x in means) / (k - 1)
    cl_lower = cl_mean - CLUSTER_MULTIPLIER * math.sqrt(cl_var / k)
    positive_share = sum(v > 0 for v in means) / k
    accepted = (mean >= MIN_MEAN_GAIN and lower > 0
                and cl_mean >= MIN_MEAN_GAIN and cl_lower > 0
                and positive_share >= MIN_FAMILY_POSITIVE
                and child_correct / n >= base_correct / n - 0.01)
    return {
        "sample_count": n,
        "workflow_clusters": k,
        "largest_workflow_share": max(map(len, by_family.values())) / n,
        "baseline_nll": sum(old_losses) / n,
        "memory_candidate_nll": sum(new_losses) / n,
        "baseline_accuracy": base_correct / n,
        "memory_candidate_accuracy": child_correct / n,
        "paired_nll_gain": mean,
        "paired_95pct_run_lower_bound": lower,
        "equal_weight_workflow_gain": cl_mean,
        "conservative_workflow_cluster_lower_bound": cl_lower,
        "positive_workflow_share": positive_share,
        "passes_predeclared_internal_gate": accepted,
        "baseline_and_candidate_evaluated_on_exact_same_runs": True,
        "independent_external_laboratory": False,
    }


def empty_state():
    state = {
        "schema": SCHEMA, "repository": REPO,
        "status": "UNINITIALIZED", "pending": None, "verdict": None,
        "research_only": True, "production_authority": False,
    }
    return dict(state, state_sha256=seal(state))


def check_state(state):
    require(isinstance(state, dict) and state.get("schema") == SCHEMA
            and state.get("repository") == REPO
            and state.get("research_only") is True
            and state.get("production_authority") is False
            and state.get("state_sha256") == seal({
                k: v for k, v in state.items() if k != "state_sha256"}),
            "MICROCORE_STATE_TAMPERED")
    require(state.get("status") in (
        "UNINITIALIZED", "FROZEN_AWAITING_FUTURE",
        "EVALUATED_RESEARCH_PASS_NO_PRODUCTION",
        "EVALUATED_HOLD_NO_CLUSTERED_GAIN",
    ), "INVALID_MICROCORE_STATUS")
    if state["status"] == "UNINITIALIZED":
        require(state.get("pending") is None and state.get("verdict") is None,
                "UNINITIALIZED_HAS_DATA")
    else:
        p = state.get("pending")
        require(isinstance(p, dict) and p.get("schema") == "janus.essence.memory_guided_candidate/3.4"
                and p.get("config") == CONFIG
                and SHA40.fullmatch(str(p.get("source_commit", "")))
                and SHA40.fullmatch(str(p.get("v32_memory_commit", "")))
                and SHA40.fullmatch(str(p.get("v33_memory_commit", "")))
                and SHA64.fullmatch(str(p.get("candidate_sha256", "")))
                and p.get("candidate_sha256") == seal({
                    k: v for k, v in p.items() if k != "candidate_sha256"})
                and p.get("frozen_training_prior") is not None
                and p.get("new_microcore_blueprints") is not None
                and p.get("source_memory") is not None,
                "CANDIDATE_FREEZE_CONTRACT_BROKEN")
        for field in ("sealed_before", "last_training_created_at"):
            utc(p[field])
        require(state.get("verdict") is None
                if state["status"] == "FROZEN_AWAITING_FUTURE"
                else isinstance(state.get("verdict"), dict)
                and state["verdict"].get("receipt_sha256") == seal({
                    k: v for k, v in state["verdict"].items()
                    if k != "receipt_sha256"}),
                "MICROCORE_VERDICT_TAMPERED")


def freeze(mem, rows, now, *, source_commit, v32_commit, v33_commit):
    for h in (source_commit, v32_commit, v33_commit):
        require(SHA40.fullmatch(str(h)), "UNPINNED_GIT_COMMIT")
    prior = count_priors(rows)
    p = {
        "schema": "janus.essence.memory_guided_candidate/3.4",
        "source_commit": source_commit,
        "v32_memory_commit": v32_commit,
        "v33_memory_commit": v33_commit,
        "source_memory": mem, "new_microcore_blueprints": blueprints(mem),
        "config": CONFIG,
        "frozen_training_prior": prior,
        "last_training_created_at": rows[-1]["created_at"],
        "train_count": len(rows),
        "train_family_count": len(prior["workflow"]),
        "train_record_ids_sha256": seal([r["id"] for r in rows]),
        "sealed_before": now.isoformat(),
        "future_outcomes_used_for_selection": False,
        "candidate_executable_operator": CONFIG["operator"],
        "production_authority": False,
    }
    p["candidate_sha256"] = seal(p)
    return p


def step(state, memories, rows, now, *, published_at=None,
         source_commit=None, v32_commit=None, v33_commit=None):
    check_state(state)
    if isinstance(now, str):
        now = utc(now)
    require(now.tzinfo is not None, "NOW_UNZONED")
    if state["status"] == "UNINITIALIZED":
        # All data must be already completed and timestamped before freeze.
        require(all(utc(r["created_at"]) <= now for r in rows),
                "TRAINING_AFTER_FREEZE")
        mem = verified_memories(*memories)
        pending = freeze(mem, rows, now, source_commit=source_commit,
                         v32_commit=v32_commit, v33_commit=v33_commit)
        result = {k: v for k, v in state.items() if k != "state_sha256"}
        result["status"] = "FROZEN_AWAITING_FUTURE"
        result["pending"] = pending
        result["state_sha256"] = seal(result)
        check_state(result)
        report = {
            "status": "FROZEN_CANDIDATE_BEFORE_FUTURE_TASKS",
            "candidate_sha256": pending["candidate_sha256"],
            "source_memory_sha256": seal(mem),
            "train_count": len(rows), "train_family_count": pending["train_family_count"],
            "proposed_microcores": pending["new_microcore_blueprints"],
            "future_task_labels_seen": False,
            "source_commit": source_commit,
            "baseline_and_candidate_frozen": True,
            "independent_gain_proven": False,
        }
        return result, sealed_report(report)
    if state["status"] != "FROZEN_AWAITING_FUTURE":
        report = {
            "status": "FROZEN_TERMINAL_VERDICT_NO_RETRAIN",
            "previous_verdict": state["status"],
            "independent_gain_proven": False,
        }
        return state, sealed_report(report)
    pending = state["pending"]
    require(published_at is not None, "CANDIDATE_GIT_PUBLICATION_TIME_REQUIRED")
    published = utc(published_at)
    freeze_time = utc(pending["sealed_before"])
    require(freeze_time <= published <= now,
            "CANDIDATE_NOT_PUBLISHED_BEFORE_FUTURE")
    cutoff = max(published, freeze_time, utc(pending["last_training_created_at"]))
    fresh = [x for x in rows if utc(x["created_at"]) > cutoff]
    ids = [r["id"] for r in fresh]
    require(len(ids) == len(set(ids)), "FUTURE_RUNS_NOT_UNIQUE")
    families = Counter(x["workflow_id"] for x in fresh)
    diverse = (len(fresh) >= MIN_FUTURE and
               len(families) >= MIN_FUTURE_FAMILIES and
               max(families.values(), default=0) / max(len(fresh), 1) <= MAX_FAMILY_SHARE and
               sum(sum(r["label"] == label for r in fresh) >= 5
                   for label in range(LABELS)) >= 2)
    if not diverse:
        return state, sealed_report({
            "status": "HOLD_AWAITING_INDEPENDENT_FUTURE_WORKFLOW_COHORT",
            "created_after_git_publication": len(fresh),
            "workflow_families": len(families),
            "largest_family_share": max(families.values(), default=0)/max(len(fresh), 1),
            "minimum_required_runs": MIN_FUTURE,
            "minimum_required_families": MIN_FUTURE_FAMILIES,
            "baseline_and_candidate_frozen": True,
            "candidate_sha256": pending["candidate_sha256"],
            "training_used_future_labels": False,
            "independent_gain_proven": False,
        })
    comparison = scored_pair(pending["frozen_training_prior"], fresh)
    comparison.update({
        "status": ("PASS_INTERNAL_PROSPECTIVE_MICROCORE_GAIN_REVIEW_REQUIRED"
                   if comparison["passes_predeclared_internal_gate"]
                   else "HOLD_NO_CLUSTER_ROBUST_CANDIDATE_GAIN"),
        "created_after_candidate_git_commit": True,
        "candidate_sha256": pending["candidate_sha256"],
        "future_run_ids_sha256": seal(ids),
        "frozen_before": pending["sealed_before"],
        "published_at": published.isoformat(),
        "first_future_created_at": fresh[0]["created_at"],
        "last_future_created_at": fresh[-1]["created_at"],
        "training_saw_future_labels": False,
        "scientific_external_validation": False,
        "production_authority": False,
        "model_weights_changed": False,
    })
    comparison["receipt_sha256"] = seal(comparison)
    result = {k: v for k, v in state.items() if k != "state_sha256"}
    result["verdict"] = comparison
    result["status"] = ("EVALUATED_RESEARCH_PASS_NO_PRODUCTION"
                        if comparison["passes_predeclared_internal_gate"]
                        else "EVALUATED_HOLD_NO_CLUSTERED_GAIN")
    result["state_sha256"] = seal(result)
    check_state(result)
    return result, sealed_report({
        "status": comparison["status"],
        "comparison": comparison,
        "candidate_sha256": pending["candidate_sha256"],
        "memory_used_to_generate_candidates": True,
        "new_microcores_auto_activated": False,
        "independent_gain_proven": False,
    })


def sealed_report(fields):
    output = {
        "schema": "janus.essence.memory_guided_prospective_receipt/3.4",
        **fields,
        "research_only": True,
        "model_weights_modified": False,
        "production_authority": False,
        "automatic_module_admission": False,
        "external_independent_replication": False,
    }
    output["receipt_sha256"] = seal(output)
    return output


def read_json(path, max_size=150000):
    p = Path(path)
    if (p.is_symlink() or not p.is_file() or p.stat().st_size < 2
            or p.stat().st_size > max_size):
        raise ValueError("UNSAFE_SOURCE_OR_STATE_FILE")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON")))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v32", type=Path, required=True)
    parser.add_argument("--v33", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--v32-commit", required=True)
    parser.add_argument("--v33-commit", required=True)
    parser.add_argument("--published-at", default="")
    parser.add_argument("--receipt", type=Path, required=True)
    a = parser.parse_args()
    now = datetime.now(timezone.utc)
    observed = rows_from_api(api_runs(os.environ.get("GH_TOKEN")), now)
    state = read_json(a.state) if a.state.is_file() else empty_state()
    check_state(state)
    memories = (read_json(a.v32), read_json(a.v33), read_json(a.outcomes))
    new_state, report = step(
        state, memories, observed, now,
        published_at=a.published_at or None,
        source_commit=a.source_commit, v32_commit=a.v32_commit,
        v33_commit=a.v33_commit)
    if a.receipt.exists():
        raise ValueError("IMMUTABLE_RECEIPT_REQUIRES_FRESH_PATH")
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   ensure_ascii=False) + "\n", encoding="utf-8")
    if new_state != state:
        a.state.parent.mkdir(parents=True, exist_ok=True)
        a.state.write_text(json.dumps(new_state, indent=2, sort_keys=True,
                                      ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"], "completed_runs_visible": len(observed),
        "state": new_state["status"], "state_changed": new_state != state,
        "candidate_blueprints": len(new_state.get("pending", {}).get(
            "new_microcore_blueprints", [])) if new_state.get("pending") else 0,
        "production_authority": False, "receipt_sha256": report["receipt_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
