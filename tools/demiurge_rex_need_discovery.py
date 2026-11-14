#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from typing import Any

POLICY_SCHEMA = "janus.rex.need_discovery_policy.v1"
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


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s or "ledger"


def bounded_module_id(family: str, suffix: str) -> str:
    base = slug(family)
    if not base.startswith("rex_"):
        base = "rex_" + base
    candidate = base + suffix
    if len(candidate) > 64:
        digest = hashlib.sha256(candidate.encode()).hexdigest()[:10]
        keep = 64 - len(suffix) - len(digest) - 1
        candidate = base[:keep].rstrip("_") + "_" + digest + suffix
    if not MODULE_ID_RE.fullmatch(candidate):
        raise SystemExit(f"unable to derive bounded module id from {family!r}")
    return candidate


def module_exists(root: pathlib.Path, module_id: str) -> bool:
    direct = [
        root / "rex/specs" / f"{module_id}.json",
        root / "rex/specs/generated" / f"{module_id}.json",
        root / "rex/admissions" / f"{module_id}.json",
        root / "rex/lifecycle" / f"{module_id}.json",
        root / "rex/candidates" / module_id,
    ]
    return any(p.exists() for p in direct)



def verified_health_parent(root: pathlib.Path, module_id: str, observed: str) -> dict[str, Any] | None:
    """Verify a previous living organ before allowing it to originate children.

    A fitness receipt is evidence of a narrow capability, never permission
    to rewrite governance, add arbitrary templates or deploy model weights.
    """
    try:
        spec = load(root / "rex/specs/generated" / f"{module_id}.json")
        fitness = load(root / "rex/candidates" / module_id / "fitness.json")
        admitted = load(root / "rex/admissions" / f"{module_id}.json")
        lifecycle = load(root / "rex/lifecycle" / f"{module_id}.json")
        source = root / "rex/candidates" / module_id / "module.py"
        if source.is_symlink():
            return None
        actual = sha256_file(source)
        sealed = dict(fitness)
        receipt = sealed.pop("receipt_sha256", None)
        expected = hashlib.sha256(json.dumps(sealed, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        snapshot = (spec.get("nexus") or {}).get("input") or {}
        if (spec.get("template") != "ledger_health" or
            spec.get("module_id") != module_id or
            snapshot.get("observed_path") != observed or
            type(snapshot.get("observed_record_count")) is not int or
            fitness.get("status") != "RESEARCH_FUNCTIONAL_GAIN" or
            fitness.get("new_functional_capability_proven") is not True or
            fitness.get("quality_on_external_future_tasks_proven") is not False or
            fitness.get("production_authority") is not False or
            fitness.get("candidate_module") != module_id or
            fitness.get("candidate_source_sha256") != actual or
            fitness.get("parent_module") != module_id.removesuffix("_ledger_health") + "_ledger_summary" or
            not isinstance(receipt, str) or receipt != expected or
            admitted.get("state") != "ADMITTED_EXACT_SHA" or
            admitted.get("source_sha256") != actual or
            lifecycle.get("state") != "LIFECYCLE_ADMITTED_EXACT_SHA" or
            lifecycle.get("source_sha256") != actual):
            return None
        return {"source_sha256": actual, "fitness_receipt_sha256": receipt,
                "observed_record_count": snapshot["observed_record_count"]}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def compact_row(obj: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "schema",
        "module_id",
        "state",
        "status",
        "result_status",
        "source_sha256",
        "trigger",
        "mode",
    )
    return {k: obj[k] for k in allowed if k in obj and isinstance(obj[k], (str, int, float, bool))}


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS Rex bounded need discovery")
    ap.add_argument("--policy", default="rex/need_discovery_policy.json")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out-dir", default="rex/need_proposals/generated")
    a = ap.parse_args()

    root = pathlib.Path(a.repo_root).resolve()
    policy_path = pathlib.Path(a.policy)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    policy = load(policy_path)
    if policy.get("schema") != POLICY_SCHEMA or policy.get("enabled") is not True:
        raise SystemExit("need discovery policy disabled or unsupported")

    obs = policy.get("observation") or {}
    prop = policy.get("proposal") or {}
    min_records = int(obs.get("min_records_per_family", 3))
    max_refs = int(obs.get("max_evidence_refs", 8))
    max_props = int(obs.get("max_proposals_per_run", 4))
    require_zero = obs.get("require_authority_delta_zero_when_present") is True
    refuse_family_suffixes = tuple(str(x) for x in (obs.get("refuse_family_suffixes") or []) if str(x))
    suffix = str(prop.get("module_suffix") or "_ledger_summary")
    template = str(prop.get("template") or "")
    lifecycle_mode = str(prop.get("lifecycle_mode") or "SCHEDULED")
    interval_minutes = int(prop.get("interval_minutes", 360))
    max_birth_rows = int(prop.get("max_birth_rows", 8))

    if template != "ledger_summary":
        raise SystemExit("v1 need discovery only supports ledger_summary")
    if lifecycle_mode != "SCHEDULED":
        raise SystemExit("v1 need discovery only supports SCHEDULED lifecycle")

    out_dir = pathlib.Path(a.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir

    made: list[str] = []
    unchanged: list[str] = []
    skipped: list[dict[str, Any]] = []
    proposed = 0

    for root_rel in obs.get("ledger_roots") or []:
        if proposed >= max_props:
            break
        if not isinstance(root_rel, str) or not root_rel.startswith("rex/"):
            raise SystemExit(f"invalid observation root: {root_rel!r}")
        ledger_root = (root / root_rel).resolve()
        try:
            ledger_root.relative_to(root)
        except ValueError as e:
            raise SystemExit("observation root escapes repository") from e
        if not ledger_root.exists():
            continue

        families = sorted(p for p in ledger_root.iterdir() if p.is_dir())
        for family_dir in families:
            if proposed >= max_props:
                break
            if any(family_dir.name.endswith(blocked) for blocked in refuse_family_suffixes):
                skipped.append({
                    "family": family_dir.relative_to(root).as_posix(),
                    "reason": "recursive_summary_family_refused",
                })
                continue

            files = sorted(family_dir.glob("*.json"))
            safe: list[tuple[pathlib.Path, dict[str, Any]]] = []
            for path in files:
                try:
                    obj = load(path)
                except Exception as exc:
                    skipped.append({"path": path.relative_to(root).as_posix(), "reason": f"invalid_json:{type(exc).__name__}"})
                    continue
                if require_zero and "authority_delta" in obj and obj.get("authority_delta") != 0:
                    skipped.append({"path": path.relative_to(root).as_posix(), "reason": "authority_delta_nonzero"})
                    continue
                safe.append((path, obj))

            if len(safe) < min_records:
                continue

            module_id = bounded_module_id(family_dir.name, suffix)
            proposed_kind = "ACCUMULATING_JSON_LEDGER"
            proposed_template = template
            if module_exists(root, module_id):
                # A real organ already exists: don't re-propose the same
                # fixed snapshot. A new capability is possible only when
                # enough *additional* ledger evidence has accumulated.
                if len(safe) < 32:
                    skipped.append({"family": family_dir.relative_to(root).as_posix(), "reason": "summary_module_already_exists", "module_id": module_id})
                    continue
                module_id = bounded_module_id(family_dir.name, "_ledger_health")
                proposed_kind = "LEDGER_HEALTH_GAP"
                proposed_template = "ledger_health"
                if module_exists(root, module_id):
                    parent_id = module_id
                    lineage = verified_health_parent(root, parent_id,
                         family_dir.relative_to(root).as_posix())
                    if lineage is None:
                        skipped.append({"family": family_dir.relative_to(root).as_posix(),
                            "reason": "HOLD_UNVERIFIED_HEALTH_PARENT", "module_id": parent_id})
                        continue
                    if len(safe) - lineage["observed_record_count"] < 12:
                        skipped.append({"family": family_dir.relative_to(root).as_posix(),
                            "reason": "HOLD_NEXT_GENERATION_REQUIRES_NEW_RECORDS",
                            "parent_module": parent_id,
                            "new_records": len(safe)-lineage["observed_record_count"]})
                        continue
                    module_id = bounded_module_id(family_dir.name, "_ledger_trend")
                    proposed_kind = "LEDGER_TREND_GAP"
                    proposed_template = "ledger_trend"
                    if module_exists(root, module_id):
                        skipped.append({"family": family_dir.relative_to(root).as_posix(),
                            "reason": "trend_module_already_exists", "module_id": module_id})
                        continue

            observed_path = family_dir.relative_to(root).as_posix()
            need_material = f"{proposed_kind}|{observed_path}|{module_id}".encode()
            proposal_id = "need_" + hashlib.sha256(need_material).hexdigest()[:16]
            evidence = []
            birth_rows = []
            schemas = set()
            for path, obj in safe[:max_refs]:
                rel = path.relative_to(root).as_posix()
                evidence.append({
                    "path": rel,
                    "sha256": sha256_file(path),
                    "schema": str(obj.get("schema") or ""),
                })
                if obj.get("schema"):
                    schemas.add(str(obj["schema"]))
            for _, obj in safe[:max_birth_rows]:
                birth_rows.append(compact_row(obj))

            desire_id = proposal_id.replace("_", "-")
            snapshot_input = {
                "origin": "JANUS_REX_NEED_DISCOVERY_V1",
                "purpose": "AUTO_DETECTED_LEDGER_SUMMARY_NEED",
                "observed_path": observed_path,
                "observed_record_count": len(safe),
                "rows": birth_rows,
            }
            if proposed_template == "ledger_trend":
                snapshot_input["verified_parent_module"] = parent_id
                snapshot_input["verified_parent_source_sha256"] = lineage["source_sha256"]
                snapshot_input["verified_parent_fitness_sha256"] = lineage["fitness_receipt_sha256"]
                snapshot_input["parent_observed_record_count"] = lineage["observed_record_count"]
            proposal = {
                "schema": PROPOSAL_SCHEMA,
                "proposal_id": proposal_id,
                "state": "PROPOSED_ONLY__NEXUS_NEED_GATE_REQUIRED",
                "need_kind": proposed_kind,
                "observed_path": observed_path,
                "evidence": {
                    "record_count": len(safe),
                    "refs": evidence,
                    "schemas": sorted(schemas),
                },
                "suggested_desire": {
                    "desire_id": desire_id,
                    "status": "REQUESTED",
                    "module_id": module_id,
                    "purpose": (f"Compare earlier and later status distributions for {family_dir.name} using new post-parent evidence; retain verified health reporting."
                                if proposed_template == "ledger_trend" else
                                f"Report status counts and detect regression in ledger family {family_dir.name} after {len(safe)} persisted receipts; independently compare with original summary."
                                if proposed_template == "ledger_health" else
                                f"Summarize a bounded snapshot of the repeatedly accumulating ledger family {family_dir.name}; Rex detected {len(safe)} persisted receipts under {observed_path}."),
                    "template": proposed_template,
                    "config": {},
                    "nexus": {
                        "request_autorun": prop.get("request_autorun") is True,
                        "input": snapshot_input,
                    },
                    "lifecycle": {
                        "enabled": True,
                        "mode": lifecycle_mode,
                        "interval_minutes": interval_minutes,
                        "input": snapshot_input,
                    },
                },
                "authority": {
                    "observation_is_desire": False,
                    "proposal_is_admission": False,
                    "proposal_grants_lifecycle": False,
                    "authority_delta": 0,
                },
                "law": "OBSERVATION_TO_PROPOSAL_NE_DESIRE_NE_ADMISSION",
            }
            path = out_dir / f"{proposal_id}.json"
            (made if write_if_changed(path, proposal) else unchanged).append(path.relative_to(root).as_posix())
            proposed += 1

    receipt = {
        "schema": "janus.rex.need_discovery_receipt.v1",
        "status": "PASS",
        "created_or_changed": made,
        "unchanged": unchanged,
        "skipped": skipped,
        "proposal_count": proposed,
        "authority_delta": 0,
        "law": "NEED_DISCOVERY_PROPOSES_ONLY",
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
