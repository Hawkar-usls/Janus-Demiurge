#!/usr/bin/env python3
"""JANUS R0: audit clock-ordered delayed-choice photon records.

This is a RECORD FORMAT AND SOFTWARE DRY RUN, not a photonic experiment.
An SHA256 in a manifest is not a trusted pre-choice timestamp. The program
cannot independently certify physical clocks, QRNG entropy or no leakage.
No postselection or detector-click filtering is permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random


EARLY_KEYS = frozenset(("trial_id", "early_a", "early_window_closed_ns", "predict_b"))
LATE_KEYS = frozenset(("trial_id", "late_b", "late_qrng_ns", "status"))
A_VALUES = (0, 1, "NO_CLICK")
MAX_TRIALS = 4096


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def is_bit(x):
    return type(x) is int and x in (0, 1)


def is_ns(x):
    return type(x) is int and x >= 0


def exact_right_binomial_tail(n, k):
    """Exact fair-Bernoulli right-tail probability for bounded fixed N."""
    require(type(n) is int and 1 <= n <= MAX_TRIALS, "N_OUT_OF_BOUNDS")
    require(type(k) is int and 0 <= k <= n, "K_OUT_OF_BOUNDS")
    return sum(math.comb(n, j) for j in range(k, n + 1)) / (1 << n)


def audit(manifest, early, late):
    require(type(manifest) is dict, "BAD_MANIFEST")
    require(type(early) is list and type(late) is list, "BAD_LEDGER")
    n = manifest.get("planned_trials")
    require(type(n) is int and 1 <= n <= MAX_TRIALS, "INVALID_PLANNED_N")
    margin = manifest.get("minimum_timing_margin_ns")
    require(is_ns(margin), "INVALID_MARGIN")
    alpha = manifest.get("alpha")
    require(type(alpha) in (float, int) and .0 < alpha < 1., "INVALID_ALPHA")
    require(len(early) == len(late) == n, "TRIALS_MISSING_OR_EXTRA")
    digest = canonical_digest(early)
    require(digest == manifest.get("early_log_sha256"), "EARLY_DIGEST_MISMATCH")
    earlier = {}
    for e in early:
        require(type(e) is dict and set(e) == EARLY_KEYS, "UNEXPECTED_EARLY_FIELD_OR_MISSING")
        i = e["trial_id"]
        require(type(i) is int and 0 <= i < n and i not in earlier,
                "EARLY_TRIAL_DUPLICATE_OR_OUT_OF_RANGE")
        require(e["early_a"] in A_VALUES and
                (type(e["early_a"]) is int or e["early_a"] == "NO_CLICK"),
                "INVALID_EARLY_OUTCOME")
        require(is_bit(e["predict_b"]), "INVALID_EARLY_PREDICTION")
        require(is_ns(e["early_window_closed_ns"]), "INVALID_EARLY_CLOCK")
        earlier[i] = e
    require(len(earlier) == n, "INCOMPLETE_EARLY_INDEX")
    later = {}
    # Validate all trial identities before comparing clocks. A duplicate must
    # never masquerade as an isolated timing failure on another trial.
    for l in late:
        require(type(l) is dict and set(l) == LATE_KEYS, "UNEXPECTED_LATE_FIELD")
        i = l["trial_id"]
        require(type(i) is int and 0 <= i < n and i not in later,
                "LATE_TRIAL_DUPLICATE_OR_OUT_OF_RANGE")
        later[i] = l
    require(len(later) == n, "INCOMPLETE_LATE_INDEX")
    for i in range(n):
        l = later[i]
        require(l["status"] in ("OK", "INFRA_ABORT"), "INVALID_LATE_STATUS")
        if l["status"] == "OK":
            require(is_bit(l["late_b"]), "INVALID_LATE_BIT")
            require(is_ns(l["late_qrng_ns"]), "INVALID_QRNG_CLOCK")
            require(l["late_qrng_ns"] >
                    earlier[i]["early_window_closed_ns"] + margin,
                    "CLOCK_ORDER_FAIL")
        else:
            require(l["late_b"] is None and l["late_qrng_ns"] is None,
                    "ABORT_MUST_NOT_HAVE_OUTCOME")
    counts = {str(a): [0, 0] for a in A_VALUES}
    matched = 0
    completed = 0
    abort_ids = []
    for i in range(n):
        e, l = earlier[i], later[i]
        if l["status"] == "INFRA_ABORT":
            abort_ids.append(i)
            continue
        completed += 1
        b = l["late_b"]
        counts[str(e["early_a"])][b] += 1
        matched += int(e["predict_b"] == b)
    # Report all scheduled trials, including aborted/no-click; never silently
    # turn a smaller completed subset into the preregistered fixed-N test.
    inference_valid = completed == n
    p = exact_right_binomial_tail(n, matched) if inference_valid else None
    n0 = sum(c[0] for c in counts.values())
    n1 = sum(c[1] for c in counts.values())
    tv = (sum(abs(c[0] / n0 - c[1] / n1) for c in counts.values()) / 2
          if inference_valid and n0 and n1 else None)
    return {
        "schema": "janus.delayed_choice.clock_audit.r0",
        "mode": "RECORD_FORMAT_AND_CPU_DRY_RUN",
        "planned_trials": n,
        "completed_trials": completed,
        "infra_abort_trial_ids": abort_ids,
        "unfiltered_early_outcomes_including_no_click": True,
        "early_log_sha256_verified_against_manifest": True,
        "external_sha_timestamp_signature_verified": False,
        "hardware_clock_calibration_verified": False,
        "hardware_QRNG_independence_verified": False,
        "physical_A_before_B_proven": False,
        "manifest_timing_margin_ns": margin,
        "software_timestamp_order_consistent": True,
        "matched_predictions": matched,
        "fixed_n_primary_valid": inference_valid,
        "one_sided_exact_binomial_p": p,
        "apparent_significance_under_fair_independent_B_assumption":
            bool(p is not None and p < alpha),
        "unconditional_A_by_late_B_counts": counts,
        "unconditional_early_A_total_variation": tv,
        "tv_is_descriptive_no_selected_shots": True,
        "hypothetical_postselection_used": False,
        "physical_retro_signal_detected": False,
        "production_promotion": "REFUSED_NO_INDEPENDENT_LAB_EVIDENCE",
        "interpretation": ("Counts and clock fields are input assertions. "
             "Even an extremely small p-value does not certify late entropy, "
             "clock ordering, independent seal or a past-directed channel.")
    }


def deterministic_mock(n=64):
    """Only a transparent positive/negative software fixture, not physical."""
    early = []
    late = []
    r = random.Random(9151)
    s = random.Random(9118)
    for i in range(n):
        early.append({"trial_id": i, "early_a": "NO_CLICK" if i % 7 == 0
                      else r.getrandbits(1),
                      "early_window_closed_ns": 10000 * i + 500,
                      "predict_b": r.getrandbits(1)})
        late.append({"trial_id": i, "late_b": s.getrandbits(1),
                     "late_qrng_ns": 10000 * i + 2000, "status": "OK"})
    return ({"planned_trials": n, "minimum_timing_margin_ns": 100,
             "alpha": .001, "early_log_sha256": canonical_digest(early)},
            early, late)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest")
    parser.add_argument("--early")
    parser.add_argument("--late")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.demo:
        require(not any((args.manifest, args.early, args.late)),
                "DEMO_MUST_BE_ISOLATED")
        manifest, early, late = deterministic_mock()
    else:
        require(all((args.manifest, args.early, args.late)),
                "REQUIRE_ALL_THREE_LEDGER_FILES")
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        early = json.loads(Path(args.early).read_text(encoding="utf-8"))
        late = json.loads(Path(args.late).read_text(encoding="utf-8"))
    result = audit(manifest, early, late)
    result["synthetic_demo_only"] = bool(args.demo)
    out = Path(args.out)
    require(not out.exists(), "REFUSE_OVERWRITE")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({"matched": result["matched_predictions"],
                      "trials": result["planned_trials"],
                      "p": result["one_sided_exact_binomial_p"],
                      "physical_evidence": result["physical_A_before_B_proven"]}))


if __name__ == "__main__":
    main()
