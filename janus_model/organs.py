from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HRAIN_AGENT = "SCOUT_HRAIN_02"
INAIHR_AGENT = "SCOUT_INAIHR_03"
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


def build_modular_context(
    scout_root: Path,
    module_registry_path: Path | None = None,
    self_memory_root: Path | None = None,
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
    degraded_module_ids = sorted(
        agent_id for agent_id, module in modules.items() if module.get("observation_degraded") is True
    )
    core = {
        "schema": "janus.model.modular_organ_context.v2",
        "status": "READ_ONLY_MODULAR_ORGAN_CONTEXT",
        "canonical_formula": "HRAIN_GROUNDS -> EYE_BRIDGES -> INAIHR_ASSOCIATES -> HRAIN_MEDIATES -> NATIVE_MODEL_DECIDES -> VERIFY_DECIDES",
        "module_count": len(modules),
        "degraded_module_count": len(degraded_module_ids),
        "degraded_module_ids": degraded_module_ids,
        "module_registry_sha256": registry_sha,
        "repository_modules": modules,
        "organs": {"HRAiN": hrain, "iNaiHR": inaihr},
        "self_memory": self_memory,
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
            "terminal_authority": "VERIFY",
        },
    }
    digest = sha256_bytes(canonical_bytes(core))
    core["context_sha256"] = digest
    core["native_prompt_suffix"] = (
        f"CTX MODULES={len(modules)}; DEGRADED={len(degraded_module_ids)}; HRAiN@{hrain['target_commit'][:8]}=STRUCTURE; "
        f"iNaiHR@{inaihr['target_commit'][:8]}=ASSOCIATION; "
        f"SELF@{(self_memory.get('digest_sha256') or 'NONE')[:8]}; "
        "VERIFY=DECIDES; AGREEMENT!=TRUTH; PATCH!=PASS"
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
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    context = build_modular_context(
        Path(args.scout_root),
        Path(args.module_registry) if args.module_registry else None,
        Path(args.self_memory_root) if args.self_memory_root else None,
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
        "hrain_commit": context["organs"]["HRAiN"]["target_commit"],
        "inaihr_commit": context["organs"]["iNaiHR"]["target_commit"],
    }, indent=2))


if __name__ == "__main__":
    main()
