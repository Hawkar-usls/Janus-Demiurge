#!/usr/bin/env python3
"""Prespecified, fail-closed complete 8-date aggregate for NOAA and drand.

No p-hacking: compute the single pooled directional binomial check only if
every originally scheduled date has complete evidence. No substitutions or
early stopping. Ordinary predictive effects and hypothetical GLOW remain
separate from potential causal-physics claims.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

SCHEMA="janus.ocean.open_causality_009_aggregate.v1"
DATES=[(dt.date(2026,11,12)+dt.timedelta(days=i)).isoformat() for i in range(8)]
N=1024
DIRECTIONAL_THRESHOLD=562
REFERENCE_P=0.5

def one_sided_binomial_tail(success,n):
    if type(success) is not int or type(n) is not int or not 0<=success<=n or n<=0:
        raise ValueError("INVALID_EXACT_BINOMIAL_INPUT")
    return sum(math.comb(n,k) for k in range(success,n+1))/2**n

def pool_future(rows):
    if len(rows)!=len(DATES):
        raise ValueError("INCOMPLETE_EIGHT_COHORT_FUTURE_TRIAL")
    bydate={}
    for item in rows:
        if (item.get("lane")!="OPEN-FUTURE-009B" or item.get("status")!="ALL_SIGNED_INDEPENDENT_DRAND_ROUNDS_SCORED"
                or item.get("n_distinct_rounds")!=128 or
                item.get("randomness_bls_verified") is not True or
                item.get("no_late_outcomes_filtered") is not True or
                item.get("retrocausality_proven") is not False):
            raise ValueError("UNVERIFIED_OR_INCOMPLETE_DRAND_COHORT")
        date=item.get("target_date")
        if date not in DATES or date in bydate:
            raise ValueError("FUTURE_DATE_MISSING_DUPLICATED_OR_CHANGED")
        bydate[date]=item
    if sorted(bydate)!=DATES:raise ValueError("FUTURE_COHORT_DATES_NOT_CONTIGUOUS")
    wins=sum(bydate[day]["matches"] for day in DATES)
    if any(type(bydate[day]["matches"]) is not int or not 0<=bydate[day]["matches"]<=128 for day in DATES):
        raise ValueError("INVALID_MATCH_COUNT")
    p=one_sided_binomial_tail(wins,N)
    brier=sum(bydate[d]["brier"] for d in DATES)/len(DATES)
    return {
      "schema":SCHEMA,"lane":"OPEN-FUTURE-009B",
      "status":"ALL_1024_PROSPECTIVE_BITS_POOLED",
      "original_8_target_dates":DATES,
      "n":N,"matches":wins,"accuracy":round(wins/N,8),
      "brier_mean":round(brier,8),"uniform_brier":0.25,
      "one_sided_binomial_p_fair_independent":p,
      "threshold_fixed_before_test":DIRECTIONAL_THRESHOLD,
      "directional_threshold_reached":wins>=DIRECTIONAL_THRESHOLD,
      "not_physical_evidence":True,
      "no_independent_physical_early_receiver":True,
      "retrocausality_proven":False,
      "independent_replication_still_required":True,
    }

def pool_light(rows):
    if len(rows)!=len(DATES):
        raise ValueError("INCOMPLETE_EIGHT_COHORT_SOLAR_TRIAL")
    bydate={}
    for item in rows:
        if (item.get("lane")!="OPEN-LIGHT-009A" or item.get("status")!="PUBLIC_REAL_NOAA_OBSERVATION_SCORED"
                or item.get("n_hours")!=24 or item.get("target_all_24_hours") is not True
                or item.get("retrocausality_proven") is not False):
            raise ValueError("MISSING_OR_UNVERIFIED_SOLAR_HOURS")
        day=item.get("target_date")
        if day not in DATES or day in bydate:raise ValueError("NOAA_DATE_MISSING_DUPLICATED_OR_CHANGED")
        scores=item.get("mae_w_m2")
        if set(scores or {})!={"JANUS_PHYSICS_HEURISTIC","persistence","diurnal","clear_sky"}:
            raise ValueError("BASELINE_COMPARISONS_NOT_PRESERVED")
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in scores.values()):
            raise ValueError("NONFINITE_MAE_IN_SOLAR_RECORD")
        bydate[day]=item
    if sorted(bydate)!=DATES:raise ValueError("SOLAR_DATES_NOT_FIXED")
    means={k:round(sum(bydate[d]["mae_w_m2"][k] for d in DATES)/8,7)
           for k in ("JANUS_PHYSICS_HEURISTIC","persistence","diurnal","clear_sky")}
    return {
      "schema":SCHEMA,"lane":"OPEN-LIGHT-009A",
      "status":"ALL_EIGHT_REAL_NOAA_DAYS_POOLED",
      "target_dates":DATES,"n_hourly_observations":8*24,
      "mean_mae_w_m2":means,
      "fixed_hybrid_beats_each_baseline":all(means["JANUS_PHYSICS_HEURISTIC"]<v
                    for k,v in means.items() if k!="JANUS_PHYSICS_HEURISTIC"),
      "hybrid_is_not_a_trained_transformer":True,
      "retrospective_selection_used":False,
      "real_glow_filament_measurements":0,
      "retrocausality_proven":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("lane",choices=("light","future"))
    p.add_argument("--input",nargs="+",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    data=[json.loads(Path(path).read_text()) for path in args.input]
    result=pool_light(data) if args.lane=="light" else pool_future(data)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x") as f:f.write(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"lane":result["lane"],
                      "n":result.get("n",result.get("n_hourly_observations")),
                      "retrocausality_proven":False}))
if __name__=="__main__":main()
