from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "janus.keymaster.candidate_materialization.v1"
FORGE_SCHEMA = "janus.keymaster.autonomous_forge.v1"

SUPPORTED_PROFILES = {
    "EXACT_INTERFACE_QUOTIENT": "EXACT_INTERFACE_QUOTIENT_REFERENCE_V1",
    "SEPARATOR_SIGNATURE_DP": "SEPARATOR_SIGNATURE_DP_REFERENCE_V1",
    "CYCLE_SPACE_PARITY_OVERLAY": "CYCLE_SPACE_PARITY_OVERLAY_REFERENCE_V1",
    "TRACTABLE_ISLAND_CONTRACTION": "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1",
    "PROOF_CARRYING_ELIMINATION_SCHEDULE": "PROOF_CARRYING_ELIMINATION_REFERENCE_V1",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_forge(forge: dict) -> dict:
    if forge.get("schema") != FORGE_SCHEMA:
        raise RuntimeError("MATERIALIZER_FORGE_SCHEMA_REJECTED")
    fw = forge.get("firewall") or {}
    if fw.get("P_VS_NP") != "OPEN" or fw.get("D1") != "EMPTY":
        raise RuntimeError("MATERIALIZER_SCIENTIFIC_BOUNDARY_REJECTED")
    for key in (
        "writes_fundamentum_main",
        "writes_user_research_branch",
        "automatic_merge",
        "automatic_theorem_promotion",
        "automatic_p_equals_np_claim",
    ):
        if fw.get(key) is not False:
            raise RuntimeError(f"MATERIALIZER_AUTHORITY_REJECTED:{key}")
    candidate = forge.get("candidate")
    if not isinstance(candidate, dict):
        raise RuntimeError("MATERIALIZER_NO_CANDIDATE")
    if not candidate.get("candidate_id") or not candidate.get("candidate_fingerprint"):
        raise RuntimeError("MATERIALIZER_CANDIDATE_IDENTITY_MISSING")
    return candidate


def _artifact_source(candidate: dict, profile_id: str) -> str:
    meta = {
        "candidate_id": candidate["candidate_id"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "operator_family": candidate.get("operator_family"),
        "profile_id": profile_id,
        "target_from_type": candidate.get("target_from_type"),
        "target_to_type": candidate.get("target_to_type"),
    }
    meta_json = json.dumps(meta, sort_keys=True)
    return f'''#!/usr/bin/env python3
import argparse
import json

META = json.loads({meta_json!r})

def even_parity_count(k):
    if k < 1:
        raise ValueError("k must be positive")
    count = 0
    for mask in range(1 << k):
        if mask.bit_count() % 2 == 0:
            count += 1
    return count

def explicit_interface_compile(instance, max_boundary=10):
    boundary = int(instance["boundary_variables"])
    if boundary > max_boundary:
        return {{
            "status": "REJECT_FIXED_INTERFACE_WIDTH",
            "boundary_variables": boundary,
            "max_boundary": max_boundary,
        }}
    rows = []
    for mask in range(1 << boundary):
        if mask.bit_count() % 2 == 0:
            rows.append(mask)
    return {{
        "status": "COMPILED_EXPLICIT_INTERFACE",
        "boundary_variables": boundary,
        "relation_rows": len(rows),
    }}

def run_battery():
    family = META["operator_family"]
    if family == "TRACTABLE_ISLAND_CONTRACTION":
        samples = []
        for k in range(2, 13):
            exact = even_parity_count(k)
            formula = 1 << (k - 1)
            samples.append({{
                "k": k,
                "exact_even_parity_rows": exact,
                "formula_rows": formula,
                "formula_verified": exact == formula,
            }})
        rejected = explicit_interface_compile({{"boundary_variables": 11}})
        return {{
            "schema": "janus.keymaster.materialized_execution.v1",
            "candidate_id": META["candidate_id"],
            "candidate_fingerprint": META["candidate_fingerprint"],
            "profile_id": META["profile_id"],
            "status": "EXACT_PROFILE_COUNTEREXAMPLE_FOUND",
            "entrypoints_complete": True,
            "samples": samples,
            "counterexample": {{
                "kind": "UNBOUNDED_PARITY_ISLAND_BOUNDARY",
                "construction": "One tractable XOR parity island with k exposed boundary variables; every boundary variable is attached to a non-island check.",
                "exact_boundary_relation": "even parity on k bits",
                "relation_cardinality": "2^(k-1)",
                "materialized_rule": "explicit interface relation with fixed max_boundary=10",
                "witness": rejected,
                "failed_obligations": ["POLYNOMIAL_STATE", "UNIVERSAL_SCOPE"],
                "scope": "THIS_MATERIALIZED_EXPLICIT_INTERFACE_VARIANT_ONLY",
            }},
        }}
    return {{
        "schema": "janus.keymaster.materialized_execution.v1",
        "candidate_id": META["candidate_id"],
        "candidate_fingerprint": META["candidate_fingerprint"],
        "profile_id": META["profile_id"],
        "status": "EXECUTED_NO_EXACT_COUNTEREXAMPLE_IN_REFERENCE_BATTERY",
        "entrypoints_complete": False,
        "samples": [],
        "counterexample": None,
    }}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", action="store_true")
    args = ap.parse_args()
    if not args.battery:
        raise SystemExit("use --battery")
    print(json.dumps(run_battery(), sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
'''


def materialize(forge: dict, artifact_path: str) -> tuple[dict, str]:
    candidate = validate_forge(forge)
    family = str(candidate.get("operator_family") or "")
    profile_id = SUPPORTED_PROFILES.get(family)
    supported = profile_id is not None
    if not supported:
        profile_id = "UNSUPPORTED_REFERENCE_PROFILE"
    source = _artifact_source(candidate, profile_id)
    artifact_sha256 = sha256_text(source)

    exact_profile_counterexample_expected = family == "TRACTABLE_ISLAND_CONTRACTION"
    entrypoints_complete = exact_profile_counterexample_expected
    status = (
        "EXECUTABLE_REFERENCE_VARIANT_READY"
        if entrypoints_complete
        else "PARTIAL_EXECUTABLE_ATTACK_PROFILE_READY"
        if supported
        else "UNMATERIALIZABLE_UNKNOWN_OPERATOR_FAMILY"
    )
    obj = {
        "schema": SCHEMA,
        "status": status,
        "candidate_id": candidate.get("candidate_id"),
        "candidate_fingerprint": candidate.get("candidate_fingerprint"),
        "operator_family": family,
        "profile_id": profile_id,
        "profile_scope": (
            "CONCRETE_REFERENCE_IMPLEMENTATION_OF_THE_CURRENT_CANDIDATE_FAMILY"
            if supported
            else "NONE"
        ),
        "executable_artifact": {
            "path": artifact_path,
            "sha256": artifact_sha256,
            "role": "MATERIALIZED_REFERENCE_VARIANT_AND_EXACT_FALSIFICATION_HARNESS",
            "entrypoints_complete": entrypoints_complete,
        },
        "battery_contract": {
            "command": f"python {artifact_path} --battery",
            "exact_counterexample_expected": exact_profile_counterexample_expected,
            "independent_replay_required": True,
            "bounded_test_pass_is_proof": False,
        },
        "candidate_scope_falsified": False,
        "materialized_variant_is_proved": False,
        "keymaster_shadow_admission": False,
        "next_action": (
            "RUN_INDEPENDENT_REPLAY_AND_ATTACK"
            if supported
            else "RETURN_TO_FORGE_WITH_UNMATERIALIZABLE_REASON"
        ),
        "firewall": {
            "branch_only_research": True,
            "generated_code_is_proof": False,
            "bounded_battery_is_proof": False,
            "materialized_variant_is_candidate_family_theorem": False,
            "automatic_theorem_promotion": False,
            "automatic_p_equals_np_claim": False,
            "automatic_merge": False,
            "writes_fundamentum_main": False,
            "writes_user_research_branch": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }
    obj["materialization_sha256"] = sha256_json(obj)
    return obj, source


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forge", required=True)
    ap.add_argument("--artifact-out", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    forge = load_json(Path(args.forge))
    artifact_out = Path(args.artifact_out)
    report_out = Path(args.out)
    obj, source = materialize(forge, str(artifact_out).replace("\\", "/"))
    artifact_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    artifact_out.write_text(source, encoding="utf-8")
    report_out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "candidate_id": obj["candidate_id"],
        "operator_family": obj["operator_family"],
        "profile_id": obj["profile_id"],
        "artifact_sha256": obj["executable_artifact"]["sha256"],
        "next_action": obj["next_action"],
        "P_VS_NP": obj["firewall"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
