from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

MEMORY_SCHEMA = "janus.verified_outcome_memory.v1"
PROPOSAL_SCHEMA = "janus.patch_proposal.v1"
RECEIPT_SCHEMA = "janus.module_actuator.receipt.v1"
MAX_RECORDS = 64
PRIOR_CAP_NLL = 0.01
REPO_RE = re.compile(r"^Hawkar-usls/[A-Za-z0-9_.-]+$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sealed_proposal_bytes(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _record_sha(record: dict) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    return sha256_bytes(canonical_bytes(body))


def _validate_previous(path: Path | None) -> list[dict]:
    if path is None or not path.is_file():
        return []
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema") != MEMORY_SCHEMA or obj.get("status") != "VERIFIED_OUTCOME_MEMORY_READY":
        raise RuntimeError("JANUS_OUTCOME_PREVIOUS_MEMORY_SCHEMA_REJECTED")
    policy = obj.get("policy") or {}
    if policy.get("silence_is_negative_evidence") is not False:
        raise RuntimeError("JANUS_OUTCOME_SILENCE_FIREWALL_REJECTED")
    if policy.get("only_target_local_verify_pass_is_positive_feedback") is not True:
        raise RuntimeError("JANUS_OUTCOME_VERIFIER_FIREWALL_REJECTED")
    if policy.get("native_model_selected_required_for_training_prior") is not True:
        raise RuntimeError("JANUS_OUTCOME_NATIVE_SELECTION_FIREWALL_REJECTED")
    if policy.get("feedback_grants_mutation_authority") is not False:
        raise RuntimeError("JANUS_OUTCOME_AUTHORITY_FIREWALL_REJECTED")
    records = obj.get("records")
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise RuntimeError("JANUS_OUTCOME_PREVIOUS_RECORDS_REJECTED")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("JANUS_OUTCOME_PREVIOUS_RECORD_OBJECT_REQUIRED")
        proposal_id = record.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id or proposal_id in seen:
            raise RuntimeError("JANUS_OUTCOME_PREVIOUS_PROPOSAL_ID_REJECTED")
        seen.add(proposal_id)
        if record.get("record_sha256") != _record_sha(record):
            raise RuntimeError(f"JANUS_OUTCOME_PREVIOUS_RECORD_HASH_REJECTED:{proposal_id}")
        if record.get("status") != "VERIFY_PASS" or record.get("terminal_authority") != "TARGET_LOCAL_VERIFIER":
            raise RuntimeError(f"JANUS_OUTCOME_PREVIOUS_VERIFIER_REJECTED:{proposal_id}")
        if record.get("autonomous_merge") is not False or record.get("main_mutated") is not False:
            raise RuntimeError(f"JANUS_OUTCOME_PREVIOUS_MUTATION_FIREWALL_REJECTED:{proposal_id}")
        if record.get("training_eligible") is True and record.get("native_model_selected") is not True:
            raise RuntimeError(f"JANUS_OUTCOME_PREVIOUS_TRAINING_SOURCE_REJECTED:{proposal_id}")
    return [dict(r) for r in records]


def _load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"JANUS_OUTCOME_JSON_OBJECT_REQUIRED:{path}")
    return obj


def validate_pair(proposal_path: Path, receipt_path: Path, branch_head: str, run_id: str) -> dict:
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    if proposal.get("schema") != PROPOSAL_SCHEMA or proposal.get("status") != "PROPOSED":
        raise RuntimeError("JANUS_OUTCOME_PROPOSAL_SCHEMA_REJECTED")
    if proposal.get("create_only") is not True or proposal.get("risk_lane") != "LOW":
        raise RuntimeError("JANUS_OUTCOME_PROPOSAL_BOUNDARY_REJECTED")
    proposal_id = proposal.get("proposal_id")
    decision_id = proposal.get("decision_id")
    if not isinstance(proposal_id, str) or not proposal_id or not isinstance(decision_id, str) or not decision_id:
        raise RuntimeError("JANUS_OUTCOME_PROPOSAL_IDENTITY_REJECTED")
    target = proposal.get("target") or {}
    repository = target.get("repository")
    expected_commit = target.get("expected_target_commit")
    verification_profile = proposal.get("verification_profile")
    if not isinstance(repository, str) or not REPO_RE.fullmatch(repository):
        raise RuntimeError(f"JANUS_OUTCOME_TARGET_REPOSITORY_REJECTED:{proposal_id}")
    if not isinstance(expected_commit, str) or not HEX40_RE.fullmatch(expected_commit):
        raise RuntimeError(f"JANUS_OUTCOME_TARGET_COMMIT_REJECTED:{proposal_id}")
    if not isinstance(verification_profile, str) or not verification_profile:
        raise RuntimeError(f"JANUS_OUTCOME_VERIFICATION_PROFILE_REJECTED:{proposal_id}")

    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("status") != "VERIFY_PASS":
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_SCHEMA_REJECTED:{proposal_id}")
    if receipt.get("proposal_id") != proposal_id or receipt.get("target_repository") != repository:
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_IDENTITY_REJECTED:{proposal_id}")
    if receipt.get("base_commit") != expected_commit:
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_BASE_REJECTED:{proposal_id}")
    expected_branch = f"janus-self/{proposal_id}"
    if receipt.get("branch") != expected_branch:
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_BRANCH_REJECTED:{proposal_id}")
    if receipt.get("verification_profile") != verification_profile:
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_PROFILE_REJECTED:{proposal_id}")
    proposal_seal_sha = sha256_bytes(sealed_proposal_bytes(proposal))
    if receipt.get("proposal_sha256") != proposal_seal_sha:
        raise RuntimeError(f"JANUS_OUTCOME_RECEIPT_PROPOSAL_HASH_REJECTED:{proposal_id}")
    if receipt.get("terminal_authority") != "TARGET_LOCAL_VERIFIER":
        raise RuntimeError(f"JANUS_OUTCOME_TERMINAL_AUTHORITY_REJECTED:{proposal_id}")
    if receipt.get("autonomous_merge") is not False or receipt.get("main_mutated") is not False:
        raise RuntimeError(f"JANUS_OUTCOME_MUTATION_FIREWALL_REJECTED:{proposal_id}")
    patch_commit = receipt.get("patch_commit")
    if not isinstance(patch_commit, str) or not HEX40_RE.fullmatch(patch_commit):
        raise RuntimeError(f"JANUS_OUTCOME_PATCH_COMMIT_REJECTED:{proposal_id}")
    if not HEX40_RE.fullmatch(branch_head):
        raise RuntimeError(f"JANUS_OUTCOME_BRANCH_HEAD_REJECTED:{proposal_id}")

    native_selected = proposal.get("native_model_selected") is True
    training_eligible = native_selected and proposal.get("proposal_class") != "BOOTSTRAP_ACTUATOR_CANARY"
    record = {
        "outcome_id": "jout-" + sha256_bytes(canonical_bytes({
            "proposal_sha256": proposal_seal_sha,
            "receipt_sha256": sha256_bytes(receipt_raw),
            "branch_head": branch_head,
        }))[:24],
        "proposal_id": proposal_id,
        "decision_id": decision_id,
        "status": "VERIFY_PASS",
        "target_repository": repository,
        "base_commit": expected_commit,
        "patch_commit": patch_commit,
        "branch": expected_branch,
        "branch_head": branch_head,
        "verification_profile": verification_profile,
        "proposal_sha256": proposal_seal_sha,
        "receipt_sha256": sha256_bytes(receipt_raw),
        "terminal_authority": "TARGET_LOCAL_VERIFIER",
        "autonomous_merge": False,
        "main_mutated": False,
        "native_model_selected": native_selected,
        "proposal_class": proposal.get("proposal_class"),
        "training_eligible": training_eligible,
        "positive_feedback": training_eligible,
        "first_seen_run_id": run_id,
        "truth_claim": False,
        "mutation_authority_granted": False,
    }
    record["record_sha256"] = _record_sha(record)
    return record


def _clone_exact_branch(repository: str, branch: str, destination: Path) -> tuple[bool, str | None]:
    if destination.exists():
        shutil.rmtree(destination)
    cmd = [
        "git", "clone", "--quiet", "--depth", "1", "--single-branch", "--branch", branch,
        f"https://github.com/{repository}.git", str(destination),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        return False, None
    head = subprocess.check_output(["git", "-C", str(destination), "rev-parse", "HEAD"], text=True).strip()
    return True, head


def collect(self_memory_root: Path, previous: Path | None, run_id: str, max_records: int = MAX_RECORDS) -> tuple[dict, dict]:
    if max_records < 1 or max_records > MAX_RECORDS:
        raise RuntimeError("JANUS_OUTCOME_MAX_RECORDS_REJECTED")
    proposals_root = self_memory_root / "JANUS" / "PATCHES" / "PROPOSALS"
    if not proposals_root.is_dir():
        raise RuntimeError("JANUS_OUTCOME_PROPOSALS_ROOT_MISSING")
    old_records = _validate_previous(previous)
    records_by_id = {r["proposal_id"]: r for r in old_records}
    observed = 0
    unavailable = 0
    new_records = 0
    new_training_eligible = 0

    with tempfile.TemporaryDirectory(prefix="janus-outcome-") as tmp:
        temp_root = Path(tmp)
        for proposal_path in sorted(proposals_root.glob("*.json")):
            proposal = _load_json(proposal_path)
            if proposal.get("schema") != PROPOSAL_SCHEMA or proposal.get("status") != "PROPOSED":
                continue
            proposal_id = proposal.get("proposal_id")
            target = proposal.get("target") or {}
            repository = target.get("repository")
            if not isinstance(proposal_id, str) or not proposal_id:
                raise RuntimeError(f"JANUS_OUTCOME_PROPOSAL_ID_REJECTED:{proposal_path.name}")
            if not isinstance(repository, str) or not REPO_RE.fullmatch(repository):
                raise RuntimeError(f"JANUS_OUTCOME_REPOSITORY_REJECTED:{proposal_id}")
            branch = f"janus-self/{proposal_id}"
            checkout = temp_root / sha256_bytes(repository.encode("utf-8"))[:12] / proposal_id
            ok, head = _clone_exact_branch(repository, branch, checkout)
            if not ok or head is None:
                unavailable += 1
                continue
            receipt_path = checkout / ".janus" / "receipts" / f"{proposal_id}.json"
            if not receipt_path.is_file():
                unavailable += 1
                continue
            record = validate_pair(proposal_path, receipt_path, head, run_id)
            observed += 1
            existing = records_by_id.get(proposal_id)
            if existing is None:
                records_by_id[proposal_id] = record
                new_records += 1
                new_training_eligible += 1 if record["training_eligible"] else 0
            else:
                record["first_seen_run_id"] = existing["first_seen_run_id"]
                record["record_sha256"] = _record_sha(record)
                if existing["record_sha256"] != record["record_sha256"]:
                    raise RuntimeError(f"JANUS_OUTCOME_IMMUTABLE_RECEIPT_DRIFT:{proposal_id}")

    ordered = list(records_by_id.values())[-max_records:]
    training_records = [r for r in ordered if r.get("training_eligible") is True]
    memory = {
        "schema": MEMORY_SCHEMA,
        "status": "VERIFIED_OUTCOME_MEMORY_READY",
        "policy": {
            "silence_is_negative_evidence": False,
            "only_target_local_verify_pass_is_positive_feedback": True,
            "native_model_selected_required_for_training_prior": True,
            "feedback_grants_mutation_authority": False,
            "historical_verify_pass_is_world_truth": False,
            "target_local_reverification_still_required": True,
            "max_records": max_records,
            "decision_prior_cap_nll": PRIOR_CAP_NLL,
        },
        "record_count": len(ordered),
        "training_eligible_count": len(training_records),
        "records": ordered,
    }
    summary = {
        "schema": "janus.verified_outcome_scan.v1",
        "status": "PASS",
        "run_id": run_id,
        "verified_receipts_observed": observed,
        "unavailable_or_not_yet_verified": unavailable,
        "new_records": new_records,
        "new_training_eligible": new_training_eligible,
        "total_records": len(ordered),
        "training_eligible_count": len(training_records),
        "silence_is_negative_evidence": False,
    }
    return memory, summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-memory-root", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scan-summary", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--max-records", type=int, default=MAX_RECORDS)
    args = ap.parse_args()
    previous = Path(args.previous) if args.previous else None
    memory, summary = collect(Path(args.self_memory_root), previous, args.run_id, args.max_records)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(memory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scan = Path(args.scan_summary)
    scan.parent.mkdir(parents=True, exist_ok=True)
    scan.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
