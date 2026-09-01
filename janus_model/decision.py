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
NO_ACTION_ID = "NO_ACTION"
ALLOWED_RISK = {"LOW"}
ALLOWED_PRIORITY_CLASSES = {"NORMAL", "CRITICAL_INTEGRITY", "CRITICAL_SECURITY", "CRITICAL_SAFETY"}
PRIMARY_TARGET = "Hawkar-usls/Janus-Fundamentum"
DEFAULT_RESEARCH_SPINE_PATH = Path("janus_model/state/JANUS_RESEARCH_SPINE.json")


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
    ids: set[str] = set()
    has_no_action = False
    modules = organ_context.get("repository_modules") or {}
    module_by_repo = {m.get("repository"): m for m in modules.values() if isinstance(m, dict)}
    out = []
    for row in candidates:
        if not isinstance(row, dict):
            raise RuntimeError("DECISION_CANDIDATE_OBJECT_REQUIRED")
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
        else:
            if row.get("risk_lane") not in ALLOWED_RISK:
                raise RuntimeError(f"DECISION_RISK_REJECTED:{cid}")
            priority_class = row.get("priority_class", "NORMAL")
            if priority_class not in ALLOWED_PRIORITY_CLASSES:
                raise RuntimeError(f"DECISION_PRIORITY_CLASS_REJECTED:{cid}")
            target = row.get("target") or {}
            repo = target.get("repository")
            module = module_by_repo.get(repo)
            if module is None:
                raise RuntimeError(f"DECISION_TARGET_NOT_OBSERVED_MODULE:{cid}")
            if target.get("expected_target_commit") != module.get("target_commit"):
                raise RuntimeError(f"DECISION_TARGET_COMMIT_NOT_SCOUT_BOUND:{cid}")
            if row.get("proposal_template") is None:
                raise RuntimeError(f"DECISION_PROPOSAL_TEMPLATE_MISSING:{cid}")
            if row.get("verification_profile") is None:
                raise RuntimeError(f"DECISION_VERIFIER_MISSING:{cid}")
        normalized = dict(row)
        normalized["priority_class"] = row.get("priority_class", "NORMAL") if cid != NO_ACTION_ID else "NORMAL"
        out.append(normalized)
    if not has_no_action:
        raise RuntimeError("DECISION_NO_ACTION_REQUIRED")
    return out


def _load_research_spine(path: Path | None) -> dict | None:
    if path is None:
        path = DEFAULT_RESEARCH_SPINE_PATH if DEFAULT_RESEARCH_SPINE_PATH.is_file() else None
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
    claims = obj.get("claim_ceiling") or {}
    if claims.get("topa_output_is_world_truth") is not False:
        raise RuntimeError("DECISION_TOPA_AUTHORITY_FIREWALL_FAIL")
    if claims.get("arxiv_presence_is_truth") is not False:
        raise RuntimeError("DECISION_ARXIV_AUTHORITY_FIREWALL_FAIL")
    if claims.get("demi_head_property_is_independent_evidence") is not False:
        raise RuntimeError("DECISION_DEMI_HEAD_AUTHORITY_FIREWALL_FAIL")
    if claims.get("target_local_verify_required") is not True:
        raise RuntimeError("DECISION_TARGET_VERIFY_FIREWALL_FAIL")
    topa = ((obj.get("research_spine") or {}).get("topa") or {}).get("router_self_test") or {}
    if topa.get("status") != "PASS":
        raise RuntimeError("DECISION_TOPA_ROUTER_NOT_VERIFIED")
    return obj


def _apply_improvement_policy(candidates: list[dict], research: dict | None) -> tuple[list[dict], list[str], dict]:
    if research is None:
        return candidates, [], {"active": False, "reason": "LEGACY_NO_RESEARCH_SPINE"}
    policy = research["improvement_policy"]
    primary = policy["primary_target"]
    overrides = set(policy.get("critical_override_classes") or [])
    no_action = [r for r in candidates if r["candidate_id"] == NO_ACTION_ID]
    critical = [r for r in candidates if r["candidate_id"] != NO_ACTION_ID and r.get("priority_class") in overrides]
    primary_rows = [
        r for r in candidates
        if r["candidate_id"] != NO_ACTION_ID and (r.get("target") or {}).get("repository") == primary
    ]
    if critical:
        admitted_ids = {r["candidate_id"] for r in no_action + critical + primary_rows}
        mode = "PRIMARY_PLUS_CRITICAL_OVERRIDE"
    elif primary_rows:
        admitted_ids = {r["candidate_id"] for r in no_action + primary_rows}
        mode = "FUNDAMENTUM_FIRST"
    else:
        admitted_ids = {NO_ACTION_ID}
        mode = "NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN"
    admitted = [r for r in candidates if r["candidate_id"] in admitted_ids]
    deferred = [r["candidate_id"] for r in candidates if r["candidate_id"] not in admitted_ids]
    return admitted, deferred, {
        "active": True,
        "policy_id": policy["policy_id"],
        "primary_target": primary,
        "mode": mode,
        "critical_override_classes": sorted(overrides),
    }


@torch.no_grad()
def continuation_avg_nll(model, prompt: str, continuation: str) -> float:
    """Score a short closed continuation under JANUS's own promoted checkpoint."""
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
) -> dict:
    model, _ = load_checkpoint(checkpoint)
    context = json.loads(organ_context_path.read_text(encoding="utf-8"))
    if context.get("status") != "READ_ONLY_MODULAR_ORGAN_CONTEXT":
        raise RuntimeError("DECISION_MODULAR_CONTEXT_REQUIRED")
    fw = context.get("firewalls") or {}
    if fw.get("terminal_authority") != "VERIFY" or fw.get("module_observation_grants_mutation") is not False:
        raise RuntimeError("DECISION_ORGAN_FIREWALL_FAIL")
    candidate_set = json.loads(candidate_set_path.read_text(encoding="utf-8"))
    candidates = _validate_candidate_set(candidate_set, context)
    research = _load_research_spine(research_spine_path)
    admitted, deferred, improvement_policy = _apply_improvement_policy(candidates, research)

    self_digest = (context.get("self_memory") or {}).get("digest_sha256") or "NONE"
    research_digest = (research or {}).get("context_sha256") or "NONE"
    topa_commit = (((research or {}).get("research_spine") or {}).get("topa") or {}).get("commit") or "NONE"
    demi_commit = (((research or {}).get("research_spine") or {}).get("demi_head") or {}).get("commit") or "NONE"
    fund_commit = (((research or {}).get("research_spine") or {}).get("fundamentum") or {}).get("commit") or "NONE"
    prompt = (
        f"JANUS DECIDE REPAIR|MODULES={context.get('module_count')}|"
        f"HRAIN={context['organs']['HRAiN']['target_commit'][:8]}|"
        f"INAIHR={context['organs']['iNaiHR']['target_commit'][:8]}|"
        f"SELF={self_digest[:8]}|RESEARCH={research_digest[:8]}|"
        f"TOPA={topa_commit[:8]}|DEMIHEAD={demi_commit[:8]}|FUND={fund_commit[:8]}|CHOICE="
    )
    rows = []
    for row in admitted:
        nll = continuation_avg_nll(model, prompt, row["score_text"])
        rows.append({
            "candidate_id": row["candidate_id"],
            "action": row.get("action"),
            "score_text": row["score_text"],
            "avg_nll": nll,
            "prevalidated": True,
            "policy_admitted": True,
            "priority_class": row.get("priority_class", "NORMAL"),
            "target": row.get("target"),
            "risk_lane": row.get("risk_lane"),
            "verification_profile": row.get("verification_profile"),
            "proposal_template": row.get("proposal_template"),
        })
    rows.sort(key=lambda x: (x["avg_nll"], x["candidate_id"]))
    top = rows[0]
    second = rows[1] if len(rows) > 1 else None
    no_action = next(r for r in rows if r["candidate_id"] == NO_ACTION_ID)
    top_margin = math.inf if second is None else second["avg_nll"] - top["avg_nll"]
    action_margin_over_noop = no_action["avg_nll"] - top["avg_nll"]

    selected = top
    gate_reason = "TOP_CANDIDATE_IS_NO_ACTION"
    if top["candidate_id"] != NO_ACTION_ID:
        if top_margin < margin:
            selected = no_action
            gate_reason = "INSUFFICIENT_TOP_MARGIN__ABSTAIN"
        elif action_margin_over_noop < margin:
            selected = no_action
            gate_reason = "INSUFFICIENT_ACTION_OVER_NO_ACTION_MARGIN__ABSTAIN"
        else:
            gate_reason = "BOUNDED_ACTION_SELECTED_BY_NATIVE_CHECKPOINT"
    elif improvement_policy.get("mode") == "NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN":
        gate_reason = "FUNDAMENTUM_FIRST_POLICY__NO_PRIMARY_OR_CRITICAL_CANDIDATE__ABSTAIN"

    identity = {
        "checkpoint_sha256": sha256_file(checkpoint),
        "candidate_set_sha256": sha256_file(candidate_set_path),
        "organ_context_sha256": context.get("context_sha256"),
        "research_context_sha256": research_digest,
        "selected_candidate_id": selected["candidate_id"],
        "scores": [(r["candidate_id"], round(r["avg_nll"], 12)) for r in rows],
        "deferred": sorted(deferred),
    }
    decision_id = "jnd-" + sha256_bytes(canonical_bytes(identity))[:24]
    return {
        "schema": DECISION_SCHEMA,
        "decision_id": decision_id,
        "status": "NO_ACTION" if selected["candidate_id"] == NO_ACTION_ID else "ACTION_SELECTED_AWAITING_TARGET_VERIFY",
        "native_model_decision": True,
        "selection_method": "FUNDAMENTUM_FIRST_POLICY_ENVELOPE_THEN_OWN_CHECKPOINT_CLOSED_CANDIDATE_AVG_NLL_WITH_ABSTENTION_GATE",
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "candidate_set_sha256": identity["candidate_set_sha256"],
        "organ_context_sha256": identity["organ_context_sha256"],
        "research_context_sha256": research_digest,
        "module_count": context.get("module_count"),
        "self_memory_digest_sha256": self_digest,
        "improvement_policy": improvement_policy,
        "policy_deferred_candidates": deferred,
        "margin_required": margin,
        "top_margin": top_margin if math.isfinite(top_margin) else None,
        "action_margin_over_no_action": action_margin_over_noop,
        "gate_reason": gate_reason,
        "selected": selected,
        "scores": rows,
        "authority": {
            "truth": False,
            "evidence": False,
            "topa_is_world_truth": False,
            "arxiv_presence_is_truth": False,
            "demi_head_property_is_independent_evidence": False,
            "direct_repository_mutation": False,
            "autonomous_merge": False,
            "target_local_verifier_required": selected["candidate_id"] != NO_ACTION_ID,
        },
        "laws": [
            "FREE_FORM_MODEL_OUTPUT_IS_NOT_A_PATCH",
            "NO_ACTION_IS_ALWAYS_AVAILABLE",
            "NO_NOVEL_BOUNDED_EVIDENCE => NO_ACTION",
            "FUNDAMENTUM_FIRST != FUNDAMENTUM_ALWAYS",
            "CRITICAL_INTEGRITY_SECURITY_SAFETY_MAY_OVERRIDE_PRIMARY_TARGET",
            "TOPA_CONTEXT != EMPIRICAL_TRUTH",
            "ARXIV_PAPER != INDEPENDENT_REPLICATION",
            "DEMI_HEAD_PROPERTY != EVIDENCE",
            "INSUFFICIENT_MARGIN_MEANS_ABSTAIN",
            "MODEL_SELECTION != VERIFIED_FIX",
            "TARGET_LOCAL_VERIFY_REQUIRED_BEFORE_PASS",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--organ-context", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--research-spine")
    ap.add_argument("--out", required=True)
    ap.add_argument("--margin", type=float, default=0.03)
    args = ap.parse_args()
    decision = decide(
        Path(args.checkpoint),
        Path(args.organ_context),
        Path(args.candidates),
        args.margin,
        Path(args.research_spine) if args.research_spine else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "decision_id": decision["decision_id"],
        "status": decision["status"],
        "selected": decision["selected"]["candidate_id"],
        "gate_reason": decision["gate_reason"],
        "improvement_policy": decision["improvement_policy"],
    }, indent=2))


if __name__ == "__main__":
    main()
