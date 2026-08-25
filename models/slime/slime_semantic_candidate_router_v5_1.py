# -*- coding: utf-8 -*-
"""JANUS Slime semantic candidate router v5.1.

Repair scope: preserve the v5 logarithmic-feedback implementation exactly and
replace only the stale hardcoded calibration fixture used by its self-test.
The authoritative seed-910000 source is copied from TOPA v14.1 provider logs.

No q, scoring, relation rule, work budget, fallback, or candidate policy is
changed relative to v5.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def _load_v5():
    path = Path(__file__).with_name("slime_semantic_candidate_router_v5.py")
    name = "janus_slime_semantic_candidate_router_v5_preserved"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load preserved Slime v5")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


v5 = _load_v5()
CAPABILITY_EXPONENT_Q = v5.CAPABILITY_EXPONENT_Q
SlimeLogFeedbackCandidateRouter = v5.SlimeLogFeedbackCandidateRouter
SlimeSemanticCandidateRouterV5 = v5.SlimeSemanticCandidateRouterV5
log_feedback_relation_signature_cap = v5.log_feedback_relation_signature_cap
v1 = v5.v1
v2 = v5.v2
v3 = v5.v3
v4 = v5.v4


def selftest():
    # Authoritative seed 910000 formula from TOPA v14.1 job 97745120578.
    formula = (
        (-1, 2, -3),
        (-2, -3, 4),
        (-3, -4, -5),
        (-2, -5, -1),
        (-5, 1, -4),
        (-2, -1, -4),
        (-1, 4, -3),
    )
    cnf = v1.canonical_cnf(formula)
    prefix = {"c:0", "v:2", "c:4", "v:5", "c:3"}
    c5 = log_feedback_relation_signature_cap(cnf, prefix | {"c:5"})
    c6 = log_feedback_relation_signature_cap(cnf, prefix | {"c:6"})
    v4_choice = log_feedback_relation_signature_cap(cnf, prefix | {"v:4"})

    assert c5["status"] == c6["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
    assert v4_choice["status"] == "CLOSED_POLY_UNDER_FEEDBACK_BUDGET"
    assert c5["combined_cap"] == 6
    assert c6["combined_cap"] == 5
    assert v4_choice["combined_cap"] == 6
    assert max(c6["left"]["cycle_rank"], c6["right"]["cycle_rank"]) == 3
    for side in (c5["left"], c5["right"], c6["left"], c6["right"]):
        assert side["worst_case_4_pow_r"] <= side["budget_L_pow_q"]

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
        "repair": "V5_001_FIXTURE_DRIFT_ONLY",
        "candidate_count": len(manifest.candidates),
        "new_candidate": manifest.candidates[-1].name,
        "c5_cap": c5["combined_cap"],
        "c6_cap": c6["combined_cap"],
        "v4_choice_cap": v4_choice["combined_cap"],
        "max_c6_cycle_rank": max(c6["left"]["cycle_rank"], c6["right"]["cycle_rank"]),
        "fixed_q": CAPABILITY_EXPONENT_Q,
        "manifest_sha256": manifest.manifest_sha256,
        "generator_truth_table_free": True,
        "generator_sat_oracle_free": True,
        "arbitrary_relation_graph_counting_admitted": False,
        "p_vs_np": "OPEN",
    }


if __name__ == "__main__":
    print(json.dumps(selftest(), indent=2, sort_keys=True))
