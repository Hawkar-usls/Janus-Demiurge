from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "janus.keymaster.autonomous_candidate_attack.v1"
FORGE_SCHEMA = "janus.keymaster.autonomous_forge.v1"
KEYMASTER_SCHEMA = "janus.keymaster.mechanism_composition_report.v1"
MATERIALIZATION_SCHEMA = "janus.keymaster.candidate_materialization.v1"
EXECUTION_SCHEMA = "janus.keymaster.materialized_execution.v1"

REQUIRED_OBLIGATIONS = (
    "EXACT_SEMANTICS",
    "POLYNOMIAL_CONSTRUCTION",
    "POLYNOMIAL_STATE",
    "POLYNOMIAL_RECONSTRUCTION",
    "POLYNOMIAL_VERIFICATION",
    "UNIVERSAL_SCOPE",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def validate_keymaster(report: dict) -> None:
    if report.get("schema") != KEYMASTER_SCHEMA:
        raise RuntimeError("ATTACK_KEYMASTER_SCHEMA_REJECTED")
    fw = report.get("firewall") or {}
    if fw.get("P_VS_NP") != "OPEN" or fw.get("D1") != "EMPTY":
        raise RuntimeError("ATTACK_KEYMASTER_BOUNDARY_REJECTED")
    if fw.get("automatic_theorem_promotion") is not False:
        raise RuntimeError("ATTACK_KEYMASTER_PROMOTION_REJECTED")


def validate_forge(forge: dict) -> None:
    if forge.get("schema") != FORGE_SCHEMA:
        raise RuntimeError("ATTACK_FORGE_SCHEMA_REJECTED")
    fw = forge.get("firewall") or {}
    if fw.get("branch_only_research") is not True:
        raise RuntimeError("ATTACK_FORGE_BRANCH_BOUNDARY_REJECTED")
    for key in (
        "writes_fundamentum_main",
        "writes_user_research_branch",
        "automatic_merge",
        "automatic_theorem_promotion",
        "automatic_p_equals_np_claim",
        "model_output_is_proof",
        "candidate_algorithm_is_proof",
    ):
        if fw.get(key) is not False:
            raise RuntimeError(f"ATTACK_FORGE_AUTHORITY_REJECTED:{key}")
    if fw.get("P_VS_NP") != "OPEN" or fw.get("D1") != "EMPTY":
        raise RuntimeError("ATTACK_FORGE_SCIENTIFIC_BOUNDARY_REJECTED")
    if forge.get("keymaster_shadow_admission") is not False:
        raise RuntimeError("ATTACK_FORGE_SHADOW_ADMISSION_REJECTED")


def target_key(value: dict | None) -> tuple[str | None, str | None]:
    value = value or {}
    return value.get("from_type"), value.get("to_type")


def current_top_gap(report: dict) -> dict | None:
    queue = report.get("missing_interface_queue") or []
    return dict(queue[0]) if queue else None


def candidate_obligations(candidate: dict | None) -> list[dict]:
    rows = candidate.get("proof_obligations") if isinstance(candidate, dict) else None
    return [dict(x) for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def obligation_ledger(candidate: dict | None) -> list[dict]:
    supplied = {str(x.get("id")): x for x in candidate_obligations(candidate)}
    out = []
    for oid in REQUIRED_OBLIGATIONS:
        row = dict(supplied.get(oid) or {})
        out.append({
            "id": oid,
            "generation_status": str(row.get("status") or "MISSING"),
            "attack": row.get("attack"),
            "attacker_status": "OPEN__REQUIRES_PROOF_OR_COUNTEREXAMPLE",
        })
    return out


def family_risk_catalog(candidate: dict | None) -> list[dict]:
    if not isinstance(candidate, dict):
        return []
    family = str(candidate.get("operator_family") or "")
    catalog = {
        "EXACT_INTERFACE_QUOTIENT": [
            ("QUOTIENT_CLASS_EXPLOSION", "Try to force exponentially many exact interface signatures."),
            ("NONCONGRUENT_MERGE", "Find two merged states separated by one legal future operation."),
            ("HIDDEN_EQUIVALENCE_ORACLE", "Reject any merge rule that requires semantic equivalence or SAT."),
        ],
        "SEPARATOR_SIGNATURE_DP": [
            ("UNBOUNDED_ADHESION", "Use expander/Tseitin controls to force separator growth."),
            ("TABLE_EXPLOSION", "Search for exponentially many exact boundary signatures."),
            ("LOCAL_TO_GLOBAL_LEAK", "Check whether locally tractable bags still encode a hard global selector."),
        ],
        "CYCLE_SPACE_PARITY_OVERLAY": [
            ("EXTENSIVE_NONAFFINE_RESIDUE", "Search parity controls where affine elimination leaves linear non-affine residue."),
            ("WIDTH_SURVIVES_QUOTIENT", "Check whether target width remains unbounded after affine quotienting."),
            ("RECONSTRUCTION_COLLISION", "Exhaustively compare lifted witnesses on bounded mixed instances."),
        ],
        "TRACTABLE_ISLAND_CONTRACTION": [
            ("TRACTABLE_MIXTURE_HARDNESS", "Try to recover unrestricted SAT through correlated island interfaces."),
            ("SELECTOR_REINTRODUCTION", "Reject explicit or disguised SAT-like selector variables."),
            ("INTERFACE_RELATION_EXPLOSION", "Measure exact interface relation size under contraction."),
        ],
        "PROOF_CARRYING_ELIMINATION_SCHEDULE": [
            ("ORDER_BLOWUP", "Run known elimination-order counterfamilies."),
            ("CUMULATIVE_SIZE_BLOWUP", "Charge all generated clauses/factors, not only local step size."),
            ("LOCAL_CERTIFICATE_INCOMPLETENESS", "Falsify local exactness/reconstruction certificates exhaustively on bounded supports."),
        ],
    }
    return [{"id": rid, "attack": attack, "status": "SCHEDULED"} for rid, attack in catalog.get(family, [])]


def normalize_control_results(value: Any) -> list[dict]:
    rows = value.get("controls") if isinstance(value, dict) else None
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "id": row.get("id"),
            "path": row.get("path"),
            "ref": row.get("ref"),
            "status": row.get("status"),
            "returncode": row.get("returncode"),
            "output_sha256": row.get("output_sha256"),
            "boundary_open_seen": row.get("boundary_open_seen"),
            "d1_empty_seen": row.get("d1_empty_seen"),
        })
    return out


def validate_materialization(value: Any, candidate: dict | None) -> dict | None:
    if not isinstance(value, dict):
        return None
    if value.get("schema") != MATERIALIZATION_SCHEMA:
        raise RuntimeError("ATTACK_MATERIALIZATION_SCHEMA_REJECTED")
    fw = value.get("firewall") or {}
    if fw.get("P_VS_NP") != "OPEN" or fw.get("D1") != "EMPTY":
        raise RuntimeError("ATTACK_MATERIALIZATION_BOUNDARY_REJECTED")
    for key in (
        "automatic_theorem_promotion",
        "automatic_p_equals_np_claim",
        "automatic_merge",
        "writes_fundamentum_main",
        "writes_user_research_branch",
    ):
        if fw.get(key) is not False:
            raise RuntimeError(f"ATTACK_MATERIALIZATION_AUTHORITY_REJECTED:{key}")
    if value.get("keymaster_shadow_admission") is not False:
        raise RuntimeError("ATTACK_MATERIALIZATION_SHADOW_ADMISSION_REJECTED")
    if isinstance(candidate, dict):
        if value.get("candidate_id") != candidate.get("candidate_id"):
            raise RuntimeError("ATTACK_MATERIALIZATION_CANDIDATE_ID_MISMATCH")
        if value.get("candidate_fingerprint") != candidate.get("candidate_fingerprint"):
            raise RuntimeError("ATTACK_MATERIALIZATION_FINGERPRINT_MISMATCH")
    return value


def validate_execution(value: Any, candidate: dict | None, materialization: dict | None) -> dict | None:
    if not isinstance(value, dict):
        return None
    if value.get("schema") != EXECUTION_SCHEMA:
        raise RuntimeError("ATTACK_EXECUTION_SCHEMA_REJECTED")
    if isinstance(candidate, dict):
        if value.get("candidate_id") != candidate.get("candidate_id"):
            raise RuntimeError("ATTACK_EXECUTION_CANDIDATE_ID_MISMATCH")
        if value.get("candidate_fingerprint") != candidate.get("candidate_fingerprint"):
            raise RuntimeError("ATTACK_EXECUTION_FINGERPRINT_MISMATCH")
    if isinstance(materialization, dict) and value.get("profile_id") != materialization.get("profile_id"):
        raise RuntimeError("ATTACK_EXECUTION_PROFILE_MISMATCH")
    return value


def independent_replay(execution: dict | None, materialization: dict | None) -> dict:
    if not isinstance(execution, dict) or not isinstance(materialization, dict):
        return {
            "status": "NOT_RUN",
            "exact_profile_counterexample_verified": False,
            "materialized_variant_falsified": False,
            "candidate_scope_falsified": False,
        }

    profile = str(materialization.get("profile_id") or "")
    if profile != "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1":
        return {
            "status": "PASS_EXECUTION_IDENTITY_ONLY",
            "exact_profile_counterexample_verified": False,
            "materialized_variant_falsified": False,
            "candidate_scope_falsified": False,
        }

    samples = execution.get("samples") or []
    sample_map = {int(x.get("k")): x for x in samples if isinstance(x, dict) and x.get("k") is not None}
    sample_ok = True
    for k in range(2, 13):
        row = sample_map.get(k)
        expected = 1 << (k - 1)
        if not row:
            sample_ok = False
            break
        if int(row.get("exact_even_parity_rows") or -1) != expected:
            sample_ok = False
            break
        if int(row.get("formula_rows") or -1) != expected or row.get("formula_verified") is not True:
            sample_ok = False
            break

    cx = execution.get("counterexample") if isinstance(execution.get("counterexample"), dict) else {}
    witness = cx.get("witness") if isinstance(cx.get("witness"), dict) else {}
    failed = set(cx.get("failed_obligations") or [])
    cx_ok = (
        execution.get("status") == "EXACT_PROFILE_COUNTEREXAMPLE_FOUND"
        and cx.get("kind") == "UNBOUNDED_PARITY_ISLAND_BOUNDARY"
        and cx.get("relation_cardinality") == "2^(k-1)"
        and cx.get("scope") == "THIS_MATERIALIZED_EXPLICIT_INTERFACE_VARIANT_ONLY"
        and witness.get("status") == "REJECT_FIXED_INTERFACE_WIDTH"
        and int(witness.get("boundary_variables") or 0) > int(witness.get("max_boundary") or 0)
        and {"POLYNOMIAL_STATE", "UNIVERSAL_SCOPE"}.issubset(failed)
    )
    verified = sample_ok and cx_ok
    return {
        "status": "PASS_EXACT_PROFILE_COUNTEREXAMPLE" if verified else "FAIL_COUNTEREXAMPLE_REPLAY",
        "exact_profile_counterexample_verified": verified,
        "materialized_variant_falsified": verified,
        "candidate_scope_falsified": False,
        "closed_obligations_for_materialized_variant": (
            ["POLYNOMIAL_STATE", "UNIVERSAL_SCOPE"] if verified else []
        ),
        "scope": "MATERIALIZED_VARIANT_ONLY",
    }


def build_attack(
    report: dict,
    forge: dict,
    controls: Any = None,
    materialization: Any = None,
    execution: Any = None,
) -> dict:
    validate_keymaster(report)
    validate_forge(forge)

    candidate = forge.get("candidate")
    top = current_top_gap(report)
    forged_target = forge.get("target") or {}
    candidate_key = (
        candidate.get("target_from_type"),
        candidate.get("target_to_type"),
    ) if isinstance(candidate, dict) else (None, None)

    top_key = target_key(top)
    forged_key = target_key(forged_target)
    controls_rows = normalize_control_results(controls)
    failed_controls = [x for x in controls_rows if x.get("status") != "PASS"]
    bad_boundary_controls = [
        x for x in controls_rows
        if x.get("status") == "PASS"
        and (x.get("boundary_open_seen") is not True or x.get("d1_empty_seen") is not True)
    ]

    typed_barriers = list((top or {}).get("barriers") or [])
    barrier_penalty = int((top or {}).get("barrier_penalty") or 0)

    mat = validate_materialization(materialization, candidate if isinstance(candidate, dict) else None)
    exe = validate_execution(execution, candidate if isinstance(candidate, dict) else None, mat)
    replay = independent_replay(exe, mat)

    legacy_executable = candidate.get("executable_artifact") if isinstance(candidate, dict) else None
    legacy_executable_bound = (
        isinstance(legacy_executable, dict)
        and bool(legacy_executable.get("path"))
        and bool(legacy_executable.get("sha256"))
    )
    materialized_artifact = (mat or {}).get("executable_artifact") if isinstance(mat, dict) else None
    materialized_executable_bound = (
        isinstance(materialized_artifact, dict)
        and bool(materialized_artifact.get("path"))
        and bool(materialized_artifact.get("sha256"))
    )
    executable_bound = legacy_executable_bound or materialized_executable_bound

    mathematical_falsification = False
    candidate_scope_falsified = False
    materialized_variant_falsified = False
    advance_forge = False

    if not isinstance(candidate, dict):
        status = "NO_CANDIDATE_TO_ATTACK"
        candidate_survives = False
        rejection = "NO_CANDIDATE"
    elif top is None:
        status = "NO_OPEN_KEYMASTER_GAP"
        candidate_survives = False
        rejection = "NO_OPEN_GAP"
    elif forged_key != top_key or candidate_key != top_key:
        status = "REJECTED_STALE_TARGET"
        candidate_survives = False
        rejection = "KEYMASTER_TOP_GAP_CHANGED"
        advance_forge = True
    elif typed_barriers or barrier_penalty > 0:
        status = "REJECTED_KNOWN_TYPED_BARRIER"
        candidate_survives = False
        rejection = "CURRENT_TARGET_HAS_PROVED_BARRIER"
        mathematical_falsification = True
        candidate_scope_falsified = True
        advance_forge = True
    elif mat is None and not legacy_executable_bound:
        status = "ATTACK_WAITING_FOR_MATERIALIZATION"
        candidate_survives = False
        rejection = "NO_MATERIALIZATION_RESULT_BOUND"
    elif isinstance(mat, dict) and mat.get("status") == "UNMATERIALIZABLE_UNKNOWN_OPERATOR_FAMILY":
        status = "PARKED_UNMATERIALIZABLE_REFERENCE_PROFILE"
        candidate_survives = False
        rejection = "NO_SUPPORTED_EXECUTABLE_REFERENCE_PROFILE"
        advance_forge = True
    elif isinstance(mat, dict) and exe is None:
        status = "ATTACK_WAITING_FOR_INDEPENDENT_EXECUTION_REPLAY"
        candidate_survives = False
        rejection = "MATERIALIZED_ARTIFACT_NOT_REPLAYED"
    elif replay.get("status") == "FAIL_COUNTEREXAMPLE_REPLAY":
        status = "ATTACK_MATERIALIZED_COUNTEREXAMPLE_REPLAY_FAILED"
        candidate_survives = False
        rejection = "COUNTEREXAMPLE_NOT_INDEPENDENTLY_REPRODUCED"
    elif replay.get("materialized_variant_falsified") is True:
        status = "REJECTED_MATERIALIZED_VARIANT_EXACT_COUNTEREXAMPLE"
        candidate_survives = False
        rejection = "EXACT_COUNTEREXAMPLE_TO_MATERIALIZED_VARIANT"
        mathematical_falsification = True
        materialized_variant_falsified = True
        advance_forge = True
    elif failed_controls or bad_boundary_controls:
        status = "ATTACK_INFRA_OR_CONTROL_UNRESOLVED"
        candidate_survives = False
        rejection = "NEGATIVE_CONTROL_REPLAY_NOT_CLEAN"
    elif isinstance(mat, dict) and not (mat.get("executable_artifact") or {}).get("entrypoints_complete"):
        status = "PARTIAL_EXECUTABLE_ATTACK_PROFILE__PROOF_OBLIGATIONS_OPEN"
        candidate_survives = False
        rejection = "REFERENCE_PROFILE_DOES_NOT_YET_IMPLEMENT_FULL_CANDIDATE"
    else:
        status = "SURVIVES_EXECUTABLE_REFERENCE_BATTERY__PROOF_OBLIGATIONS_OPEN"
        candidate_survives = True
        rejection = None

    obligations = obligation_ledger(candidate if isinstance(candidate, dict) else None)
    for row in obligations:
        if row["id"] in set(replay.get("closed_obligations_for_materialized_variant") or []):
            row["attacker_status"] = "FALSIFIED_FOR_MATERIALIZED_VARIANT"

    falsifiers = list(candidate.get("falsification_tests") or []) if isinstance(candidate, dict) else []
    risks = family_risk_catalog(candidate if isinstance(candidate, dict) else None)

    packet = {
        "candidate_id": candidate.get("candidate_id") if isinstance(candidate, dict) else None,
        "candidate_fingerprint": candidate.get("candidate_fingerprint") if isinstance(candidate, dict) else None,
        "target": top,
        "priority": "MATERIALIZE_THEN_EXACT_COUNTEREXAMPLE_THEN_PROOF_OBLIGATIONS",
        "proof_obligations": obligations,
        "candidate_falsifiers": falsifiers,
        "family_red_team": risks,
        "required_promotion_evidence": [
            "EXPLICIT_EXACT_SEMANTICS_PROOF",
            "ARBITRARY_SIZE_POLYNOMIAL_CONSTRUCTION_BOUND",
            "ARBITRARY_SIZE_POLYNOMIAL_STATE_BOUND",
            "POLYNOMIAL_RECONSTRUCTION_PROOF",
            "POLYNOMIAL_VERIFICATION_PROOF",
            "UNIVERSAL_SCOPE_PROOF",
            "INDEPENDENT_REPLAY",
        ],
        "automatic_shadow_admission": False,
        "automatic_theorem_promotion": False,
    }

    obj = {
        "schema": SCHEMA,
        "status": status,
        "candidate_survives_known_screen": candidate_survives,
        "candidate_is_proved": False,
        "candidate_is_keymaster_edge": False,
        "advance_forge": advance_forge,
        "mathematical_falsification": mathematical_falsification,
        "candidate_scope_falsified": candidate_scope_falsified,
        "materialized_variant_falsified": materialized_variant_falsified,
        "falsification_scope": (
            "CANDIDATE_SCOPE"
            if candidate_scope_falsified
            else "MATERIALIZED_VARIANT_ONLY"
            if materialized_variant_falsified
            else None
        ),
        "executable_artifact_bound": executable_bound,
        "keymaster_shadow_admission": False,
        "rejection_reason": rejection,
        "keymaster_report_sha256": report.get("report_sha256"),
        "forge_state_sha256": forge.get("state_sha256"),
        "current_top_gap": top,
        "forge_target": forged_target,
        "candidate": {
            "candidate_id": candidate.get("candidate_id"),
            "title": candidate.get("title"),
            "operator_family": candidate.get("operator_family"),
            "candidate_fingerprint": candidate.get("candidate_fingerprint"),
            "status": candidate.get("status"),
        } if isinstance(candidate, dict) else None,
        "materialization": {
            "status": (mat or {}).get("status"),
            "profile_id": (mat or {}).get("profile_id"),
            "materialization_sha256": (mat or {}).get("materialization_sha256"),
            "artifact": materialized_artifact,
        } if isinstance(mat, dict) else None,
        "independent_replay": replay,
        "typed_barrier_screen": {
            "penalty": barrier_penalty,
            "barriers": typed_barriers,
            "status": "PASS_NO_TYPED_BARRIER" if not typed_barriers and barrier_penalty == 0 else "FAIL_KNOWN_BARRIER",
        },
        "control_replay": {
            "status": "PASS" if controls_rows and not failed_controls and not bad_boundary_controls else "NOT_RUN" if not controls_rows else "UNRESOLVED",
            "controls": controls_rows,
            "failed_count": len(failed_controls),
            "boundary_violation_count": len(bad_boundary_controls),
            "controls_are_candidate_proof": False,
        },
        "proof_work_packet": packet,
        "next_action": (
            "RETURN_TO_FORGE_FOR_DIFFERENT_CANDIDATE"
            if advance_forge
            else "MATERIALIZE_CURRENT_CANDIDATE"
            if status == "ATTACK_WAITING_FOR_MATERIALIZATION"
            else "REPLAY_MATERIALIZED_ARTIFACT"
            if status == "ATTACK_WAITING_FOR_INDEPENDENT_EXECUTION_REPLAY"
            else "IMPLEMENT_FULL_REFERENCE_VARIANT_OR_ATTACK_OPEN_OBLIGATIONS"
            if status == "PARTIAL_EXECUTABLE_ATTACK_PROFILE__PROOF_OBLIGATIONS_OPEN"
            else "ATTACK_OPEN_PROOF_OBLIGATIONS"
            if candidate_survives
            else "REPAIR_ATTACK_REPLAY"
            if status in {"ATTACK_INFRA_OR_CONTROL_UNRESOLVED", "ATTACK_MATERIALIZED_COUNTEREXAMPLE_REPLAY_FAILED"}
            else "WAIT"
        ),
        "firewall": {
            "branch_only_research": True,
            "control_pass_is_proof": False,
            "candidate_generation_is_proof": False,
            "candidate_survival_is_proof": False,
            "materialized_variant_falsification_is_candidate_family_falsification": False,
            "deferred_nonexecutability_is_mathematical_falsification": False,
            "automatic_shadow_admission": False,
            "automatic_theorem_promotion": False,
            "automatic_p_equals_np_claim": False,
            "automatic_merge": False,
            "writes_fundamentum_main": False,
            "writes_user_research_branch": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }
    obj["attack_sha256"] = sha256_json(obj)
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keymaster", required=True)
    ap.add_argument("--forge", required=True)
    ap.add_argument("--controls")
    ap.add_argument("--materialization")
    ap.add_argument("--execution")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    report = load_json(Path(args.keymaster))
    forge = load_json(Path(args.forge))
    controls = load_json(Path(args.controls), {}) if args.controls else {}
    materialization = load_json(Path(args.materialization), None) if args.materialization else None
    execution = load_json(Path(args.execution), None) if args.execution else None
    obj = build_attack(report, forge, controls, materialization, execution)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "candidate_survives_known_screen": obj["candidate_survives_known_screen"],
        "candidate_is_proved": obj["candidate_is_proved"],
        "advance_forge": obj["advance_forge"],
        "mathematical_falsification": obj["mathematical_falsification"],
        "candidate_scope_falsified": obj["candidate_scope_falsified"],
        "materialized_variant_falsified": obj["materialized_variant_falsified"],
        "keymaster_shadow_admission": obj["keymaster_shadow_admission"],
        "next_action": obj["next_action"],
        "attack_sha256": obj["attack_sha256"],
        "P_VS_NP": obj["firewall"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
