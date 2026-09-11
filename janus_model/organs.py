from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HRAIN_AGENT = "SCOUT_HRAIN_02"
INAIHR_AGENT = "SCOUT_INAIHR_03"
DEFAULT_TRUMP_RESEARCH_CONTEXT = Path("janus_model/state/JANUS_TRUMP_RESEARCH_CONTEXT.json")
CORE_EXPECTED = {
    HRAIN_AGENT: ("Hawkar-usls/Hrain", "LEFT_HRAIN", "STRUCTURAL_CONTEXT_GROUNDING_MEDIATOR"),
    INAIHR_AGENT: ("Hawkar-usls/iNaiHR", "RIGHT_INAIHR", "ASSOCIATIVE_CONTEXT"),
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"JSON_MISSING:{path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"JSON_OBJECT_REQUIRED:{path}")
    return obj


def _load_agent(root: Path, agent_id: str, expected_repository: str | None = None) -> dict:
    path = root / f"{agent_id}.json"
    if not path.exists():
        raise RuntimeError(f"ORGAN_SCOUT_STATE_MISSING:{agent_id}")
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    if obj.get("agent_id") != agent_id:
        raise RuntimeError(f"ORGAN_AGENT_ID_MISMATCH:{agent_id}")

    scout_status = obj.get("status")
    observation_degraded = isinstance(scout_status, str) and scout_status.startswith("DEGRADED_")
    if scout_status != "OBSERVED_REPOSITORY_STATE" and not observation_degraded:
        raise RuntimeError(f"ORGAN_STATE_NOT_OBSERVED:{agent_id}")

    target = obj.get("target") or {}
    snapshot = obj.get("repository_snapshot") or {}
    repository = target.get("repository")
    if not isinstance(repository, str) or not repository:
        raise RuntimeError(f"ORGAN_REPOSITORY_MISSING:{agent_id}")
    if snapshot.get("target_repo") != repository:
        raise RuntimeError(f"ORGAN_SNAPSHOT_REPOSITORY_MISMATCH:{agent_id}")
    if expected_repository is not None and repository != expected_repository:
        raise RuntimeError(f"ORGAN_REPOSITORY_MISMATCH:{agent_id}")
    commit = snapshot.get("target_commit")
    if not isinstance(commit, str) or len(commit) != 40:
        raise RuntimeError(f"ORGAN_TARGET_COMMIT_INVALID:{agent_id}")
    return {
        "agent_id": agent_id,
        "scout_role": obj.get("role"),
        "scout_status": scout_status,
        "observation_degraded": observation_degraded,
        "observed_at_utc": obj.get("created_at_utc"),
        "repository": repository,
        "ref": target.get("ref"),
        "target_commit": commit,
        "file_count": snapshot.get("file_count"),
        "focus": obj.get("focus"),
        "recent_commits": list(snapshot.get("recent_commits") or [])[:5],
        "scout_state_sha256": sha256_bytes(raw),
    }


def _self_memory_identity(self_memory_root: Path | None) -> dict:
    if self_memory_root is None:
        return {
            "status": "SELF_MEMORY_NOT_BOUND",
            "digest_sha256": None,
            "file_count": 0,
            "raw_reflections_are_training_source": False,
        }
    if not self_memory_root.exists():
        raise RuntimeError("JANUS_SELF_MEMORY_ROOT_MISSING")
    rows: list[dict[str, Any]] = []
    for path in sorted(p for p in self_memory_root.rglob("*") if p.is_file()):
        rel = path.relative_to(self_memory_root).as_posix()
        rows.append({"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    digest = sha256_bytes(canonical_bytes(rows))
    return {
        "status": "BOUND_READ_ONLY_SELF_MEMORY",
        "root": self_memory_root.as_posix(),
        "digest_sha256": digest,
        "file_count": len(rows),
        "raw_reflections_are_training_source": False,
    }


def _trump_research_identity(path: Path | None) -> dict:
    if path is None:
        path = DEFAULT_TRUMP_RESEARCH_CONTEXT
    if not path.is_file():
        return {
            "status": "TRUMP_RESEARCH_CONTEXT_NOT_BOUND",
            "digest_sha256": None,
            "P_VS_NP": "OPEN",
            "frontier_candidate_count": 0,
            "frontier_top_ref": None,
            "frontier_top_commit": None,
            "grants_mutation_authority": False,
            "frontier_is_proof": False,
        }
    obj = _load_json(path)
    if obj.get("P_VS_NP") != "OPEN":
        raise RuntimeError("ORGAN_TRUMP_P_VS_NP_MUST_REMAIN_OPEN")
    authority = obj.get("authority") or {}
    if authority.get("may_grant_runtime_promotion") is not False:
        raise RuntimeError("ORGAN_TRUMP_RUNTIME_AUTHORITY_REJECTED")
    if authority.get("proof_ladder_state_is_theorem") is not False:
        raise RuntimeError("ORGAN_TRUMP_THEOREM_AUTHORITY_REJECTED")
    if authority.get("frontier_observation_changes_active_lineage") not in {None, False}:
        raise RuntimeError("ORGAN_TRUMP_FRONTIER_LINEAGE_AUTHORITY_REJECTED")
    if authority.get("frontier_observation_is_proof") not in {None, False}:
        raise RuntimeError("ORGAN_TRUMP_FRONTIER_PROOF_AUTHORITY_REJECTED")
    fundamentum = obj.get("fundamentum") or {}
    frontier = fundamentum.get("independent_frontier_observation") or {}
    candidates = frontier.get("candidates") or []
    if not isinstance(candidates, list):
        raise RuntimeError("ORGAN_TRUMP_FRONTIER_CANDIDATES_REJECTED")
    top = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    return {
        "status": "BOUND_READ_ONLY_TRUMP_RESEARCH_CONTEXT",
        "digest_sha256": sha256_file(path),
        "context_sha256": obj.get("context_sha256"),
        "P_VS_NP": "OPEN",
        "active_stage": fundamentum.get("active_stage"),
        "active_commit": fundamentum.get("observed_commit"),
        "next_gate": fundamentum.get("next_gate"),
        "frontier_candidate_count": len(candidates),
        "frontier_top_ref": top.get("ref"),
        "frontier_top_commit": top.get("commit"),
        "grants_mutation_authority": False,
        "frontier_is_proof": False,
    }


def build_modular_context(
    scout_root: Path,
    module_registry_path: Path | None = None,
    self_memory_root: Path | None = None,
    trump_research_context_path: Path | None = None,
) -> dict:
    if module_registry_path is not None:
        registry = _load_json(module_registry_path)
        discovery = registry.get("discovery") or {}
        agent_ids = discovery.get("discovered_agent_ids")
        if not isinstance(agent_ids, list) or not agent_ids:
            raise RuntimeError("MODULE_REGISTRY_AGENT_LIST_MISSING")
        if len(agent_ids) != len(set(agent_ids)):
            raise RuntimeError("MODULE_REGISTRY_DUPLICATE_AGENT_ID")
        registry_sha = sha256_file(module_registry_path)
    else:
        agent_ids = sorted(p.stem for p in scout_root.glob("SCOUT_*.json"))
        registry_sha = None
    modules: dict[str, dict] = {}
    repositories: set[str] = set()
    for agent_id in agent_ids:
        module = _load_agent(scout_root, str(agent_id))
        repository = module["repository"]
        if repository in repositories:
            raise RuntimeError(f"DUPLICATE_REPOSITORY_MODULE:{repository}")
        repositories.add(repository)
        module["module_id"] = f"REPO::{repository}"
        module["authority_lane"] = "READ_ONLY"
        module["mutation_authority"] = False
        modules[str(agent_id)] = module

    for agent_id, (repository, hemisphere, organ_role) in CORE_EXPECTED.items():
        if agent_id not in modules:
            raise RuntimeError(f"CORE_ORGAN_MISSING:{agent_id}")
        if modules[agent_id]["repository"] != repository:
            raise RuntimeError(f"CORE_ORGAN_REPOSITORY_MISMATCH:{agent_id}")
        modules[agent_id]["hemisphere"] = hemisphere
        modules[agent_id]["organ_role"] = organ_role

    hrain = modules[HRAIN_AGENT]
    inaihr = modules[INAIHR_AGENT]
    self_memory = _self_memory_identity(self_memory_root)
    trump_research = _trump_research_identity(trump_research_context_path)
    degraded_module_ids = sorted(
        agent_id for agent_id, module in modules.items() if module.get("observation_degraded") is True
    )
    core = {
        "schema": "janus.model.modular_organ_context.v3",
        "status": "READ_ONLY_MODULAR_ORGAN_CONTEXT",
        "canonical_formula": "HRAIN_GROUNDS -> EYE_BRIDGES -> INAIHR_ASSOCIATES -> HRAIN_MEDIATES -> TRUMP_RESEARCH_INFORMS -> NATIVE_MODEL_DECIDES -> VERIFY_DECIDES",
        "module_count": len(modules),
        "degraded_module_count": len(degraded_module_ids),
        "degraded_module_ids": degraded_module_ids,
        "module_registry_sha256": registry_sha,
        "repository_modules": modules,
        "organs": {"HRAiN": hrain, "iNaiHR": inaihr},
        "self_memory": self_memory,
        "trump_research": trump_research,
        "firewalls": {
            "read_only": True,
            "module_observation_grants_mutation": False,
            "degraded_observation_is_health": False,
            "degraded_observation_blocks_valid_snapshot_context": False,
            "direct_cross_hemisphere_mutation": False,
            "direct_eye_to_inaihr_bypass": False,
            "bicameral_agreement_is_truth": False,
            "inaihr_association_is_evidence": False,
            "raw_self_reflection_is_training_source": False,
            "trump_context_grants_mutation": False,
            "trump_frontier_is_proof": False,
            "terminal_authority": "VERIFY",
        },
    }
    digest = sha256_bytes(canonical_bytes(core))
    core["context_sha256"] = digest
    trump_digest = (trump_research.get("digest_sha256") or "NONE")[:8]
    frontier_commit = (trump_research.get("frontier_top_commit") or "NONE")[:8]
    core["native_prompt_suffix"] = (
        f"CTX MODULES={len(modules)}; DEGRADED={len(degraded_module_ids)}; HRAiN@{hrain['target_commit'][:8]}=STRUCTURE; "
        f"iNaiHR@{inaihr['target_commit'][:8]}=ASSOCIATION; "
        f"SELF@{(self_memory.get('digest_sha256') or 'NONE')[:8]}; "
        f"TRUMP@{trump_digest}=OPEN; FRONTIER@{frontier_commit}; "
        "VERIFY=DECIDES; AGREEMENT!=TRUTH; FRONTIER!=PROOF; PATCH!=PASS"
    )
    return core


def build_bicameral_context(scout_root: Path) -> dict:
    """Compatibility entrypoint retained for callers that only need the original pair."""
    return build_modular_context(scout_root)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scout-root", default="scout_swarm/state/agents")
    ap.add_argument("--module-registry")
    ap.add_argument("--self-memory-root")
    ap.add_argument("--trump-research-context")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    context = build_modular_context(
        Path(args.scout_root),
        Path(args.module_registry) if args.module_registry else None,
        Path(args.self_memory_root) if args.self_memory_root else None,
        Path(args.trump_research_context) if args.trump_research_context else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": context["status"],
        "context_sha256": context["context_sha256"],
        "module_count": context["module_count"],
        "degraded_module_count": context["degraded_module_count"],
        "degraded_module_ids": context["degraded_module_ids"],
        "self_memory_digest": context["self_memory"]["digest_sha256"],
        "trump_research_status": context["trump_research"]["status"],
        "trump_research_digest": context["trump_research"]["digest_sha256"],
        "trump_frontier_top_commit": context["trump_research"]["frontier_top_commit"],
        "hrain_commit": context["organs"]["HRAiN"]["target_commit"],
        "inaihr_commit": context["organs"]["iNaiHR"]["target_commit"],
    }, indent=2))


if __name__ == "__main__":
    main()
