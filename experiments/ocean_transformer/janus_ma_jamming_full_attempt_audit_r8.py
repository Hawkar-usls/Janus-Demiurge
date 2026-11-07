#!/usr/bin/env python3
"""JANUS R8 strict ALL-ATTEMPT joint-early vs later choice audit.

Primary test: compare the entire 3x3 early X,Z distribution under later
independent B=0 vs B=1, INCLUDING NO_CLICK states. A B-label permutation
test, not heralded or photon-coincidence postselection.

Physically necessary external attestations are explicitly NOT provided by
this script. Simulated source flags must never be laundered into physical
claims. Timestamp integers supplied by the same machine do not constitute
independently sealed pre-choice chronological evidence.

The deliberate positive control uses B to generate earlier X,Z. It is
synthetic future-leak injection, not backwards signalling.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

N=2048
PERMUTATIONS=4999
ALPHA=0.001
EARLY_SCHEMA="janus.ma_jamming.early.r8"
LATE_SCHEMA="janus.ma_jamming.late.r8"
MANIFEST_SCHEMA="janus.ma_jamming.manifest.r8"
NOC="NO_CLICK"
VALUES=(0,1,NOC)
CELLS=tuple((x,z) for x in VALUES for z in VALUES)
SYNTHETIC_MODES=("normal","leak_injected","quantum_heralded")


def require(x,reason):
    if not x:raise ValueError(reason)


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode()


def sha(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def early_category(r):
    return (r["x"],r["z"])


def synthetic(seed,mode="normal"):
    require(type(seed) is int and 0<=seed<2**64,"INVALID_SEED")
    require(mode in SYNTHETIC_MODES,"INVALID_SYNTHETIC_MODEL")
    rng=random.Random(seed)
    late_rng=random.Random(seed ^ 0x7F4A7C159E3779B9)
    # In normal/quantum, B is sampled AFTER the early ledger is frozen.
    # The deliberately planted positive control is anti-chronological:
    # late B is supplied to earlier generation. The dataset self-labels
    # that fact and can NEVER count as physical evidence.
    preloaded=[late_rng.getrandbits(1) for _ in range(N)] if mode=="leak_injected" else None
    rows=[]
    for i in range(N):
        x=rng.randrange(2)
        z=rng.randrange(2)
        if mode=="leak_injected":z=x^preloaded[i]
        # Separate detector losses: complete, explicit no-click records.
        if rng.random()<.035:x=NOC
        if rng.random()<.035:z=NOC
        rows.append({"trial_id":i,"early_epoch_ns":1_000_000_000+i*100,
                     "x":x,"z":z})
    # At this point the full early ledger exists for normal modes.
    bits=preloaded if preloaded is not None else [
        late_rng.getrandbits(1) for _ in range(N)]
    late=[]
    for i,(r,b) in enumerate(zip(rows,bits)):
        if mode=="normal":
            # Pure forward-i.i.d. control: do not manufacture a quantum herald.
            v="NO_FOURFOLD" if NOC in (r["x"],r["z"]) else "UNMODELED_LATE"
        elif NOC in (r["x"],r["z"]):
            v="NO_FOURFOLD"
        elif b==0:
            v=f"SSM_{r['x']}{r['z']}"
        else:
            branch="PHI" if r["x"]==r["z"] else "PSI"
            v=f"BSM_{branch}_{late_rng.randrange(2)}"
        late.append({"trial_id":i,
                     "late_epoch_ns":r["early_epoch_ns"]+1_000_000,
                     "b":b,"late_outcome":v})
    early_digest=sha(rows)
    future_digest=sha(late)
    manifest={
        "schema":MANIFEST_SCHEMA,
        "trial_count":N,
        "primary_endpoint":"TV(P(X,Z|late B=0),P(X,Z|late B=1)) including NO_CLICK",
        "primary_permutations":PERMUTATIONS,
        "primary_alpha":ALPHA,
        "early_sha256":early_digest,
        "late_sha256":future_digest,
        "source_type":"SYNTHETIC_CPU",
        "control_mode":mode,
        "independent_late_hardware_QRNG_verified":False,
        "independent_external_early_timestamp_seal_verified":False,
        "all_trials_preselected_before_late_outcome":True,
        "late_B_preloaded_for_early_generation":mode=="leak_injected",
        "quantum_late_outcome_sampled_using_early_record":mode!="normal",
        "all_attempts_included":True,
        "not_an_operational_retrocausal_resource":True
    }
    return {"schema":EARLY_SCHEMA,"records":rows},{
        "schema":LATE_SCHEMA,"records":late},manifest


def verify(early,late,manifest):
    require(type(early) is dict and type(late) is dict and
            type(manifest) is dict and
            early.get("schema")==EARLY_SCHEMA and
            late.get("schema")==LATE_SCHEMA and
            manifest.get("schema")==MANIFEST_SCHEMA,
            "UNKNOWN_DATA_SCHEMAS")
    a,b=early.get("records"),late.get("records")
    require(type(a) is list and type(b) is list and
            len(a)==len(b)==manifest.get("trial_count")==N,
            "INCOMPLETE_FIXED_N_NO_POSTSELECTION")
    require(manifest.get("early_sha256")==sha(a) and
            manifest.get("late_sha256")==sha(b),
            "LEDGER_DIGEST_CHANGED")
    require(manifest.get("primary_alpha")==ALPHA and
            manifest.get("primary_permutations")==PERMUTATIONS and
            manifest.get("all_attempts_included") is True,
            "PREDECLARED_TEST_CHANGED")
    require(manifest.get("source_type") in ("SYNTHETIC_CPU","PHYSICAL_EXTERNAL"),
            "SOURCE_NOT_DECLARED")
    for i,(x,y) in enumerate(zip(a,b)):
        require(type(x) is dict and type(y) is dict and
                set(x)=={"trial_id","early_epoch_ns","x","z"} and
                set(y)=={"trial_id","late_epoch_ns","b","late_outcome"},
                "FUTURE_LEAK_INTO_EARLY_OR_UNEXPECTED_FIELD")
        require(type(x["trial_id"]) is int and type(y["trial_id"]) is int
                and x["trial_id"]==y["trial_id"]==i,
                "TRIAL_ID_GAP_DUPLICATE_OR_REORDER")
        require(x["x"] in VALUES and x["z"] in VALUES and
                type(x["x"]) is not bool and type(x["z"]) is not bool and
                type(y["b"]) is int and y["b"] in (0,1) and
                type(y["late_outcome"]) is str and y["late_outcome"],
                "BAD_EARLY_OUTCOME_OR_LATE_CHOICE")
        require(type(x["early_epoch_ns"]) is int and
                type(y["late_epoch_ns"]) is int and
                0<x["early_epoch_ns"]<y["late_epoch_ns"],
                "CLOCK_ORDER_VIOLATION")
    require(any(r["b"]==0 for r in b) and any(r["b"]==1 for r in b),
            "NO_INDEPENDENT_LATE_CHOICE_VARIATION")
    return True


def tv_from_counts(a,b):
    n0=sum(x==0 for x in b)
    n1=len(b)-n0
    require(n0 and n1,"MISSING_LATE_CHOICE_CLASS")
    c0=Counter(c for c,v in zip(a,b) if v==0)
    c1=Counter(c for c,v in zip(a,b) if v==1)
    tv=.5*sum(abs(c0[k]/n0-c1[k]/n1) for k in CELLS)
    def one_component(which):
        vals=VALUES
        ca=Counter(c[which] for c,v in zip(a,b) if v==0)
        cb=Counter(c[which] for c,v in zip(a,b) if v==1)
        return .5*sum(abs(ca[k]/n0-cb[k]/n1) for k in vals)
    return tv,one_component(0),one_component(1)


def score(early,late,manifest,permutations=PERMUTATIONS):
    verify(early,late,manifest)
    require(type(permutations) is int and 199<=permutations<=PERMUTATIONS,
            "INVALID_PERMUTATION_BUDGET")
    categories=[early_category(r) for r in early["records"]]
    b=[r["b"] for r in late["records"]]
    tv,tvx,tvz=tv_from_counts(categories,b)
    rng=random.Random(20261107)
    pool=b[:]
    exceed=0
    for _ in range(permutations):
        rng.shuffle(pool)
        value,*_=tv_from_counts(categories,pool)
        exceed += value>=tv-1e-12
    p=(exceed+1)/(permutations+1)
    # Descriptive SECONDARY sorting: a later phi herald selects already
    # written X=Z records. It never enters the fixed-N primary p-value.
    heralded=None
    if manifest.get("control_mode")=="quantum_heralded":
        phi=[a for a,l in zip(early["records"],late["records"])
             if l["late_outcome"].startswith("BSM_PHI_")]
        heralded={
            "late_herald":"BSM_PHI",
            "accepted_heralded_events":len(phi),
            "all_scheduled_attempts":N,
            "parity_equal_among_heralded":(
                sum(a["x"]==a["z"] for a in phi)/len(phi) if phi else None),
            "only_available_after_late_outcome":True,
            "excluded_from_primary_statistic":True,
            "is_not_past_directed_signalling":True
        }
    result={
       "schema":"janus.ma_jamming.joint_early_permutation_report.r8",
       "source_type":manifest["source_type"],
       "control_mode":manifest.get("control_mode"),
       "fixed_sample_N":N,
       "observed_joint_early_TV_between_late_choices":tv,
       "observed_single_X_TV":tvx,
       "observed_single_Z_TV":tvz,
       "p_label_permutation_one_sided":p,
       "planned_alpha":ALPHA,
       "permutations_executed":permutations,
       "pass_statistical_gate":p<ALPHA if permutations==PERMUTATIONS else None,
       "complete_early_attempts":len(categories),
       "no_click_attempts":sum(NOC in c for c in categories),
       "all_trials_included_in_primary_endpoint":True,
       "fourfold_or_late_herald_postselection_in_primary":False,
       "source_preloaded_late_B":manifest.get("late_B_preloaded_for_early_generation") is True,
       "late_heralded_secondary_exploratory":heralded,
       "independent_hardware_QRNG_verified":False,
       "independent_external_timestamp_seal_verified":False,
       "physical_causal_intervention_replicated":False,
       "actual_physical_retrocausal_signal_proven":False,
       "reason":"No actual physical early detector and independent later intervention connected; machine timestamps and planted synthetic correlation have no external attestation.",
       "research_only":True
    }
    return result


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    s=sub.add_parser("simulate")
    s.add_argument("--seed",type=int,default=20261107)
    s.add_argument("--model",choices=SYNTHETIC_MODES,default="normal")
    s.add_argument("--output-dir",type=Path,required=True)
    t=sub.add_parser("score")
    t.add_argument("--early",type=Path,required=True)
    t.add_argument("--late",type=Path,required=True)
    t.add_argument("--manifest",type=Path,required=True)
    t.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.mode=="simulate":
        e,l,m=synthetic(args.seed,args.model)
        args.output_dir.mkdir(parents=True,exist_ok=True)
        for filename,value in (("early.json",e),("late.json",l),("manifest.json",m)):
            path=args.output_dir/filename
            if path.exists():raise RuntimeError("REFUSE_OVERWRITE")
            path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
        print(json.dumps({"model":args.model,"records":N,
                          "future_preloaded":m["late_B_preloaded_for_early_generation"]}))
    else:
        out=score(*(json.loads(p.read_text()) for p in (
                  args.early,args.late,args.manifest)))
        if args.out.exists():raise RuntimeError("REFUSE_OVERWRITE")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
        print(json.dumps({k:out[k] for k in (
              "observed_joint_early_TV_between_late_choices",
              "observed_single_X_TV","observed_single_Z_TV",
              "p_label_permutation_one_sided",
              "pass_statistical_gate",
              "actual_physical_retrocausal_signal_proven")}))


if __name__=="__main__":
    main()
