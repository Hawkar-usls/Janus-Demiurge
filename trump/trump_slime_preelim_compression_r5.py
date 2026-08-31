#!/usr/bin/env python3
"""TRUMP Slime pre-elimination compression R5.

R5 is a canonical-first OPEN-rescue experiment.  It does not modify C025 proof
semantics.  When canonical C025 returns OPEN, R5 may replace a resolvent-product
elimination attempt with the exact Shannon/OR-lift identity

    F = U & (x|A_i)... & (-x|B_j)...
    SAT(F) <=> SAT(U&A_i...) OR SAT(U&B_j...).

Children are ordinary canonical CNFs produced by the unchanged C025 `restrict`
primitive.  Split nodes contain only fingerprints of children; unique residuals
are hash-consed and evaluated once.  Every admitted split is independently
recomputed before use.  Every leaf is decided only by the unchanged pinned C025
solver.  Budget exhaustion is OPEN.  P_VS_NP remains OPEN.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Sequence

from looking_for_something_policy import paid_work
from trump_candidate import (
    TrumpCandidateError,
    canonical_bytes,
    fetch_source_bytes,
    import_candidate_module,
    load_manifest,
    primary_source,
)

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_PREELIM_COMPRESSION_R5_FROZEN_BENCH_V1.json"


class PreelimCompressionR5Error(RuntimeError):
    pass


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_PREELIM_COMPRESSION_R5_FROZEN_C1K0_BENCH_V1":
        raise PreelimCompressionR5Error("R5_FROZEN_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R5_IMPLEMENTATION":
        raise PreelimCompressionR5Error("R5_FROZEN_SPEC_STATUS_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise PreelimCompressionR5Error("R5_WINNER_PREREGISTRATION_FORBIDDEN")
    return spec


def load_pinned_solver() -> tuple[ModuleType, dict[str, Any]]:
    manifest = load_manifest()
    source = primary_source(manifest)
    expected = load_frozen_spec()["solver"]
    if (
        source.get("repository") != expected.get("repository")
        or source.get("pinned_commit") != expected.get("commit")
        or source.get("path") != expected.get("path")
        or source.get("git_blob_sha") != expected.get("git_blob_sha")
    ):
        raise PreelimCompressionR5Error("R5_PINNED_SOLVER_DRIFT")
    data = fetch_source_bytes(source)
    return import_candidate_module(data, source), source


def _boundary_ok(result: dict[str, Any]) -> bool:
    sb = result.get("scientific_boundary") or {}
    return (
        result.get("status") in {"SAT", "UNSAT", "OPEN"}
        and sb.get("P_VS_NP") == "OPEN"
        and sb.get("claims_p_eq_np") is False
        and sb.get("claims_p_neq_np") is False
        and sb.get("heuristic_promotion") is False
        and sb.get("general_sat_oracle") is False
        and sb.get("semantic_equivalence_oracle") is False
    )


def _cnf_json(cnf) -> list[list[int]]:
    return [list(c) for c in cnf]


def _verify_local_witness(solver: ModuleType, cnf, witness: dict[int, int] | dict[str, int] | None) -> bool:
    if witness is None:
        return False
    normalized = {int(k): int(v) for k, v in witness.items()}
    return solver.verify_total_assignment(cnf, normalized)


def branch_pressure(
    solver: ModuleType,
    cnf,
) -> tuple[int, Any, Any, dict[str, Any]]:
    """Frozen source-only R5 pivot order.  No elimination product or SAT probe."""
    pivots = list(solver.vars_of(cnf))
    if not pivots:
        raise PreelimCompressionR5Error("R5_BRANCH_PRESSURE_NO_LIVE_PIVOT")
    rows: list[dict[str, Any]] = []
    scan_units = sum(1 + len(c) for c in cnf)
    structural_work = 0
    for canonical_index, pivot in enumerate(pivots):
        child0 = solver.restrict(cnf, pivot, 0)
        child1 = solver.restrict(cnf, pivot, 1)
        u0 = int(solver.state_units(child0))
        u1 = int(solver.state_units(child1))
        p = sum(pivot in c for c in cnf)
        q = sum(-pivot in c for c in cnf)
        structural_work += 2 * scan_units + 2 * len(cnf)
        rows.append({
            "pivot": int(pivot),
            "canonical_index": int(canonical_index),
            "child0": child0,
            "child1": child1,
            "child0_units": u0,
            "child1_units": u1,
            "max_child_units": max(u0, u1),
            "sum_child_units": u0 + u1,
            "parent_pairs": int(p * q),
            "balance": abs(u0 - u1),
        })
    chosen = min(
        rows,
        key=lambda r: (
            r["max_child_units"],
            r["sum_child_units"],
            r["parent_pairs"],
            r["balance"],
            r["canonical_index"],
        ),
    )
    public_rows = [
        {k: v for k, v in row.items() if k not in {"child0", "child1"}}
        for row in rows
    ]
    return int(chosen["pivot"]), chosen["child0"], chosen["child1"], {
        "structural_work": int(structural_work),
        "rows": public_rows,
        "selected_score": [
            int(chosen["max_child_units"]),
            int(chosen["sum_child_units"]),
            int(chosen["parent_pairs"]),
            int(chosen["balance"]),
            int(chosen["canonical_index"]),
        ],
    }


def verify_split(
    solver: ModuleType,
    source,
    pivot: int,
    child0,
    child1,
    *,
    state_cap: int,
) -> dict[str, Any]:
    live = set(solver.vars_of(source))
    if pivot not in live:
        raise PreelimCompressionR5Error("R5_SPLIT_PIVOT_NOT_LIVE")
    expected0 = solver.restrict(source, pivot, 0)
    expected1 = solver.restrict(source, pivot, 1)
    if expected0 != child0 or expected1 != child1:
        raise PreelimCompressionR5Error("R5_SPLIT_CHILD_REPLAY_MISMATCH")
    fp0 = solver.fingerprint(child0)
    fp1 = solver.fingerprint(child1)
    if pivot in solver.vars_of(child0) or pivot in solver.vars_of(child1):
        raise PreelimCompressionR5Error("R5_SPLIT_PIVOT_SURVIVED_CHILD")
    if not set(solver.vars_of(child0)).issubset(live) or not set(solver.vars_of(child1)).issubset(live):
        raise PreelimCompressionR5Error("R5_SPLIT_INTRODUCED_VARIABLE")
    u0, u1 = int(solver.state_units(child0)), int(solver.state_units(child1))
    if u0 > state_cap or u1 > state_cap:
        raise PreelimCompressionR5Error("R5_SPLIT_CHILD_EXCEEDS_UNCHANGED_STATE_CAP")
    return {
        "pivot": int(pivot),
        "child0_fingerprint": fp0,
        "child1_fingerprint": fp1,
        "child0_units": u0,
        "child1_units": u1,
        "verification_work": int(2 * sum(1 + len(c) for c in source) + len(source)),
    }


@dataclass
class R5Context:
    solver: ModuleType
    profile: dict[str, int]
    root_cnf: Any
    root_state_cap: int
    node_budget: int
    max_depth: int
    memo: dict[str, dict[str, Any]] = field(default_factory=dict)
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    telemetry: dict[str, int] = field(default_factory=lambda: {
        "unique_factor_dag_nodes": 0,
        "hash_cons_cache_hits": 0,
        "split_proposals": 0,
        "verified_splits": 0,
        "structural_work": 0,
        "split_verification_work": 0,
        "child_c025_exact_paid_work": 0,
        "max_child_state_units": 0,
        "node_budget_exhaustions": 0,
        "depth_budget_exhaustions": 0,
        "canonical_child_calls": 0,
    })

    def _memo_result(self, fp: str, result: dict[str, Any]) -> dict[str, Any]:
        self.memo[fp] = result
        return result

    def solve_node(self, cnf, depth: int, *, root_known_open: bool = False) -> dict[str, Any]:
        fp = self.solver.fingerprint(cnf)
        if fp in self.memo:
            self.telemetry["hash_cons_cache_hits"] += 1
            return self.memo[fp]
        if len(self.nodes) >= self.node_budget:
            self.telemetry["node_budget_exhaustions"] += 1
            return self._memo_result(fp, {"status": "OPEN", "reason": "R5_NODE_BUDGET", "witness": None})

        self.telemetry["unique_factor_dag_nodes"] += 1
        node: dict[str, Any] = {
            "fingerprint": fp,
            "state_units": int(self.solver.state_units(cnf)),
            "depth": int(depth),
            "kind": None,
        }
        self.nodes[fp] = node

        if not root_known_open:
            self.telemetry["canonical_child_calls"] += 1
            exact = self.solver.solve_fail_closed(_cnf_json(cnf), **self.profile)
            if not _boundary_ok(exact):
                raise TrumpCandidateError("R5_CHILD_EXACT_BOUNDARY_VIOLATION")
            self.telemetry["child_c025_exact_paid_work"] += int(paid_work(exact))
            if exact["status"] in {"SAT", "UNSAT"}:
                witness = exact.get("witness")
                if exact["status"] == "SAT" and not _verify_local_witness(self.solver, cnf, witness):
                    raise PreelimCompressionR5Error("R5_CHILD_SAT_WITNESS_INVALID")
                node.update({
                    "kind": "CANONICAL_DECISIVE_LEAF",
                    "status": str(exact["status"]),
                    "canonical_reason": exact.get("reason"),
                    "witness": witness,
                })
                return self._memo_result(fp, {
                    "status": str(exact["status"]),
                    "reason": "R5_CANONICAL_CHILD",
                    "witness": None if witness is None else {int(k): int(v) for k, v in witness.items()},
                })

        if depth >= self.max_depth:
            self.telemetry["depth_budget_exhaustions"] += 1
            node.update({"kind": "OPEN_LEAF", "status": "OPEN", "reason": "R5_DEPTH_BUDGET"})
            return self._memo_result(fp, {"status": "OPEN", "reason": "R5_DEPTH_BUDGET", "witness": None})

        pivots = list(self.solver.vars_of(cnf))
        if not pivots:
            # A non-decisive no-variable residual is not promotable here.
            node.update({"kind": "OPEN_LEAF", "status": "OPEN", "reason": "R5_NO_LIVE_PIVOT"})
            return self._memo_result(fp, {"status": "OPEN", "reason": "R5_NO_LIVE_PIVOT", "witness": None})

        pivot, child0, child1, pressure = branch_pressure(self.solver, cnf)
        self.telemetry["split_proposals"] += 1
        self.telemetry["structural_work"] += int(pressure["structural_work"])
        split = verify_split(
            self.solver,
            cnf,
            pivot,
            child0,
            child1,
            state_cap=self.root_state_cap,
        )
        self.telemetry["verified_splits"] += 1
        self.telemetry["split_verification_work"] += int(split["verification_work"])
        self.telemetry["max_child_state_units"] = max(
            self.telemetry["max_child_state_units"],
            int(split["child0_units"]),
            int(split["child1_units"]),
        )
        child_by_bit = {0: child0, 1: child1}
        # Frozen execution order: smaller state first; bit is deterministic tie-break.
        bits = sorted((0, 1), key=lambda bit: (self.solver.state_units(child_by_bit[bit]), bit))
        results: dict[int, dict[str, Any]] = {}
        for bit in bits:
            child = child_by_bit[bit]
            result = self.solve_node(child, depth + 1)
            results[bit] = result
            if result["status"] == "SAT":
                witness = dict(result.get("witness") or {})
                witness[int(pivot)] = int(bit)
                if not self.solver.verify_total_assignment(cnf, witness):
                    raise PreelimCompressionR5Error("R5_LIFTED_SAT_WITNESS_INVALID")
                node.update({
                    "kind": "EXACT_OR_LIFT_SPLIT",
                    "status": "SAT",
                    "pivot": int(pivot),
                    "child0_fingerprint": split["child0_fingerprint"],
                    "child1_fingerprint": split["child1_fingerprint"],
                    "decisive_child_bit": int(bit),
                    "pressure": pressure,
                    "witness": witness,
                })
                return self._memo_result(fp, {"status": "SAT", "reason": "R5_OR_CHILD_SAT", "witness": witness})

        if len(results) == 2 and all(results[b]["status"] == "UNSAT" for b in (0, 1)):
            node.update({
                "kind": "EXACT_OR_LIFT_SPLIT",
                "status": "UNSAT",
                "pivot": int(pivot),
                "child0_fingerprint": split["child0_fingerprint"],
                "child1_fingerprint": split["child1_fingerprint"],
                "pressure": pressure,
                "witness": None,
            })
            return self._memo_result(fp, {"status": "UNSAT", "reason": "R5_BOTH_OR_CHILDREN_UNSAT", "witness": None})

        # If first branch was OPEN we still explored the other branch; a SAT
        # there would already have returned.  Anything else remains OPEN.
        node.update({
            "kind": "EXACT_OR_LIFT_SPLIT",
            "status": "OPEN",
            "pivot": int(pivot),
            "child0_fingerprint": split["child0_fingerprint"],
            "child1_fingerprint": split["child1_fingerprint"],
            "pressure": pressure,
            "witness": None,
        })
        return self._memo_result(fp, {"status": "OPEN", "reason": "R5_REQUIRED_CHILD_OPEN", "witness": None})


def verify_decisive_receipt(
    solver: ModuleType,
    root_cnf,
    receipt: dict[str, Any],
    *,
    profile: dict[str, int],
    root_state_cap: int,
) -> dict[str, Any]:
    """Independent deterministic proof replay over a decisive R5 DAG receipt."""
    nodes = receipt.get("nodes") or {}
    replay_work = 0
    seen: set[str] = set()

    def replay(cnf) -> tuple[str, dict[int, int] | None]:
        nonlocal replay_work
        fp = solver.fingerprint(cnf)
        node = nodes.get(fp)
        if not isinstance(node, dict) or node.get("fingerprint") != fp:
            raise PreelimCompressionR5Error("R5_RECEIPT_NODE_MISSING_OR_FINGERPRINT_TAMPER")
        if fp in seen:
            # A hash-consed residual has one immutable recorded status/witness.
            status = str(node.get("status"))
            witness = node.get("witness")
            if status == "SAT" and not _verify_local_witness(solver, cnf, witness):
                raise PreelimCompressionR5Error("R5_RECEIPT_MEMO_SAT_WITNESS_INVALID")
            return status, None if witness is None else {int(k): int(v) for k, v in witness.items()}
        seen.add(fp)

        kind = node.get("kind")
        if kind == "CANONICAL_DECISIVE_LEAF":
            exact = solver.solve_fail_closed(_cnf_json(cnf), **profile)
            if not _boundary_ok(exact) or exact.get("status") not in {"SAT", "UNSAT"}:
                raise PreelimCompressionR5Error("R5_RECEIPT_CANONICAL_LEAF_NOT_DECISIVE_ON_REPLAY")
            replay_work += int(paid_work(exact))
            if str(exact["status"]) != str(node.get("status")):
                raise PreelimCompressionR5Error("R5_RECEIPT_CANONICAL_LEAF_STATUS_MISMATCH")
            witness = node.get("witness")
            if exact["status"] == "SAT" and not _verify_local_witness(solver, cnf, witness):
                raise PreelimCompressionR5Error("R5_RECEIPT_CANONICAL_SAT_WITNESS_INVALID")
            return str(exact["status"]), None if witness is None else {int(k): int(v) for k, v in witness.items()}

        if kind != "EXACT_OR_LIFT_SPLIT":
            raise PreelimCompressionR5Error("R5_RECEIPT_DECISIVE_PATH_CONTAINS_NONDECISIVE_LEAF")
        pivot = int(node["pivot"])
        child0 = solver.restrict(cnf, pivot, 0)
        child1 = solver.restrict(cnf, pivot, 1)
        split = verify_split(solver, cnf, pivot, child0, child1, state_cap=root_state_cap)
        replay_work += int(split["verification_work"])
        if node.get("child0_fingerprint") != split["child0_fingerprint"] or node.get("child1_fingerprint") != split["child1_fingerprint"]:
            raise PreelimCompressionR5Error("R5_RECEIPT_CHILD_FINGERPRINT_TAMPER")

        recorded = str(node.get("status"))
        if recorded == "SAT":
            bit = int(node.get("decisive_child_bit"))
            if bit not in (0, 1):
                raise PreelimCompressionR5Error("R5_RECEIPT_SAT_CHILD_BIT_INVALID")
            child = child0 if bit == 0 else child1
            child_status, child_witness = replay(child)
            if child_status != "SAT" or child_witness is None:
                raise PreelimCompressionR5Error("R5_RECEIPT_SAT_CHILD_NOT_SAT")
            lifted = dict(child_witness)
            lifted[pivot] = bit
            if not solver.verify_total_assignment(cnf, lifted):
                raise PreelimCompressionR5Error("R5_RECEIPT_LIFTED_WITNESS_INVALID")
            stored = {int(k): int(v) for k, v in (node.get("witness") or {}).items()}
            if stored != lifted:
                raise PreelimCompressionR5Error("R5_RECEIPT_STORED_WITNESS_MISMATCH")
            return "SAT", lifted

        if recorded == "UNSAT":
            s0, _ = replay(child0)
            s1, _ = replay(child1)
            if s0 != "UNSAT" or s1 != "UNSAT":
                raise PreelimCompressionR5Error("R5_RECEIPT_UNSAT_WITHOUT_BOTH_UNSAT_CHILDREN")
            return "UNSAT", None

        raise PreelimCompressionR5Error("R5_RECEIPT_NONDECISIVE_STATUS_IN_DECISIVE_REPLAY")

    status, witness = replay(root_cnf)
    if status != receipt.get("status"):
        raise PreelimCompressionR5Error("R5_RECEIPT_ROOT_STATUS_MISMATCH")
    if status == "SAT" and (witness is None or not solver.verify_total_assignment(root_cnf, witness)):
        raise PreelimCompressionR5Error("R5_RECEIPT_ROOT_SAT_WITNESS_INVALID")
    return {"status": status, "witness": witness, "replay_work": int(replay_work), "nodes_replayed": len(seen)}


def solve_r5_fallback(
    solver: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    cap_exponent: int = 1,
    extension_exponent: int = 0,
    bounded_resolution_width: int = 3,
) -> dict[str, Any]:
    spec = load_frozen_spec()
    profile = {
        "cap_exponent": int(cap_exponent),
        "extension_exponent": int(extension_exponent),
        "bounded_resolution_width": int(bounded_resolution_width),
    }
    root = solver.canon_cnf(clauses)
    N = int(solver.input_size_units(root))
    node_budget = min(N * N, 128)
    max_depth = int(spec["bounded_continuation"]["maximum_factor_depth"])
    root_state_cap = N ** int(cap_exponent)
    ctx = R5Context(
        solver=solver,
        profile=profile,
        root_cnf=root,
        root_state_cap=root_state_cap,
        node_budget=node_budget,
        max_depth=max_depth,
    )
    result = ctx.solve_node(root, 0, root_known_open=True)
    receipt = {
        "schema": "janus.trump.slime_preelim_compression_r5.factor_dag_receipt.v1",
        "root_fingerprint": solver.fingerprint(root),
        "status": result["status"],
        "reason": result["reason"],
        "witness": result.get("witness"),
        "node_budget": node_budget,
        "maximum_factor_depth": max_depth,
        "root_state_cap": root_state_cap,
        "nodes": ctx.nodes,
        "telemetry": dict(ctx.telemetry),
        "authority": {
            "proof_authority": False,
            "scientific_claim_promotion_authority": False,
            "command_authority": False,
            "external_effect_authority": False,
        },
        "scientific_boundary": {
            "P_VS_NP": "OPEN",
            "P_equals_NP_proved": False,
            "bounded_factor_DAG_is_complete": False,
            "coverage_boost_implies_speedup": False,
        },
    }
    replay = None
    if result["status"] in {"SAT", "UNSAT"}:
        replay = verify_decisive_receipt(
            solver,
            root,
            receipt,
            profile=profile,
            root_state_cap=root_state_cap,
        )
        if replay["status"] != result["status"]:
            raise PreelimCompressionR5Error("R5_DECISIVE_REPLAY_STATUS_MISMATCH")
    combined_work = (
        int(ctx.telemetry["structural_work"])
        + int(ctx.telemetry["split_verification_work"])
        + int(ctx.telemetry["child_c025_exact_paid_work"])
    )
    return {
        "receipt": receipt,
        "exact_result": result,
        "telemetry": dict(ctx.telemetry),
        "combined_fallback_work": int(combined_work),
        "replay": replay,
        "replay_work": 0 if replay is None else int(replay["replay_work"]),
    }


def solve_canonical_then_r5(
    solver: ModuleType,
    clauses: Sequence[Sequence[int]],
    *,
    cap_exponent: int = 1,
    extension_exponent: int = 0,
    bounded_resolution_width: int = 3,
) -> dict[str, Any]:
    profile = {
        "cap_exponent": int(cap_exponent),
        "extension_exponent": int(extension_exponent),
        "bounded_resolution_width": int(bounded_resolution_width),
    }
    canonical = solver.solve_fail_closed(clauses, **profile)
    if not _boundary_ok(canonical):
        raise TrumpCandidateError("R5_CANONICAL_BOUNDARY_VIOLATION")
    canonical_work = int(paid_work(canonical))
    if canonical["status"] in {"SAT", "UNSAT"}:
        replay = solver.solve_fail_closed(clauses, **profile)
        if canonical_bytes(canonical) != canonical_bytes(replay):
            raise TrumpCandidateError("R5_CANONICAL_DECISIVE_REPLAY_MISMATCH")
        return {
            "schema": "janus.trump.slime_preelim_compression_r5.ecology.v1",
            "winner": "CANONICAL",
            "r5_invoked": False,
            "baseline": canonical,
            "final_result": canonical,
            "canonical_exact_paid_work": canonical_work,
            "canonical_replay_work": int(paid_work(replay)),
            "r5": None,
        }

    r5 = solve_r5_fallback(solver, clauses, **profile)
    final = r5["exact_result"]
    return {
        "schema": "janus.trump.slime_preelim_compression_r5.ecology.v1",
        "winner": "R5_FACTOR_DAG" if final["status"] in {"SAT", "UNSAT"} else None,
        "r5_invoked": True,
        "baseline": canonical,
        "final_result": final,
        "canonical_exact_paid_work": canonical_work,
        "canonical_replay_work": 0,
        "r5": r5,
    }


def selftest() -> dict[str, Any]:
    solver, source = load_pinned_solver()
    # Small formula deliberately exercises exact split verification independent
    # of whether canonical C025 itself would decide it.
    cnf = solver.canon_cnf(((1, 2, 3), (-1, 2, 3), (1, -2, 3), (-1, -2, -3)))
    pivot, c0, c1, pressure = branch_pressure(solver, cnf)
    split = verify_split(
        solver,
        cnf,
        pivot,
        c0,
        c1,
        state_cap=solver.input_size_units(cnf),
    )
    if pressure["structural_work"] <= 0 or split["verification_work"] <= 0:
        raise AssertionError("R5_SELFTEST_WORK_ACCOUNTING_MISSING")
    return {
        "status": "PASS",
        "P_VS_NP": "OPEN",
        "source_commit": source["pinned_commit"],
        "selected_pivot": pivot,
        "child0_fingerprint": split["child0_fingerprint"],
        "child1_fingerprint": split["child1_fingerprint"],
        "split_verified": True,
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
