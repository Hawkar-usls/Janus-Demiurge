#!/usr/bin/env python3
"""Execution-only cache wrapper for the frozen R1 benchmark.

This cache changes no candidate metric or solver ledger.  It memoizes the pure
`bounded_width_resolution_refutes(cnf, width)` function by exact CNF+width and
returns a fresh certificate dict on reuse.  The C025 solver still charges the
certificate's original `work` field on every logical invocation, so measured
exact paid_work is identical to uncached execution.  The optimization exists
only to avoid physically recomputing the same exact closure across the 17
candidate-order runs of one frozen formula.
"""
from __future__ import annotations

import copy
import json

import run_trump_slime_pivot_r1_benchmark as bench

_ORIGINAL_LOAD = bench.load_pinned_solver
_CACHE_STATS = {"requests": 0, "hits": 0, "misses": 0}


def _cached_load_solver():
    solver, source = _ORIGINAL_LOAD()
    original = solver.bounded_width_resolution_refutes
    cache = {}

    def cached(cnf, width=3):
        _CACHE_STATS["requests"] += 1
        key = (cnf, int(width))
        if key in cache:
            _CACHE_STATS["hits"] += 1
            refuted, cert = cache[key]
            return refuted, copy.deepcopy(cert)
        _CACHE_STATS["misses"] += 1
        refuted, cert = original(cnf, width)
        cache[key] = (refuted, copy.deepcopy(cert))
        return refuted, cert

    solver.bounded_width_resolution_refutes = cached
    return solver, source


bench.load_pinned_solver = _cached_load_solver
_ORIGINAL_EXECUTE = bench.execute


def _execute_with_cache_receipt():
    result = _ORIGINAL_EXECUTE()
    result["benchmark_execution_optimization"] = {
        "kind": "PURE_BOUNDED_WIDTH_RESOLUTION_MEMOIZATION",
        "key": "EXACT_CNF_PLUS_WIDTH",
        "logical_solver_work_charged_unchanged": True,
        "candidate_metric_changed": False,
        "cache_stats": dict(_CACHE_STATS),
    }
    return result


bench.execute = _execute_with_cache_receipt

if __name__ == "__main__":
    raise SystemExit(bench.main())
