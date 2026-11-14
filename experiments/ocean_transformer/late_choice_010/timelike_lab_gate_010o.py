#!/usr/bin/env python3
"""010O: independently calibrated hardware timelike-event readiness audit.

This parser proves NUMERIC interval separation only. It cannot verify
that timestamps are physical, that the QRNG is truly generated after A,
or that early data were independently and immutably committed.
Physical authority ALWAYS false absent a separately reviewed lab.
Scientific alpha/N remain the sealed physical-010 protocol.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path

EXPECTED_N=16384
STAGES=("A_commit","C_entropy_generation","C_basis_latch","B_detection")
SCHEMA="janus.physical010o.hardware_timeline_candidate.v1"

def require_int(x,label):
    if type(x) is not int or x<0:raise ValueError("INVALID_NONNEGATIVE_INT_"+label)
    return x

def check_interval(d,name):
    if type(d) is not dict or set(d)!={"t_ns","u_ns"}:
        raise ValueError("INVALID_TIME_UNCERTAINTY_PAIR_"+name)
    t=require_int(d["t_ns"],name+"_timestamp")
    u=require_int(d["u_ns"],name+"_uncertainty")
    if u>t:raise ValueError("NEGATIVE_LOWER_BOUND_"+name)
    return t-u,t+u

def chronology(trial):
    if not isinstance(trial,dict):raise ValueError("TRIAL_MUST_BE_OBJECT")
    if any(stage not in trial for stage in STAGES):
        raise ValueError("MISSING_PHYSICAL_STAGE_TIMESTAMP")
    intervals=[check_interval(trial[name],name) for name in STAGES]
    sep=[intervals[i+1][0]-intervals[i][1] for i in range(len(STAGES)-1)]
    return {"chronological_order_robust_given_claimed_common_time":all(d>0 for d in sep),
            "minimum_separation_margin_ns":min(sep),
            "individual_stage_gaps_ns":sep}

def assess(manifest):
    if type(manifest) is not dict or manifest.get("schema")!=SCHEMA:
        raise ValueError("WRONG_SOURCE_SCHEMA")
    if manifest.get("expected_n")!=EXPECTED_N:
        raise ValueError("SEALED_TRIAL_COUNT_CHANGED")
    trials=manifest.get("trials")
    if type(trials) is not list:raise ValueError("REQUIRE_ALL_TRIAL_LIST")
    if len(trials)>EXPECTED_N:raise ValueError("MORE_TRIALS_THAN_SEALED")
    bad=0;first_bad=[]
    minimum=None
    for i,t in enumerate(trials):
        if type(t) is not dict or t.get("trial_id")!=i:
            raise ValueError("MISSING_DUPLICATE_OR_REORDERED_TRIAL")
        if type(t.get("A")) is not int or t["A"] not in (0,1) or type(t.get("C")) is not int or t["C"] not in (0,1):
            raise ValueError("INVALID_PHYSICAL_BINARY_RESULT_OR_CHOICE")
        ord_check=chronology(t)
        if not ord_check["chronological_order_robust_given_claimed_common_time"]:
            bad+=1
            if len(first_bad)<8:first_bad.append({"trial_id":i,"margins_ns":ord_check["individual_stage_gaps_ns"]})
        margin=ord_check["minimum_separation_margin_ns"]
        minimum=margin if minimum is None else min(minimum,margin)
    status=("BLOCKED_NO_PHYSICAL_TRIALS" if not trials else
        "BLOCKED_MISSING_PREREGISTERED_TRIALS" if len(trials)<EXPECTED_N else
        "BLOCKED_CHRONOLOGY_UNCERTAINTY_OVERLAP" if bad else
        "NUMERIC_ORDER_ONLY_EXTERNAL_CUSTODY_REQUIRED")
    return {
      "schema":"janus.physical010o.hardware_timeline_assessment.v1",
      "expected_physical_trials":EXPECTED_N,
      "numeric_trials_provided":len(trials),
      "numeric_chronology_failures":bad,
      "first_eight_chronology_failures":first_bad,
      "minimum_numeric_timing_margin_ns":minimum,
      "claim_common_absolute_timebase_certified":False,
      "early_A_WORM_external_signature_and_order_verified":False,
      "QRNG_actual_physical_entropy_generation_time_verified":False,
      "Bob_basis_actuation_after_C_verified":False,
      "lab_independent_clock_path_calibration_and_uncertainties_verified":False,
      "physical_source_entangled_pair_quality_verified":False,
      "independent_lab_custody_verified":False,
      "ready_to_apply_original_sealed_Fisher_alpha_0_001":False,
      "physically_late_choice_proven":False,
      "retrocausal_channel_proven":False,
      "status":status,
      "no_self_attested_source_credence":True,
      "scientific_gate":"This code checks user-supplied numeric intervals only. Independent physical witnesses, genuine after-A QRNG generation, source/path latency and no postselection need external laboratory verification before any real physical effect can be inferred."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",help="External lab candidate JSON; no input emits default blocked readiness report")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    src=json.loads(Path(a.input).read_text(encoding="utf8")) if a.input else {
      "schema":SCHEMA,"expected_n":EXPECTED_N,"trials":[],
      "physical_experiment_connection":None}
    report=assess(src)
    report["input_sha256"]=hashlib.sha256(json.dumps(src,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    dst=Path(a.output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf8") as f:
        json.dump(report,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("JANUS_010O_RESULT "+json.dumps({"status":report["status"],
      "physical_trials":report["numeric_trials_provided"],
      "physically_late_choice_proven":False},sort_keys=True),flush=True)

if __name__=="__main__":main()
