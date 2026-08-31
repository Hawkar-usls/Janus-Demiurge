#!/usr/bin/env python3
"""TRUMP R6: receipt-grounded Keymaster/Pivot-Slime + M2R root navigator.

R6 never changes proof authority.  It learns only aggregate route-cost context
from exact pre-holdout calibration receipts and may choose one root split.  The
chosen split is independently verified, all continuation below the root is the
unchanged merged R5 state machine, and unchanged R5 remains mandatory fallback.

OPEN calibration routes are exposures, not negative/cost labels.  Numeric pivot
IDs are local provenance only and are absent from transferable context buckets.
P_VS_NP remains OPEN.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
from types import ModuleType
from typing import Any, Iterable, Sequence

import trump_slime_preelim_compression_r5 as r5

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "TRUMP_SLIME_R6_KEYMASTER_M2R_ROOT_ROUTING_FROZEN_BENCH_V1.json"
R5_BLOB_SHA = "bb9471e3e3c7129ec394ad02f727d9ca6691439b"
C025_BLOB_SHA = "230ca949bb51f6eeb5e7dbeea364a0752f9d0636"
DONOR_COMMIT = "80a495cafc521b1dfe5ab8d1c13bbc023bfec655"


class R6Error(RuntimeError):
    pass


def stable_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def load_frozen_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("benchmark_id") != "JANUS_TRUMP_SLIME_R6_KEYMASTER_M2R_ROOT_ROUTING_FROZEN_C1K0_BENCH_V1":
        raise R6Error("R6_FROZEN_SPEC_ID_DRIFT")
    if spec.get("status") != "FROZEN_BEFORE_R6_IMPLEMENTATION__COST_LEAK_CORRECTED_PREIMPLEMENTATION":
        raise R6Error("R6_FROZEN_SPEC_STATUS_DRIFT")
    if spec.get("winner_preregistered") is not False:
        raise R6Error("R6_WINNER_PREREGISTRATION_FORBIDDEN")
    return spec


def source_identity() -> dict[str, str]:
    return {
        "R5_runtime_git_blob_sha": R5_BLOB_SHA,
        "C025_git_blob_sha": C025_BLOB_SHA,
        "keymaster_donor_commit": DONOR_COMMIT,
    }


def verify_receipt_training_sources(spec: dict[str, Any]) -> dict[str, Any]:
    sources = spec["finalized_calibration_sources"]
    initial = json.loads((HERE / "TRUMP_SLIME_PREELIM_COMPRESSION_R5_FROZEN_PASS_RECEIPT_2026-08-31.json").read_text(encoding="utf-8"))
    r5b2 = json.loads((HERE / "TRUMP_SLIME_R5B2_GRAPH_TAUTOLOGY_UNSAT_FROZEN_PASS_RECEIPT_2026-08-31.json").read_text(encoding="utf-8"))
    r5a2 = json.loads((HERE / "TRUMP_SLIME_R5A2_WRAPPED_GT_HASH_CONS_FROZEN_PASS_RECEIPT_2026-08-31.json").read_text(encoding="utf-8"))

    initial_available = set(int(x) for x in initial["freeze"]["holdout_seeds"])
    initial_requested = set(int(x) for x in sources["initial_R5_receipt"]["training_subjects"]["seeds"])
    if not initial_requested <= initial_available:
        raise R6Error("R6_CALIBRATION_RANDOM_SEED_NOT_IN_FINALIZED_RECEIPT")

    gt6_available = set(int(x) for x in r5b2["freeze"]["GT6_seeds"])
    gt7_available = set(int(x) for x in r5b2["freeze"]["GT7_seeds"])
    if not set(sources["R5B2_receipt"]["training_subjects"]["GT6"]) <= gt6_available:
        raise R6Error("R6_CALIBRATION_GT6_SEED_NOT_IN_FINALIZED_RECEIPT")
    if not set(sources["R5B2_receipt"]["training_subjects"]["GT7"]) <= gt7_available:
        raise R6Error("R6_CALIBRATION_GT7_SEED_NOT_IN_FINALIZED_RECEIPT")

    w6_available = set(int(x) for x in r5a2["freeze"]["GT6_WRAPPED_seeds"])
    w7_available = set(int(x) for x in r5a2["freeze"]["GT7_WRAPPED_seeds"])
    if not set(sources["R5A2_receipt"]["training_subjects"]["GT6_WRAPPED"]) <= w6_available:
        raise R6Error("R6_CALIBRATION_WRAPPED_GT6_SEED_NOT_IN_FINALIZED_RECEIPT")
    if not set(sources["R5A2_receipt"]["training_subjects"]["GT7_WRAPPED"]) <= w7_available:
        raise R6Error("R6_CALIBRATION_WRAPPED_GT7_SEED_NOT_IN_FINALIZED_RECEIPT")

    return {
        "initial_receipt_status": initial["status"],
        "R5B2_receipt_status": r5b2["status"],
        "R5A2_receipt_status": r5a2["status"],
        "training_subjects_verified_against_finalized_receipts": True,
    }


def canonical_clause(values: Iterable[int]) -> tuple[int, ...]:
    xs = set(int(v) for v in values)
    if 0 in xs or any(-x in xs for x in xs):
        raise R6Error("R6_FORMULA_GENERATOR_INVALID_CLAUSE")
    return tuple(sorted(xs, key=lambda z: (abs(z), z < 0)))


def connected_random_3cnf(seed: int, variables: int = 10, clauses: int = 42) -> list[list[int]]:
    rng = random.Random(int(seed))
    out: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    def add_support(support: Sequence[int]) -> None:
        clause = canonical_clause(v if rng.getrandbits(1) else -v for v in support)
        if clause not in seen:
            seen.add(clause)
            out.append(clause)
    for i in range(1, variables - 1):
        add_support((i, i + 1, i + 2))
    while len(out) < clauses:
        add_support(rng.sample(range(1, variables + 1), 3))
    return [list(c) for c in out]


def logical_graph_tautology(n: int) -> tuple[tuple[tuple[int, ...], ...], int]:
    pair_var: dict[tuple[int, int], int] = {}
    nxt = 1
    for left in range(n):
        for right in range(left + 1, n):
            pair_var[(left, right)] = nxt
            nxt += 1
    def lt(left: int, right: int) -> int:
        return pair_var[(left, right)] if left < right else -pair_var[(right, left)]
    clauses: list[tuple[int, ...]] = []
    for vertex in range(n):
        clauses.append(tuple(lt(other, vertex) for other in range(n) if other != vertex))
    for first, second, third in itertools.permutations(range(n), 3):
        clauses.append((lt(first, second), lt(second, third), lt(third, first)))
    return tuple(clauses), nxt - 1


def rename_graph_tautology(n: int, seed: int) -> list[list[int]]:
    logical, count = logical_graph_tautology(n)
    targets = list(range(1, count + 1))
    random.Random(int(seed)).shuffle(targets)
    mapping = {i: targets[i - 1] for i in range(1, count + 1)}
    rows = []
    for clause in logical:
        rows.append([mapping[abs(lit)] if lit > 0 else -mapping[abs(lit)] for lit in clause])
    return rows


def wrapped_graph_tautology(n: int, seed: int) -> list[list[int]]:
    logical, count = logical_graph_tautology(n)
    targets = list(range(2, count + 2))
    random.Random(int(seed)).shuffle(targets)
    mapping = {i: targets[i - 1] for i in range(1, count + 1)}
    root = []
    for clause in logical:
        base = [mapping[abs(lit)] if lit > 0 else -mapping[abs(lit)] for lit in clause]
        root.append([1, *base])
        root.append([-1, *base])
    return root


def formula_for(family: str, seed: int) -> list[list[int]]:
    if family == "CONNECTED_RANDOM_3CNF_V1":
        return connected_random_3cnf(seed)
    if family == "GT6":
        return rename_graph_tautology(6, seed)
    if family == "GT7":
        return rename_graph_tautology(7, seed)
    if family == "GT6_WRAPPED":
        return wrapped_graph_tautology(6, seed)
    if family == "GT7_WRAPPED":
        return wrapped_graph_tautology(7, seed)
    raise R6Error(f"R6_UNKNOWN_FORMULA_FAMILY:{family}")


def _mean_width(rows: Sequence[Sequence[int]]) -> float:
    return sum(len(c) for c in rows) / max(1, len(rows))


def structural_feature_rows(solver: ModuleType, cnf) -> tuple[list[dict[str, Any]], int]:
    pivots = list(solver.vars_of(cnf))
    canonical_index = {v: i for i, v in enumerate(pivots)}
    clause_scan_units = sum(1 + len(c) for c in cnf)
    literal_updates = sum(len(c) for c in cnf)
    root_units = int(solver.state_units(cnf))
    cap = int(solver.input_size_units(cnf))
    rows = []
    for pivot in pivots:
        pos = [c for c in cnf if pivot in c]
        neg = [c for c in cnf if -pivot in c]
        retained = [c for c in cnf if pivot not in c and -pivot not in c]
        p, q = len(pos), len(neg)
        pairs = p * q
        conflict_mass = 0
        aligned_mass = 0
        overlap_mass = 0
        for other in pivots:
            if other == pivot:
                continue
            pp = sum(other in c for c in pos)
            pm = sum(-other in c for c in pos)
            np = sum(other in c for c in neg)
            nm = sum(-other in c for c in neg)
            conflict_mass += pp * nm + pm * np
            aligned_mass += pp * np + pm * nm
            overlap_mass += (pp + pm) * (np + nm)
        rows.append({
            "var": int(pivot),
            "canonical_index": int(canonical_index[pivot]),
            "case_n": len(pivots),
            "root_units": root_units,
            "cap": cap,
            "degree_d": p + q,
            "positive_p": p,
            "negative_q": q,
            "balance_ratio": min(p, q) / max(1, max(p, q)),
            "parent_pairs": pairs,
            "positive_parent_mean_width": _mean_width(pos),
            "negative_parent_mean_width": _mean_width(neg),
            "parent_mean_width_sum": _mean_width(pos) + _mean_width(neg),
            "retained_clause_count": len(retained),
            "retained_units": int(solver.state_units(tuple(retained))),
            "single_conflict_mass_per_pair": conflict_mass / max(1, pairs),
            "same_sign_mass_per_pair": aligned_mass / max(1, pairs),
            "support_overlap_mass_per_pair": overlap_mass / max(1, pairs),
        })
    feature_work = clause_scan_units + 4 * literal_updates + 20 * len(pivots)
    return rows, int(feature_work)


def transferable_features(row: dict[str, Any]) -> dict[str, Any]:
    return {k: row[k] for k in (
        "case_n", "root_units", "cap", "degree_d", "positive_p", "negative_q",
        "balance_ratio", "parent_pairs", "positive_parent_mean_width",
        "negative_parent_mean_width", "retained_clause_count", "retained_units",
        "single_conflict_mass_per_pair", "same_sign_mass_per_pair",
        "support_overlap_mass_per_pair",
    )}


def coarse_bucket(features: dict[str, Any]) -> str:
    bucket = {
        "n": features["case_n"],
        "d": features["degree_d"],
        "p": features["positive_p"],
        "q": features["negative_q"],
        "pw": round(features["positive_parent_mean_width"], 2),
        "nw": round(features["negative_parent_mean_width"], 2),
        "retained": features["retained_clause_count"],
        "conflict": round(features["single_conflict_mass_per_pair"], 3),
        "aligned": round(features["same_sign_mass_per_pair"], 3),
        "overlap": round(features["support_overlap_mass_per_pair"], 3),
    }
    return stable_hash(bucket)[:24]


def _axis_value(row: dict[str, Any], axis: str) -> float:
    return float(row[axis])


def _normalized_vectors(rows: list[dict[str, Any]]) -> dict[int, tuple[float, ...]]:
    axes = ("degree_d", "balance_ratio", "parent_pairs", "parent_mean_width_sum", "retained_units", "single_conflict_mass_per_pair", "same_sign_mass_per_pair", "support_overlap_mass_per_pair")
    mins = {a: min(_axis_value(r, a) for r in rows) for a in axes}
    maxs = {a: max(_axis_value(r, a) for r in rows) for a in axes}
    out = {}
    for row in rows:
        vals = []
        for axis in axes:
            lo, hi = mins[axis], maxs[axis]
            value = _axis_value(row, axis)
            vals.append(0.0 if hi == lo else (value - lo) / (hi - lo))
        out[int(row["var"])] = tuple(vals)
    return out


def build_candidate_views(solver: ModuleType, cnf) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    rows, feature_work = structural_feature_rows(solver, cnf)
    if not rows:
        return [], feature_work, rows
    low = min(rows, key=lambda r: (int(r["parent_pairs"]), int(r["retained_units"]), float(r["parent_mean_width_sum"]), int(r["canonical_index"])))
    conflict = max(rows, key=lambda r: (float(r["single_conflict_mass_per_pair"]), -int(r["parent_pairs"]), -int(r["canonical_index"])))
    vectors = _normalized_vectors(rows)
    anchor = int(low["var"])
    av = vectors[anchor]
    diversity = max(rows, key=lambda r: (sum(abs(a - b) for a, b in zip(vectors[int(r["var"])], av)), -int(r["canonical_index"])))
    proposed = [
        ("LOW_PAIR_RISK", low),
        ("CONFLICT_CANCELLATION", conflict),
        ("STRUCTURAL_DIVERSITY", diversity),
    ]
    candidates = []
    seen = set()
    for view, row in proposed:
        pivot = int(row["var"])
        if pivot in seen:
            continue
        seen.add(pivot)
        candidates.append({
            "view": view,
            "pivot_id_local": pivot,
            "canonical_index": int(row["canonical_index"]),
            "features": transferable_features(row),
            "context_bucket": coarse_bucket(transferable_features(row)),
            "vector": vectors[pivot],
        })
    return candidates, feature_work, rows


def _record_root_node(ctx: r5.R5Context, root, pivot: int, split: dict[str, Any], status: str, *, decisive_child_bit: int | None = None, witness: dict[int, int] | None = None) -> None:
    fp = ctx.solver.fingerprint(root)
    node = {
        "fingerprint": fp,
        "state_units": int(ctx.solver.state_units(root)),
        "depth": 0,
        "kind": "EXACT_OR_LIFT_SPLIT",
        "status": status,
        "pivot": int(pivot),
        "child0_fingerprint": split["child0_fingerprint"],
        "child1_fingerprint": split["child1_fingerprint"],
        "pressure": {"forced_by_R6": True},
        "witness": witness,
    }
    if decisive_child_bit is not None:
        node["decisive_child_bit"] = int(decisive_child_bit)
    ctx.nodes[fp] = node


def run_forced_root_route(solver: ModuleType, clauses: Sequence[Sequence[int]], pivot: int, profile: dict[str, int]) -> dict[str, Any]:
    root = solver.canon_cnf(clauses)
    if pivot not in solver.vars_of(root):
        raise R6Error("R6_FORCED_ROOT_PIVOT_NOT_LIVE")
    N = int(solver.input_size_units(root))
    state_cap = N ** int(profile["cap_exponent"])
    base_spec = r5.load_frozen_spec()
    max_depth = int(base_spec["bounded_continuation"]["maximum_factor_depth"])
    node_budget = min(N * N, 128)
    ctx = r5.R5Context(solver=solver, profile=dict(profile), root_cnf=root, root_state_cap=state_cap, node_budget=node_budget, max_depth=max_depth)
    root_fp = solver.fingerprint(root)
    ctx.nodes[root_fp] = {"fingerprint": root_fp, "state_units": int(solver.state_units(root)), "depth": 0, "kind": None}
    ctx.telemetry["unique_factor_dag_nodes"] += 1

    scan_units = sum(1 + len(c) for c in root)
    child0 = solver.restrict(root, pivot, 0)
    child1 = solver.restrict(root, pivot, 1)
    ctx.telemetry["split_proposals"] += 1
    ctx.telemetry["structural_work"] += int(2 * scan_units + 2 * len(root))
    split = r5.verify_split(solver, root, pivot, child0, child1, state_cap=state_cap)
    ctx.telemetry["verified_splits"] += 1
    ctx.telemetry["split_verification_work"] += int(split["verification_work"])
    ctx.telemetry["max_child_state_units"] = max(int(split["child0_units"]), int(split["child1_units"]))

    children = {0: child0, 1: child1}
    results: dict[int, dict[str, Any]] = {}
    status = "OPEN"
    reason = "R6_FORCED_ROOT_REQUIRED_CHILD_OPEN"
    witness = None
    decisive_bit = None
    for bit in sorted((0, 1), key=lambda b: (solver.state_units(children[b]), b)):
        result = ctx.solve_node(children[bit], 1)
        results[bit] = result
        if result["status"] == "SAT":
            lifted = dict(result.get("witness") or {})
            lifted[int(pivot)] = int(bit)
            if not solver.verify_total_assignment(root, lifted):
                raise R6Error("R6_FORCED_ROOT_LIFTED_SAT_WITNESS_INVALID")
            status, reason, witness, decisive_bit = "SAT", "R6_FORCED_ROOT_OR_CHILD_SAT", lifted, bit
            break
    if status != "SAT" and len(results) == 2 and all(results[b]["status"] == "UNSAT" for b in (0, 1)):
        status, reason = "UNSAT", "R6_FORCED_ROOT_BOTH_CHILDREN_UNSAT"

    _record_root_node(ctx, root, pivot, split, status, decisive_child_bit=decisive_bit, witness=witness)
    result = {"status": status, "reason": reason, "witness": witness}
    ctx.memo[root_fp] = result
    receipt = {
        "schema": "janus.trump.slime_r6.forced_root_receipt.v1",
        "root_fingerprint": root_fp,
        "status": status,
        "reason": reason,
        "witness": witness,
        "node_budget": node_budget,
        "maximum_factor_depth": max_depth,
        "root_state_cap": state_cap,
        "nodes": ctx.nodes,
        "telemetry": dict(ctx.telemetry),
        "authority": {"proof_authority": False, "scientific_claim_promotion_authority": False, "command_authority": False, "external_effect_authority": False},
        "scientific_boundary": {"P_VS_NP": "OPEN", "R6_prediction_is_proof": False},
    }
    replay = None
    if status in {"SAT", "UNSAT"}:
        replay = r5.verify_decisive_receipt(solver, root, receipt, profile=profile, root_state_cap=state_cap)
        if replay["status"] != status:
            raise R6Error("R6_FORCED_ROOT_DECISIVE_REPLAY_MISMATCH")
    telemetry = dict(ctx.telemetry)
    execution_work = int(telemetry["child_c025_exact_paid_work"] + telemetry["structural_work"] + telemetry["split_verification_work"])
    return {
        "status": status,
        "reason": reason,
        "witness": witness,
        "receipt": receipt,
        "telemetry": telemetry,
        "execution_work": execution_work,
        "replay_work": 0 if replay is None else int(replay["replay_work"]),
        "replay": replay,
        "selected_split_verified": True,
    }


@dataclass
class Welford:
    n: int = 0
    mean: float = 0.0
    M2: float = 0.0
    def add(self, x: float) -> None:
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        self.M2 += delta * (x - self.mean)
    def json(self) -> dict[str, Any]:
        return {"count": self.n, "mean": self.mean, "M2": self.M2, "sample_variance": self.M2 / (self.n - 1) if self.n > 1 else 0.0}


def calibration_subjects(spec: dict[str, Any]) -> list[tuple[str, int, str]]:
    s = spec["finalized_calibration_sources"]
    rows = [("CONNECTED_RANDOM_3CNF_V1", int(seed), "R5_INITIAL") for seed in s["initial_R5_receipt"]["training_subjects"]["seeds"]]
    for family in ("GT6", "GT7"):
        rows += [(family, int(seed), "R5B2") for seed in s["R5B2_receipt"]["training_subjects"][family]]
    for family in ("GT6_WRAPPED", "GT7_WRAPPED"):
        rows += [(family, int(seed), "R5A2") for seed in s["R5A2_receipt"]["training_subjects"][family]]
    return rows


def build_frozen_memory(solver: ModuleType, spec: dict[str, Any]) -> dict[str, Any]:
    verification = verify_receipt_training_sources(spec)
    profile = {k: int(v) for k, v in spec["profile"].items()}
    episodes = []
    calibration_feature_work = 0
    calibration_exact_execution_work = 0
    calibration_replay_work = 0
    canonical_open_subjects = 0
    canonical_decisive_skipped = 0

    for family, seed, receipt_id in calibration_subjects(spec):
        clauses = formula_for(family, seed)
        root = solver.canon_cnf(clauses)
        canonical = solver.solve_fail_closed(clauses, **profile)
        if canonical["status"] != "OPEN":
            canonical_decisive_skipped += 1
            continue
        canonical_open_subjects += 1
        candidates, feature_work, _ = build_candidate_views(solver, root)
        calibration_feature_work += feature_work
        fp = solver.fingerprint(root)
        for candidate in candidates:
            route = run_forced_root_route(solver, clauses, int(candidate["pivot_id_local"]), profile)
            calibration_exact_execution_work += int(route["execution_work"])
            calibration_replay_work += int(route["replay_work"])
            episodes.append({
                "episode_id": stable_hash({"receipt": receipt_id, "family": family, "seed": seed, "fp": fp, "view": candidate["view"], "features": candidate["features"], "status": route["status"], "execution_work": route["execution_work"]}),
                "receipt_source": receipt_id,
                "family": family,
                "seed": seed,
                "root_fingerprint": fp,
                "candidate_view": candidate["view"],
                "pivot_id_local_provenance_only": int(candidate["pivot_id_local"]),
                "features": candidate["features"],
                "context_bucket": candidate["context_bucket"],
                "exact_status": route["status"],
                "exact_execution_work": int(route["execution_work"]),
                "exact_replay_work": int(route["replay_work"]),
                "exact_telemetry": route["telemetry"],
            })

    global_stats = Welford()
    buckets: dict[str, Welford] = {}
    open_exposures: dict[str, int] = {}
    decisive = 0
    open_count = 0
    for episode in episodes:
        bucket = episode["context_bucket"]
        if episode["exact_status"] in {"SAT", "UNSAT"}:
            decisive += 1
            value = float(episode["exact_execution_work"])
            global_stats.add(value)
            buckets.setdefault(bucket, Welford()).add(value)
        else:
            open_count += 1
            open_exposures[bucket] = open_exposures.get(bucket, 0) + 1
    if global_stats.n == 0:
        raise R6Error("R6_CALIBRATION_HAS_NO_DECISIVE_ROUTE_EPISODES")
    aggregates = {bucket: {**stats.json(), "OPEN_exposures": open_exposures.get(bucket, 0)} for bucket, stats in sorted(buckets.items())}
    calibration_digest = stable_hash(episodes)
    aggregate_digest = stable_hash(aggregates)
    memory = {
        "schema": "janus.trump.slime_r6.keymaster_m2r_memory.v1",
        "status": "FROZEN_BEFORE_HOLDOUT__ADVISORY_ONLY",
        "source_identity": source_identity(),
        "receipt_source_verification": verification,
        "calibration_subject_count": len(calibration_subjects(spec)),
        "calibration_canonical_OPEN_subjects": canonical_open_subjects,
        "calibration_canonical_decisive_skipped": canonical_decisive_skipped,
        "episode_count": len(episodes),
        "decisive_episode_count": decisive,
        "OPEN_exposure_count": open_count,
        "episodes": episodes,
        "global_decisive_execution_work": global_stats.json(),
        "aggregates": aggregates,
        "calibration_episode_digest": calibration_digest,
        "aggregate_digest": aggregate_digest,
        "calibration_work": {
            "feature_work": calibration_feature_work,
            "exact_execution_work": calibration_exact_execution_work,
            "replay_work": calibration_replay_work,
            "total": calibration_feature_work + calibration_exact_execution_work + calibration_replay_work,
        },
        "authority": {"proof_authority": False, "scientific_claim_promotion_authority": False, "command_authority": False, "external_effect_authority": False},
        "P_VS_NP": "OPEN",
    }
    memory["memory_state_identity"] = stable_hash({"source_identity": memory["source_identity"], "calibration_episode_digest": calibration_digest, "aggregate_digest": aggregate_digest})
    return memory


def _distance(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(abs(float(x) - float(y)) for x, y in zip(a, b))


def select_root_route(solver: ModuleType, cnf, memory: dict[str, Any], *, identity: dict[str, str] | None = None) -> dict[str, Any]:
    current_identity = identity or source_identity()
    candidates, feature_work, _ = build_candidate_views(solver, cnf)
    if current_identity != memory.get("source_identity"):
        return {
            "selected": None,
            "memory_stale": True,
            "cold_reset": True,
            "history_retained": bool(memory.get("episodes")),
            "feature_inference_work": feature_work + 8,
            "candidates": candidates,
            "supported": [],
            "top_k": ["R5_FALLBACK_SENTINEL"],
            "exploration_trigger": False,
        }
    minimum_support = int(load_frozen_spec()["M2R_memory_fit"]["minimum_bucket_decisive_support"])
    shrink = float(load_frozen_spec()["M2R_memory_fit"]["small_n_shrinkage_strength"])
    global_mean = float(memory["global_decisive_execution_work"]["mean"])
    supported = []
    for candidate in candidates:
        agg = memory["aggregates"].get(candidate["context_bucket"])
        if not agg or int(agg["count"]) < minimum_support:
            continue
        n = int(agg["count"])
        predicted = (n * float(agg["mean"]) + shrink * global_mean) / (n + shrink)
        supported.append({**candidate, "support": n, "predicted_execution_work": predicted, "OPEN_exposures": int(agg.get("OPEN_exposures", 0))})
    view_rank = {name: i for i, name in enumerate(load_frozen_spec()["candidate_views"]["view_order"])}
    supported.sort(key=lambda c: (float(c["predicted_execution_work"]), view_rank[c["view"]], int(c["canonical_index"])))
    selected = supported[0] if supported else None
    alternate = None
    if selected is not None:
        rest = [c for c in supported if int(c["pivot_id_local"]) != int(selected["pivot_id_local"])]
        if rest:
            alternate = max(rest, key=lambda c: (_distance(c["vector"], selected["vector"]), -view_rank[c["view"]], -int(c["canonical_index"])))
    fp = solver.fingerprint(cnf)
    explore = int(fp[:8], 16) % 10 == 0
    if explore and alternate is not None:
        selected = alternate
    lookups = len(candidates)
    predictions = len(supported)
    inference_work = int(feature_work + 8 * lookups + 8 * predictions + 8)
    top_k = [c["view"] for c in supported[:1]]
    if alternate is not None and alternate["view"] not in top_k:
        top_k.append(alternate["view"])
    top_k.append("R5_FALLBACK_SENTINEL")
    return {
        "selected": selected,
        "memory_stale": False,
        "cold_reset": False,
        "history_retained": True,
        "feature_inference_work": inference_work,
        "candidates": candidates,
        "supported": supported,
        "diversity_alternate": alternate,
        "top_k": top_k,
        "exploration_trigger": explore,
    }


def selftest() -> dict[str, Any]:
    solver, source = r5.load_pinned_solver()
    spec = load_frozen_spec()
    verify_receipt_training_sources(spec)
    cnf = solver.canon_cnf(connected_random_3cnf(6101))
    candidates, work, _ = build_candidate_views(solver, cnf)
    if not candidates or len(candidates) > 3 or work <= 0:
        raise AssertionError("R6_SELFTEST_CANDIDATE_FEATURE_FAILURE")
    if any("pivot_id_local" in c["features"] for c in candidates):
        raise AssertionError("R6_SELFTEST_NUMERIC_PIVOT_LEAK")
    return {"status": "PASS", "P_VS_NP": "OPEN", "source_commit": source["pinned_commit"], "candidate_count": len(candidates), "feature_work": work}


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
