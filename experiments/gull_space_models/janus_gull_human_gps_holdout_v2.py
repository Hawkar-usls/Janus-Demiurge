#!/usr/bin/env python3
"""JANUS Gull R12b: REAL human-scored 2016 behavior vs same-bird preceding GPS.

Scientific firewall: This is a tiny independently labelled sensor/behavior
BENCHMARK, NOT the earlier optical-field study and NOT a test of Hoffman's
ontological claim. 2016 HG_TEXEL's human activity categories are expert
annotations, not a gull's choices, survival utility, or eye measurements.
GULLIVER machine-generated labels are fully EXCLUDED from ground truth.

Compare two exact 1-bit encoders of THE SAME ground-speed GPS feature:
(A) 'geometry': threshold chosen UNSUPERVISED on training-speed MSE, then
    best training-only label decoder for that code;
(B) 'task': threshold and decoder learned to optimize training behavior
    balanced accuracy, representing an adaptive TASK code, not true fitness.
Apply leave-one-bird-out validation, no trial from test bird touches fitting.
Only PRECEDING GPS records within 120 seconds accepted. Never publish exact
animal IDs, individual geo coordinates or nest locations. Resource bounded.

Source https://zenodo.org/records/23923176 (2026-11-04), original publisher
MD5 values pinned below. Python standard library only.
"""
from __future__ import annotations
import argparse
import bisect
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from fractions import Fraction as F
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

from janus_gull_real_data_audit_v2 import download, assert_source, sha, ZENODO

ACCESSORY="HG_TEXEL-accessory-measurements-2016.csv.gz"
GPS="HG_TEXEL-gps-2016.csv.gz"
ORIGINAL_MD5={
 ACCESSORY:"fa96822fc65b746b626ce9ff9a382272",
 GPS:"cf0af35d196b35d73461e0ba55778583",
}
HUMAN_LABEL="human"
FLIGHT={"flap","soar","exflap"}
GROUND={"stationary","walk","peck","float","boat"}
AMBIGUOUS={"mixed"}
MAX_LAG_SECONDS=120
MAX_GPS_ROWS=6000000
MIN_MATCHED=20
MIN_BIRDS=3


def source_bytes(name,limit):
    assert_source(name in ORIGINAL_MD5,"UNRECOGNIZED_PUBLISHED_GPS_SOURCE")
    raw=download(ZENODO+name+"?download=1",limit)
    assert_source(hashlib.md5(raw).hexdigest()==ORIGINAL_MD5[name],
                  "PUBLISHER_MD5_CHECK_FAILED")
    return raw


def gz_rows(original):
    with gzip.GzipFile(fileobj=io.BytesIO(original)) as infile:
        with io.TextIOWrapper(infile,encoding="utf-8-sig",
                              errors="strict",newline="") as f:
            yield from csv.DictReader(f)


def epoch(value):
    if not isinstance(value,str) or not value.strip():
        return None
    try:
        x=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
        if x.tzinfo is None:
            x=x.replace(tzinfo=timezone.utc)
        return x.timestamp()
    except (TypeError,ValueError,OverflowError):
        return None


def flight_binary(value):
    x=(value or "").strip().lower()
    if x in FLIGHT:return 1
    if x in GROUND:return 0
    return None


def human_events(accessory):
    observed=[]
    all_human=0; counts=Counter(); all_machine=0
    for row in gz_rows(accessory):
        source=(row.get("study-specific-measurement") or "").strip().lower()
        if source!=HUMAN_LABEL:
            if source=="machine":all_machine+=1
            continue
        all_human+=1
        label=(row.get("behavioural-classification") or "").strip().lower()
        counts[label]+=1
        bird=(row.get("individual-local-identifier") or "").strip()
        t=epoch(row.get("timestamp"))
        if bird and t is not None and flight_binary(label) is not None:
            observed.append({"bird":bird,"time":t,"label":flight_binary(label)})
    return observed,{"human_labels_total":all_human,
                     "machine_labels_excluded":all_machine,
                     "human_label_counts":dict(sorted(counts.items())),
                     "human_scored_binary_labels":len(observed),
                     "human_birds_with_scored_labels":len(
                         {x["bird"] for x in observed})}


def attach_prior_gps(humans,gps):
    by_bird=defaultdict(list)
    for idx,h in enumerate(humans):
        by_bird[h["bird"]].append((h["time"],idx))
    times={}
    indices={}
    for bird,rows in by_bird.items():
        rows.sort()
        times[bird]=[x[0] for x in rows]
        indices[bird]=[x[1] for x in rows]
    matches={} # idx -> (t_gps, speed)
    scanned=0; eligible=0; rejected_outliers=0
    for gps_row in gz_rows(gps):
        scanned+=1
        if scanned>MAX_GPS_ROWS:
            raise ValueError("GPS_TRIAL_LIMIT_EXCEEDED_NO_UNCHECKED_RESULTS")
        bird=(gps_row.get("individual-local-identifier") or "").strip()
        if bird not in times:
            continue
        t=epoch(gps_row.get("timestamp"))
        if t is None:
            continue
        if (gps_row.get("import-marked-outlier") or "").strip().lower() in (
             "true","t","1","yes"):
            rejected_outliers+=1
            continue
        try:
            speed=float(gps_row.get("ground-speed",""))
        except (ValueError,TypeError):
            continue
        if not math.isfinite(speed) or speed<0:
            continue
        eligible+=1
        ctimes=times[bird]
        j=bisect.bisect_left(ctimes,t)
        while j<len(ctimes) and ctimes[j]-t<=MAX_LAG_SECONDS:
            idx=indices[bird][j]
            previous=matches.get(idx)
            if t<=ctimes[j] and (
                previous is None or t>previous[0]):
                matches[idx]=(t,speed)
            j+=1
    matched=[]
    for i,x in enumerate(humans):
        if i in matches:
            t,speed=matches[i]
            assert_source(t<=x["time"] and
                          x["time"]-t<=MAX_LAG_SECONDS,
                          "FUTURE_GPS_LEAK_OR_TIME_MISMATCH")
            matched.append({"bird":x["bird"],"speed":speed,"label":x["label"],
                            "lag":x["time"]-t})
    return matched,{
      "original_gps_rows_scanned":scanned,
      "candidate_gps_rows_on_human_labeled_birds":eligible,
      "gps_outliers_refused":rejected_outliers,
      "human_labels_with_past_gps_match":len(matched),
      "human_labels_without_past_gps_match":len(humans)-len(matched),
      "matched_distinct_birds":len({x["bird"] for x in matched}),
      "max_allowed_past_gps_lag_seconds":MAX_LAG_SECONDS,
      "max_observed_match_lag_seconds":max(
         (x["lag"] for x in matched),default=None),
      "later_gps_after_human_annotation_ever_used":False
    }


def thresholds(data):
    unique=sorted({x["speed"] for x in data})
    assert_source(unique,"EMPTY_TRAINING_GPS")
    edges=[unique[0]-1.]
    edges.extend((a+b)/2 for a,b in zip(unique,unique[1:]))
    edges.append(unique[-1]+1.)
    return edges


def predict(codebook,th,speed):
    return codebook[1 if speed>=th else 0]


def balanced_accuracy(predictions,labels):
    true_labels=set(labels)
    if true_labels!={0,1}:
        # do not give deceptively high balanced accuracy for one-class fold
        return None
    return sum(sum(int(p==y) for p,v in zip(predictions,labels) if v==y)/
               sum(int(v==y) for v in labels) for y in (0,1))/2


def fit(training,objective):
    assert_source(objective in ("metric","task"),"UNKNOWN_ADAPTIVE_OBJECTIVE")
    assert_source(set(x["label"] for x in training)=={0,1},
                  "TRAINING_MISSING_HUMAN_CLASSES")
    # Include both possible 1-bit decoders; training labels only.
    best=None
    for th in thresholds(training):
        groups={0:[x for x in training if x["speed"]<th],
                1:[x for x in training if x["speed"]>=th]}
        codebook={}
        for c,group in groups.items():
            if not group:
                codebook[c]=max(
                    (0,1),key=lambda k:(
                       sum(x["label"]==k for x in training),-k))
            else:
                codebook[c]=max(
                    (0,1),key=lambda k:(
                       sum(x["label"]==k for x in group),-k))
        y=[x["label"] for x in training]
        preds=[predict(codebook,th,x["speed"]) for x in training]
        acc=balanced_accuracy(preds,y)
        mse=0.
        for members in groups.values():
            if members:
                avg=sum(x["speed"] for x in members)/len(members)
                mse+=sum((x["speed"]-avg)**2 for x in members)/len(training)
        # Fixed tie rule by threshold; no held-out bird participates.
        rank=(mse,-acc,th) if objective=="metric" else (-acc,mse,th)
        if best is None or rank<best[0]:
            best=(rank,{"threshold":th,"codebook":codebook})
    return best[1]


def held_out_bird_validation(matched):
    birds=sorted({x["bird"] for x in matched})
    if len(matched)<MIN_MATCHED or len(birds)<MIN_BIRDS or (
            {x["label"] for x in matched}!={0,1}):
        return {"status":"NOT_SCORABLE_INSUFFICIENT_HUMAN_GPS_MATCHES",
                "matched_human_labels":len(matched),
                "matched_birds":len(birds),
                "reason":"Require >=20 matched human labels over >=3 birds, both flight/nonflight classes."}
    evaluated=[];folds=0; skipped_folds=0
    for bird in birds:
        train=[x for x in matched if x["bird"]!=bird]
        test=[x for x in matched if x["bird"]==bird]
        if {x["label"] for x in train}!={0,1}:
            skipped_folds+=1
            continue
        geom=fit(train,"metric")
        task=fit(train,"task")
        base=max((0,1),key=lambda k:(
            sum(x["label"]==k for x in train),-k))
        for x in test:
            evaluated.append({
               "label":x["label"],
               "geometry":predict(geom["codebook"],geom["threshold"],x["speed"]),
               "task":predict(task["codebook"],task["threshold"],x["speed"]),
               "majority":base})
        folds+=1
    if not evaluated:
        return {"status":"NOT_SCORABLE_TRAIN_SPLITS_WITHOUT_BOTH_CLASSES",
                "matched_human_labels":len(matched),
                "matched_birds":len(birds)}
    y=[x["label"] for x in evaluated]
    def one(model):
        pred=[x[model] for x in evaluated]
        return {
         "accuracy":sum(p==l for p,l in zip(pred,y))/len(y),
         "balanced_accuracy":balanced_accuracy(pred,y),
         "confusion":{"TP":sum(p==l==1 for p,l in zip(pred,y)),
                      "TN":sum(p==l==0 for p,l in zip(pred,y)),
                      "FP":sum(p==1 and l==0 for p,l in zip(pred,y)),
                      "FN":sum(p==0 and l==1 for p,l in zip(pred,y))}}
    return {
      "status":"HUMAN_ANNOTATION_LOBO_BENCHMARK_COMPLETE",
      "held_out_unit":"Entire bird, never individual row split",
      "total_labeled_human_rows_in_original_subset":len(matched),
      "evaluated_rows":len(evaluated),
      "distinct_matched_birds":len(birds),
      "folds_complete":folds,"folds_not_scored":skipped_folds,
      "target":"expert labeled flight vs ground activity",
      "source_of_class_labels":"study-specific-measurement=human ONLY",
      "sensor":"one real GPS ground-speed scalar, both models have exactly 1-bit code",
      "metric_encoder":"Train-only threshold minimizes GPS-speed squared reconstruction error; label decoding fit from train.",
      "task_encoder":"Train-only threshold maximizes behavior balanced accuracy; label decoding fit from train.",
      "models":{model:one(model) for model in ("geometry","task","majority")},
      "none_of_this_is_measured_gull_fitness_or_eye_to_brain_processing":True,
      "no_ontological_conclusion_from_behavioral_proxy":True
    }


def report():
    original_accessory=source_bytes(ACCESSORY,12_000_000)
    humans,annotations=human_events(original_accessory)
    original_gps=source_bytes(GPS,55_000_000)
    matched,alignment=attach_prior_gps(humans,original_gps)
    result=held_out_bird_validation(matched)
    return {
      "schema":"janus.gull.real_human_behavior_holdout.v2",
      "published_dataset_doi":"10.5281/zenodo.23923176",
      "published_source_release_date":"2026-11-04",
      "human_annotation_sha256_source":sha(original_accessory),
      "gps_sha256_source":sha(original_gps),
      "publisher_md5_checks_verified_both":True,
      "human_annotation_counts":annotations,
      "earlier_gps_alignment":alignment,
      "real_holdout_result":result,
      "all_machine_annotations_excluded_from_validation":True,
      "exact_animal_ids_or_nest_gps_coordinates_published":False,
      "original_raw_52MB_not_archived_in_github":True,
      "different_2024_eye-field_individuals_never_joined":True,
      "limits":"Per-bird human behavioral annotation and GPS speed only; no experimental sensory stimulus, no observed decision payoffs, no actual retinal map or Hoffman's ontological test.",
      "JANUS_transformer_or_production_modified":False
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    assert_source(not args.out.exists(),"REFUSE_HUMAN_HOLDOUT_OVERWRITE")
    ans=report()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(ans,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
       "stage":"REPRODUCIBLE_REAL_HUMAN_BIRD_HOLDOUT",
       "manual_labels":ans["human_annotation_counts"]["human_labels_total"],
       "human_usable":ans["human_annotation_counts"]["human_scored_binary_labels"],
       "matched_before_human_time":ans["earlier_gps_alignment"]["human_labels_with_past_gps_match"],
       "matched_birds":ans["earlier_gps_alignment"]["matched_distinct_birds"],
       "holdout_status":ans["real_holdout_result"]["status"],
       "models":ans["real_holdout_result"].get("models"),
       "real_vision_vs_Hoffman_causal_test":False
    },sort_keys=True))


if __name__=="__main__":
    main()
