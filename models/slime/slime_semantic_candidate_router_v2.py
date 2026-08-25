# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate router v2: signature-cap pressure.

This remains a candidate generator only.  It extends the frozen v1 portfolio
with one assignment-independent, proof-carrying source feature:

For a PS cut with selected variables X and selected clauses C,

  |PS_left|  <= 2^min(|X|, q_left)
  |PS_right| <= 2^min(|V\\X|, q_right)

where q_left is the number of outside clauses whose projection to X is nonempty
and q_right is the number of selected clauses whose projection to V\\X is
nonempty.  Therefore

  log2(max PS side count) <=
      max(min(|X|,q_left), min(|V\\X|,q_right)).

The router uses only that certified upper-bound exponent plus the existing v1
incidence/group pressure.  It never computes SAT, truth tables, PS-width, or
post-hoc exact probe outcomes.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


def _load_v1():
    path = Path(__file__).with_name("slime_semantic_candidate_router.py")
    name = "janus_slime_semantic_candidate_router_v1_embedded"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Slime semantic router v1")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


v1 = _load_v1()


def signature_cap_exponent(cnf, selected_leaves):
    """Return a source-only certified log2 upper bound for both PS sides."""
    selected_variables = {
        int(leaf.split(":", 1)[1])
        for leaf in selected_leaves
        if leaf.startswith("v:")
    }
    selected_clauses = {
        int(leaf.split(":", 1)[1])
        for leaf in selected_leaves
        if leaf.startswith("c:")
    }
    all_variables = set(v1.variables_of(cnf))
    right_variables = all_variables - selected_variables

    q_left = 0
    for clause_index, clause in enumerate(cnf):
        if clause_index in selected_clauses:
            continue
        if any(abs(lit) in selected_variables for lit in clause):
            q_left += 1

    q_right = 0
    for clause_index in selected_clauses:
        clause = cnf[clause_index]
        if any(abs(lit) in right_variables for lit in clause):
            q_right += 1

    left_exp = min(len(selected_variables), q_left)
    right_exp = min(len(right_variables), q_right)
    return {
        "cap_log2": max(left_exp, right_exp),
        "left_log2": left_exp,
        "right_log2": right_exp,
        "selected_variable_count": len(selected_variables),
        "active_left_clause_count": q_left,
        "right_variable_count": len(right_variables),
        "active_right_clause_count": q_right,
    }


class SlimeSignatureCapCandidateRouter:
    """Frozen v1 portfolio + one signature-cap-aware Slime candidate."""

    def __init__(self, trace_ema: float = 0.85):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0,1)")
        self.trace_ema = float(trace_ema)
        self.base = v1.SlimeSemanticCandidateRouter(trace_ema=trace_ema)

    def _cap_pressure_order(self, cnf, clause_to_group, profiles):
        adjacency = v1.incidence(cnf)
        remaining = set(adjacency)
        selected = set()
        trace = {leaf: 0.5 for leaf in adjacency}
        order = []
        charged_ops = 0

        unique_profiles = sorted(set(profiles.values()))
        profile_ids = {profile: index for index, profile in enumerate(unique_profiles)}
        leaf_group = {}
        for variable, profile in profiles.items():
            leaf_group[f"v:{variable}"] = f"VP:{profile_ids[profile]}"
        for clause_index, group_id in clause_to_group.items():
            leaf_group[f"c:{clause_index}"] = f"CG:{group_id}"

        literal_volume = sum(len(clause) for clause in cnf)
        while remaining:
            local = []
            for leaf in sorted(remaining):
                trial = selected | {leaf}
                cap = signature_cap_exponent(cnf, trial)
                edge_pressure = self.base._crossing(adjacency, trial)
                semantic_pressure = self.base._semantic_frontier(
                    adjacency, trial, leaf_group
                )
                # Charge all source scans used by the cap and graph metrics.
                charged_ops += (
                    2 * len(cnf)
                    + 2 * literal_volume
                    + 2 * (1 + sum(len(adjacency[node]) for node in trial))
                )
                scale = max(1.0, float(len(adjacency)))
                error = (
                    4.0 * cap["cap_log2"]
                    + 1.5 * semantic_pressure
                    + edge_pressure
                ) / scale
                bond = math.exp(-min(20.0, error))
                trace[leaf] = (
                    self.trace_ema * trace[leaf]
                    + (1.0 - self.trace_ema) * bond
                )
                local.append(
                    (
                        leaf,
                        cap["cap_log2"],
                        semantic_pressure,
                        edge_pressure,
                        trace[leaf],
                    )
                )

            # The certified signature-cap exponent is the primary pressure.
            chosen = min(
                local,
                key=lambda row: (row[1], row[2], row[3], -row[4], row[0]),
            )[0]
            order.append(chosen)
            selected.add(chosen)
            remaining.remove(chosen)

        return order, charged_ops

    def generate_manifest(self, clauses):
        # First produce the frozen v1 four-candidate manifest unchanged.
        manifest = self.base.generate_manifest(clauses)
        cnf = v1.canonical_cnf(clauses)
        groups, clause_to_group = v1.clause_group_map(cnf)
        profiles = v1.variable_profiles(cnf, clause_to_group)

        cap_order, cap_ops = self._cap_pressure_order(cnf, clause_to_group, profiles)
        expected = sorted(v1.all_leaves(cnf))
        if sorted(cap_order) != expected or len(cap_order) != len(expected):
            raise AssertionError("signature-cap candidate is not a leaf permutation")

        manifest.candidates.append(
            v1.Candidate(
                "SLIME_SIGNATURE_CAP_PRESSURE",
                cap_order,
                "certified PS-signature-count upper-bound exponent, then v1 semantic/incidence pressure",
                cap_ops,
            )
        )
        manifest.feature_certificate["feature_classes"].append(
            "LOG_SIGNATURE_CAP_UPPER_BOUND"
        )
        manifest.feature_certificate["signature_cap_theorem"] = {
            "left": "|PS_left| <= 2^min(|X|, q_left)",
            "right": "|PS_right| <= 2^min(|V\\X|, q_right)",
            "combined_log2_upper_bound": "max(min(|X|,q_left), min(|V\\X|,q_right))",
            "assignment_independent": True,
            "truth_table_free": True,
            "authority": "UPPER_BOUND_ONLY_NOT_EXACT_PSWIDTH",
        }
        manifest.total_generation_ops += cap_ops
        manifest.artifact_id = "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V2"
        manifest.exact_ps_width_computed_inside_generator = False
        manifest.sat_oracle_used = False
        return manifest.seal()


# Stable public alias for cross-repo pinning.
SlimeSemanticCandidateRouterV2 = SlimeSignatureCapCandidateRouter


def selftest():
    router = SlimeSignatureCapCandidateRouter()
    formula = (
        (-1, 2, -3),
        (2, 3, 4),
        (-3, -4, -5),
        (1, -5, 2),
        (-1, -2, -5),
        (1, 4, -5),
        (2, -5, -3),
    )
    manifest = router.generate_manifest(formula)
    assert manifest.artifact_id == "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V2"
    assert len(manifest.candidates) == 5
    assert manifest.candidates[-1].name == "SLIME_SIGNATURE_CAP_PRESSURE"
    assert manifest.exact_ps_width_computed_inside_generator is False
    assert manifest.sat_oracle_used is False
    assert manifest.feature_certificate["signature_cap_theorem"]["truth_table_free"] is True
    cap = signature_cap_exponent(v1.canonical_cnf(formula), {"c:0", "c:1"})
    assert cap["cap_log2"] >= 0
    return {
        "status": "PASS",
        "candidate_count": len(manifest.candidates),
        "manifest_sha256": manifest.manifest_sha256,
        "new_candidate": manifest.candidates[-1].name,
        "generator_truth_table_free": True,
        "generator_sat_oracle_free": True,
        "authority": "HEURISTIC_GENERATOR_WITH_PROOF_CARRYING_UPPER_BOUND",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), indent=2, sort_keys=True))
