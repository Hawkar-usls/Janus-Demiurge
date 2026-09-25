#!/usr/bin/env python3
import argparse
import json

META = json.loads('{"candidate_fingerprint": "e59ede110bae47388703effa35337eb67a4662aa12b7c63b661163e1d73184b5", "candidate_id": "AUTO_TRACTABLE_ISLAND_CONTRACTION_BOOLEAN_XOR_AND_CHECK_CIRCUIT_TO_CNF_WITH_POLY_PREFIX_FACTOR_WIDTH_VTREE_ORDER", "operator_family": "TRACTABLE_ISLAND_CONTRACTION", "profile_id": "TRACTABLE_ISLAND_CONTRACTION_EXPLICIT_INTERFACE_V1", "target_from_type": "BOOLEAN_XOR_AND_CHECK_CIRCUIT", "target_to_type": "CNF_WITH_POLY_PREFIX_FACTOR_WIDTH_VTREE_ORDER"}')

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
        return {
            "status": "REJECT_FIXED_INTERFACE_WIDTH",
            "boundary_variables": boundary,
            "max_boundary": max_boundary,
        }
    rows = []
    for mask in range(1 << boundary):
        if mask.bit_count() % 2 == 0:
            rows.append(mask)
    return {
        "status": "COMPILED_EXPLICIT_INTERFACE",
        "boundary_variables": boundary,
        "relation_rows": len(rows),
    }

def run_battery():
    family = META["operator_family"]
    if family == "TRACTABLE_ISLAND_CONTRACTION":
        samples = []
        for k in range(2, 13):
            exact = even_parity_count(k)
            formula = 1 << (k - 1)
            samples.append({
                "k": k,
                "exact_even_parity_rows": exact,
                "formula_rows": formula,
                "formula_verified": exact == formula,
            })
        rejected = explicit_interface_compile({"boundary_variables": 11})
        return {
            "schema": "janus.keymaster.materialized_execution.v1",
            "candidate_id": META["candidate_id"],
            "candidate_fingerprint": META["candidate_fingerprint"],
            "profile_id": META["profile_id"],
            "status": "EXACT_PROFILE_COUNTEREXAMPLE_FOUND",
            "entrypoints_complete": True,
            "samples": samples,
            "counterexample": {
                "kind": "UNBOUNDED_PARITY_ISLAND_BOUNDARY",
                "construction": "One tractable XOR parity island with k exposed boundary variables; every boundary variable is attached to a non-island check.",
                "exact_boundary_relation": "even parity on k bits",
                "relation_cardinality": "2^(k-1)",
                "materialized_rule": "explicit interface relation with fixed max_boundary=10",
                "witness": rejected,
                "failed_obligations": ["POLYNOMIAL_STATE", "UNIVERSAL_SCOPE"],
                "scope": "THIS_MATERIALIZED_EXPLICIT_INTERFACE_VARIANT_ONLY",
            },
        }
    return {
        "schema": "janus.keymaster.materialized_execution.v1",
        "candidate_id": META["candidate_id"],
        "candidate_fingerprint": META["candidate_fingerprint"],
        "profile_id": META["profile_id"],
        "status": "EXECUTED_NO_EXACT_COUNTEREXAMPLE_IN_REFERENCE_BATTERY",
        "entrypoints_complete": False,
        "samples": [],
        "counterexample": None,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", action="store_true")
    args = ap.parse_args()
    if not args.battery:
        raise SystemExit("use --battery")
    print(json.dumps(run_battery(), sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
