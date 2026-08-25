# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate router v5: logarithmic feedback relation cap.

Candidate generator only. v5 keeps every v1-v4 candidate and adds one new
assignment-independent candidate. It uses *all* already-certified binary
relations between distinct nonempty projected clauses only when their relation
graph has a proof-carrying feedback-edge budget small enough for exact counting
in a fixed polynomial envelope.

Let r be the cyclomatic number of the relation graph. A canonical spanning
forest leaves exactly r feedback edges. If U is the set of endpoints of those
edges, |U| <= 2r. Enumerate assignments to U, reject feedback-edge violations,
and count the remaining spanning forest exactly by tree DP with U fixed. Thus
work is O(4^r poly(L)).

Frozen capability rule (v5): q = 2 and admit this full-relation count only if

    4^r <= L^q,

where L = 1 + variables + clauses + literal occurrences of the source CNF.
If either cut side exceeds that fixed budget, this v5 feature returns OPEN and
the candidate falls back to the already-admitted v4 pseudoforest pressure for
that local choice. OPEN is never promoted to hardness.

No SAT solver, truth table, exact PS-width scorer, branch assignment, arbitrary
relation-graph counting, or post-probe feedback is used here.
"""
from __future__ import annotations

import importlib.util
import itertools
import math
from pathlib import Path
import sys

CAPABILITY_EXPONENT_Q = 2


def _load_v4():
    path = Path(__file__).with_name("slime_semantic_candidate_router_v4.py")
    name = "janus_slime_semantic_candidate_router_v4_embedded"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Slime v4")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


v4 = _load_v4()
v3 = v4.v3
v2 = v4.v2
v1 = v4.v1


def _relation_edges(clauses):
    return [
        (i, j, allowed, reasons)
        for _, i, j, allowed, reasons in v4._all_sound_relation_edges(clauses)
    ]


def _spanning_forest_feedback(node_count, edges):
    parent = list(range(node_count))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    forest = []
    feedback = []
    for edge in edges:
        i, j = edge[0], edge[1]
        ri, rj = find(i), find(j)
        if ri == rj:
            feedback.append(edge)
        else:
            if ri > rj:
                ri, rj = rj, ri
            parent[rj] = ri
            forest.append(edge)
    return forest, feedback


def _exact_feedback_count(node_count, edges, L):
    forest, feedback = _spanning_forest_feedback(node_count, edges)
    rank = len(feedback)
    budget = L ** CAPABILITY_EXPONENT_Q
    worst_case_rows = 4 ** rank
    endpoints = sorted({v for edge in feedback for v in (edge[0], edge[1])})
    enumeration_rows = 1 << len(endpoints)

    if worst_case_rows > budget:
        return {
            "status": "OPEN_FEEDBACK_BUDGET",
            "cycle_rank": rank,
            "feedback_endpoint_count": len(endpoints),
            "worst_case_4_pow_r": worst_case_rows,
            "enumeration_rows": enumeration_rows,
            "budget_L_pow_q": budget,
            "exact_relation_pattern_count": None,
            "feedback_checks": 0,
            "tree_dp_calls": 0,
            "accepted_endpoint_rows": 0,
        }

    components = v4._componentize(node_count, forest)
    total = 0
    feedback_checks = 0
    tree_dp_calls = 0
    accepted = 0

    for bits in itertools.product((0, 1), repeat=len(endpoints)):
        fixed = dict(zip(endpoints, bits))
        valid = True
        for i, j, allowed, _ in feedback:
            feedback_checks += 1
            if (fixed[i], fixed[j]) not in set(allowed):
                valid = False
                break
        if not valid:
            continue
        accepted += 1
        ways = 1
        for vertices, component_edges in components:
            ways *= v4._tree_component_count(vertices, component_edges, fixed)
            tree_dp_calls += 1
        total += ways

    return {
        "status": "CLOSED_POLY_UNDER_FEEDBACK_BUDGET",
        "cycle_rank": rank,
        "feedback_endpoint_count": len(endpoints),
        "worst_case_4_pow_r": worst_case_rows,
        "enumeration_rows": enumeration_rows,
        "budget_L_pow_q": budget,
        "exact_relation_pattern_count": total,
        "feedback_checks": feedback_checks,
        "tree_dp_calls": tree_dp_calls,
        "accepted_endpoint_rows": accepted,
    }


def _feedback_side_cap(cnf, clause_indices, visible_variables, L):
    clauses = v3._distinct_projected(cnf, clause_indices, visible_variables)
    edges = _relation_edges(clauses)
    count = _exact_feedback_count(len(clauses), edges, L)
    assignment_bound = 1 << len(visible_variables)
    result = {
        "distinct_projected_clause_count": len(clauses),
        "relation_edge_count": len(edges),
        "assignment_bound": assignment_bound,
        **count,
    }
    if count["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET":
        result["certified_signature_cap"] = min(
            assignment_bound,
            count["exact_relation_pattern_count"],
        )
    else:
        result["certified_signature_cap"] = None
    return result


def log_feedback_relation_signature_cap(cnf, selected_leaves):
    all_clause_indices = set(range(len(cnf)))
    all_variables = set(v1.variables_of(cnf))
    selected_variables = {
        int(x.split(":", 1)[1])
        for x in selected_leaves
        if x.startswith("v:")
    }
    selected_clauses = {
        int(x.split(":", 1)[1])
        for x in selected_leaves
        if x.startswith("c:")
    }
    right_variables = all_variables - selected_variables
    literal_count = sum(len(clause) for clause in cnf)
    L = 1 + len(all_variables) + len(cnf) + literal_count

    left = _feedback_side_cap(
        cnf,
        all_clause_indices - selected_clauses,
        selected_variables,
        L,
    )
    right = _feedback_side_cap(
        cnf,
        selected_clauses,
        right_variables,
        L,
    )
    closed = (
        left["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
        and right["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
    )
    return {
        "status": (
            "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
            if closed
            else "OPEN_FEEDBACK_BUDGET"
        ),
        "combined_cap": (
            max(left["certified_signature_cap"], right["certified_signature_cap"])
            if closed
            else None
        ),
        "source_size_L": L,
        "capability_exponent_q": CAPABILITY_EXPONENT_Q,
        "left": left,
        "right": right,
    }


class SlimeLogFeedbackCandidateRouter:
    def __init__(self, trace_ema: float = 0.85):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0,1)")
        self.base = v4.SlimeRelationPseudoforestCandidateRouter(trace_ema=trace_ema)
        self.trace_ema = float(trace_ema)

    def _feedback_order(self, cnf, clause_to_group, profiles):
        adjacency = v1.incidence(cnf)
        remaining = set(adjacency)
        selected = set()
        order = []
        trace = {leaf: 0.5 for leaf in adjacency}
        charged_ops = 0

        unique_profiles = sorted(set(profiles.values()))
        profile_ids = {p: i for i, p in enumerate(unique_profiles)}
        leaf_group = {
            f"v:{variable}": f"VP:{profile_ids[profile]}"
            for variable, profile in profiles.items()
        }
        leaf_group.update(
            {
                f"c:{clause_index}": f"CG:{group_id}"
                for clause_index, group_id in clause_to_group.items()
            }
        )
        q = len(cnf)
        literal_volume = sum(len(c) for c in cnf)

        while remaining:
            local = []
            for leaf in sorted(remaining):
                trial = selected | {leaf}
                feedback = log_feedback_relation_signature_cap(cnf, trial)
                pseudo = v4.relation_pseudoforest_signature_cap(cnf, trial)
                forest = v3.relation_forest_signature_cap(cnf, trial)
                coarse = v2.signature_cap_exponent(cnf, trial)
                frontier = v1.SlimeSemanticCandidateRouter._semantic_frontier(
                    adjacency, trial, leaf_group
                )
                crossing = v1.SlimeSemanticCandidateRouter._crossing(
                    adjacency, trial
                )

                exact_feedback_work = sum(
                    side["enumeration_rows"]
                    + side["feedback_checks"]
                    + side["tree_dp_calls"]
                    for side in (feedback["left"], feedback["right"])
                    if side["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
                )
                # Charge source relation construction plus the exact bounded
                # feedback enumeration/tree-DP work actually performed.
                charged_ops += (
                    20 * (
                        q * q
                        + literal_volume
                        + 1
                        + sum(len(adjacency[node]) for node in trial)
                    )
                    + exact_feedback_work
                )

                closed = feedback["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
                effective_cap = (
                    feedback["combined_cap"] if closed else pseudo["combined_cap"]
                )
                scale = max(1.0, float(len(adjacency)))
                error = (
                    6.0 * math.log2(max(1, effective_cap))
                    + 1.5 * math.log2(max(1, pseudo["combined_cap"]))
                    + 0.75 * math.log2(max(1, forest["combined_cap"]))
                    + 0.5 * coarse["cap_log2"]
                    + 0.125 * frontier
                    + 0.0625 * crossing
                ) / scale
                bond = math.exp(-min(20.0, error))
                trace[leaf] = (
                    self.trace_ema * trace[leaf]
                    + (1.0 - self.trace_ema) * bond
                )
                local.append(
                    (
                        leaf,
                        0 if closed else 1,
                        effective_cap,
                        pseudo["combined_cap"],
                        forest["combined_cap"],
                        coarse["cap_log2"],
                        frontier,
                        crossing,
                        trace[leaf],
                    )
                )

            chosen = min(
                local,
                key=lambda row: (
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    -row[8],
                    row[0],
                ),
            )[0]
            order.append(chosen)
            selected.add(chosen)
            remaining.remove(chosen)

        return order, charged_ops

    def generate_manifest(self, clauses):
        manifest = self.base.generate_manifest(clauses)
        cnf = v1.canonical_cnf(clauses)
        _, clause_to_group = v1.clause_group_map(cnf)
        profiles = v1.variable_profiles(cnf, clause_to_group)
        order, ops = self._feedback_order(cnf, clause_to_group, profiles)

        expected = sorted(v1.all_leaves(cnf))
        if sorted(order) != expected or len(order) != len(expected):
            raise AssertionError("log-feedback candidate is not a leaf permutation")

        manifest.candidates.append(
            v1.Candidate(
                "SLIME_LOG_FEEDBACK_RELATION_PRESSURE",
                order,
                "all certified pair relations when 4^r <= L^2; otherwise v4 pseudoforest fallback",
                ops,
            )
        )
        manifest.feature_certificate["feature_classes"].append(
            "LOG_FEEDBACK_RELATION_CAP"
        )
        manifest.feature_certificate["log_feedback_relation_theorem"] = {
            "cycle_rank_is_feedback_edge_count_of_canonical_spanning_forest": True,
            "feedback_endpoint_count_at_most_2r": True,
            "endpoint_assignments_at_most_4_pow_r": True,
            "forest_remainder_counted_exactly_by_tree_dp": True,
            "runtime_bound": "O(4^r * poly(L))",
            "fixed_capability_exponent_q": CAPABILITY_EXPONENT_Q,
            "admission_rule": "4^r <= L^2",
            "open_falls_back_to_v4_candidate_pressure": True,
            "assignment_independent": True,
            "truth_table_free": True,
            "arbitrary_relation_graph_counting_admitted": False,
            "authority": "RESTRICTED_POLYNOMIAL_UPPER_BOUND_NOT_EXACT_PSWIDTH",
        }
        manifest.total_generation_ops += ops
        manifest.artifact_id = "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V5"
        manifest.exact_ps_width_computed_inside_generator = False
        manifest.sat_oracle_used = False
        return manifest.seal()


SlimeSemanticCandidateRouterV5 = SlimeLogFeedbackCandidateRouter


def selftest():
    formula = (
        (1, 2, -3),
        (2, 3, 5),
        (1, 4, 5),
        (1, -3, -5),
        (1, 4, -3),
        (2, 4, -5),
        (-4, 5, -2),
    )
    cnf = v1.canonical_cnf(formula)
    prefix = {"c:0", "v:2", "c:4", "v:5", "c:3"}
    c5 = log_feedback_relation_signature_cap(cnf, prefix | {"c:5"})
    c6 = log_feedback_relation_signature_cap(cnf, prefix | {"c:6"})
    assert c5["status"] == c6["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
    assert c5["combined_cap"] == 6
    assert c6["combined_cap"] == 5
    assert c6["right"]["cycle_rank"] == 3
    assert c6["right"]["worst_case_4_pow_r"] <= c6["right"]["budget_L_pow_q"]

    router = SlimeLogFeedbackCandidateRouter()
    manifest = router.generate_manifest(formula)
    assert manifest.artifact_id == "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V5"
    assert len(manifest.candidates) == 8
    assert manifest.candidates[-1].name == "SLIME_LOG_FEEDBACK_RELATION_PRESSURE"
    assert manifest.exact_ps_width_computed_inside_generator is False
    assert manifest.sat_oracle_used is False
    theorem = manifest.feature_certificate["log_feedback_relation_theorem"]
    assert theorem["fixed_capability_exponent_q"] == 2
    assert theorem["arbitrary_relation_graph_counting_admitted"] is False
    return {
        "status": "PASS",
        "candidate_count": len(manifest.candidates),
        "new_candidate": manifest.candidates[-1].name,
        "c5_cap": c5["combined_cap"],
        "c6_cap": c6["combined_cap"],
        "c6_cycle_rank": c6["right"]["cycle_rank"],
        "manifest_sha256": manifest.manifest_sha256,
        "generator_truth_table_free": True,
        "generator_sat_oracle_free": True,
        "arbitrary_relation_graph_counting_admitted": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), indent=2, sort_keys=True))
