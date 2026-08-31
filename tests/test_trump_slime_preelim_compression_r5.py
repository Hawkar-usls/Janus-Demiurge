from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRUMP = ROOT / "trump"
if str(TRUMP) not in sys.path:
    sys.path.insert(0, str(TRUMP))

import trump_slime_preelim_compression_r5 as r5


def canon_clause(clause):
    xs = set(int(x) for x in clause)
    if any(-x in xs for x in xs):
        return None
    return tuple(sorted(xs, key=lambda z: (abs(z), z < 0)))


def canon_cnf(rows):
    clean = []
    for row in rows:
        c = canon_clause(row)
        if c is not None:
            clean.append(c)
    uniq = sorted(set(clean), key=lambda c: (len(c), c))
    kept = []
    sets = []
    for c in uniq:
        cs = frozenset(c)
        if any(s <= cs for s in sets):
            continue
        kept.append(c)
        sets.append(cs)
    return tuple(kept)


class FakeSolver:
    def __init__(self, decisions=None):
        self.decisions = decisions or {}
        self.calls = 0

    @staticmethod
    def canon_cnf(rows):
        return canon_cnf(rows)

    @staticmethod
    def vars_of(cnf):
        return tuple(sorted({abs(l) for c in cnf for l in c}))

    @staticmethod
    def state_units(cnf):
        return 1 + len(cnf) + sum(len(c) for c in cnf)

    @classmethod
    def input_size_units(cls, cnf):
        return max(2, cls.state_units(cnf) + len(cls.vars_of(cnf)))

    @staticmethod
    def fingerprint(cnf):
        raw = json.dumps([list(c) for c in cnf], separators=(",", ":")).encode("ascii")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def restrict(cnf, var, bit):
        true_lit = var if bit else -var
        false_lit = -true_lit
        out = []
        for c in cnf:
            if true_lit in c:
                continue
            out.append(tuple(l for l in c if l != false_lit))
        return canon_cnf(out)

    @staticmethod
    def verify_total_assignment(cnf, assignment):
        for c in cnf:
            if not any(assignment.get(abs(l), -1) == int(l > 0) for l in c):
                return False
        return True

    def solve_fail_closed(self, clauses, **profile):
        self.calls += 1
        cnf = self.canon_cnf(clauses)
        fp = self.fingerprint(cnf)
        status, witness = self.decisions.get(fp, ("OPEN", None))
        return {
            "status": status,
            "reason": "FAKE",
            "witness": witness,
            "ledger": {
                "proposal_work": 1,
                "certificate_discovery_work": 0,
                "verification_work": 0,
                "elimination_pair_work": 0,
                "recompression_work": 0,
                "witness_recovery_work": 0,
                "bounded_width_resolution_work": 0,
                "two_sat_work": 0,
                "gf2_work": 0,
            },
            "scientific_boundary": {
                "P_VS_NP": "OPEN",
                "claims_p_eq_np": False,
                "claims_p_neq_np": False,
                "heuristic_promotion": False,
                "general_sat_oracle": False,
                "semantic_equivalence_oracle": False,
            },
        }


def ctx(solver, root, *, nodes=32, depth=4):
    return r5.R5Context(
        solver=solver,
        profile={"cap_exponent": 1, "extension_exponent": 0, "bounded_resolution_width": 3},
        root_cnf=root,
        root_state_cap=solver.input_size_units(root),
        node_budget=nodes,
        max_depth=depth,
    )


def test_branch_pressure_uses_restriction_size_and_never_resolution_product():
    solver = FakeSolver()
    cnf = solver.canon_cnf(((1, 2, 3), (-1, 2, 3), (2, 3, 4), (-2, -3, 4)))
    pivot, c0, c1, detail = r5.branch_pressure(solver, cnf)
    assert pivot in solver.vars_of(cnf)
    assert pivot not in solver.vars_of(c0)
    assert pivot not in solver.vars_of(c1)
    assert detail["structural_work"] > 0
    row = next(row for row in detail["rows"] if row["pivot"] == pivot)
    assert detail["selected_score"][:4] == [
        row["max_child_units"], row["sum_child_units"], row["parent_pairs"], row["balance"]
    ]


def test_split_verifier_rejects_tampered_child_before_admission():
    solver = FakeSolver()
    cnf = solver.canon_cnf(((1, 2), (-1, 3), (2, 3)))
    c0 = solver.restrict(cnf, 1, 0)
    c1 = solver.restrict(cnf, 1, 1)
    tampered = solver.canon_cnf((*c1, (99,)))
    with pytest.raises(r5.PreelimCompressionR5Error, match="CHILD_REPLAY_MISMATCH"):
        r5.verify_split(solver, cnf, 1, c0, tampered, state_cap=100)


def test_split_verifier_rejects_nonlive_pivot():
    solver = FakeSolver()
    cnf = solver.canon_cnf(((1, 2), (-1, 3)))
    with pytest.raises(r5.PreelimCompressionR5Error, match="PIVOT_NOT_LIVE"):
        r5.verify_split(solver, cnf, 9, cnf, cnf, state_cap=100)


def test_both_unsat_children_are_required_for_unsat_and_hash_consed():
    solver = FakeSolver()
    root = solver.canon_cnf(((1,), (-1,)))
    child = solver.restrict(root, 1, 0)
    assert child == solver.restrict(root, 1, 1)
    solver.decisions[solver.fingerprint(child)] = ("UNSAT", None)
    c = ctx(solver, root)
    result = c.solve_node(root, 0, root_known_open=True)
    assert result["status"] == "UNSAT"
    assert c.telemetry["hash_cons_cache_hits"] >= 1
    assert c.nodes[solver.fingerprint(root)]["status"] == "UNSAT"


def test_one_unsat_one_open_cannot_promote_parent_to_unsat():
    solver = FakeSolver()
    root = solver.canon_cnf(((1, 2), (-1, 3), (2, 3)))
    pivot, c0, c1, _ = r5.branch_pressure(solver, root)
    # Force chosen children to UNSAT/OPEN.  max_depth=1 means OPEN child cannot split further.
    solver.decisions[solver.fingerprint(c0)] = ("UNSAT", None)
    solver.decisions[solver.fingerprint(c1)] = ("OPEN", None)
    c = ctx(solver, root, depth=1)
    result = c.solve_node(root, 0, root_known_open=True)
    assert result["status"] == "OPEN"
    assert c.nodes[solver.fingerprint(root)]["status"] == "OPEN"


def test_sat_child_witness_is_lifted_and_root_verified():
    solver = FakeSolver()
    root = solver.canon_cnf(((1, 2), (-1, 3)))
    pivot, c0, c1, _ = r5.branch_pressure(solver, root)
    assert pivot == 1
    # bit 0 child is (2); bit 1 child is (3).  Smaller-state tie executes bit 0 first.
    solver.decisions[solver.fingerprint(c0)] = ("SAT", {2: 1})
    solver.decisions[solver.fingerprint(c1)] = ("OPEN", None)
    c = ctx(solver, root)
    result = c.solve_node(root, 0, root_known_open=True)
    assert result["status"] == "SAT"
    assert solver.verify_total_assignment(root, result["witness"])
    assert result["witness"][1] == 0


def test_invalid_child_sat_witness_fails_closed():
    solver = FakeSolver()
    root = solver.canon_cnf(((1, 2), (-1, 3)))
    _, c0, _, _ = r5.branch_pressure(solver, root)
    solver.decisions[solver.fingerprint(c0)] = ("SAT", {2: 0})
    c = ctx(solver, root)
    with pytest.raises(r5.PreelimCompressionR5Error, match="CHILD_SAT_WITNESS_INVALID"):
        c.solve_node(root, 0, root_known_open=True)


def test_node_budget_exhaustion_is_open_not_guess():
    solver = FakeSolver()
    root = solver.canon_cnf(((1, 2), (-1, 3), (2, 3)))
    c = ctx(solver, root, nodes=1, depth=4)
    result = c.solve_node(root, 0, root_known_open=True)
    assert result["status"] == "OPEN"
    assert c.telemetry["node_budget_exhaustions"] >= 1


def test_receipt_child_fingerprint_tamper_is_rejected():
    solver = FakeSolver()
    root = solver.canon_cnf(((1,), (-1,)))
    child = solver.restrict(root, 1, 0)
    solver.decisions[solver.fingerprint(child)] = ("UNSAT", None)
    c = ctx(solver, root)
    result = c.solve_node(root, 0, root_known_open=True)
    receipt = {"status": result["status"], "nodes": c.nodes}
    receipt["nodes"][solver.fingerprint(root)]["child0_fingerprint"] = "0" * 64
    with pytest.raises(r5.PreelimCompressionR5Error, match="CHILD_FINGERPRINT_TAMPER"):
        r5.verify_decisive_receipt(
            solver,
            root,
            receipt,
            profile=c.profile,
            root_state_cap=c.root_state_cap,
        )
