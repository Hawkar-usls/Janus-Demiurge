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

FRONTIER_SCHEMA = "janus.trump.frontier_observation.v1"
ATTENTION_SCHEMA = "janus.trump.native_frontier_attention.v1"
NO_INSPECTION = "NO_INSPECTION"
MAX_CANDIDATES = 32
MAX_REF_BYTES = 240
# These markers are explicit repository-author signals that a branch is a
# fixture/self-test and must not be considered an autonomous research intake
# target. This is eligibility filtering only; it does not rank scientific value.
INELIGIBLE_REF_MARKERS = (
    "do-not-use",
    "do_not_use",
    "self-test",
    "self_test",
    "test-fixture",
    "test_fixture",
)


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _frontier_ref_eligible(ref: str) -> bool:
    lowered = ref.casefold()
    return not any(marker in lowered for marker in INELIGIBLE_REF_MARKERS)


def validate_frontier(obj: dict) -> list[dict]:
    if obj.get("schema") != FRONTIER_SCHEMA or obj.get("status") != "READ_ONLY_ADVISORY_FRONTIER":
        raise RuntimeError("TRUMP_ATTENTION_FRONTIER_SCHEMA_REJECTED")
    authority = obj.get("authority") or {}
    if authority.get("read_only_observation") is not True:
        raise RuntimeError("TRUMP_ATTENTION_FRONTIER_READ_ONLY_REQUIRED")
    for key in (
        "changes_active_lineage",
        "changes_proof_ladder",
        "grants_theorem_authority",
        "grants_runtime_promotion",
        "mutates_observed_repository",
    ):
        if authority.get(key) is not False:
            raise RuntimeError(f"TRUMP_ATTENTION_FRONTIER_AUTHORITY_REJECTED:{key}")
    candidates = obj.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise RuntimeError("TRUMP_ATTENTION_FRONTIER_CANDIDATES_REJECTED")
    out: list[dict] = []
    seen: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            raise RuntimeError("TRUMP_ATTENTION_FRONTIER_ROW_REJECTED")
        ref = row.get("ref")
        commit = row.get("commit")
        if not isinstance(ref, str) or not ref.startswith("refs/heads/") or len(ref.encode()) > MAX_REF_BYTES:
            raise RuntimeError("TRUMP_ATTENTION_FRONTIER_REF_REJECTED")
        if ref in seen:
            raise RuntimeError("TRUMP_ATTENTION_FRONTIER_DUPLICATE_REF")
        seen.add(ref)
        if not isinstance(commit, str) or len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
            raise RuntimeError(f"TRUMP_ATTENTION_FRONTIER_COMMIT_REJECTED:{ref}")
        if not _frontier_ref_eligible(ref):
            continue
        out.append({
            "ref": ref,
            "commit": commit,
            "date_hint": row.get("date_hint") if isinstance(row.get("date_hint"), str) else None,
        })
    return out


@torch.no_grad()
def continuation_avg_nll(model, prompt: str, continuation: str) -> float:
    model.eval()
    prefix = ByteTokenizer.encode(prompt, bos=True)
    continuation_ids = ByteTokenizer.encode(continuation, eos=False)
    if not continuation_ids:
        raise RuntimeError("TRUMP_ATTENTION_EMPTY_CONTINUATION")
    losses: list[float] = []
    for token_id in continuation_ids:
        x = torch.tensor([prefix[-model.config.context_length :]], dtype=torch.long)
        logits, _ = model(x)
        logp = F.log_softmax(logits[0, -1], dim=-1)
        losses.append(float(-logp[int(token_id)].item()))
        prefix.append(int(token_id))
    return sum(losses) / len(losses)


def choose_frontier(
    checkpoint: Path,
    frontier_path: Path,
    *,
    margin: float = 0.01,
) -> dict:
    if margin < 0.0 or margin > 1.0:
        raise RuntimeError("TRUMP_ATTENTION_MARGIN_REJECTED")
    frontier_raw = frontier_path.read_bytes()
    frontier = json.loads(frontier_raw)
    raw_candidates = frontier.get("candidates") if isinstance(frontier.get("candidates"), list) else []
    candidates = validate_frontier(frontier)
    model, _ = load_checkpoint(checkpoint)

    prompt = (
        "JANUS TRUMP READ-ONLY FRONTIER ATTENTION|P_VS_NP=OPEN|"
        "OBSERVE!=PROOF|NEWER!=BETTER|NO_WRITEBACK|CHOOSE="
    )
    rows = [{
        "id": NO_INSPECTION,
        "ref": None,
        "commit": None,
        "date_hint": None,
        "continuation": "NO_INSPECTION",
    }]
    for row in candidates:
        branch = row["ref"].removeprefix("refs/heads/")
        date = row.get("date_hint") or "UNDATED"
        rows.append({
            "id": row["commit"],
            "ref": row["ref"],
            "commit": row["commit"],
            "date_hint": row.get("date_hint"),
            "continuation": f"INSPECT_READ_ONLY {branch} DATE={date}",
        })

    scored = []
    for row in rows:
        score = continuation_avg_nll(model, prompt, row["continuation"])
        scored.append({**row, "avg_nll": score})
    scored.sort(key=lambda row: (row["avg_nll"], row["id"]))

    top = scored[0]
    second = scored[1] if len(scored) > 1 else None
    no_inspection = next(row for row in scored if row["id"] == NO_INSPECTION)
    top_margin = math.inf if second is None else second["avg_nll"] - top["avg_nll"]
    action_margin = no_inspection["avg_nll"] - top["avg_nll"]

    selected = top
    reason = "TOP_IS_NO_INSPECTION"
    if top["id"] != NO_INSPECTION:
        if top_margin < margin:
            selected = no_inspection
            reason = "INSUFFICIENT_TOP_MARGIN__ABSTAIN"
        elif action_margin < margin:
            selected = no_inspection
            reason = "INSUFFICIENT_ACTION_OVER_NO_INSPECTION_MARGIN__ABSTAIN"
        else:
            reason = "NATIVE_CHECKPOINT_SELECTED_READ_ONLY_FRONTIER"

    identity = {
        "checkpoint_sha256": sha256_file(checkpoint),
        "frontier_sha256": sha256_bytes(frontier_raw),
        "selected_id": selected["id"],
        "scores": [(row["id"], round(row["avg_nll"], 12)) for row in scored],
        "margin": margin,
    }
    attention_id = "jta-" + sha256_bytes(canonical_bytes(identity))[:24]
    out = {
        "schema": ATTENTION_SCHEMA,
        "attention_id": attention_id,
        "status": "ABSTAIN" if selected["id"] == NO_INSPECTION else "READ_ONLY_INSPECTION_SELECTED",
        "selection_method": "OWN_CHECKPOINT_AVG_NLL_WITH_NO_INSPECTION_AND_MARGIN_GATE",
        "checkpoint_sha256": identity["checkpoint_sha256"],
        "frontier_sha256": identity["frontier_sha256"],
        "frontier_observation_sha256": frontier.get("observation_sha256"),
        "raw_candidate_count": len(raw_candidates),
        "candidate_count": len(candidates),
        "ineligible_candidate_count": len(raw_candidates) - len(candidates),
        "ineligible_ref_markers": list(INELIGIBLE_REF_MARKERS),
        "margin_required": margin,
        "top_margin": None if not math.isfinite(top_margin) else top_margin,
        "action_margin_over_no_inspection": action_margin,
        "reason": reason,
        "selected": {
            "ref": selected["ref"],
            "commit": selected["commit"],
            "date_hint": selected["date_hint"],
        },
        "scores": [
            {
                "id": row["id"],
                "ref": row["ref"],
                "commit": row["commit"],
                "date_hint": row["date_hint"],
                "avg_nll": row["avg_nll"],
            }
            for row in scored
        ],
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "selection_is_proof": False,
            "selection_is_active_lineage_change": False,
            "selection_is_runtime_promotion": False,
        },
        "authority": {
            "read_only_inspection_only": True,
            "may_write_observed_repository": False,
            "may_change_active_lineage": False,
            "may_change_proof_ladder": False,
            "may_promote_theorem": False,
            "may_promote_runtime": False,
            "may_merge": False,
            "authority_delta": 0,
        },
        "laws": [
            "ATTENTION != PROOF",
            "ATTENTION != ACTIVE_LINEAGE",
            "READ_ONLY_FETCH != WRITE_AUTHORITY",
            "EXPLICIT_DO_NOT_USE_BRANCH != ELIGIBLE_AUTONOMOUS_INTAKE",
            "NEWER_BRANCH != BETTER_BRANCH",
            "NO_INSPECTION_IS_VALID",
            "P_VS_NP = OPEN",
        ],
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--frontier", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--margin", type=float, default=0.01)
    args = ap.parse_args()
    obj = choose_frontier(Path(args.checkpoint), Path(args.frontier), margin=args.margin)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "attention_id": obj["attention_id"],
        "status": obj["status"],
        "reason": obj["reason"],
        "selected_ref": obj["selected"]["ref"],
        "selected_commit": obj["selected"]["commit"],
        "raw_candidate_count": obj["raw_candidate_count"],
        "candidate_count": obj["candidate_count"],
        "ineligible_candidate_count": obj["ineligible_candidate_count"],
        "P_VS_NP": obj["scientific_boundary"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
