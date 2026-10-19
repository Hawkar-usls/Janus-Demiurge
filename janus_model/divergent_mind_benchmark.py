"""Offline, algorithm-blind *diagnostic* of JANUS Divergent Mind v0.

Rubric labels are deliberately not fed to the generator. They are designer-
specified question-relevance targets, not scientific truths or external judges.
The structural baseline intentionally does not generate cross-domain bridges:
this contrast tests mechanics only, not superiority over a matched AI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from janus_model.divergent_mind import _digest, run


HERE = Path(__file__).resolve().parent
PACK_PATH = HERE / "eval" / "DIVERGENT_MIND_SOURCE_PACK-v0.json"
RUBRIC_PATH = HERE / "eval" / "DIVERGENT_MIND_PRIVATE_EVAL-v0.json"
BENCHMARK_SCHEMA = "janus.divergent_mind.benchmark.v0"


def _candidate_keys(report: dict) -> set[tuple[str, tuple[str, ...]]]:
    return {(x["operator"], tuple(sorted(x["source_ids"])))
            for x in report["B_cross_domain_candidates"]}


def evaluate(pack: dict, rubric: dict) -> dict:
    if (rubric.get("schema") != "janus.divergent_mind.algorithm_blind_rubric.v0" or
            rubric.get("source_pack_id") != pack.get("pack_id")):
        raise ValueError("rubric and source pack mismatch")
    baseline = run(pack, "structural_baseline")
    divergent = run(pack, "divergent")
    target_keys = {
        (case["operator"], tuple(sorted(case["source_ids"])))
        for case in rubric["relevant_cross_domain_questions"]
    }
    if len(target_keys) != len(rubric["relevant_cross_domain_questions"]):
        raise ValueError("duplicate relevance targets")
    missed = sorted(target_keys - _candidate_keys(divergent))
    present = sorted(target_keys & _candidate_keys(divergent))
    negative = rubric["negative_controls"]
    pair = set(negative["same_underlying_lineage_must_not_form_independent_bridge"])
    subject = negative["stale_ack_must_be_reported_as_temporal_change_not_current_concurrent_conflict"]
    temporal = [x for x in divergent["A_attention"] if x["subject"] == subject]
    not_same_lineage = all(not pair.issubset(set(x["source_ids"]))
                           for x in divergent["B_cross_domain_candidates"])
    temporal_pass = len(temporal) == 1 and temporal[0]["kind"] == "TEMPORAL_CHANGE__RECHECK_LATEST"
    no_promotion = (divergent["verifier"]["positive_claim_count"] ==
                    negative["all_candidate_claim_promotions_must_equal"] and
                    all(x["claim_promotion"] is False and x["effect_authority"] is False
                        for x in divergent["B_cross_domain_candidates"]))
    independent = all(x["independence_verified"] is
                      negative["independence_verified_without_external_review"]
                      for x in divergent["B_cross_domain_candidates"])
    pnp = [x for x in pack["observations"] if x["subject"] == "P_VS_NP"]
    gates = (negative["P_VS_NP_must_remain"] == "OPEN" and
             len(pnp) == 1 and pnp[0]["value"].startswith("P_VS_NP_OPEN_") and
             divergent["verifier"]["frozen_scientific_gates_unchanged"] is True and
             divergent["permissions"]["authority_delta"] == 0 and
             not any(divergent["permissions"][key] for key in divergent["permissions"]
                     if key != "authority_delta"))
    controls = {
        "same_lineage_not_independent_bridge": not_same_lineage,
        "historical_stale_ack_not_concurrent_outage": temporal_pass,
        "zero_scientific_claim_promotions": no_promotion,
        "zero_independence_automatically_verified": independent,
        "frozen_gates_and_no_authority": gates,
        "candidate_generator_never_receives_rubric": True,
    }
    return {
        "schema": BENCHMARK_SCHEMA,
        "source_pack_id": pack["pack_id"],
        "source_pack_sha256": divergent["source_pack_sha256"],
        "rubric_sha256": _digest(rubric),
        "baseline": {
            "attention_signals": len(baseline["A_attention"]),
            "cross_domain_candidates": len(baseline["B_cross_domain_candidates"]),
            "relevance_targets_hit": 0,
        },
        "divergent": {
            "attention_signals": len(divergent["A_attention"]),
            "cross_domain_candidates": len(divergent["B_cross_domain_candidates"]),
            "falsification_questions": len(divergent["V_fundamental_falsification_questions"]),
            "relevance_targets_hit": len(present),
            "relevance_targets_total": len(target_keys),
            "heuristic_relevance_fraction": round(len(present) / len(target_keys), 4),
            "matched_targets": [{"operator": op, "source_ids": list(ids)} for op, ids in present],
            "missed_targets": [{"operator": op, "source_ids": list(ids)} for op, ids in missed],
        },
        "negative_controls": controls,
        "diagnostic_status": "SMOKE_PASS" if all(controls.values()) else "SMOKE_FAIL",
        "scientific_status": "OPEN__NO_INDEPENDENT_VERIFICATION_OR_WORLD_CLAIM",
        "limitations": [
            "DESIGNER_AUTHORED_RUBRIC__NOT_INDEPENDENT_BLIND_VALIDATION",
            "BASELINE_MECHANICALLY_EXCLUDES_BRIDGES__NO_MATCHED_AI_COMPARISON",
            "CROSS_DOMAIN_PAIRING_IS_NOT_CAUSAL_MECHANISM_OR_SCIENTIFIC_EVIDENCE",
            "PINNED_GITHUB_FILES_ARE_SOURCE_OBSERVATIONS_NOT_RUNTIME_EXPERIMENTS",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline JANUS Divergent Mind diagnostic benchmark")
    parser.add_argument("--pack", type=Path, default=PACK_PATH)
    parser.add_argument("--rubric", type=Path, default=RUBRIC_PATH)
    args = parser.parse_args()
    report = evaluate(
        json.loads(args.pack.read_text(encoding="utf-8")),
        json.loads(args.rubric.read_text(encoding="utf-8")),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["diagnostic_status"] == "SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
