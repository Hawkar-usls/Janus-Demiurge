#!/usr/bin/env python3
"""JANUS Gull R12c — REAL lesser black-backed gull annotated behavior.

Use 3503 human-scored behavior entries published across 2012–14 in the
LBBG_TEXEL archive DOI 10.5281/zenodo.23942209; never use its GULLIVER
machine-assigned classes as truth. GPS at or BEFORE annotation time, same
individual, lag <=120s, publisher-original MD5 pinned. Leave entire
individual birds out for each heldout fold.

Finite one-bit sensor benchmark on the REAL behavioral labels:
(A) speed geometry encoder threshold selected by unlabeled speed MSE,
    then classify using labeled TRAIN birds only.
(B) speed task-oriented encoder threshold selected by balanced activity
    accuracy on labeled TRAIN birds; no heldout fold tuning.
This is NOT a trial of external visual stimuli, retinal anatomy, or the
physical truth of Hoffman's consciousness/space metaphysics.

Published individual IDs and nest GPS never leave local transient worker.
Online source data are downloaded read-only; result aggregates only.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path

from janus_gull_real_data_audit_v2 import download,sha,assert_source
from janus_gull_human_gps_holdout_v2 import (
  human_events,attach_prior_gps,balanced_accuracy,predict
)

RECORD="https://zenodo.org/records/23942209/files/"
DOI="10.5281/zenodo.23942209"
PUBLISHED={
 2012:{"accessory":"7f3375e52f707dfe3dcbf028747b3081",
       "gps":"79daa423e19af985c7d590c08ac0f872"},
 2013:{"accessory":"200d384d61918302f051d3fbcc9f734e",
       "gps":"d1c54be360d1b66abe4a44109ea1f287"},
 2014:{"accessory":"e706dc9fad9ddeab31e54e78d09c1ec0",
       "gps":"c87a406df93f49b997bc8fed0beeb4c3"}
}
YEAR_SET=(2012,2013,2014)


def official_data(year,kind):
    assert_source(year in PUBLISHED and kind in ("accessory","gps"),
                  "UNKNOWN_PUBLISHED_SOURCE")
    name=f"LBBG_TEXEL-{'accessory-measurements' if kind=='accessory' else 'gps'}-{year}.csv.gz"
    raw=download(RECORD+name+"?download=1",
                 max_bytes=5_000_000 if kind=="accessory" else 32_000_000)
    assert_source(hashlib.md5(raw).hexdigest()==PUBLISHED[year][kind],
                  "PUBLISHER_MD5_MISMATCH")
    return raw


def fit_fast(train,objective):
    """Exact same two-state encoding family as R12b, O(n log n) fit."""
    assert_source(objective in ("metric","task"),"UNKNOWN_OBJECTIVE")
    assert_source({r["label"] for r in train}=={0,1},
                  "TRAINING_NOT_BOTH_HUMAN_CLASSES")
    sorted_rows=sorted(train,key=lambda r:r["speed"])
    n=len(sorted_rows)
    n1=sum(r["label"] for r in sorted_rows)
    n0=n-n1
    assert_source(n0 and n1,"INVALID_GROUND_TRUTH_CLASS_COUNTS")
    total_speed=sum(r["speed"] for r in sorted_rows)
    total_squared=sum(r["speed"]**2 for r in sorted_rows)
    left_sum=0.;left_squared=0.;left_pos=0
    best=None
    # Cuts at the first distinct value, every midpoint, and just past max.
    cuts=[]
    i=0
    while i<n:
        x=sorted_rows[i]["speed"]
        cuts.append((i,x-1.0 if i==0 else
                     (sorted_rows[i-1]["speed"]+x)/2))
        while i<n and sorted_rows[i]["speed"]==x:
            left_sum+=sorted_rows[i]["speed"]
            left_squared+=sorted_rows[i]["speed"]**2
            left_pos+=sorted_rows[i]["label"]
            i+=1
    # Create prefix summaries in a single second pass so every candidate
    # gets the correct cut-specific n, count/sum/squared values.
    prefixes=[]
    j=0;s0=0.;s2=0.;p=0
    for cut,th in cuts:
        while j<cut:
            r=sorted_rows[j];s0+=r["speed"];s2+=r["speed"]**2;p+=r["label"];j+=1
        prefixes.append((cut,th,s0,s2,p))
    prefixes.append((n,sorted_rows[-1]["speed"]+1.,
                     total_speed,total_squared,n1))
    for k,th,s0,s2,p0 in prefixes:
        left_n=k;right_n=n-k
        right_pos=n1-p0
        left_neg=left_n-p0
        right_neg=right_n-right_pos
        # Empty group takes the training global majority. Stable tie -> 0.
        left_label=1 if (p0>left_neg if left_n else n1>n0) else 0
        right_label=1 if (right_pos>right_neg if right_n else n1>n0) else 0
        TP=(p0 if left_label else 0)+(right_pos if right_label else 0)
        TN=(left_neg if not left_label else 0)+(
            right_neg if not right_label else 0)
        BA=(TP/n1+TN/n0)/2
        SSE=(s2-s0*s0/left_n if left_n else 0)+(
            total_squared-s2-
            (total_speed-s0)**2/right_n if right_n else 0)
        MSE=max(0.,SSE/n)
        rank=(MSE,-BA,th) if objective=="metric" else (-BA,MSE,th)
        if best is None or rank<best[0]:
            best=(rank,{"threshold":th,
                        "codebook":{0:left_label,1:right_label}})
    assert_source(best is not None,"NO_LEARNED_ONE_BIT_CODE")
    return best[1]


def leave_bird_out(data):
    birds=sorted({r["bird"] for r in data})
    if len(data)<40 or len(birds)<3 or {r["label"] for r in data}!={0,1}:
        return {
          "status":"NOT_SCORABLE_NOT_ENOUGH_MATCHED_HUMAN_BIRDS_OR_CLASSES",
          "matched_rows":len(data),"matched_individuals":len(birds),
          "physical_Hoffman_theory_test":False
        }
    all_preds=[];complete_folds=0;excluded=[]
    for bird in birds:
        train=[r for r in data if r["bird"]!=bird]
        test=[r for r in data if r["bird"]==bird]
        if {r["label"] for r in train}!={0,1}:
            excluded.append("TRAIN_WITH_ONE_CLASS")
            continue
        g=fit_fast(train,"metric")
        t=fit_fast(train,"task")
        majority=int(sum(r["label"] for r in train)>len(train)/2)
        for x in test:
            all_preds.append({
              "truth":x["label"],
              "geometry":predict(g["codebook"],g["threshold"],x["speed"]),
              "task":predict(t["codebook"],t["threshold"],x["speed"]),
              "majority":majority})
        complete_folds+=1
    if complete_folds<3 or not all_preds:
        return {"status":"NOT_SCORABLE_INCOMPLETE_BIRD_FOLDS",
                "complete_folds":complete_folds,
                "excluded_folds":len(excluded),
                "matched_rows":len(data)}
    truth=[r["truth"] for r in all_preds]
    def metrics(name):
        pred=[r[name] for r in all_preds]
        return {
            "n":len(pred),
            "accuracy":sum(p==v for p,v in zip(pred,truth))/len(pred),
            "balanced_accuracy":balanced_accuracy(pred,truth),
            "confusion":{
              "TP":sum(p==v==1 for p,v in zip(pred,truth)),
              "TN":sum(p==v==0 for p,v in zip(pred,truth)),
              "FP":sum(p==1 and v==0 for p,v in zip(pred,truth)),
              "FN":sum(p==0 and v==1 for p,v in zip(pred,truth))}
        }
    return {
       "status":"REAL_HUMAN_BEHAVIOR_CROSS_BIRD_HOLDOUT_COMPLETE",
       "matched_records":len(data),
       "distinct_birds":len(birds),
       "evaluated_rows":len(all_preds),
       "complete_held_out_birds":complete_folds,
       "unscored_folds":len(excluded),
       "target":"Human expert label flight vs ground behavior (not fitness)",
       "geometry":"One bit of real GPS speed optimized for speed reconstruction using TRAIN birds only",
       "task":"One bit of the SAME speed optimized for classification balanced accuracy using TRAIN birds only",
       "models":{k:metrics(k) for k in ("geometry","task","majority")},
       "no_real_retina_or_choice_payoffs":True,
       "same_original_individuals_across_2012_2014_grouped_in_one_bird_fold":True,
       "machine_predicted_labels_used_as_ground_truth":False,
       "Hoffman_theory_proven":False
    }


def report(years):
    assert_source(years and all(y in YEAR_SET for y in years) and
                  len(set(years))==len(years),"INVALID_YEAR_SET")
    all_humans=[];all_aligned=[]
    by_year=[]
    for year in sorted(years):
        accessory=official_data(year,"accessory")
        humans,counters=human_events(accessory)
        gps=official_data(year,"gps")
        aligned,alignment=attach_prior_gps(humans,gps)
        all_humans+=humans
        all_aligned+=aligned
        by_year.append({
          "year":year,
          "source_doi":DOI,
          "accessory_sha256":sha(accessory),
          "gps_sha256":sha(gps),
          "publisher_md5_check_passed":True,
          "manual_annotation_summary":counters,
          "preceding_gps_match_summary":alignment,
          "raw_individual_identifiers_or_locations_exported":False})
    model=leave_bird_out(all_aligned)
    return {
       "schema":"janus.gull.lbbg_human_label_cross_bird_evaluation.v3",
       "published_doi":DOI,
       "published_release_date_utc":"2026-11-04",
       "years_evaluated":sorted(years),
       "all_source_md5_verified":True,
       "annotation_years":by_year,
       "total_expert_human_rows":sum(x["manual_annotation_summary"][
          "human_labels_total"] for x in by_year),
       "expert_bird_count_across_years":len(
           {r["bird"] for r in all_humans}),
       "total_preceding_gps_matches":len(all_aligned),
       "matched_bird_count":len({r["bird"] for r in all_aligned}),
       "leave_one_individual_out":model,
       "strict_late_GPS_exclusion":True,
       "all_GULLIVER_machine_labels_excluded":True,
       "raw_IDs_GPS_locations_and_nests_not_exported":True,
       "different_2024_eye_measurement_individuals_never_joined":True,
       "space_perception_vs_Hoffman_empirically_distinguished":False,
       "model_checkpoint_or_NAS_modified":False,
       "interpretation":"REAL HUMAN-ANNOTATED MOVEMENT benchmark, not a test of retinal visual models or consciousness ontology; no behavior rewards or experimental visual stimuli present."
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--years",default="2012,2013,2014")
    args=ap.parse_args()
    years=[int(y.strip()) for y in args.years.split(",") if y.strip()]
    assert_source(not args.out.exists(),"REFUSE_TO_OVERWRITE_RESEARCH_EVIDENCE")
    result=report(years)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "stage":"REAL_LBBG_HUMAN_CROSS_BIRD_VALIDATION",
        "humans":result["total_expert_human_rows"],
        "expert_birds":result["expert_bird_count_across_years"],
        "gps_matches":result["total_preceding_gps_matches"],
        "matched_birds":result["matched_bird_count"],
        "holdout_status":result["leave_one_individual_out"]["status"],
        "models":result["leave_one_individual_out"].get("models"),
        "measured_retina_or_Hoffman_ontology":False
    },sort_keys=True))


if __name__=="__main__":
    main()
