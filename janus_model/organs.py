from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HRAIN_AGENT = "SCOUT_HRAIN_02"
INAIHR_AGENT = "SCOUT_INAIHR_03"
EXPECTED = {
    HRAIN_AGENT: ("Hawkar-usls/Hrain", "LEFT_HRAIN", "STRUCTURAL_CONTEXT_GROUNDING_MEDIATOR"),
    INAIHR_AGENT: ("Hawkar-usls/iNaiHR", "RIGHT_INAIHR", "ASSOCIATIVE_CONTEXT"),
}


def canonical_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load_agent(root: Path, agent_id: str) -> dict:
    path = root / f"{agent_id}.json"
    if not path.exists():
        raise RuntimeError(f"ORGAN_SCOUT_STATE_MISSING:{agent_id}")
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    repository, hemisphere, organ_role = EXPECTED[agent_id]
    if obj.get("agent_id") != agent_id:
        raise RuntimeError(f"ORGAN_AGENT_ID_MISMATCH:{agent_id}")
    if obj.get("status") != "OBSERVED_REPOSITORY_STATE":
        raise RuntimeError(f"ORGAN_STATE_NOT_OBSERVED:{agent_id}")
    target = obj.get("target") or {}
    snapshot = obj.get("repository_snapshot") or {}
    if target.get("repository") != repository or snapshot.get("target_repo") != repository:
        raise RuntimeError(f"ORGAN_REPOSITORY_MISMATCH:{agent_id}")
    commit = snapshot.get("target_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise RuntimeError(f"ORGAN_TARGET_COMMIT_INVALID:{agent_id}")
    return {
        "agent_id": agent_id,
        "hemisphere": hemisphere,
        "organ_role": organ_role,
        "scout_role": obj.get("role"),
        "observed_at_utc": obj.get("created_at_utc"),
        "repository": repository,
        "ref": target.get("ref"),
        "target_commit": commit,
        "file_count": snapshot.get("file_count"),
        "focus": obj.get("focus"),
        "recent_commits": list(snapshot.get("recent_commits") or [])[:5],
        "scout_state_sha256": sha256_bytes(raw),
    }


def build_bicameral_context(scout_root: Path) -> dict:
    hrain = _load_agent(scout_root, HRAIN_AGENT)
    inaihr = _load_agent(scout_root, INAIHR_AGENT)
    core = {
        "schema": "janus.model.bicameral_organ_context.v1",
        "status": "READ_ONLY_ORGAN_CONTEXT",
        "canonical_formula": "HRAIN_GROUNDS -> EYE_BRIDGES -> INAIHR_ASSOCIATES -> HRAIN_MEDIATES -> VERIFY_DECIDES",
        "organs": {"HRAiN": hrain, "iNaiHR": inaihr},
        "firewalls": {
            "read_only": True,
            "direct_cross_hemisphere_mutation": False,
            "direct_eye_to_inaihr_bypass": False,
            "bicameral_agreement_is_truth": False,
            "inaihr_association_is_evidence": False,
            "terminal_authority": "VERIFY",
        },
    }
    digest = sha256_bytes(canonical_bytes(core))
    core["context_sha256"] = digest
    core["native_prompt_suffix"] = (
        f"CTX HRAiN@{hrain['target_commit'][:8]}=STRUCTURE; "
        f"iNaiHR@{inaihr['target_commit'][:8]}=ASSOCIATION; VERIFY=DECIDES; AGREEMENT!=TRUTH"
    )
    return core


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scout-root", default="scout_swarm/state/agents")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    context = build_bicameral_context(Path(args.scout_root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": context["status"],
        "context_sha256": context["context_sha256"],
        "hrain_commit": context["organs"]["HRAiN"]["target_commit"],
        "inaihr_commit": context["organs"]["iNaiHR"]["target_commit"],
    }, indent=2))


if __name__ == "__main__":
    main()
