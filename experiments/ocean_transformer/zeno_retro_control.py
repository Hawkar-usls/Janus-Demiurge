#!/usr/bin/env python3
"""JANUS-ZENO-TEMPORAL-001: two-phase *synthetic* future-choice control.

Receiver creates an early SHA-256-committed bitstream before sender creates
the independent later bitstream on the same GitHub runner. This makes a
testable chronology WITHIN THE WORKFLOW, but is not a physically independent
sender or proof of communication from the future. No postselection of early
records or tuning after revealing later choices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
import time
from pathlib import Path

EXPERIMENT_ID = "JANUS-ZENO-TEMPORAL-001"
SCHEMA = "janus.ocean.zeno_late_choice_control.v1"
COUNT = 2048


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def write_once(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise ValueError("REFUSE_OVERWRITE_FROZEN_RECEIPT")
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check_bits(bits, n):
    if not isinstance(bits, str) or len(bits) != n or set(bits) - set("01"):
        raise ValueError("MALFORMED_FIXED_SIZE_BITSTREAM")


def receiver(count=COUNT):
    if type(count) is not int or not 512 <= count <= 4096:
        raise ValueError("INVALID_PREDECLARED_SAMPLE_COUNT")
    raw = secrets.token_bytes((count + 7) // 8)
    bits = "".join(f"{x:08b}" for x in raw)[:count]
    record = {
        "schema": SCHEMA, "experiment_id": EXPERIMENT_ID,
        "phase": "EARLY_RECEIVER_PRECOMMIT",
        "clock_wall_time_ns": time.time_ns(),
        "n": count, "early_bits": bits,
        "source": "OS_CSPRNG_SAME_RUNNER_ONLY",
        "future_choice_generated": False,
        "early_data_changed_after_choice": False,
    }
    record["receipt_sha256"] = digest(record)
    return record


def validate_receiver(record):
    if not isinstance(record, dict) or record.get("schema") != SCHEMA:
        raise ValueError("RECEIVER_SCHEMA_MISMATCH")
    if record.get("phase") != "EARLY_RECEIVER_PRECOMMIT":
        raise ValueError("RECEIVER_PHASE_MISMATCH")
    n = record.get("n")
    if type(n) is not int or not 512 <= n <= 4096:
        raise ValueError("RECEIVER_COUNT_INVALID")
    _check_bits(record.get("early_bits"), n)
    supplied = record.get("receipt_sha256")
    bare = {k: v for k, v in record.items() if k != "receipt_sha256"}
    if digest(bare) != supplied:
        raise ValueError("EARLY_SHA256_PRECOMMIT_MISMATCH")
    return supplied


def sender(record):
    receipt = validate_receiver(record)
    count = record["n"]
    raw = secrets.token_bytes((count + 7) // 8)
    later = "".join(f"{x:08b}" for x in raw)[:count]
    now = time.time_ns()
    if now <= record["clock_wall_time_ns"]:
        raise ValueError("LATE_CHOICE_CHRONOLOGY_VIOLATION")
    result = {
        "schema": SCHEMA, "experiment_id": EXPERIMENT_ID,
        "phase": "LATE_CHOICE_COMMITTED",
        "clock_wall_time_ns": now, "n": count,
        "late_choice_bits": later,
        "source": "OS_CSPRNG_SAME_RUNNER_ONLY",
        "preexisting_receiver_receipt_sha256": receipt,
        "early_data_changed_after_choice": False,
    }
    result["receipt_sha256"] = digest(result)
    return result


def validate_sender(early, late):
    early_digest = validate_receiver(early)
    if not isinstance(late, dict) or late.get("schema") != SCHEMA:
        raise ValueError("SENDER_SCHEMA_MISMATCH")
    if late.get("phase") != "LATE_CHOICE_COMMITTED":
        raise ValueError("SENDER_PHASE_MISMATCH")
    if late.get("n") != early["n"]:
        raise ValueError("EARLY_LATE_COUNT_MISMATCH")
    if late.get("preexisting_receiver_receipt_sha256") != early_digest:
        raise ValueError("EARLY_LATE_BINDING_MISMATCH")
    _check_bits(late.get("late_choice_bits"), early["n"])
    supplied = late.get("receipt_sha256")
    bare = {k: v for k, v in late.items() if k != "receipt_sha256"}
    if supplied != digest(bare):
        raise ValueError("LATE_SHA256_RECEIPT_MISMATCH")
    if not (type(early["clock_wall_time_ns"]) is int
            and type(late.get("clock_wall_time_ns")) is int
            and late["clock_wall_time_ns"] > early["clock_wall_time_ns"]):
        raise ValueError("CHRONOLOGY_INVALID")
    return supplied


def exact_two_sided_binomial_p(matches, n):
    """Two-sided exact equal-tail binomial p under fair independent bits."""
    if not (type(matches) is int and type(n) is int and 0 <= matches <= n):
        raise ValueError("INVALID_BINOMIAL_INPUT")
    m = min(matches, n - matches)
    coefficient = 1
    accumulated = 1
    for k in range(1, m + 1):
        coefficient = coefficient * (n-k+1) // k
        accumulated += coefficient
    return min(1.0, (2*accumulated) / (1 << n))


def assess(early, late):
    validate_sender(early, late)
    n = early["n"]
    matches = sum(a == b for a, b in zip(early["early_bits"], late["late_choice_bits"]))
    # Illustrative postselection trap: after seeing both messages, retaining
    # only matching pairs gives 100% matches by construction. Do not infer signal.
    heralded = matches
    return {
        "schema": SCHEMA, "experiment_id": EXPERIMENT_ID,
        "status": "SAME_RUNNER_INDEPENDENT_RANDOM_NEGATIVE_CONTROL",
        "phase": "ASSESSMENT_AFTER_BOTH_COMMITMENTS",
        "n": n, "raw_matches": matches,
        "raw_accuracy": matches / n,
        "predeclared_test": "exact two-sided binomial, H0 p_match=0.5",
        "raw_two_sided_p": exact_two_sided_binomial_p(matches, n),
        "early_receipt_sha256": early["receipt_sha256"],
        "late_receipt_sha256": late["receipt_sha256"],
        "negative_control": {
            "raw_early_bits_included": n,
            "postselection_allowed_for_primary_test": False,
            "illustrative_herald_selection_after_reveal": "keep only positions where bits match",
            "selected_cases": heralded,
            "selected_accuracy": 1.0 if heralded else None,
            "selected_accuracy_is_artifact": True,
        },
        "sampling": {
            "predeclared_n": COUNT,
            "early_committed_before_late_generation": True,
            "same_runner_not_independent_external_sender": True,
            "external_temporal_witness": False,
            "real_quantum_hardware": False,
            "future_choice_labels_used_in_early_model": False,
        },
        "findings": {
            "independent_physical_retrocausal_signal_established": False,
            "statistical_outlier_if_p_below_0_05": exact_two_sided_binomial_p(matches,n) < .05,
            "outlier_is_not_proof_of_retrocausality": True,
            "next_gate": "INDEPENDENT_EXTERNAL_PRECOMMIT_AND_BLINDED_LATE_SENDER",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("receiver", "sender", "assess"))
    parser.add_argument("--receiver", help="Frozen receipt path")
    parser.add_argument("--sender", help="Frozen later-choice path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.phase == "receiver":
        result = receiver()
    elif args.phase == "sender":
        if not args.receiver:
            parser.error("--receiver required for sender")
        result = sender(read(args.receiver))
    else:
        if not args.receiver or not args.sender:
            parser.error("--receiver and --sender required for assess")
        result = assess(read(args.receiver), read(args.sender))
    write_once(args.output, result)
    print(json.dumps({"experiment": EXPERIMENT_ID, "phase": args.phase,
                      "receipt": digest(result), "status": result.get("status", "FROZEN"),
                      "retrocausality_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
