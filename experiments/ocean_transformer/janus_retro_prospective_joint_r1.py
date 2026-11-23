#!/usr/bin/env python3
"""Precommitted JANUS R1 24-trial prospective early-vs-late audit.

This is a software statistical check of future OS randomness on a fixed-N
prospective window. It does not create retrocausality; a CPU simulator cannot
know a truly independent late bit without an information channel.

Selection MUST be made from early.json only before any future.json is read.
Aborts/incomplete selected trial IDs are never substituted by later successes.
The historical 7 trials are excluded from the prospective endpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path

from janus_retro_raw_recount_r1 import examine, load, require, tail_fair_bits, validate_bits
from janus_retro_early_joint_witness_r1 import permutation_pvalue
from janus_retro_decoder_challengers_r1 import score_challengers

EXPECTED_SCHEMA = "janus.retro.prospective_joint_probe.precommit.v1"
EXPECTED_MODEL = "2c38788e8468a98e9377fcdb9058c488ec3ec17dfacfbf553402a9b1a86cd4ca"
EXPECTED_COUNT = 24
BITS = 256
ALPHA = 1e-4
MIN_PERMUTATIONS = 9999


def unix_time(value):
    require(type(value) is str and value.endswith("Z"), "BAD_PROTOCOL_UTC_DATE")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError as ex:
        raise ValueError("BAD_PROTOCOL_UTC_DATE") from ex
    require(math.isfinite(result), "BAD_PROTOCOL_UTC_DATE")
    return result


def validate_protocol(p):
    require(type(p) is dict and p.get("schema") == EXPECTED_SCHEMA,
            "UNKNOWN_PROSPECTIVE_PROTOCOL")
    require(p.get("trials_required") == EXPECTED_COUNT and
            type(p.get("trials_required")) is int and
            p.get("bits_per_trial") == BITS and
            type(p.get("bits_per_trial")) is int,
            "UNREGISTERED_SAMPLE_SIZE")
    require(p.get("source_model_sha256") == EXPECTED_MODEL and
            p.get("no_adaptive_prediction_selection") is True and
            p.get("no_postselection") is True,
            "UNFROZEN_MODEL_OR_FILTERING")
    require(p.get("primary_alpha") == ALPHA and
            p.get("secondary_familywise_threshold") == 0.001,
            "UNREGISTERED_TEST_ALPHA")
    start,end = map(unix_time, (p.get("eligible_start_utc"),
                               p.get("eligible_end_exclusive_utc")))
    require(start < end, "EMPTY_PROSPECTIVE_WINDOW")
    return start,end


def null_report(status, first, selected, eligible, protocol):
    return {
        "schema": "janus.retro.prospective_joint_audit.r1",
        "status": status,
        "first_eligible_trial_utc": protocol["eligible_start_utc"],
        "selected_trial_ids": selected,
        "selected_so_far": len(selected),
        "eligible_early_records": len(eligible),
        "required_trials": EXPECTED_COUNT,
        "missing_or_incomplete_trial_ids": first,
        "primary_exact_p": None,
        "secondary_joint_permutation": None,
        "precommitted_challenger_suite": None,
        "all_selected_attempts_kept": True,
        "postselection": False,
        "statistical_claim_eligible": False,
        "external_physical_time_attestation": False,
        "future_source_independence_certified_externally": False,
        "physical_retrocausality_proven": False,
        "production_promotion": False
    }


def audit(root, protocol, permutations=MIN_PERMUTATIONS):
    start, end = validate_protocol(protocol)
    require(root.is_dir(), "MISSING_LEDGER")
    require(type(permutations) is int and permutations >= 99,
            "PERMUTATION_BUDGET_INVALID")
    # The prospective set is defined ONLY by EARLY precommit time and ID.
    # Never inspect late file existence or success when selecting sample.
    early_only = []
    for folder in root.iterdir():
        if not(folder.is_dir() and folder.name.startswith("janus-retro-")):
            continue
        ep=folder / "early.json"
        if not ep.is_file():
            continue
        early = load(ep)
        stamp = early.get("issued_at_epoch_utc")
        require(type(stamp) in (int, float) and math.isfinite(stamp),
                "INVALID_EARLY_ISSUED_TIMESTAMP")
        if start <= stamp < end:
            require(early.get("trial_id") == folder.name,
                    "EARLY_TRIAL_ID_MISMATCH")
            early_only.append((stamp,folder.name,folder))
    early_only.sort(key=lambda t:(t[0],t[1]))
    eligible_names=[name for _,name,_ in early_only]
    chosen=early_only[:EXPECTED_COUNT]
    selected=[name for _,name,_ in chosen]
    if len(chosen) < EXPECTED_COUNT:
        return null_report("PENDING_MORE_PRECOMMITTED_TRIALS",[],
                           selected,eligible_names,protocol)
    missing=[name for _,name,folder in chosen if not all(
        (folder/f).is_file() for f in ("early.json","future.json","comparison.json"))]
    if missing:
        return null_report("HOLD_INCOMPLETE_PRESELECTED_TRIALS",
                           missing,selected,eligible_names,protocol)
    groups=[]
    total_hits=0
    for _, name, folder in chosen:
        verified = examine(folder)
        early=load(folder/"early.json")
        future=load(folder/"future.json")
        require(early.get("model_sha256") == EXPECTED_MODEL,
                "MIXED_PRECOMMITTED_MODEL")
        a = [int(x) for x in validate_bits(early["predicted_bits"])]
        b = [int(x) for x in validate_bits(future["future_bits"])]
        p=early["p1_model_probs"]
        require(type(p) is list and len(p)==BITS and
                all(type(x) in (float,int) and math.isfinite(x) and 0 <= x <= 1
                    for x in p), "INVALID_EARLY_CONFIDENCE")
        c = [int(abs(x-0.5)>=0.25) for x in p]
        hits=sum(x==y for x,y in zip(a,b))
        require(hits == verified["recomputed_bits_correct"],
                "EARLY_LATE_RECOUNT_DISAGREEMENT")
        groups.append((a,c,b))
        total_hits+=hits
    n=BITS*EXPECTED_COUNT
    primary_p=tail_fair_bits(n,total_hits)
    witness=permutation_pvalue(groups,permutations,seed=20261107)
    challenger_spec=load(Path(__file__).with_name("janus_retro_decoder_challengers_r1.json"))
    challengers=score_challengers(groups,challenger_spec)
    # Substituting a lower permutation budget for a unit test is explicitly
    # forbidden from creating a scientific significance report.
    full_budget=permutations==MIN_PERMUTATIONS
    return {
        "schema":"janus.retro.prospective_joint_audit.r1",
        "status":"PROSPECTIVE_STATISTICAL_EVALUATION_COMPLETE" if full_budget
                  else "REGRESSION_ONLY_REDUCED_PERMUTATION_BUDGET",
        "trial_count":EXPECTED_COUNT,
        "bits":n,
        "selected_trial_ids":selected,
        "eligible_early_records":len(eligible_names),
        "unconditionally_correct_bits":total_hits,
        "unconditional_accuracy":total_hits/n,
        "primary_exact_p":primary_p,
        "primary_alpha":ALPHA,
        "primary_statistical_anomaly":full_budget and primary_p<ALPHA,
        "secondary_joint_permutation":witness,
        "precommitted_challenger_suite":challengers,
        "secondary_familywise_threshold":0.001,
        "secondary_exploratory_anomaly":full_budget and
            witness["bonferroni_adjusted_min_p_two_views"]<0.001,
        "all_selected_attempts_kept":True,
        "postselection":False,
        "early_sample_selected_without_late_data":True,
        "excluded_historical_pre_cutoff_trials":True,
        "external_physical_time_attestation":False,
        "future_source_independence_certified_externally":False,
        "physical_retrocausality_proven":False,
        "production_promotion":False,
        "interpretation":"A statistically unusual prospective result, if any, would require proof of externally sealed earlier outputs and independent later entropy, leak audit and independent replication. This software cannot establish a physical backward channel."
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--protocol",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    require(not args.out.exists(),"REFUSE_OVERWRITE")
    result=audit(args.ledger,load(args.protocol))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        "status":result["status"],
        "selected_so_far":len(result["selected_trial_ids"]),
        "primary_exact_p":result["primary_exact_p"],
        "physical_retrocausality_proven":False
    },indent=2))


if __name__=="__main__":
    main()
