# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate router v4: relation pseudoforest cap.

Candidate generator only. v4 keeps every v1-v3 candidate and adds one new
assignment-independent candidate driven by a proof-carrying polynomial upper
bound on PS-signature diversity.

v3 retained only an acyclic forest of sound binary relations between distinct
nonempty projected clauses. v4 admits at most one cycle per connected relation
component (a pseudoforest). This preserves exact polynomial pattern counting:

* tree component -> ordinary binary tree DP;
* unicyclic component -> remove the unique closing edge (u,v), run the tree DP
  for each of the at most four endpoint value pairs admitted by that edge, and
  sum the compatible counts.

Sound pair relations are inherited from v3:
  A subseteq B        => (s_A,s_B)=(1,0) impossible
  B subseteq A        => (0,1) impossible
  A union B tautology => (0,0) impossible
  complementary units => (1,1) impossible

A deterministic strongest-first pseudoforest is selected. Rejected sound edges
are ignored, which can only loosen the resulting upper bound. The relation
pattern bound is intersected with the visible-assignment bound 2^r.

No SAT solver, truth table, exact PS-width scorer, branch assignment, arbitrary
relation-graph counting, or post-probe feedback is used here.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


def _load_v3():
    path = Path(__file__).with_name("slime_semantic_candidate_router_v3.py")
    name = "janus_slime_semantic_candidate_router_v3_embedded"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen Slime v3")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


v3 = _load_v3()
v2 = v3.v2
v1 = v3.v1


class _PseudoDSU:
    """Union-find admitting at most one cycle per connected component."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.has_cycle = [False] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def admit_edge(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            if self.has_cycle[ra]:
                return False
            self.has_cycle[ra] = True
            return True
        if self.has_cycle[ra] and self.has_cycle[rb]:
            return False
        if ra > rb:
            ra, rb = rb, ra
        cycle = self.has_cycle[ra] or self.has_cycle[rb]
        self.parent[rb] = ra
        self.has_cycle[ra] = cycle
        return True


def _all_sound_relation_edges(clauses):
    edges = []
    for i in range(len(clauses)):
        for j in range(i + 1, len(clauses)):
            allowed, reasons = v3._allowed_pairs(clauses[i], clauses[j])
            if len(allowed) < 4:
                edges.append(
                    (
                        len(allowed),
                        i,
                        j,
                        tuple(allowed),
                        tuple(reasons),
                    )
                )
    return sorted(edges, key=lambda row: (row[0], row[1], row[2]))


def _relation_pseudoforest(clauses):
    dsu = _PseudoDSU(len(clauses))
    selected = []
    rejected = 0
    for strength, i, j, allowed, reasons in _all_sound_relation_edges(clauses):
        if dsu.admit_edge(i, j):
            selected.append((i, j, allowed, reasons))
        else:
            rejected += 1
    return selected, rejected


def _tree_component_count(vertices, edges, fixed=None):
    """Exact pattern count on one tree/isolated component."""
    fixed = fixed or {}
    vertices = tuple(sorted(vertices))
    if not vertices:
        return 1
    adjacency = {v: [] for v in vertices}
    for i, j, allowed, _ in edges:
        aset = set(allowed)
        adjacency[i].append((j, aset, False))
        adjacency[j].append((i, aset, True))

    root = vertices[0]
    parent = {root: None}
    parent_edge = {}
    order = [root]
    for node in order:
        for nxt, allowed, reversed_dir in adjacency[node]:
            if nxt in parent:
                continue
            parent[nxt] = node
            parent_edge[nxt] = (allowed, reversed_dir)
            order.append(nxt)
    if set(order) != set(vertices):
        raise AssertionError("tree component traversal incomplete")

    dp = {}
    for node in reversed(order):
        values = [0, 0]
        children = [child for child, par in parent.items() if par == node]
        for node_value in (0, 1):
            if node in fixed and fixed[node] != node_value:
                continue
            count = 1
            for child in children:
                allowed, reversed_dir = parent_edge[child]
                subtotal = 0
                for child_value in (0, 1):
                    pair = (
                        (child_value, node_value)
                        if reversed_dir
                        else (node_value, child_value)
                    )
                    if pair in allowed:
                        subtotal += dp[child][child_value]
                count *= subtotal
            values[node_value] = count
        dp[node] = values
    return dp[root][0] + dp[root][1]


def _componentize(n, edges):
    adjacency = [[] for _ in range(n)]
    for edge_index, (i, j, _, _) in enumerate(edges):
        adjacency[i].append((j, edge_index))
        adjacency[j].append((i, edge_index))
    seen = set()
    components = []
    for start in range(n):
        if start in seen:
            continue
        vertices = []
        edge_ids = set()
        stack = [start]
        seen.add(start)
        while stack:
            node = stack.pop()
            vertices.append(node)
            for nxt, edge_id in adjacency[node]:
                edge_ids.add(edge_id)
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(
            (
                tuple(sorted(vertices)),
                tuple(edges[i] for i in sorted(edge_ids)),
            )
        )
    return components


def _count_pseudoforest_patterns(n, edges):
    if n == 0:
        return 1, {"components": 0, "tree_components": 0, "unicyclic_components": 0}

    total = 1
    tree_components = 0
    unicyclic_components = 0

    for vertices, component_edges in _componentize(n, edges):
        vertex_count = len(vertices)
        edge_count = len(component_edges)
        if edge_count == 0:
            total *= 2
            tree_components += 1
            continue
        if edge_count == vertex_count - 1:
            total *= _tree_component_count(vertices, component_edges)
            tree_components += 1
            continue
        if edge_count != vertex_count:
            raise AssertionError("selected relation graph is not a pseudoforest")

        # Deterministically replay Kruskal-like union to locate the unique
        # cycle-closing edge in this component.
        local_parent = {v: v for v in vertices}

        def find(x):
            while local_parent[x] != x:
                local_parent[x] = local_parent[local_parent[x]]
                x = local_parent[x]
            return x

        tree_edges = []
        closing = None
        for edge in component_edges:
            i, j, _, _ = edge
            ri, rj = find(i), find(j)
            if ri == rj:
                if closing is not None:
                    raise AssertionError("component has more than one cycle")
                closing = edge
            else:
                if ri > rj:
                    ri, rj = rj, ri
                local_parent[rj] = ri
                tree_edges.append(edge)
        if closing is None:
            raise AssertionError("unicyclic component missing closing edge")

        u, v, allowed_pairs, _ = closing
        subtotal = 0
        for u_value, v_value in allowed_pairs:
            subtotal += _tree_component_count(
                vertices,
                tree_edges,
                {u: u_value, v: v_value},
            )
        total *= subtotal
        unicyclic_components += 1

    return total, {
        "components": tree_components + unicyclic_components,
        "tree_components": tree_components,
        "unicyclic_components": unicyclic_components,
    }


def _pseudoforest_side_cap(cnf, clause_indices, visible_variables):
    clauses = v3._distinct_projected(cnf, clause_indices, visible_variables)
    edges, rejected = _relation_pseudoforest(clauses)
    relation_bound, shape = _count_pseudoforest_patterns(len(clauses), edges)
    assignment_bound = 1 << len(visible_variables)
    return {
        "distinct_projected_clause_count": len(clauses),
        "selected_relation_edge_count": len(edges),
        "rejected_sound_relation_edge_count": rejected,
        "tree_components": shape["tree_components"],
        "unicyclic_components": shape["unicyclic_components"],
        "relation_pattern_bound": relation_bound,
        "assignment_bound": assignment_bound,
        "certified_signature_cap": min(assignment_bound, relation_bound),
    }


def relation_pseudoforest_signature_cap(cnf, selected_leaves):
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
    left = _pseudoforest_side_cap(
        cnf,
        all_clause_indices - selected_clauses,
        selected_variables,
    )
    right = _pseudoforest_side_cap(
        cnf,
        selected_clauses,
        right_variables,
    )
    return {
        "left": left,
        "right": right,
        "combined_cap": max(
            left["certified_signature_cap"],
            right["certified_signature_cap"],
        ),
    }


class SlimeRelationPseudoforestCandidateRouter:
    def __init__(self, trace_ema: float = 0.85):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0,1)")
        self.base = v3.SlimeRelationForestCandidateRouter(trace_ema=trace_ema)
        self.trace_ema = float(trace_ema)

    def _pseudoforest_order(self, cnf, clause_to_group, profiles):
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
        literal_volume = sum(len(clause) for clause in cnf)
        q = len(cnf)

        while remaining:
            local = []
            for leaf in sorted(remaining):
                trial = selected | {leaf}
                pseudo = relation_pseudoforest_signature_cap(cnf, trial)
                forest = v3.relation_forest_signature_cap(cnf, trial)
                coarse = v2.signature_cap_exponent(cnf, trial)
                frontier = v1.SlimeSemanticCandidateRouter._semantic_frontier(
                    adjacency,
                    trial,
                    leaf_group,
                )
                crossing = v1.SlimeSemanticCandidateRouter._crossing(
                    adjacency,
                    trial,
                )

                # Conservative polynomial accounting proxy: every trial may
                # build O(q^2) sound pair relations, select a pseudoforest,
                # componentize it, run tree/unicyclic DP, and scan incidence.
                charged_ops += 16 * (
                    q * q
                    + literal_volume
                    + 1
                    + sum(len(adjacency[node]) for node in trial)
                )

                scale = max(1.0, float(len(adjacency)))
                error = (
                    5.0 * math.log2(max(1, pseudo["combined_cap"]))
                    + 1.5 * math.log2(max(1, forest["combined_cap"]))
                    + 0.75 * coarse["cap_log2"]
                    + 0.25 * frontier
                    + 0.125 * crossing
                ) / scale
                bond = math.exp(-min(20.0, error))
                trace[leaf] = (
                    self.trace_ema * trace[leaf]
                    + (1.0 - self.trace_ema) * bond
                )
                local.append(
                    (
                        leaf,
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
                    -row[6],
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
        order, ops = self._pseudoforest_order(cnf, clause_to_group, profiles)

        expected = sorted(v1.all_leaves(cnf))
        if sorted(order) != expected or len(order) != len(expected):
            raise AssertionError("relation-pseudoforest candidate is not a leaf permutation")

        manifest.candidates.append(
            v1.Candidate(
                "SLIME_RELATION_PSEUDOFOREST_PRESSURE",
                order,
                "certified projected-clause relation-pseudoforest signature cap, then v3/v2/v1 pressure",
                ops,
            )
        )
        manifest.feature_certificate["feature_classes"].append(
            "PROJECTED_CLAUSE_RELATION_PSEUDOFOREST_CAP"
        )
        manifest.feature_certificate["relation_pseudoforest_theorem"] = {
            "at_most_one_cycle_per_component": True,
            "tree_count_exact_by_tree_dp": True,
            "unicyclic_count_by_break_edge_and_endpoint_conditioning": True,
            "endpoint_conditions_per_cycle_edge_at_most": 4,
            "unselected_sound_relations_ignored_only_loosen_bound": True,
            "assignment_independent": True,
            "truth_table_free": True,
            "arbitrary_relation_graph_counting_admitted": False,
            "authority": "UPPER_BOUND_ONLY_NOT_EXACT_PSWIDTH",
        }
        manifest.total_generation_ops += ops
        manifest.artifact_id = "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V4"
        manifest.exact_ps_width_computed_inside_generator = False
        manifest.sat_oracle_used = False
        return manifest.seal()


SlimeSemanticCandidateRouterV4 = SlimeRelationPseudoforestCandidateRouter


def selftest():
    # Canonical 909002 diagnostic source from the already-observed v13 gap.
    formula = (
        (1, 2, -3),
        (-2, -3, 4),
        (-3, -4, -5),
        (1, 4, -3),
        (5, 2, -1),
        (-4, -5, -1),
        (-4, 2, 5),
    )
    cnf = v1.canonical_cnf(formula)
    prefix = {"c:0", "v:1", "c:1", "v:2", "c:3"}
    c2 = relation_pseudoforest_signature_cap(cnf, prefix | {"c:2"})
    c5 = relation_pseudoforest_signature_cap(cnf, prefix | {"c:5"})
    assert c2["combined_cap"] == 4
    assert c5["combined_cap"] == 5
    assert c2["right"]["unicyclic_components"] >= 1

    router = SlimeRelationPseudoforestCandidateRouter()
    manifest = router.generate_manifest(formula)
    assert manifest.artifact_id == "JANUS-SLIME-SEMANTIC-CANDIDATE-MANIFEST-V4"
    assert len(manifest.candidates) == 7
    assert manifest.candidates[-1].name == "SLIME_RELATION_PSEUDOFOREST_PRESSURE"
    assert manifest.exact_ps_width_computed_inside_generator is False
    assert manifest.sat_oracle_used is False
    theorem = manifest.feature_certificate["relation_pseudoforest_theorem"]
    assert theorem["arbitrary_relation_graph_counting_admitted"] is False
    return {
        "status": "PASS",
        "candidate_count": len(manifest.candidates),
        "new_candidate": manifest.candidates[-1].name,
        "c2_cap": c2["combined_cap"],
        "c5_cap": c5["combined_cap"],
        "manifest_sha256": manifest.manifest_sha256,
        "generator_truth_table_free": True,
        "generator_sat_oracle_free": True,
        "arbitrary_relation_graph_counting_admitted": False,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(selftest(), indent=2, sort_keys=True))
