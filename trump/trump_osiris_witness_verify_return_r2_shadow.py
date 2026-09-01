#!/usr/bin/env python3
"""R2 shadow epistemic automaton for TRUMP/OSIRIS double-spiral search.

Concrete translation of:
    RESONANCE -> PRESERVE -> TEST -> RETURN_HIGHER

The overlay has zero proof authority.  It observes a structural pattern before
truth is known, seals that observation as a witness, executes the existing R1
candidate, independently verifies the root truth with the exact R0 baseline,
and only then emits an experience record that may become future advisory
memory.  Pattern recognition can never promote SAT/UNSAT.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Dict, Optional

from trump_osiris_double_spiral_meet_r0 import (
    CNF,
    build_primal_graph,
    canonicalize,
    exact_search,
    formula_digest,
    verify_root_sat,
)
from trump_osiris_double_spiral_meet_r1_advisory import (
    DENSITY_SKIP_THRESHOLD,
    MAX_PAIR_PROPOSALS,
    double_spiral_meet_r1,
)

RULE_ID = "TRUMP_R2_PATTERN_RULE_DENSITY_ROUTE_v1"
PATTERN_ADMISSION_MIN_PROSPECTIVE_CASES = 24
PATTERN_ADMISSION_MIN_ACCURACY = 0.95


def _stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


def structural_signature(clauses: CNF) -> dict:
    """Compute an observation without consulting SAT/UNSAT truth."""
    clauses = canonicalize(clauses)
    graph, graph_ops = build_primal_graph(clauses)
    n = len(graph)
    edge_count = sum(len(v) for v in graph.values()) // 2
    density = 0.0 if n < 2 else (2.0 * edge_count) / (n * (n - 1))
    degrees = sorted(len(v) for v in graph.values())
    return {
        "formula_sha256": formula_digest(clauses),
        "n_vars": n,
        "n_clauses": len(clauses),
        "edge_count": edge_count,
        "graph_density": density,
        "density_class": "DENSE" if density > DENSITY_SKIP_THRESHOLD else "NON_DENSE",
        "degree_min": 0 if not degrees else degrees[0],
        "degree_max": 0 if not degrees else degrees[-1],
        "degree_sum": sum(degrees),
        "observation_ops": graph_ops + n,
    }


def frozen_pattern_prediction(signature: dict) -> dict:
    """Frozen pre-truth encoding rule.

    It predicts only which *advisory route class* should be attempted.  It does
    not predict SAT/UNSAT and therefore has no truth authority.
    """
    if signature["graph_density"] > DENSITY_SKIP_THRESHOLD:
        predicted = "DENSITY_SKIP_TO_EXACT_FALLBACK"
    else:
        predicted = "ATTEMPT_EXACT_SEPARATOR_MEET"
    return {
        "rule_id": RULE_ID,
        "predicted_route_class": predicted,
        "density_skip_threshold": DENSITY_SKIP_THRESHOLD,
        "max_pair_proposals": MAX_PAIR_PROPOSALS,
        "truth_prediction": None,
        "proof_authority": False,
    }


def observed_route_class(candidate_dict: dict) -> str:
    decision = candidate_dict["advisory"]["decision"]
    if decision == "DENSITY_SKIP_TO_EXACT_FALLBACK":
        return decision
    # For a non-dense graph the frozen rule predicts an attempt, not guaranteed
    # success.  Exact rejection of proposals is still a valid attempted meet.
    return "ATTEMPT_EXACT_SEPARATOR_MEET"


@dataclass
class R2ShadowResult:
    observation: dict
    prediction: dict
    pre_verification_witness: dict
    candidate: dict
    independent_verification: dict
    return_higher: dict

    def as_dict(self) -> dict:
        return {
            "observation": self.observation,
            "prediction": self.prediction,
            "pre_verification_witness": self.pre_verification_witness,
            "candidate": self.candidate,
            "independent_verification": self.independent_verification,
            "return_higher": self.return_higher,
        }


def witness_verify_return_r2_shadow(clauses: CNF) -> R2ShadowResult:
    """Run O -> W -> V -> DeltaH while keeping truth authority exact."""
    clauses = canonicalize(clauses)

    # O: resonance / observation is computed before truth is known.
    observation = structural_signature(clauses)
    prediction = frozen_pattern_prediction(observation)

    # W: preserve an immutable witness before candidate or baseline truth runs.
    witness_payload = {
        "schema": "JANUS/TRUMP/R2-PRE-VERIFICATION-WITNESS/v1.0",
        "formula_sha256": observation["formula_sha256"],
        "observation": observation,
        "prediction": prediction,
        "truth": None,
        "stage": "PRESERVED_BEFORE_TRUTH_VERIFICATION",
    }
    witness = {
        "witness_sha256": _stable_hash(witness_payload),
        "payload": witness_payload,
    }

    # Candidate search remains R1 exact-meet/fallback logic.
    candidate_obj = double_spiral_meet_r1(clauses)
    candidate = candidate_obj.as_dict()

    # V: independent exact root truth.  This is the authority in this experiment.
    baseline_terminal, baseline_witness, baseline_work = exact_search(clauses)
    terminal_match = candidate["terminal"] == baseline_terminal
    candidate_sat_replay = candidate["terminal"] != "SAT" or verify_root_sat(clauses, candidate_obj.witness)
    baseline_sat_replay = baseline_terminal != "SAT" or verify_root_sat(clauses, baseline_witness)
    verification_pass = terminal_match and candidate_sat_replay and baseline_sat_replay

    actual_route = observed_route_class(candidate)
    prediction_match = prediction["predicted_route_class"] == actual_route

    verification = {
        "baseline_terminal": baseline_terminal,
        "baseline_exact_nodes": baseline_work.nodes,
        "terminal_match": terminal_match,
        "candidate_sat_root_replay": candidate_sat_replay,
        "baseline_sat_root_replay": baseline_sat_replay,
        "verification_pass": verification_pass,
        "actual_route_class": actual_route,
        "frozen_pattern_prediction_match": prediction_match,
        "truth_authority": "INDEPENDENT_EXACT_ROOT_SEARCH_PLUS_ROOT_REPLAY",
    }

    # DeltaH / RETURN_HIGHER: only verified experience is eligible for memory.
    experience_payload = {
        "schema": "JANUS/TRUMP/R2-VERIFIED-EXPERIENCE/v1.0",
        "parent_witness_sha256": witness["witness_sha256"],
        "formula_sha256": observation["formula_sha256"],
        "signature": {
            "density_class": observation["density_class"],
            "n_vars": observation["n_vars"],
            "n_clauses": observation["n_clauses"],
        },
        "actual_route_class": actual_route,
        "pattern_prediction_match": prediction_match,
        "candidate_terminal": candidate["terminal"],
        "candidate_mode": candidate["mode"],
        "candidate_charged_ops": candidate["work"]["charged_abstract_ops"],
        "verification_pass": verification_pass,
        "proof_authority": False,
        "routing_authority": False,
    }
    experience_eligible = verification_pass
    return_higher = {
        "experience_eligible": experience_eligible,
        "verified_experience_sha256": _stable_hash(experience_payload) if experience_eligible else None,
        "experience": experience_payload if experience_eligible else None,
        "pattern_support": bool(experience_eligible and prediction_match),
        "memory_status": "SHADOW_ONLY_VERIFIED" if experience_eligible else "REJECTED_UNVERIFIED",
        "proof_authority": False,
        "routing_authority": False,
    }

    return R2ShadowResult(
        observation=observation,
        prediction=prediction,
        pre_verification_witness=witness,
        candidate=candidate,
        independent_verification=verification,
        return_higher=return_higher,
    )


def prospective_pattern_admission_gate(rows: list[dict], rule_frozen_before_holdout: bool) -> dict:
    """Prospective admission gate for *future routing memory*, never truth."""
    total = len(rows)
    support = sum(bool(r["return_higher"]["pattern_support"]) for r in rows)
    verified = sum(bool(r["independent_verification"]["verification_pass"]) for r in rows)
    contradictions = sum(not bool(r["independent_verification"]["terminal_match"]) for r in rows)
    accuracy = 0.0 if total == 0 else support / total
    pass_gate = (
        rule_frozen_before_holdout
        and total >= PATTERN_ADMISSION_MIN_PROSPECTIVE_CASES
        and accuracy >= PATTERN_ADMISSION_MIN_ACCURACY
        and verified == total
        and contradictions == 0
    )
    return {
        "pass": pass_gate,
        "rule_id": RULE_ID,
        "rule_frozen_before_holdout": rule_frozen_before_holdout,
        "prospective_cases": total,
        "required_cases": PATTERN_ADMISSION_MIN_PROSPECTIVE_CASES,
        "pattern_support": support,
        "accuracy": accuracy,
        "required_accuracy": PATTERN_ADMISSION_MIN_ACCURACY,
        "independently_verified": verified,
        "truth_contradictions": contradictions,
        "promotion_if_pass": "FUTURE_ADVISORY_MEMORY_ELIGIBLE_ONLY",
        "truth_authority_if_pass": False,
        "current_run_routing_authority": False,
    }
