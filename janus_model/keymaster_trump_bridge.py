from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KEYMASTER_SCHEMA = "janus.keymaster.mechanism_composition_report.v1"
TRUMP_SCHEMA = "janus.trump.manifest.v0.1"
BRIDGE_SCHEMA = "janus.keymaster.trump_runtime_bridge.v1"

EVIDENCE_RANK = {
    "PINNED_SOURCE": 1,
    "PINNED_SOURCE_PLUS_SELFTEST": 2,
    "INDEPENDENT_REPLAY_PASS": 3,
    "PROOF_RELEASE_BOUND": 4,
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"KEYMASTER_TRUMP_JSON_OBJECT_REQUIRED:{path}")
    return value


def validate_keymaster(report: dict) -> None:
    if report.get("schema") != KEYMASTER_SCHEMA:
        raise RuntimeError("KEYMASTER_TRUMP_REPORT_SCHEMA_MISMATCH")
    fw = report.get("firewall") or {}
    if fw.get("P_VS_NP") != "OPEN" or fw.get("D1") != "EMPTY":
        raise RuntimeError("KEYMASTER_TRUMP_SCIENTIFIC_BOUNDARY_VIOLATION")
    required_false = (
        "automatic_theorem_promotion",
        "automatic_d1_promotion",
        "automatic_p_equals_np_claim",
        "training_signal_is_evidence",
        "complete_path_is_proof",
    )
    if any(fw.get(k) is not False for k in required_false):
        raise RuntimeError("KEYMASTER_TRUMP_REPORT_AUTHORITY_ESCALATION")
    progress = report.get("progress_readout") or {}
    if progress.get("metric_kind") != "PROOF_OBLIGATION_COMPLETENESS_NOT_PROBABILITY":
        raise RuntimeError("KEYMASTER_TRUMP_PROGRESS_KIND_REJECTED")
    if progress.get("p_equals_np_probability") is not None:
        raise RuntimeError("KEYMASTER_TRUMP_PNP_PROBABILITY_FORBIDDEN")


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema") != TRUMP_SCHEMA:
        raise RuntimeError("KEYMASTER_TRUMP_MANIFEST_SCHEMA_MISMATCH")
    activation = manifest.get("activation") or {}
    if activation.get("use_allowed") is not True or activation.get("candidate_experiment_allowed") is not True:
        raise RuntimeError("KEYMASTER_TRUMP_CANDIDATE_USE_DISABLED")
    for key in (
        "proof_authority",
        "scientific_claim_promotion_authority",
        "command_authority",
        "external_effect_authority",
        "physical_runtime_effect_authority",
    ):
        if activation.get(key) is not False:
            raise RuntimeError(f"KEYMASTER_TRUMP_AUTHORITY_CEILING_VIOLATION:{key}")
    boundary = manifest.get("scientific_boundary") or {}
    if boundary.get("P_VS_NP") != "OPEN" or boundary.get("P_equals_NP_proved") is not False:
        raise RuntimeError("KEYMASTER_TRUMP_MANIFEST_SCIENTIFIC_BOUNDARY_VIOLATION")
    bridge = manifest.get("keymaster_runtime_bridge") or {}
    if bridge.get("enabled") is not True:
        raise RuntimeError("KEYMASTER_TRUMP_BRIDGE_NOT_ENABLED")
    if bridge.get("automatic_proof_promotion") is not False or bridge.get("automatic_main_writeback") is not False:
        raise RuntimeError("KEYMASTER_TRUMP_BRIDGE_WRITE_OR_PROOF_ESCALATION")


def _hex40(value: Any) -> bool:
    s = str(value or "")
    return len(s) == 40 and all(c in "0123456789abcdef" for c in s)


def admitted_source(source: dict) -> tuple[bool, str]:
    if source.get("repository") != "Hawkar-usls/Janus-Fundamentum":
        return False, "UNTRUSTED_REPOSITORY"
    if source.get("runtime_role") not in {"PRIMARY_EXECUTABLE_CANDIDATE", "EXECUTABLE_CANDIDATE"}:
        return False, "NOT_EXECUTABLE_RUNTIME_ROLE"
    if not _hex40(source.get("pinned_commit")) or not _hex40(source.get("git_blob_sha")):
        return False, "INVALID_IMMUTABLE_PIN"
    entrypoints = set(source.get("required_entrypoints") or [])
    if not {"solve_fail_closed", "selftest"}.issubset(entrypoints):
        return False, "MISSING_REQUIRED_ENTRYPOINTS"
    boundary = source.get("scientific_boundary") or {}
    if boundary.get("P_VS_NP") != "OPEN" or boundary.get("claims_p_eq_np") is not False:
        return False, "SOURCE_SCIENTIFIC_BOUNDARY_VIOLATION"
    selection = source.get("runtime_selection") or {}
    if selection.get("candidate_runtime_admitted") is not True:
        return False, "RUNTIME_NOT_ADMITTED"
    level = selection.get("evidence_level")
    if level not in EVIDENCE_RANK:
        return False, "UNKNOWN_EVIDENCE_LEVEL"
    return True, "ADMITTED"


def select_source(manifest: dict) -> tuple[dict | None, list[dict]]:
    assessed = []
    for source in manifest.get("candidate_sources") or []:
        ok, reason = admitted_source(source)
        selection = source.get("runtime_selection") or {}
        level = selection.get("evidence_level")
        assessed.append({
            "id": source.get("id"),
            "admitted": ok,
            "reason": reason,
            "evidence_level": level,
            "evidence_rank": EVIDENCE_RANK.get(level, 0),
            "tie_break_priority": int(selection.get("tie_break_priority", 0)),
            "source": source,
        })
    eligible = [x for x in assessed if x["admitted"]]
    eligible.sort(
        key=lambda x: (
            -x["evidence_rank"],
            -x["tie_break_priority"],
            str(x["id"] or ""),
        )
    )
    return (eligible[0]["source"] if eligible else None), assessed


def build_bridge(report: dict, manifest: dict) -> dict:
    validate_keymaster(report)
    validate_manifest(manifest)
    selected, assessed = select_source(manifest)

    progress = report["progress_readout"]
    selected_id = selected.get("id") if selected else None
    source_rows = [
        {
            "id": x["id"],
            "admitted": x["admitted"],
            "reason": x["reason"],
            "evidence_level": x["evidence_level"],
            "evidence_rank": x["evidence_rank"],
            "tie_break_priority": x["tie_break_priority"],
        }
        for x in assessed
    ]

    bridge = {
        "schema": BRIDGE_SCHEMA,
        "status": "CANDIDATE_RUNTIME_SELECTED" if selected else "NO_ADMITTED_RUNTIME",
        "selection_mode": "FAIL_CLOSED_EVIDENCE_FIRST",
        "selection_order": [
            "ADMISSION_AND_SCIENTIFIC_FIREWALLS",
            "EVIDENCE_LEVEL",
            "EXPLICIT_TIE_BREAK_PRIORITY",
            "SOURCE_ID",
        ],
        "keymaster_report_sha256": report.get("report_sha256"),
        "trump_manifest_sha256": sha256_json(manifest),
        "selected_source_id": selected_id,
        "eligible_source_count": sum(1 for x in assessed if x["admitted"]),
        "sources": source_rows,
        "progress_readout": progress,
        "self_application": {
            "enabled": selected is not None,
            "mode": "CANDIDATE_INTERNAL_TASKS_ONLY",
            "selected_runtime_may_solve_internal_candidate_tasks": selected is not None,
            "selected_runtime_may_run_selftest": selected is not None,
            "automatic_switch_to_higher_ranked_admitted_runtime": True,
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "direct_main_writeback": False,
            "automatic_merge": False,
            "on_authoritative_complete_route": "VERIFY_SOURCE_THEN_SELFTEST_THEN_INDEPENDENT_REPLAY_THEN_RELEASE_GATE",
        },
        "firewall": {
            "best_runtime_candidate_is_p_equals_np_proof": False,
            "route_coverage_is_probability": False,
            "complete_route_is_proof": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }
    bridge["bridge_sha256"] = sha256_json(bridge)
    return bridge


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keymaster", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = load_json(Path(args.keymaster))
    manifest = load_json(Path(args.manifest))
    bridge = build_bridge(report, manifest)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bridge, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": bridge["status"],
        "selected_source_id": bridge["selected_source_id"],
        "eligible_source_count": bridge["eligible_source_count"],
        "progress_stage": bridge["progress_readout"]["stage"],
        "best_route_coverage_percent": bridge["progress_readout"]["best_route_coverage_percent"],
        "bridge_sha256": bridge["bridge_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
