from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

TARGET = "Hawkar-usls/Janus-Demiurge"
EXPECTED_ACTOR = "Hawkar-usls"
GRANT_SCHEMA = "janus.activator.execution_grant.v0.7"
OPERATION = "READ_ONLY_ORIENTATION_SNAPSHOT"
RISK_CLASS = "R0_INTERNAL_READ_ONLY_ORIENTATION"
EXECUTION_SCOPE = "TARGET_REPOSITORY_LOCAL_READ_ONLY_METADATA"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_grant(grant: Dict[str, Any]) -> bool:
    if not isinstance(grant, dict):
        return False
    claimed = str(grant.get("grant_hash") or "")
    if len(claimed) != 64:
        return False
    body = dict(grant)
    body.pop("grant_hash", None)
    if canonical_hash(body) != claimed:
        return False
    expected_id = "xg-" + canonical_hash({
        "authenticated_final_receipt_hash": grant.get("authenticated_final_receipt_hash"),
        "packet_id": grant.get("packet_id"),
        "packet_hash": grant.get("packet_hash"),
        "target_organ": grant.get("target_organ"),
        "operation": grant.get("operation"),
    })
    return all([
        grant.get("schema") == GRANT_SCHEMA,
        grant.get("grant_id") == expected_id,
        grant.get("target_organ") == TARGET,
        grant.get("operation") == OPERATION,
        grant.get("risk_class") == RISK_CLASS,
        grant.get("execution_scope") == EXECUTION_SCOPE,
        grant.get("terminal") == "EXECUTION_GRANT_ISSUED_READ_ONLY_ORIENTATION",
        grant.get("target_execution_authorized") is True,
        grant.get("repository_write_authorized") is False,
        grant.get("network_access_authorized") is False,
        grant.get("model_access_authorized") is False,
        grant.get("command_authority_granted") is False,
        grant.get("claim_authority_granted") is False,
        grant.get("scientific_evidence_authority_granted") is False,
        grant.get("external_effect_authorized") is False,
        grant.get("physical_runtime_effect_authorized") is False,
    ])


def orientation_snapshot(repo_root: str | Path, target_head_sha: str) -> Dict[str, Any]:
    root = Path(repo_root).resolve()
    selected = [
        "PROJECT_STATUS.json",
        "scout_swarm/SCOUT_SWARM_MANIFEST-v1.json",
        "protocol/DEMIURGE_SPIRAL_EVOLUTION-v1.json",
        "scout_swarm/orchestrator/TOPA_SCOUT_EPISTEMIC_PROTOCOL-v1.json",
        "tools/demiurge_scout_swarm.py",
    ]
    selected_hashes: Dict[str, str] = {}
    for rel in selected:
        path = root / rel
        if path.is_file():
            selected_hashes[rel] = file_sha256(path)

    counts = {
        "agent_manifests": len(list((root / ".github" / "agents").glob("*.agent.md"))) if (root / ".github" / "agents").is_dir() else 0,
        "workflows": len(list((root / ".github" / "workflows").glob("*.yml"))) + len(list((root / ".github" / "workflows").glob("*.yaml"))) if (root / ".github" / "workflows").is_dir() else 0,
        "protocol_json": len(list((root / "protocol").glob("*.json"))) if (root / "protocol").is_dir() else 0,
        "python_tests": len(list((root / "tests").glob("test*.py"))) if (root / "tests").is_dir() else 0,
        "python_tools": len(list((root / "tools").glob("*.py"))) if (root / "tools").is_dir() else 0,
    }
    snapshot = {
        "schema": "janus.demiurge.readonly_orientation_snapshot.v0.1",
        "repository": TARGET,
        "target_head_sha": str(target_head_sha),
        "counts": counts,
        "selected_control_file_sha256": selected_hashes,
        "source_scope": "CHECKED_OUT_REPOSITORY_ONLY",
        "target_process_network_access": False,
        "model_access": False,
        "repository_write_performed": False,
        "external_effect_performed": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
    }
    snapshot["snapshot_hash"] = canonical_hash(snapshot)
    return snapshot


def execute(
    grant: Dict[str, Any],
    *,
    repo_root: str | Path,
    target_head_sha: str,
    source_actor: str,
    expected_actor: str = EXPECTED_ACTOR,
) -> Dict[str, Any]:
    source_actor = str(source_actor).strip()
    grant_claimed_hash = str(grant.get("grant_hash") or "") if isinstance(grant, dict) else ""
    bound_grant_hash = grant_claimed_hash if len(grant_claimed_hash) == 64 else canonical_hash(grant)
    grant_id = str(grant.get("grant_id") or "xg-" + "0" * 64) if isinstance(grant, dict) else "xg-" + "0" * 64
    execution_id = "exec-" + canonical_hash({
        "grant_hash": bound_grant_hash,
        "grant_id": grant_id,
        "target_head_sha": str(target_head_sha),
        "operation": OPERATION,
    })

    terminal = "EXECUTED_READ_ONLY_ORIENTATION"
    reasons: list[str] = []
    performed = False
    snapshot: Dict[str, Any] | None = None

    if source_actor != expected_actor:
        terminal = "EXECUTION_BLOCKED_UNTRUSTED_GITHUB_ACTOR"
        reasons.append("repository_dispatch actor is outside the pinned initial GitHub execution trust model.")
    elif not verify_grant(grant):
        terminal = "EXECUTION_BLOCKED_INVALID_GRANT"
        reasons.append("Execution grant failed integrity, deterministic identity, target, operation or authority-ceiling checks.")
    else:
        snapshot = orientation_snapshot(repo_root, target_head_sha)
        performed = True
        reasons.extend([
            "Valid bounded v0.7 execution grant admitted under the explicit initial GitHub actor trust model.",
            "Only checked-out repository metadata was read by the target process.",
            "No model call, target-process network access, repository write, claim authority or external-world effect was authorized or performed.",
        ])

    receipt = {
        "schema": "janus.demiurge.activator_execution_receipt.v0.1",
        "execution_id": execution_id,
        "created_at": time.time(),
        "source_actor": source_actor,
        "source_actor_trust_model": f"PINNED_GITHUB_ACTOR:{expected_actor}",
        "grant_id": grant_id,
        "grant_hash": bound_grant_hash,
        "target_repository": TARGET,
        "target_head_sha": str(target_head_sha),
        "operation": OPERATION,
        "risk_class": RISK_CLASS,
        "execution_scope": EXECUTION_SCOPE,
        "execution_authorized": bool(performed),
        "execution_performed": bool(performed),
        "snapshot_hash": snapshot.get("snapshot_hash") if snapshot else None,
        "target_process_network_access": False,
        "model_access": False,
        "repository_write_performed": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "external_effect_performed": False,
        "physical_runtime_effect_authorized": False,
        "terminal": terminal,
        "reasons": reasons,
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return {"receipt": receipt, "snapshot": snapshot}


def verify_execution_receipt(receipt: Dict[str, Any]) -> bool:
    if not isinstance(receipt, dict):
        return False
    claimed = str(receipt.get("receipt_hash") or "")
    if len(claimed) != 64:
        return False
    body = dict(receipt)
    body.pop("receipt_hash", None)
    if canonical_hash(body) != claimed:
        return False
    if receipt.get("schema") != "janus.demiurge.activator_execution_receipt.v0.1":
        return False
    if receipt.get("external_effect_authorized") is not False or receipt.get("external_effect_performed") is not False:
        return False
    if receipt.get("repository_write_performed") is not False or receipt.get("target_process_network_access") is not False:
        return False
    if receipt.get("model_access") is not False or receipt.get("claim_authority_granted") is not False:
        return False
    if receipt.get("scientific_evidence_authority_granted") is not False:
        return False
    if receipt.get("terminal") == "EXECUTED_READ_ONLY_ORIENTATION":
        return receipt.get("execution_authorized") is True and receipt.get("execution_performed") is True and isinstance(receipt.get("snapshot_hash"), str)
    return receipt.get("execution_authorized") is False and receipt.get("execution_performed") is False and receipt.get("snapshot_hash") is None


def main() -> None:
    parser = argparse.ArgumentParser(description="JANUS Demiurge bounded read-only Activator execution")
    parser.add_argument("--grant", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-head-sha", required=True)
    parser.add_argument("--source-actor", required=True)
    parser.add_argument("--receipt-out", required=True)
    parser.add_argument("--snapshot-out", required=True)
    args = parser.parse_args()

    grant = json.loads(Path(args.grant).read_text(encoding="utf-8"))
    if not isinstance(grant, dict):
        raise SystemExit("EXECUTION_GRANT_JSON_OBJECT_REQUIRED")
    result = execute(
        grant,
        repo_root=args.repo_root,
        target_head_sha=args.target_head_sha,
        source_actor=args.source_actor,
    )
    receipt_path = Path(args.receipt_out)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(result["receipt"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["snapshot"] is not None:
        snapshot_path = Path(args.snapshot_out)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(result["snapshot"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["receipt"], ensure_ascii=False, indent=2, sort_keys=True))
    if result["receipt"]["terminal"] != "EXECUTED_READ_ONLY_ORIENTATION":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
