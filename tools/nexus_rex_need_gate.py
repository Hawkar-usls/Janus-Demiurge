#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Any

POLICY_SCHEMA = "janus.nexus.rex_need_gate_policy.v1"
PROPOSAL_SCHEMA = "janus.rex.desire_proposal.v1"
MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def load(path: pathlib.Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"JSON object required: {path}")
    return obj


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_if_changed(path: pathlib.Path, obj: dict[str, Any]) -> bool:
    raw = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == raw:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    return True


def is_under(rel: str, roots: list[str]) -> bool:
    return any(rel == root or rel.startswith(root.rstrip("/") + "/") for root in roots)


def module_exists(root: pathlib.Path, module_id: str) -> bool:
    paths = [
        root / "rex/specs" / f"{module_id}.json",
        root / "rex/specs/generated" / f"{module_id}.json",
        root / "rex/admissions" / f"{module_id}.json",
        root / "rex/lifecycle" / f"{module_id}.json",
        root / "rex/candidates" / module_id,
    ]
    return any(p.exists() for p in paths)


def safe_record_count(path: pathlib.Path) -> int:
    count = 0
    for item in sorted(path.glob("*.json")):
        obj = load(item)
        if "authority_delta" in obj and obj.get("authority_delta") != 0:
            continue
        count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description="External Nexus gate for Rex need proposals")
    ap.add_argument("--policy", default="rex/need_gate_policy.json")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--proposals-dir", default="rex/need_proposals/generated")
    ap.add_argument("--desires-dir", default="rex/desires/approved")
    ap.add_argument("--admissions-dir", default="rex/need_admissions")
    a = ap.parse_args()

    root = pathlib.Path(a.repo_root).resolve()
    policy_path = pathlib.Path(a.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load(policy_path)
    if policy.get("schema") != POLICY_SCHEMA or policy.get("enabled") is not True:
        raise SystemExit("Nexus need gate disabled or unsupported")

    req = policy.get("requirements") or {}
    allowed_kinds = set(policy.get("allowed_need_kinds") or [])
    allowed_templates = set(policy.get("allowed_templates") or [])
    allowed_roots = [str(x) for x in policy.get("allowed_observed_roots") or []]
    min_records = int(req.get("min_evidence_records", 3))
    max_approvals = int(req.get("max_auto_approvals_per_run", 1))
    required_state = str(req.get("proposal_state") or "")
    required_lifecycle = str(req.get("lifecycle_mode") or "SCHEDULED")
    required_interval = int(req.get("scheduled_interval_minutes", 360))

    proposals_dir = pathlib.Path(a.proposals_dir)
    if not proposals_dir.is_absolute():
        proposals_dir = root / proposals_dir
    desires_dir = pathlib.Path(a.desires_dir)
    if not desires_dir.is_absolute():
        desires_dir = root / desires_dir
    admissions_dir = pathlib.Path(a.admissions_dir)
    if not admissions_dir.is_absolute():
        admissions_dir = root / admissions_dir

    approved = 0
    created: list[str] = []
    unchanged: list[str] = []
    skipped: list[dict[str, Any]] = []

    proposal_paths = sorted(proposals_dir.glob("*.json")) if proposals_dir.exists() else []

    for proposal_path in proposal_paths:
        proposal = load(proposal_path)
        proposal_id = str(proposal.get("proposal_id") or "")
        if proposal.get("schema") != PROPOSAL_SCHEMA:
            raise SystemExit(f"unsupported proposal schema: {proposal_path}")
        if proposal.get("state") != required_state:
            raise SystemExit(f"proposal state refused: {proposal_id}")
        if (proposal.get("authority") or {}).get("authority_delta") != 0:
            raise SystemExit(f"proposal authority refused: {proposal_id}")
        if proposal.get("need_kind") not in allowed_kinds:
            raise SystemExit(f"need kind refused: {proposal_id}")

        observed = str(proposal.get("observed_path") or "")
        if not observed or not is_under(observed, allowed_roots):
            raise SystemExit(f"observed path refused: {proposal_id}")
        observed_path = (root / observed).resolve()
        try:
            observed_path.relative_to(root)
        except ValueError as e:
            raise SystemExit("observed path escapes repository") from e
        if not observed_path.is_dir():
            raise SystemExit(f"observed path missing: {proposal_id}")

        evidence = proposal.get("evidence") or {}
        record_count = evidence.get("record_count")
        refs = evidence.get("refs") or []
        if not isinstance(record_count, int) or record_count < min_records:
            raise SystemExit(f"insufficient evidence count: {proposal_id}")
        actual_count = safe_record_count(observed_path)
        if actual_count != record_count:
            raise SystemExit(f"evidence count drift: {proposal_id}:{record_count}!={actual_count}")
        if not isinstance(refs, list) or not refs:
            raise SystemExit(f"evidence refs required: {proposal_id}")
        for ref in refs:
            if not isinstance(ref, dict):
                raise SystemExit(f"invalid evidence ref: {proposal_id}")
            rel = str(ref.get("path") or "")
            if not rel.startswith(observed.rstrip("/") + "/"):
                raise SystemExit(f"evidence ref outside observed family: {proposal_id}")
            p = (root / rel).resolve()
            try:
                p.relative_to(observed_path)
            except ValueError as e:
                raise SystemExit(f"evidence ref escapes family: {proposal_id}") from e
            if not p.is_file() or sha256_file(p) != ref.get("sha256"):
                raise SystemExit(f"evidence SHA mismatch: {proposal_id}:{rel}")

        desire = proposal.get("suggested_desire")
        if not isinstance(desire, dict):
            raise SystemExit(f"suggested desire missing: {proposal_id}")
        module_id = str(desire.get("module_id") or "")
        if not MODULE_ID_RE.fullmatch(module_id):
            raise SystemExit(f"module id refused: {proposal_id}")
        if desire.get("template") not in allowed_templates:
            raise SystemExit(f"template refused: {proposal_id}")
        if (desire.get("nexus") or {}).get("request_autorun") is not bool(req.get("request_autorun", True)):
            raise SystemExit(f"autorun policy mismatch: {proposal_id}")
        lifecycle = desire.get("lifecycle") or {}
        if lifecycle.get("enabled") is not True or lifecycle.get("mode") != required_lifecycle:
            raise SystemExit(f"lifecycle mode refused: {proposal_id}")
        if lifecycle.get("interval_minutes") != required_interval:
            raise SystemExit(f"lifecycle interval refused: {proposal_id}")
        life_input = lifecycle.get("input")
        nexus_input = (desire.get("nexus") or {}).get("input")
        if not isinstance(life_input, dict) or not isinstance(nexus_input, dict):
            raise SystemExit(f"bounded inputs required: {proposal_id}")
        if life_input != nexus_input:
            raise SystemExit(f"birth/lifecycle snapshot mismatch: {proposal_id}")

        desire_path = desires_dir / f"{proposal_id}.json"
        receipt_path = admissions_dir / f"{proposal_id}.json"
        if module_exists(root, module_id):
            skipped.append({"proposal_id": proposal_id, "reason": "module_already_exists", "module_id": module_id})
            continue
        if desire_path.exists() and receipt_path.exists():
            unchanged += [desire_path.relative_to(root).as_posix(), receipt_path.relative_to(root).as_posix()]
            continue
        if approved >= max_approvals:
            skipped.append({"proposal_id": proposal_id, "reason": "approval_budget_exhausted"})
            continue

        approved_desires = {
            "schema": "janus.rex.desires.v1",
            "version": "1.2",
            "status": "ACTIVE_BOUNDED_NEXUS_NEED_APPROVAL",
            "authority": {
                "desire_is_evidence": False,
                "desire_is_source_code": False,
                "desire_grants_admission": False,
                "desire_grants_lifecycle": False,
                "authority_delta": 0,
            },
            "requests": [dict(desire, need_provenance={
                "proposal_id": proposal_id,
                "proposal_sha256": sha256_file(proposal_path),
                "gate": "NEXUS_REX_NEED_GATE_V1",
                "gate_grants_code_admission": False,
                "gate_grants_lifecycle": False,
                "authority_delta": 0,
            })],
        }
        receipt = {
            "schema": "janus.nexus.rex_need_admission.v1",
            "proposal_id": proposal_id,
            "proposal_sha256": sha256_file(proposal_path),
            "module_id": module_id,
            "need_kind": proposal.get("need_kind"),
            "evidence_record_count": record_count,
            "state": "NEXUS_NEED_APPROVED_FOR_DIRECTOR_ONLY",
            "grants_code_admission": False,
            "grants_lifecycle": False,
            "director_required": True,
            "auditor_required": True,
            "exact_sha_nexus_admission_required": True,
            "authority_delta": 0,
            "law": "NEED_APPROVAL_NE_CODE_ADMISSION_NE_LIFECYCLE_ADMISSION",
        }
        d_changed = write_if_changed(desire_path, approved_desires)
        r_changed = write_if_changed(receipt_path, receipt)
        for p, changed in ((desire_path, d_changed), (receipt_path, r_changed)):
            (created if changed else unchanged).append(p.relative_to(root).as_posix())
        approved += 1

    summary = {
        "schema": "janus.nexus.rex_need_gate_receipt.v1",
        "status": "PASS",
        "approved_this_run": approved,
        "created_or_changed": created,
        "unchanged": sorted(set(unchanged)),
        "skipped": skipped,
        "authority_delta": 0,
        "law": "NEXUS_NEED_GATE_CAN_APPROVE_DESIRE_ONLY",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
