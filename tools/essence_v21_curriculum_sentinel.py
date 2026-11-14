#!/usr/bin/env python3
"""ESSENCE v2.1: prospective, fail-closed dated-cohort fitness auditor.

Runs *before* gradient jobs. This is data suitability only; it never trains,
selects a model, calls external services, or grants scientific/production PASS.
A separate job sees the heldout labels; downstream gradient workers receive
only a YES/NO and a manifest binding, never that heldout packet.
"""
from __future__ import annotations
import argparse
from collections import Counter
import datetime as dt
import json
import math
from pathlib import Path
from tools import essence_v19_gradirnya as e

SCHEMA="janus.essence.curriculum_sentinel/2.1"
MIN_CLASSES=3
MIN_SUPPORT=3
MAX_DOMINANCE=.85
MIN_ENTROPY_BITS=.65

def profile(rows):
    counts=Counter(x["label"] for x in rows)
    size=len(rows)
    represented=sum(n>=MIN_SUPPORT for n in counts.values())
    dominance=max(counts.values())/size
    entropy=-sum((n/size)*math.log2(n/size) for n in counts.values())
    return {"documents":size,"represented_supported_classes":represented,
            "dominance":round(dominance,6),
            "entropy_bits":round(entropy,6),
            "eligible":represented>=MIN_CLASSES and
                       dominance<=MAX_DOMINANCE and
                       entropy>=MIN_ENTROPY_BITS}

def assess(manifest,train,validation,holdout,*,past_parent=None):
    source=manifest.get("source_commit") if isinstance(manifest,dict) else None
    e.validate_manifest(manifest,source)
    packets={"train":train,"validation":validation,"holdout":holdout}
    samples={}
    for role,packet in packets.items():
        rows=e.check_packet(packet,role,source,manifest["dataset_sha256"])
        if (packet["packet_sha256"]!=manifest["split_sha256"][role]
            or len(rows)!=manifest["split_sizes"][role]):
            raise ValueError("PROSPECTIVE_PACKET_NOT_MANIFEST_BOUND")
        samples[role]=rows
    if [sum(x["label"]==i for x in samples["train"]) for i in range(len(e.r.LABELS))]!=manifest["train_label_counts"]:
        raise ValueError("TRAIN_CLASS_COUNTS_CHANGED")
    dates=[]
    identities=[]
    for kind in ("train","validation","holdout"):
        rows=samples[kind]
        start=min(x["date"] for x in rows)
        end=max(x["date"] for x in rows)
        if manifest["split_dates"][kind]!=[start,end]:
            raise ValueError("CHRONOLOGY_MANIFEST_DISAGREEMENT")
        if dt.date.fromisoformat(start)>dt.date.fromisoformat(end):
            raise ValueError("REVERSED_COHORT_DATE")
        dates.append([start,end])
        identities.append({x["identity"] for x in rows})
    if not (dates[0][1]<dates[1][0] and dates[1][1]<dates[2][0]):
        raise ValueError("NON_CHRONOLOGICAL_SPLITS")
    if len(set.union(*identities))!=sum(len(v) for v in identities):
        raise ValueError("DUPLICATE_DOCUMENT_ACROSS_COHORTS")

    parent_status="NO_PREVIOUS_RESEARCH_PARENT"
    if past_parent is not None:
        from tools import essence_v20_ancestry as v20
        v20.valid_for_new_history(past_parent,manifest)
        parent_status="PARENT_FUTURE_ONLY_ACCEPTED"
    val=profile(samples["validation"])
    test=profile(samples["holdout"])
    failed=[]
    if not val["eligible"]:failed.append("HOLD_VALIDATION_LOW_INFORMATION")
    if not test["eligible"]:failed.append("HOLD_HOLDOUT_LOW_INFORMATION")
    if not any(x["date"]>dates[1][1] for x in samples["holdout"]):
        raise ValueError("DATE_SPLIT_REPLAY")
    eligible=not failed
    report={
        "schema":SCHEMA,
        "status":"RESEARCH_COHORT_SUITABLE_FOR_TRIAL" if eligible
                 else "HOLD_PRETRAIN_COHORT_INFORMATION_FAILURE",
        "eligible_for_research_training":eligible,
        "rejection_codes":failed,
        "manifest_sha256":manifest["receipt_sha256"],
        "train_packet_sha256":train["packet_sha256"],
        "validation_packet_sha256":validation["packet_sha256"],
        "holdout_packet_sha256":holdout["packet_sha256"],
        "source_commit":source,
        "source_dataset_sha256":manifest["dataset_sha256"],
        "parent":parent_status,
        "validation_documents":val["documents"],
        "heldout_documents":test["documents"],
        "min_classes_with_at_least_three_documents":MIN_CLASSES,
        "max_class_fraction":MAX_DOMINANCE,
        "min_class_entropy_bits":MIN_ENTROPY_BITS,
        # Do NOT expose labels, class counts, logits or per-example results to
        # training workers; even a benign summary could enable test tuning.
        "training_saw_holdout":False,
        "historical_public_data_not_external_blind":True,
        "scientific_model_improvement_proven":False,
        "target_hardware_proven":False,
        "live_production_rollback_proven":False,
        "automatic_model_promotion":False,
        "production_authority":False,
    }
    report["receipt_sha256"]=e.seal(report)
    return report

def cli():
    p=argparse.ArgumentParser()
    for key in ("manifest","train","validation","holdout","out"):
        p.add_argument("--"+key,required=True)
    a=p.parse_args()
    result=assess(e.read_json(a.manifest),e.read_json(a.train),
                  e.read_json(a.validation),e.read_json(a.holdout))
    e.atomic_json(a.out,result)
    print(json.dumps({"status":result["status"],
                      "eligible":result["eligible_for_research_training"],
                      "rejection_codes":result["rejection_codes"],
                      "production_authority":False},sort_keys=True))

if __name__=="__main__":cli()
