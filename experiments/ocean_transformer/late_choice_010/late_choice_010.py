#!/usr/bin/env python3
"""JANUS LATE-CHOICE-010: sealed, unconditional delayed-setting test.

No past-directed signal is assumed. A trustworthy physical result requires
independently calibrated/signed times and genuinely late physical settings;
this code does NOT provide either. It rejects post-selection, missing trials,
bad event ordering and altered input hashes. Only local simulations run in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets

SCHEMA="janus.late_choice_010.v1"
ALPHA=0.001
PHYSICAL_N=16384
PROTOCOL_VERSION="1"
MODEL_TEST="two-sided Fisher exact conditional on A and C counts"
REQUIRED_ORIGIN="PHYSICAL_QRNG_GENERATED_AFTER_EARLY_MEASUREMENT"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False).encode("utf8")


def hash_obj(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_once(path, value):
    target=Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x",encoding="utf8") as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def as_int(value, label, lower=None):
    if type(value) is not int:
        raise ValueError(f"{label}: REQUIRED_INTEGER")
    if lower is not None and value < lower:
        raise ValueError(f"{label}: OUT_OF_BOUNDS")
    return value


def check_rows(early,late,n,required_origin=REQUIRED_ORIGIN):
    if not isinstance(early,list) or not isinstance(late,list) or len(early)!=n or len(late)!=n:
        raise ValueError("ALL_PREDECLARED_TRIALS_REQUIRED_NO_POSTSELECTION")
    if not 0<n<=1000000:
        raise ValueError("INVALID_PREDECLARED_N")
    counts=[[0,0],[0,0]] # C rows; A columns.
    raw=[]
    for i,(e,l) in enumerate(zip(early,late)):
        if not isinstance(e,dict) or not isinstance(l,dict):
            raise ValueError("BAD_TRIAL_SCHEMA")
        if as_int(e.get("trial"),"early.trial",0)!=i or as_int(l.get("trial"),"late.trial",0)!=i:
            raise ValueError("MISSING_DUPLICATED_OR_REORDERED_TRIAL")
        a=as_int(e.get("a"),"a",0)
        c=as_int(l.get("c"),"c",0)
        if a not in (0,1) or c not in (0,1):
            raise ValueError("NONBINARY_PREDECLARED_OUTCOME")
        ta=as_int(e.get("t_a_ns"),"t_a_ns",0)
        ua=as_int(e.get("u_a_ns"),"u_a_ns",0)
        tc=as_int(l.get("t_c_ns"),"t_c_ns",0)
        uc=as_int(l.get("u_c_ns"),"u_c_ns",0)
        tb=as_int(l.get("t_b_ns"),"t_b_ns",0)
        ub=as_int(l.get("u_b_ns"),"u_b_ns",0)
        if not (ta+ua < tc-uc and tc+uc < tb-ub):
            raise ValueError("EVENT_ORDER_NOT_PROVEN_WITH_UNCERTAINTY")
        if l.get("choice_origin")!=required_origin:
            raise ValueError("LATE_CHOICE_NOT_DECLARED_PHYSICAL")
        if l.get("b") not in (0,1,None) or type(l.get("b")) not in (int,type(None)):
            raise ValueError("B_AUDIT_OUTCOME_INVALID")
        counts[c][a]+=1
        raw.append({"trial":i,"a":a,"c":c,"b":l["b"]})
    if any(sum(r)==0 for r in counts):
        raise ValueError("NO_VARIATION_IN_LATE_SETTING")
    return counts,raw


def log_choose(n,k):
    if not 0<=k<=n: return float("-inf")
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)


def fisher_two_sided(table):
    """Freeman-Halton probability-ordering exact conditional 2x2 test."""
    if len(table)!=2 or any(len(row)!=2 for row in table):
        raise ValueError("NOT_2X2")
    for row in table:
        for x in row:
            as_int(x,"count",0)
    n0=sum(table[0]);n1=sum(table[1])
    n=n0+n1
    if n==0 or min(n0,n1)==0:raise ValueError("EMPTY_SETTING")
    success=table[0][1]+table[1][1]
    lo=max(0,success-n1)
    hi=min(success,n0)
    observed=table[0][1]
    logs=[log_choose(success,x)+log_choose(n-success,n0-x)-log_choose(n,n0)
          for x in range(lo,hi+1)]
    obs_log=logs[observed-lo]
    # Relative probabilities avoid cancellation and underflow.
    mx=max(logs)
    total=sum(math.exp(lp-mx) for lp in logs)
    numerator=sum(math.exp(lp-mx) for lp in logs if lp<=obs_log+1e-10)
    return min(1.0,numerator/total)


def statistic(table):
    n0=sum(table[0]); n1=sum(table[1])
    p0=table[0][1]/n0
    p1=table[1][1]/n1
    return {"n":n0+n1,"counts_c_by_a":table,"p_a1_c0":p0,"p_a1_c1":p1,
            "delta_p_a1":p1-p0,"fisher_exact_two_sided_p":fisher_two_sided(table),
            "alpha":ALPHA}


def optional_postselection_trap(rows):
    """Exploratory diagnostic only; never feeds primary statistics."""
    only=[r for r in rows if r["b"]==0]
    t=[[0,0],[0,0]]
    for r in only:t[r["c"]][r["a"]]+=1
    if not only or not all(sum(v)>0 for v in t):return None
    return {"n_postselected":len(only),"table_c_by_a":t,
            "p_two_sided_postselected_NOT_PRIMARY":fisher_two_sided(t),
            "interpretation":"Selection on B after late C creates collider/conditional correlations"}


def analyze(precommit,early,late,mode):
    if mode not in ("SIMULATION_ONLY","EXTERNAL_DATA_UNVERIFIED"):
        raise ValueError("INVALID_MODE")
    if not isinstance(precommit,dict) or precommit.get("schema")!=SCHEMA:
        raise ValueError("WRONG_PREDECLARED_SCHEMA")
    if precommit.get("protocol_version")!=PROTOCOL_VERSION or precommit.get("alpha")!=ALPHA:
        raise ValueError("PREDECLARED_PROTOCOL_CHANGED")
    if precommit.get("primary_test")!=MODEL_TEST or precommit.get("postselection_allowed") is not False:
        raise ValueError("PREDECLARED_PRIMARY_CHANGED")
    n=as_int(precommit.get("n"),"n",1)
    if mode=="EXTERNAL_DATA_UNVERIFIED" and n!=PHYSICAL_N:
        raise ValueError("PHYSICAL_N_DIFFERS_FROM_FROZEN_PLAN")
    counts,raw=check_rows(early,late,n)
    if precommit.get("required_choice_origin")!=REQUIRED_ORIGIN:
        raise ValueError("QRNG_REQUIRED")
    primary=statistic(counts)
    result={"schema":"janus.late_choice_010.assessment.v1",
            "mode":mode,"n_expected":n,"n_received":n,
            "precommit_sha256":hash_obj(precommit),
            "early_records_sha256":hash_obj(early),
            "late_records_sha256":hash_obj(late),
            "primary_unconditional":primary,
            "postselection_diagnostic_exploratory":optional_postselection_trap(raw),
            "all_trials_in_primary":True,
            "physical_independence_verified":False,
            "third_party_timestamp_signatures_verified":False,
            "hardware_shielding_and_crosstalk_audited":False,
            "eligible_to_claim_retrocausality":False,
            "significant_unverified_exploratory":primary["fisher_exact_two_sided_p"]<ALPHA,
            "status":"SIMULATION_NOT_SCIENTIFIC_EVIDENCE" if mode=="SIMULATION_ONLY"
                     else "PHYSICAL_ORIGIN_AND_CUSTODY_AUDIT_REQUIRED",
            "no_signal_is_not_a_proof_of_no_possible_retrocausality":True}
    return result


def make_simulation(n):
    """Early A first; C produced using OS entropy only AFTER early file fsync.

    Classical B=A XOR C exhibits a striking postselection artifact but gives
    no raw A-C dependence. Synthetic timestamps only: NOT a physical clock.
    """
    a_bits=secrets.token_bytes((n+7)//8)
    aa=[(a_bits[i//8]>>(7-i%8))&1 for i in range(n)]
    early=[{"trial":i,"a":a,"t_a_ns":i*1000000,"u_a_ns":100}
           for i,a in enumerate(aa)]
    return early


def late_simulation(early):
    raw=secrets.token_bytes((len(early)+7)//8)
    c_bits=[(raw[i//8]>>(7-i%8))&1 for i in range(len(early))]
    return [{"trial":i,"c":c,"t_c_ns":e["t_a_ns"]+300000,
             "u_c_ns":100,"t_b_ns":e["t_a_ns"]+600000,"u_b_ns":100,
             "choice_origin":REQUIRED_ORIGIN,"b":e["a"]^c}
            for i,(e,c) in enumerate(zip(early,c_bits))]


def simulation(out,n=4096):
    precommit={"schema":SCHEMA,"protocol_version":PROTOCOL_VERSION,
               "alpha":ALPHA,"n":n,"primary_test":MODEL_TEST,
               "postselection_allowed":False,
               "required_choice_origin":REQUIRED_ORIGIN,
               "hypothesis":"Early raw A marginal independent of later C"}
    early=make_simulation(n)
    write_once(out/"010_sim_early_frozen.json",{"precommit":precommit,"early":early})
    late=late_simulation(early)
    result=analyze(precommit,early,late,"SIMULATION_ONLY")
    write_once(out/"010_sim_late.json",late)
    write_once(out/"010_sim_score.json",result)
    print("JANUS_010_SIM "+json.dumps({"primary":result["primary_unconditional"],
      "postselected_example":result["postselection_diagnostic_exploratory"],
      "status":result["status"]},sort_keys=True),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["simulate","assess"])
    parser.add_argument("--output-dir",required=True)
    parser.add_argument("--precommit")
    parser.add_argument("--early")
    parser.add_argument("--late")
    args=parser.parse_args()
    dest=Path(args.output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    if args.mode=="simulate":
        simulation(dest)
    else:
        if not args.precommit or not args.early or not args.late:
            parser.error("assess requires --precommit, --early, --late")
        precommit=json.loads(Path(args.precommit).read_text())
        early=json.loads(Path(args.early).read_text())
        late=json.loads(Path(args.late).read_text())
        write_once(dest/"010_external_unverified_score.json",
                   analyze(precommit,early,late,"EXTERNAL_DATA_UNVERIFIED"))


if __name__=="__main__":main()
