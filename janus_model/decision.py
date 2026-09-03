from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint, sha256_file

SCHEMA = "janus.native_repair_candidate_set.v1"
DECISION_SCHEMA = "janus.native_repair_decision.v1"
RESEARCH_SPINE_SCHEMA = "janus.research_spine.v1"
OUTCOME_MEMORY_SCHEMA = "janus.verified_outcome_memory.v1"
NO_ACTION_ID = "NO_ACTION"
ALLOWED_RISK = {"LOW"}
ALLOWED_PRIORITY_CLASSES = {"NORMAL", "CRITICAL_INTEGRITY", "CRITICAL_SECURITY", "CRITICAL_SAFETY"}
PRIMARY_TARGET = "Hawkar-usls/Janus-Fundamentum"
DEFAULT_RESEARCH_SPINE_PATH = Path("janus_model/state/JANUS_RESEARCH_SPINE.json")
DEFAULT_OUTCOME_MEMORY_PATH = Path("janus_model/state/JANUS_VERIFIED_OUTCOME_MEMORY.json")
LATEST_DECISION_PATH = Path("janus_model/state/JANUS_LATEST_DECISION.json")
MAX_OUTCOME_RECORDS = 64
MAX_OUTCOME_PRIOR_CAP_NLL = 0.01
OUTCOME_PRIOR_PER_VERIFY_PASS_NLL = 0.002


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _validate_candidate_set(obj: dict, organ_context: dict) -> list[dict]:
    if obj.get("schema") != SCHEMA:
        raise RuntimeError("DECISION_CANDIDATE_SET_SCHEMA_REJECTED")
    if obj.get("status") != "BOUNDED_PREVALIDATED_CANDIDATES":
        raise RuntimeError("DECISION_CANDIDATE_SET_STATUS_REJECTED")
    candidates = obj.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("DECISION_CANDIDATES_EMPTY")
    modules = organ_context.get("repository_modules") or {}
    module_by_repo = {m.get("repository"): m for m in modules.values() if isinstance(m, dict)}
    ids: set[str] = set()
    has_no_action = False
    out: list[dict] = []
    for source in candidates:
        if not isinstance(source, dict):
            raise RuntimeError("DECISION_CANDIDATE_OBJECT_REQUIRED")
        row = dict(source)
        cid = row.get("candidate_id")
        if not isinstance(cid, str) or not cid or cid in ids:
            raise RuntimeError("DECISION_CANDIDATE_ID_INVALID_OR_DUPLICATE")
        ids.add(cid)
        text = row.get("score_text")
        if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 96:
            raise RuntimeError(f"DECISION_SCORE_TEXT_REJECTED:{cid}")
        if cid == NO_ACTION_ID:
            has_no_action = True
            if row.get("action") != "NO_ACTION":
                raise RuntimeError("DECISION_NO_ACTION_SHAPE_REJECTED")
            row["priority_class"] = "NORMAL"
        else:
            if row.get("risk_lane") not in ALLOWED_RISK:
                raise RuntimeError(f"DECISION_RISK_REJECTED:{cid}")
            row["priority_class"] = row.get("priority_class", "NORMAL")
            if row["priority_class"] not in ALLOWED_PRIORITY_CLASSES:
                raise RuntimeError(f"DECISION_PRIORITY_CLASS_REJECTED:{cid}")
            target = row.get("target") or {}
            module = module_by_repo.get(target.get("repository"))
            if module is None:
                raise RuntimeError(f"DECISION_TARGET_NOT_OBSERVED_MODULE:{cid}")
            if row.get("proposal_template") is None:
                raise RuntimeError(f"DECISION_PROPOSAL_TEMPLATE_MISSING:{cid}")
            if row.get("verification_profile") is None:
                raise RuntimeError(f"DECISION_VERIFIER_MISSING:{cid}")
            if target.get("expected_target_commit") != module.get("target_commit"):
                # A candidate bound to an older observed HEAD is not evidence of
                # failure and must not abort a newer learning cycle. Neutralize
                # only this exact stale-base condition after every other strict
                # shape/risk/verifier check has passed. Unknown targets and
                # malformed candidates still fail closed above.
                continue
        out.append(row)
    if not has_no_action:
        raise RuntimeError("DECISION_NO_ACTION_REQUIRED")
    return out


def _load_research_spine(path: Path | None) -> dict | None:
    if path is None and DEFAULT_RESEARCH_SPINE_PATH.is_file():
        path = DEFAULT_RESEARCH_SPINE_PATH
    if path is None:
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != RESEARCH_SPINE_SCHEMA:
        raise RuntimeError("DECISION_RESEARCH_SPINE_SCHEMA_REJECTED")
    if obj.get("status") not in {"READY", "READY_WITH_ARXIV_DEGRADED"}:
        raise RuntimeError("DECISION_RESEARCH_SPINE_NOT_READY")
    policy = obj.get("improvement_policy") or {}
    if policy.get("policy_id") != "FUNDAMENTUM_FIRST_WITH_CRITICAL_OVERRIDE":
        raise RuntimeError("DECISION_IMPROVEMENT_POLICY_REJECTED")
    if policy.get("primary_target") != PRIMARY_TARGET:
        raise RuntimeError("DECISION_PRIMARY_TARGET_REJECTED")
    if policy.get("no_novel_bounded_evidence_means_no_action") is not True:
        raise RuntimeError("DECISION_NO_EVIDENCE_FIREWALL_MISSING")
    ceiling = obj.get("claim_ceiling") or {}
    if ceiling.get("topa_output_is_world_truth") is not False:
        raise RuntimeError("DECISION_TOPA_AUTHORITY_FIREWALL_FAIL")
    if ceiling.get("arxiv_presence_is_truth") is not False:
        raise RuntimeError("DECISION_ARXIV_AUTHORITY_FIREWALL_FAIL")
    if ceiling.get("demi_head_property_is_independent_evidence") is not False:
        raise RuntimeError("DECISION_DEMI_HEAD_AUTHORITY_FIREWALL_FAIL")
    if ceiling.get("target_local_verify_required") is not True:
        raise RuntimeError("DECISION_TARGET_VERIFY_FIREWALL_FAIL")
    topa = ((obj.get("research_spine") or {}).get("topa") or {}).get("router_self_test") or {}
    if topa.get("status") != "PASS":
        raise RuntimeError("DECISION_TOPA_ROUTER_NOT_VERIFIED")
    return obj


def _load_outcome_memory(path: Path | None) -> dict | None:
    if path is None and DEFAULT_OUTCOME_MEMORY_PATH.is_file():
        path = DEFAULT_OUTCOME_MEMORY_PATH
    if path is None:
        return None
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != OUTCOME_MEMORY_SCHEMA or obj.get("status") != "VERIFIED_OUTCOME_MEMORY_READY":
        raise RuntimeError("DECISION_OUTCOME_MEMORY_SCHEMA_REJECTED")
    policy = obj.get("policy") or {}
    if policy.get("silence_is_negative_evidence") is not False:
        raise RuntimeError("DECISION_OUTCOME_SILENCE_FIREWALL_FAIL")
    if policy.get("only_target_local_verify_pass_is_positive_feedback") is not True:
        raise RuntimeError("DECISION_OUTCOME_VERIFIER_FIREWALL_FAIL")
    if policy.get("native_model_selected_required_for_training_prior") is not True:
        raise RuntimeError("DECISION_OUTCOME_NATIVE_SELECTION_FIREWALL_FAIL")
    if policy.get("feedback_grants_mutation_authority") is not False:
        raise RuntimeError("DECISION_OUTCOME_AUTHORITY_FIREWALL_FAIL")
    if policy.get("historical_verify_pass_is_world_truth") is not False:
        raise RuntimeError("DECISION_OUTCOME_TRUTH_FIREWALL_FAIL")
    if policy.get("target_local_reverification_still_required") is not True:
        raise RuntimeError("DECISION_OUTCOME_REVERIFY_FIREWALL_FAIL")
    cap = float(policy.get("decision_prior_cap_nll", -1.0))
    if not 0.0 <= cap <= MAX_OUTCOME_PRIOR_CAP_NLL:
        raise RuntimeError("DECISION_OUTCOME_PRIOR_CAP_REJECTED")
    records = obj.get("records")
    if not isinstance(records, list) or len(records) > MAX_OUTCOME_RECORDS:
        raise RuntimeError("DECISION_OUTCOME_RECORDS_REJECTED")
    if obj.get("record_count") != len(records):
        raise RuntimeError("DECISION_OUTCOME_RECORD_COUNT_REJECTED")
    training_count = 0
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("DECISION_OUTCOME_RECORD_OBJECT_REQUIRED")
        proposal_id = record.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id or proposal_id in seen:
            raise RuntimeError("DECISION_OUTCOME_PROPOSAL_ID_REJECTED")
        seen.add(proposal_id)
        body = dict(record)
        record_sha = body.pop("record_sha256", None)
        if record_sha != sha256_bytes(canonical_bytes(body)):
            raise RuntimeError(f"DECISION_OUTCOME_RECORD_HASH_REJECTED:{proposal_id}")
        if record.get("status") != "VERIFY_PASS" or record.get("terminal_authority") != "TARGET_LOCAL_VERIFIER":
            raise RuntimeError(f"DECISION_OUTCOME_VERIFIER_REJECTED:{proposal_id}")
        if record.get("autonomous_merge") is not False or record.get("main_mutated") is not False:
            raise RuntimeError(f"DECISION_OUTCOME_MUTATION_FIREWALL_REJECTED:{proposal_id}")
        if record.get("truth_claim") is not False or record.get("mutation_authority_granted") is not False:
            raise RuntimeError(f"DECISION_OUTCOME_AUTHORITY_RECORD_REJECTED:{proposal_id}")
        eligible = record.get("training_eligible") is True
        if record.get("positive_feedback") is not eligible:
            raise RuntimeError(f"DECISION_OUTCOME_POSITIVE_FEEDBACK_REJECTED:{proposal_id}")
        if eligible:
            if record.get("native_model_selected") is not True:
                raise RuntimeError(f"DECISION_OUTCOME_TRAINING_SOURCE_REJECTED:{proposal_id}")
            if not isinstance(record.get("target_repository"), str) or not isinstance(record.get("verification_profile"), str):
                raise RuntimeError(f"DECISION_OUTCOME_TRAINING_KEY_REJECTED:{proposal_id}")
            training_count += 1
    if obj.get("training_eligible_count") != training_count:
        raise RuntimeError("DECISION_OUTCOME_TRAINING_COUNT_REJECTED")
    return obj


def _apply_improvement_policy(candidates: list[dict], research: dict | None) -> tuple[list[dict], list[str], dict]:
    if research is None:
        return candidates, [], {"active": False, "reason": "LEGACY_NO_RESEARCH_SPINE"}
    policy = research["improvement_policy"]
    primary = policy["primary_target"]
    overrides = set(policy.get("critical_override_classes") or [])
    no_action = [r for r in candidates if r["candidate_id"] == NO_ACTION_ID]
    critical = [r for r in candidates if r["candidate_id"] != NO_ACTION_ID and r.get("priority_class") in overrides]
    primary_rows = [r for r in candidates if r["candidate_id"] != NO_ACTION_ID and (r.get("target") or {}).get("repository") == primary]
    if critical:
        allowed = {r["candidate_id"] for r in no_action + critical + primary_rows}
        mode = "PRIMARY_PLUS_CRITICAL_OVERRIDE"
    elif primary_rows:
        allowed = {r["candidate_id"] for r in no_action + primary_rows}
        mode = "FUNDAMENTUM_FIRST"
    else:
        allowed = {NO_ACTION_ID}
        mode = "NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN"
    admitted = [r for r in candidates if r["candidate_id"] in allowed]
    deferred = [r["candidate_id"] for r in candidates if r["candidate_id"] not in allowed]
    return admitted, deferred, {
        "active": True,
        "policy_id": policy["policy_id"],
        "primary_target": primary,
        "mode": mode,
        "critical_override_classes": sorted(overrides),
    }


def _verified_outcome_prior(candidate: dict, outcome_memory: dict | None) -> tuple[int, float]:
    if outcome_memory is None or candidate.get("candidate_id") == NO_ACTION_ID:
        return 0, 0.0
    target_repository = (candidate.get("target") or {}).get("repository")
    verification_profile = candidate.get("verification_profile")
    matches = [
        record for record in outcome_memory["records"]
        if record.get("training_eligible") is True
        and record.get("target_repository") == target_repository
        and record.get("verification_profile") == verification_profile
    ]
    cap = float(outcome_memory["policy"]["decision_prior_cap_nll"])
    bonus = min(cap, len(matches) * OUTCOME_PRIOR_PER_VERIFY_PASS_NLL)
    return len(matches), bonus


@torch.no_grad()
def continuation_avg_nll(model, prompt: str, continuation: str) -> float:
    model.eval()
    prefix = ByteTokenizer.encode(prompt, bos=True)
    continuation_ids = ByteTokenizer.encode(continuation, eos=False)
    if not continuation_ids:
        raise RuntimeError("DECISION_EMPTY_CONTINUATION")
    losses = []
    for token_id in continuation_ids:
        x = torch.tensor([prefix[-model.config.context_length :]], dtype=torch.long)
        logits, _ = model(x)
        logp = F.log_softmax(logits[0, -1], dim=-1)
        losses.append(float(-logp[int(token_id)].item()))
        prefix.append(int(token_id))
    return sum(losses) / len(losses)


def decide(
    checkpoint: Path,
    organ_context_path: Path,
    candidate_set_path: Path,
    margin: float = 0.03,
    research_spine_path: Path | None = None,
    outcome_memory_path: Path | None = None,
) -> dict:
    model, _ = load_checkpoint(checkpoint)
    context = json.loads(organ_context_path.read_text(encoding="utf-8"))
    if context.get("status") != "READ_ONLY_MODULAR_ORGAN_CONTEXT":
        raise RuntimeError("DECISION_MODULAR_CONTEXT_REQUIRED")
    fw = context.get("firewalls") or {}
    if fw.get("terminal_authority") != "VERIFY" or fw.get("module_observation_grants_mutation") is not False:
        raise RuntimeError("DECISION_ORGAN_FIREWALL_FAIL")
    candidates = _validate_candidate_set(json.loads(candidate_set_path.read_text(encoding="utf-8")), context)
    research = _load_research_spine(research_spine_path)
    outcome_memory = _load_outcome_memory(outcome_memory_path)
    admitted, deferred, improvement_policy = _apply_improvement_policy(candidates, research)

    self_digest = (context.get("self_memory") or {}).get("digest_sha256") or "NONE"
    research_digest = (research or {}).get("context_sha256") or "NONE"
    spine = (research or {}).get("research_spine") or {}
    topa_commit = (spine.get("topa") or {}).get("commit") or "NONE"
    demi_commit = (spine.get("demi_head") or {}).get("commit") or "NONE"
    fund_commit = (spine.get("fundamentum") or {}).get("commit") or "NONE"
    outcome_memory_digest = sha256_bytes(canonical_bytes(outcome_memory)) if outcome_memory else "NONE"
    training_records = [r for r in (outcome_memory or {}).get("records", []) if r.get("training_eligible") is True]
    outcome_training_digest = sha256_bytes(canonical_bytes(training_records)) if training_records else "NONE"
    prompt = (
        f"JANUS DECIDE REPAIR|MODULES={context.get('module_count')}|"
        f"HRAIN={context['organs']['HRAiN']['target_commit'][:8]}|"
        f"INAIHR={context['organs']['iNaiHR']['target_commit'][:8]}|SELF={self_digest[:8]}|"
        f"RESEARCH={research_digest[:8]}|TOPA={topa_commit[:8]}|DEMIHEAD={demi_commit[:8]}|FUND={fund_commit[:8]}|CHOICE="
    )
    rows = []
    for row in admitted:
        raw_nll = continuation_avg_nll(model, prompt, row["score_text"])
        verified_pass_count, outcome_bonus = _verified_outcome_prior(row, outcome_memory)
        adjusted_nll = raw_nll - outcome_bonus
        rows.append({
            "candidate_id": row["candidate_id"], "action": row.get("action"), "score_text": row["score_text"],
            "avg_nll": adjusted_nll, "avg_nll_raw": raw_nll,
            "verified_outcome_bonus_nll": outcome_bonus, "verified_pass_count": verified_pass_count,
            "prevalidated": True, "policy_admitted": True, "priority_class": row.get("priority_class", "NORMAL"),
            "target": row.get("target"), "risk_lane": row.get("risk_lane"),
            "verification_profile": row.get("verification_profile"), "proposal_template": row.get("proposal_template"),
        })
    rows.sort(key=lambda x: (x["avg_nll"], x["candidate_id"]))
    top = rows[0]
    second = rows[1] if len(rows) > 1 else None
    no_action = next(r for r in rows if r["candidate_id"] == NO_ACTION_ID)
    top_margin = math.inf if second is None else second["avg_nll"] - top["avg_nll"]
    action_margin = no_action["avg_nll"] - top["avg_nll"]
    selected = top
    gate_reason = "TOP_CANDIDATE_IS_NO_ACTION"
    if top["candidate_id"] != NO_ACTION_ID:
        if top_margin < margin:
            selected, gate_reason = no_action, "INSUFFICIENT_TOP_MARGIN__ABSTAIN"
        elif action_margin < margin:
            selected, gate_reason = no_action, "INSUFFICIENT_ACTION_OVER_NO_ACTION_MARGIN__ABSTAIN"
        else:
            gate_reason = "BOUNDED_ACTION_SELECTED_BY_NATIVE_CHECKPOINT"
    elif improvement_policy.get("mode") == "NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN":
        gate_reason = "FUNDAMENTUM_FIRST_POLICY__NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN"

    identity = {
        "checkpoint_sha256": sha256_file(checkpoint), "candidate_set_sha256": sha256_file(candidate_set_path),
        "organ_context_sha256": context.get("context_sha256"), "research_context_sha256": research_digest,
        "selected_candidate_id": selected["candidate_id"],
        "scores": [(r["candidate_id"], round(r["avg_nll"], 12)) for r in rows], "deferred": sorted(deferred),
    }
    if outcome_training_digest != "NONE":
        identity["verified_outcome_training_sha256"] = outcome_training_digest
    decision_id = "jnd-" + sha256_bytes(canonical_bytes(identity))[:24]
    return {
        "schema": DECISION_SCHEMA, "decision_id": decision_id,
        "status": "NO_ACTION" if selected["candidate_id"] == NO_ACTION_ID else "ACTION_SELECTED_AWAITING_TARGET_VERIFY",
        "native_model_decision": True,
        "selection_method": "FUNDAMENTUM_FIRST_POLICY_ENVELOPE_THEN_OWN_CHECKPOINT_AVG_NLL_PLUS_BOUNDED_TARGET_VERIFIED_OUTCOME_PRIOR_WITH_ABSTENTION_GATE",
        "checkpoint_sha256": identity["checkpoint_sha256"], "candidate_set_sha256": identity["candidate_set_sha256"],
        "organ_context_sha256": identity["organ_context_sha256"], "research_context_sha256": research_digest,
        "research_source_commits": {"TOPA": topa_commit, "Demi_Head": demi_commit, "Janus-Fundamentum": fund_commit},
        "module_count": context.get("module_count"), "self_memory_digest_sha256": self_digest,
        "improvement_policy": improvement_policy, "policy_deferred_candidates": deferred,
        "outcome_learning": {
            "active": bool(training_records),
            "memory_context_sha256": outcome_memory_digest,
            "training_context_sha256": outcome_training_digest,
            "verified_record_count": int((outcome_memory or {}).get("record_count", 0)),
            "training_eligible_count": len(training_records),
            "prior_per_verify_pass_nll": OUTCOME_PRIOR_PER_VERIFY_PASS_NLL,
            "prior_cap_nll": float((outcome_memory or {}).get("policy", {}).get("decision_prior_cap_nll", 0.0)),
            "silence_is_negative_evidence": False,
            "historical_verify_pass_is_world_truth": False,
            "target_local_reverification_still_required": True,
        },
        "margin_required": margin, "top_margin": top_margin if math.isfinite(top_margin) else None,
        "action_margin_over_no_action": action_margin, "gate_reason": gate_reason, "selected": selected, "scores": rows,
        "authority": {
            "truth": False, "evidence": False, "topa_is_world_truth": False, "arxiv_presence_is_truth": False,
            "demi_head_property_is_independent_evidence": False, "historical_verify_pass_is_world_truth": False,
            "outcome_memory_grants_authority": False, "direct_repository_mutation": False,
            "autonomous_merge": False, "target_local_verifier_required": selected["candidate_id"] != NO_ACTION_ID,
        },
        "laws": [
            "FREE_FORM_MODEL_OUTPUT_IS_NOT_A_PATCH", "NO_ACTION_IS_ALWAYS_AVAILABLE", "NO_NOVEL_BOUNDED_EVIDENCE => NO_ACTION",
            "FUNDAMENTUM_FIRST != FUNDAMENTUM_ALWAYS", "CRITICAL_INTEGRITY_SECURITY_SAFETY_MAY_OVERRIDE_PRIMARY_TARGET",
            "TOPA_CONTEXT != EMPIRICAL_TRUTH", "ARXIV_PAPER != INDEPENDENT_REPLICATION", "DEMI_HEAD_PROPERTY != EVIDENCE",
            "SILENCE != NEGATIVE_EVIDENCE", "HISTORICAL_VERIFY_PASS != WORLD_TRUTH",
            "VERIFIED_OUTCOME_PRIOR != TARGET_VERIFICATION", "OUTCOME_MEMORY != MUTATION_AUTHORITY",
            "INSUFFICIENT_MARGIN_MEANS_ABSTAIN", "MODEL_SELECTION != VERIFIED_FIX", "TARGET_LOCAL_VERIFY_REQUIRED_BEFORE_PASS",
        ],
    }


def persist_latest_decision(decision: dict, path: Path = LATEST_DECISION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--organ-context", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--research-spine")
    ap.add_argument("--outcome-memory")
    ap.add_argument("--out", required=True)
    ap.add_argument("--margin", type=float, default=0.03)
    args = ap.parse_args()
    decision = decide(
        Path(args.checkpoint), Path(args.organ_context), Path(args.candidates), args.margin,
        Path(args.research_spine) if args.research_spine else None,
        Path(args.outcome_memory) if args.outcome_memory else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    persist_latest_decision(decision)
    print(json.dumps({
        "decision_id": decision["decision_id"], "status": decision["status"],
        "selected": decision["selected"]["candidate_id"], "gate_reason": decision["gate_reason"],
        "research_context_sha256": decision["research_context_sha256"], "improvement_policy": decision["improvement_policy"],
        "outcome_learning": decision["outcome_learning"],
    }, indent=2))


if __name__ == "__main__":
    main()
