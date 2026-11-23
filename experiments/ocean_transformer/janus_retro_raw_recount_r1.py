#!/usr/bin/env python3
"""JANUS R1 independent raw-data audit of sealed-then-late retro-byte trials.

No simulation or retrospective selection counts as physical retrocausality.
Run on a READ-ONLY checkout of janus/retro-quantum-lab-ledger. Recalculate
every score from EARLY and FUTURE files instead of trusting comparison.json.
Original records are never modified, sorted, selected or overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

BITS_PER_TRIAL = 256
MAX_TRIALS = 64


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def tail_fair_bits(n, matches):
    require(0 <= matches <= n <= BITS_PER_TRIAL * MAX_TRIALS, "INVALID_BIT_COUNTS")
    # Exact rational arithmetic; no normal approximation to small tail p.
    return sum(math.comb(n, j) for j in range(matches, n + 1)) / (1 << n)


def tail_byte_matches(n, matches):
    require(0 <= matches <= n <= MAX_TRIALS * 32, "INVALID_BYTE_COUNTS")
    return (sum(math.comb(n, j) * 255 ** (n-j) for j in range(matches, n+1))
            / (256 ** n))


def validate_bits(value):
    require(type(value) is str and len(value) == BITS_PER_TRIAL and
            set(value) <= {"0", "1"}, "INVALID_256_BIT_PAYLOAD")
    return value


def examine(directory):
    early_path = directory / "early.json"
    future_path = directory / "future.json"
    compare_path = directory / "comparison.json"
    require(all(p.is_file() for p in (early_path, future_path, compare_path)),
            "TRIAL_MISSING_RAW_OR_COMPARISON_FILE")
    early, future, reported = [load(p) for p in
                               (early_path, future_path, compare_path)]
    require(type(early) is dict and type(future) is dict and
            type(reported) is dict, "INVALID_RECORD_SHAPE")
    trial_id = directory.name
    require(trial_id.startswith("janus-retro-") and
            all(x.get("trial_id") == trial_id for x in (early,future,reported)),
            "TRIAL_ID_MISMATCH")
    a = validate_bits(early.get("predicted_bits"))
    b = validate_bits(future.get("future_bits"))
    require(early.get("number_bits") == BITS_PER_TRIAL and
            reported.get("total_bits") == BITS_PER_TRIAL, "N_BIT_MISMATCH")
    require(digest(a.encode("ascii")) ==
            early.get("predicted_256_bits_sha256") ==
            reported.get("predicted_bits_sha256"), "EARLY_PREDICTION_HASH_MISMATCH")
    raw_future = bytes.fromhex(future["target_payload_hex"])
    require(len(raw_future) == BITS_PER_TRIAL // 8 and
            "".join(f"{i:08b}" for i in raw_future) == b and
            digest(raw_future) == future.get("target_sha256") ==
            reported.get("late_random_sha256"),
            "FUTURE_TARGET_HASH_MISMATCH")
    early_stamp = early.get("issued_at_epoch_utc")
    commit_stamp = future.get("receiver_commit_confirmed_epoch")
    future_stamp = future.get("future_generated_epoch_utc")
    require(all(type(x) in (float,int) and math.isfinite(x)
                for x in (early_stamp, commit_stamp, future_stamp)),
            "INVALID_TIMESTAMP")
    separation = future.get("minimum_separation_seconds")
    require(type(separation) in (float,int) and separation >= 120,
            "INSUFFICIENT_SEPARATION_RULE")
    require(early_stamp <= commit_stamp and
            future_stamp >= commit_stamp + separation,
            "INTERNAL_CHRONOLOGY_CONTRADICTION")
    # These timestamp fields are user-space assertions, not signed third-party
    # clock evidence. This tool *cannot* certify the timing externally.
    matches = sum(c == d for c,d in zip(a,b))
    full_bytes = [i for i in range(32)
                  if a[i*8:(i+1)*8] == b[i*8:(i+1)*8]]
    require(matches == reported.get("unconditional_matching_bits"),
            "REPORTED_BIT_COUNT_CONTRADICTS_RAW_DATA")
    previous_byte_record = reported.get("unconditional_full_byte_matches")
    if previous_byte_record is not None:
        require(previous_byte_record.get("count") == len(full_bytes) and
                previous_byte_record.get("indices_zero_based") == full_bytes,
                "REPORTED_BYTE_COUNTS_CONTRADICT_RAW_DATA")
    require(not reported.get("physical_retrocausality_proven", False),
            "UNSUPPORTED_PHYSICAL_CLAIM_IN_ARCHIVE")
    p1 = early.get("p1_model_probs")
    require(type(p1) is list and len(p1) == BITS_PER_TRIAL and
            all(type(p) in (int,float) and math.isfinite(p) and 0 <= p <= 1
                for p in p1), "EARLY_CONFIDENCE_MISSING_OR_INVALID")
    brier = sum((p-int(bi))**2 for p,bi in zip(p1,b))/BITS_PER_TRIAL
    return {
        "trial_id": trial_id,
        "recomputed_bits_correct": matches,
        "recomputed_full_byte_count": len(full_bytes),
        "recomputed_full_byte_indices": full_bytes,
        "brier_recomputed": round(brier, 8),
        "internal_separation_seconds": round(future_stamp-commit_stamp, 6),
        "files_sha256": {p.name: digest(p.read_bytes()) for p in
                          (early_path, future_path, compare_path)},
        "original_comparison_includes_byte_metric": previous_byte_record is not None,
        "source_model_sha256": early.get("model_sha256"),
        "physically_attested_timestamps": False,
        "physical_retrocausal_signal": False,
    }


def audit(ledger):
    require(ledger.is_dir(), "MISSING_LEDGER_DIRECTORY")
    dirs = sorted(p for p in ledger.iterdir() if p.is_dir()
                  and p.name.startswith("janus-retro-"))
    require(0 < len(dirs) <= MAX_TRIALS, "UNBOUNDED_OR_EMPTY_ARCHIVE")
    rows = [examine(d) for d in dirs]
    ids = [r["trial_id"] for r in rows]
    require(len(set(ids)) == len(ids), "DUPLICATE_TRIAL")
    bits = BITS_PER_TRIAL * len(rows)
    correct = sum(r["recomputed_bits_correct"] for r in rows)
    total_bytes = bits // 8
    matched_bytes = sum(r["recomputed_full_byte_count"] for r in rows)
    p_bits = tail_fair_bits(bits, correct)
    p_bytes = tail_byte_matches(total_bytes, matched_bytes)
    # Post-hoc aggregation: descriptive only. Cumulative candidate selection
    # and interim looks prevent this becoming a new confirmatory p value.
    return {
        "schema": "janus.retro.raw_recount_audit.r1",
        "mode": "READ_ONLY_RETROSPECTIVE_INDEPENDENT_RECOUNT",
        "records": rows,
        "trial_count": len(rows),
        "total_bits": bits,
        "unconditionally_correct_bits": correct,
        "unconditional_bit_accuracy": correct/bits,
        "total_full_bytes": total_bytes,
        "matching_full_bytes": matched_bytes,
        "chance_expected_bytes": total_bytes/256,
        "exploratory_exact_binomial_p_ge_bit_matches": p_bits,
        "exploratory_exact_binomial_p_ge_byte_matches": p_bytes,
        "exact_byte_probability_under_independent_uniform_late_bits": 1/256,
        "old_schema_records_with_recovered_byte_counts":
            sum(not r["original_comparison_includes_byte_metric"] for r in rows),
        "read_all_available_archived_trials": True,
        "postselection": False,
        "historical_claim_is_not_preregistered": True,
        "externally_attested_physical_time_order": False,
        "independent_physically_certified_QRNG": False,
        "independent_laboratory_replication": False,
        "quantum_computer_required": False,
        "CPU_computation_is_not_an_actual_time_travel_channel": True,
        "physical_retrocausal_signal_demonstrated": False,
        "production_promotion": "REFUSED_NO_PHYSICAL_CAUSAL_PROOF",
        "interpretation": (
            "Recount all archived A/B bitstreams, never cherry-pick successes. "
            "P values are descriptive under independent fair-future-bit null, "
            "not a validated physical time-order proof or a new pre-registered "
            "hypothesis. Nonzero full-byte matches can arise by chance."
        )
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    a=parser.parse_args()
    if a.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    result=audit(a.ledger)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
                     encoding="utf-8")
    print(json.dumps({k:result[k] for k in
                      ("trial_count","unconditionally_correct_bits",
                       "total_bits","matching_full_bytes","total_full_bytes",
                       "exploratory_exact_binomial_p_ge_bit_matches",
                       "exploratory_exact_binomial_p_ge_byte_matches",
                       "physical_retrocausal_signal_demonstrated")},indent=2))


if __name__=="__main__":
    main()
