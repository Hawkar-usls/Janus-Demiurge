#!/usr/bin/env python3
"""TRINITY R1 critic qualification: openly reproducible diagnostic, NOT blind exam.

Runs the pinned SmolLM2 critic on disjoint arithmetic examples (correct,
incorrect, and malformed proposed answers). Model votes are advisory;
the symbolic oracle is the only truth reference. No JANUS training,
checkpoint writes, promotion or private Genesis exam access.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu

SCHEMA = "janus.trinity.critic_diagnostic.v1"
THRESHOLD = {"correct_approve": 10, "wrong_veto": 10, "ambiguous_not_approve": 12}
PROMPT_VERSION = "critic-v1-fixed-before-first-diagnostic"


def cases():
    rows = []
    for i in range(12):
        a = 129 + (17 * i)
        b = 204 + (19 * i)
        problem = f"What is {a} plus {b}? Reply with a single nonnegative integer."
        good = str(a + b)
        choices = (
            ("CORRECT", good),
            ("INCORRECT", str(a + b + 1 + i % 3)),
            ("AMBIGUOUS", f"Possibly {good}, or maybe {a+b+2}"),
        )
        for category, proposal in choices:
            rows.append({"id": f"CRITIC-{i+1:02d}-{category}", "kind": category,
                         "problem": problem, "proposal": proposal,
                         "partition": "PUBLIC_CRITIC_DIAGNOSTIC_NOT_STUDENT_EXAM"})
    return rows


def prompt(row):
    if not isinstance(row, dict) or row not in cases():
        raise ValueError("TRINITY_UNRECOGNIZED_CRITIC_PROBE")
    return (
        "You are checking basic integer addition. Respond with exactly YES "
        "only if the proposed answer is ONE canonical decimal integer and "
        "it equals the mathematically correct sum. Otherwise respond with "
        "exactly NO. Never explain.\n"
        + row["problem"] + "\nProposed answer: " + row["proposal"]
        + "\nVerdict (YES or NO):"
    )


def evaluate(rows, outputs):
    if not isinstance(outputs, list) or len(outputs) != len(rows):
        raise ValueError("TRINITY_INCOMPLETE_CRITIC_PROBE")
    if rows != cases():
        raise ValueError("TRINITY_CRITIC_DIAGNOSTIC_MODIFIED")
    metrics = {"CORRECT": {"APPROVE": 0, "VETO": 0, "ABSTAIN": 0},
               "INCORRECT": {"APPROVE": 0, "VETO": 0, "ABSTAIN": 0},
               "AMBIGUOUS": {"APPROVE": 0, "VETO": 0, "ABSTAIN": 0}}
    item_receipts = []
    for row, value in zip(rows, outputs):
        if not isinstance(value, str) or len(value) > 100:
            raise ValueError("TRINITY_MALFORMED_CRITIC_OUTPUT")
        decision = c.critic_decision(value)
        metrics[row["kind"]][decision] += 1
        item_receipts.append({"id": row["id"], "kind": row["kind"],
                              "decision": decision,
                              "output_sha256": c.digest({"output": value})})
    criterion = {
        "correct_approval": metrics["CORRECT"]["APPROVE"] >= THRESHOLD["correct_approve"],
        "wrong_detection": metrics["INCORRECT"]["VETO"] >= THRESHOLD["wrong_veto"],
        "ambiguous_rejection": metrics["AMBIGUOUS"]["APPROVE"] == 0,
    }
    passed = all(criterion.values())
    report = {
        "schema": SCHEMA,
        "model": c.SMOL,
        "prompt_version": PROMPT_VERSION,
        "diagnostic_case_count": len(rows),
        "case_set_sha256": c.digest(rows),
        "metrics": metrics,
        "criteria": criterion,
        "qualification": "PUBLIC_DIAGNOSTIC_PASS_STILL_NEEDS_UNSEEN_CRITIC_HOLDOUT" if passed
                         else "HOLD_CRITIC_NOT_QUALIFIED",
        "eligible_to_certify_student_training": False,
        "may_promote_native_weights": False,
        "may_change_graduation_policy": False,
        "independent_external_exam": False,
        "student_64_case_exam_used": False,
        "responses": item_receipts,
    }
    return c.sealed(report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tk, model = cpu.load_parent(c.SMOL)
    rows = cases()
    outputs = [cpu.parent_answer(tk, model, prompt(row), max_tokens=7) for row in rows]
    result = evaluate(rows, outputs)
    cpu.save_new(args.out, result)
    print(json.dumps({"qualification": result["qualification"], "metrics": result["metrics"],
                      "case_set_sha256": result["case_set_sha256"],
                      "may_promote_native_weights": False}, sort_keys=True))


if __name__ == "__main__":
    main()
