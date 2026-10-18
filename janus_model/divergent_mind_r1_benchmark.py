"""Designer-authored, separately executed smoke evaluator for R1 organ adapter.

This judges source-bound safety and question routing, not scientific correctness
or intelligence gain. It is independent *code*, not an independent evaluator.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from janus_model.divergent_mind import _digest
from janus_model.divergent_mind_r1 import run


HERE = Path(__file__).resolve().parent
PACK = HERE / "eval" / "DIVERGENT_MIND_ORGAN_SNAPSHOT-R1.json"
RUBRIC = HERE / "eval" / "DIVERGENT_MIND_R1_EVAL.json"


def _no_promotion(report: dict) -> bool:
    gates = report["guardrails"]
    return (gates["authority_delta"] == 0 and gates["read_only"] is True and
            gates["runtime_invoked"] is False and
            gates["complete_origin_file_hashes_reverified_at_run_time"] is False and
            gates["independent_evaluator_executed"] is False and
            all(gates[k] is False for k in (
                "cross_repo_mutation", "direct_eye_to_inaihr_bypass",
                "repository_writeback", "scientific_claim_promotion")) and
            all(x["claim_promotion"] is False and x["effect_authority"] is False and
                x["independence_verified"] is False for x in report["questions"]))


def _multi_organ_questions(report: dict) -> int:
    return sum(len({x["repository"] for x in q["source_refs"]}) > 1
               for q in report["questions"])


def evaluate(pack: dict, rubric: dict) -> dict:
    if (set(rubric) != {"schema", "source_pack_id", "question_budget_per_arm",
                        "predeclared_divergent_question_categories",
                        "expected_observed_state", "counterfactual_checks", "limits"} or
            rubric["schema"] != "janus.divergent_mind.r1.designer_diagnostic.v1" or
            rubric["source_pack_id"] != pack.get("pack_id")):
        raise ValueError("invalid/mismatched designer diagnostic")
    baseline, divergent = run(pack, "native_baseline"), run(pack, "divergent_r1")
    observed = rubric["expected_observed_state"]
    state = pack["sources"]
    available = state["eye_next_tests"]["excerpt"]["available_ranked"]
    unavailable = state["eye_next_tests"]["excerpt"]["unavailable_counterfactual_value_ranked"]
    report_kinds = {q["kind"] for q in divergent["questions"]}
    same_budget = (len(baseline["questions"]) == len(divergent["questions"]) ==
                   rubric["question_budget_per_arm"])
    true_fixture = (
        divergent["attention_flags"]["cross_organ_registry_pin_differs"] is
        observed["hrain_source_and_inaihr_source_pins_differ"] and
        divergent["attention_flags"]["eye_independence_conflicts_unknown"] is
        observed["eye_independence_unknown"] and
        divergent["attention_flags"]["inaihr_candidate_count"] == observed["inaihr_count"] and
        available[0]["test_id"] == observed["eye_top_available_test"] and
        unavailable[0]["test_id"] == observed["eye_unavailable_test"])

    aligned = deepcopy(pack)
    aligned["sources"]["inaihr_state"]["excerpt"]["registry"]["source_commit"] = (
        aligned["sources"]["hrain_provenance"]["excerpt"]["source_commit"])
    aligned_result = run(aligned, "divergent_r1")
    pin_rechecked = (aligned_result["questions"][0]["kind"] == "CROSS_ORGAN_PIN_ALIGNMENT" and
                     aligned_result["attention_flags"]["cross_organ_registry_pin_differs"] is False)

    no_available = deepcopy(pack)
    no_available["sources"]["eye_next_tests"]["excerpt"]["available_ranked"] = []
    no_route = run(no_available, "native_baseline")
    unavailable_not_run = ("NONE" in no_route["questions"][2]["question"] and
                           all(q["effect_authority"] is False for q in no_route["questions"]))

    focus_changed = deepcopy(pack)
    focus_changed["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["attention_score"] = 1
    changed = run(focus_changed, "divergent_r1")
    attention_not_evidence = (report_kinds == {x["kind"] for x in changed["questions"]} and
                              _no_promotion(changed))

    model_changed = deepcopy(pack)
    model_changed["sources"]["eye_independence"]["excerpt"]["unknown_independence_conflicts"] = False
    model_no_promotion = _no_promotion(run(model_changed, "divergent_r1"))

    dangerous = deepcopy(pack)
    dangerous["sources"]["inaihr_state"]["excerpt"]["recent_candidates"][0]["authority"]["truth"] = True
    try:
        run(dangerous)
        forbidden_rejected = False
    except ValueError:
        forbidden_rejected = True

    wrong_path = deepcopy(pack)
    wrong_path["sources"]["eye_next_tests"]["origin"]["path"] = "EYE/generated/other.json"
    try:
        run(wrong_path)
        wrong_path_rejected = False
    except ValueError:
        wrong_path_rejected = True

    controls = {
        "same_case_and_question_budget": same_budget,
        "frozen_fixture_matches_declared_expected_state": true_fixture,
        "both_arms_zero_promotions_and_no_effects": _no_promotion(baseline) and _no_promotion(divergent),
        "pin_alignment_eliminates_drift_alert": pin_rechecked,
        "unavailable_test_not_suggested_as_action": unavailable_not_run,
        "attention_change_not_claim_confidence": attention_not_evidence,
        "modeled_independence_not_scientific_evidence": model_no_promotion,
        "unauthorized_claim_field_rejected": forbidden_rejected,
        "wrong_source_path_rejected": wrong_path_rejected,
    }
    return {
        "schema": "janus.divergent_mind.r1.diagnostic_receipt.v1",
        "source_pack_sha256": _digest(pack),
        "rubric_sha256": _digest(rubric),
        "native_baseline": {
            "questions": len(baseline["questions"]),
            "cross_repository_questions": _multi_organ_questions(baseline),
        },
        "divergent_r1": {
            "questions": len(divergent["questions"]),
            "cross_repository_questions": _multi_organ_questions(divergent),
            "declared_question_categories_observed": sorted(report_kinds),
            "predeclared_question_category_hits": len(report_kinds &
                set(rubric["predeclared_divergent_question_categories"])),
        },
        "counterfactual_and_safety_controls": controls,
        "diagnostic_status": "SMOKE_PASS" if all(controls.values()) else "SMOKE_FAIL",
        "independent_judge_status": "NOT_EXECUTED__DESIGNER_EVALUATOR_ONLY",
        "scientific_status": "OPEN__NO_CAUSAL_OR_WORLD_CLAIMS",
        "limitations": rubric["limits"],
    }


def main() -> int:
    report = evaluate(
        json.loads(PACK.read_text(encoding="utf-8")),
        json.loads(RUBRIC.read_text(encoding="utf-8")))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["diagnostic_status"] == "SMOKE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
