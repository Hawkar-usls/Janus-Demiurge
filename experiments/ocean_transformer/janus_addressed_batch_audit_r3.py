#!/usr/bin/env python3
"""JANUS R3 sharded 20-lane addressed-handshake CPU evidence aggregator.

Reads only the 60 GitHub Actions artifacts from the SAME run, refuses
missing/extra shards and inconsistent hashes. Every request is retained.
This is a classical forward-time RNG / sham-routing control, NOT evidence
of a physically available retrocausal information channel.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

import janus_addressed_handshake_cpu_r2 as r2

SHARDS = 20
ATTEMPTS_PER_SHARD = r2.N
PERMUTATIONS = 1999


def read_file(p):
    r2.require(p.is_file(), f"MISSING_SHARD_ARTIFACT:{p.name}")
    return json.loads(p.read_text(encoding="utf-8"))


def exact_tail(n,k):
    r2.require(type(n) is int and type(k) is int and 0<=k<=n<=
               SHARDS*ATTEMPTS_PER_SHARD, "BAD_AGGREGATE_BINOMIAL_N")
    return sum(math.comb(n,i) for i in range(k,n+1))/(1<<n)


def collect(root, run_id, shards=SHARDS):
    r2.require(root.is_dir() and type(run_id) is str and run_id.isdigit(),
               "INVALID_ARTIFACT_ROOT_OR_RUN_ID")
    r2.require(type(shards) is int and shards==SHARDS,
               "MATRIX_COUNT_CHANGED")
    paths={}
    for phase in ("early","future","comparison"):
        for slot in range(shards):
            dirname=f"janus-addressed-r3-{phase}-{run_id}-{slot}"
            folder=root/dirname
            r2.require(folder.is_dir(),f"MISSING_COMPLETE_SHARD:{dirname}")
            paths[(phase,slot)]=folder / {
                "early":"early.json",
                "future":"future.json",
                "comparison":"score.json"
            }[phase]
    # Do not accept an extra 'winning' shard or unexpected artifact.
    actual={p.name for p in root.iterdir() if p.is_dir() and
            p.name.startswith("janus-addressed-r3-")}
    expected={p.parent.name for p in paths.values()}
    r2.require(actual==expected, "MISSING_OR_EXTRA_ARTIFACT_DIRECTORY")
    shards_rows=[]
    trial_ids=[]
    per_slot=[]
    all_rows=[]
    for slot in range(shards):
        early=read_file(paths[("early",slot)])
        future=read_file(paths[("future",slot)])
        comparison=read_file(paths[("comparison",slot)])
        r2.verify(early,future)
        expected_trial=f"{run_id}{slot:02d}"
        r2.require(early["trial_id"]==expected_trial and
                   future["trial_id"]==expected_trial and
                   comparison.get("trial_id")==expected_trial,
                   "TRIAL_ID_NOT_UNIQUE_BY_SHARD")
        r2.require(comparison.get("schema")==r2.SCHEMA_SCORE and
                   comparison.get("all_64_trials_included") is True and
                   comparison.get("no_postselection") is True and
                   comparison.get("precommit_digest")==early["records_sha256"] and
                   comparison.get("future_digest")==future["records_sha256"] and
                   comparison.get("physical_retrocausal_signal_proven") is False,
                   "COMPARISON_INTEGRITY_OR_SAFETY_GATES")
        rows=[]
        for a,b in zip(early["records"],future["records"]):
            t=b["future_target_bit"]
            rows.append({
                "request_type":a["request_type"],
                "route_mode":b["route_mode"],
                "advantage":int(a["guess_addressed"]==t)-
                            int(a["guess_unaddressed"]==t)
            })
        delta,me=r2.interaction(rows)
        r2.require(abs(delta-comparison["addressing_interaction_difference_in_differences"])<1e-12,
                   "REPORTED_INTERACTION_CHANGED")
        shards_rows.append(rows)
        all_rows.extend(rows)
        trial_ids.append(expected_trial)
        per_slot.append({
            "slot":slot,
            "trial_id":expected_trial,
            "unfiltered_attempts":len(rows),
            "delta":delta,
            "early_records_sha256":early["records_sha256"],
            "late_records_sha256":future["records_sha256"],
            "artifact_score_permutation_p":comparison["routing_label_permutation_p"]
        })
    r2.require(len(all_rows)==SHARDS*ATTEMPTS_PER_SHARD,
               "INCOMPLETE_AGGREGATE_ATTEMPTS")
    return shards_rows, per_slot, all_rows


def global_permutation_p(shards_rows, observed, count=PERMUTATIONS,
                         seed=20261107):
    r2.require(type(count) is int and 199<=count<=9999,
               "INVALID_GLOBAL_PERMUTATION_BUDGET")
    rng=random.Random(seed)
    extreme=0
    for _ in range(count):
        shuffled=[]
        for rows in shards_rows:
            routing={}
            for rt in r2.LABELS:
                seq=[r["route_mode"] for r in rows if r["request_type"]==rt]
                rng.shuffle(seq)
                routing[rt]=iter(seq)
            shuffled.extend({**r,"route_mode":next(routing[r["request_type"]])}
                            for r in rows)
        delta,_=r2.interaction(shuffled)
        extreme+=delta>=observed-1e-12
    return (extreme+1)/(count+1)


def aggregate(root,run_id,permutations=PERMUTATIONS):
    groups,per_slot,all_rows=collect(root,run_id)
    delta,me=r2.interaction(all_rows)
    matched_addressed=[r for r in all_rows if
                       r["request_type"]=="matched_request" and
                       r["route_mode"]=="addressed"]
    assert len(matched_addressed)==320
    plus=sum(x["advantage"]==1 for x in matched_addressed)
    minus=sum(x["advantage"]==-1 for x in matched_addressed)
    paired_p=exact_tail(plus+minus,plus)
    perm_p=global_permutation_p(groups,delta,permutations)
    full_budget=permutations==PERMUTATIONS
    return {
        "schema":"janus.addressed_handshake.batch_r3.v1",
        "run_id":run_id,
        "status":"COMPLETE_RESEARCH_ONLY" if full_budget else "TEST_ONLY_REDUCED_BUDGET",
        "shards":SHARDS,
        "total_github_stage_jobs":60,
        "unfiltered_total_trials":len(all_rows),
        "attempts_per_shard":ATTEMPTS_PER_SHARD,
        "balanced_four_cell_counts":{
            f"{rt}|{mode}":320 for rt in r2.LABELS for mode in r2.MODES
        },
        "difference_in_differences_addressing_effect":delta,
        "cell_mean_advantage":{
            f"{rt}|{mode}":me[(rt,mode)]
            for rt in r2.LABELS for mode in r2.MODES
        },
        "matched_addressed_discordant_plus":plus,
        "matched_addressed_discordant_minus":minus,
        "paired_exact_p":paired_p,
        "shard_stratified_routing_permutation_p":perm_p,
        "two_tests_bonferroni_min_p":min(1.,2*min(paired_p,perm_p)),
        "planned_permutations":permutations,
        "fixed_seed_for_test_reproducibility":20261107,
        "per_shard":per_slot,
        "all_20_shards_required":True,
        "no_missing_or_early_filtered_attempts":True,
        "late_rng_never_downloads_early_artifacts":True,
        "120_sec_gap_checked_by_workflow_sequence_only":True,
        "independently_attested_physical_clock":False,
        "independently_certified_future_entropy":False,
        "physical_message_into_past":False,
        "physical_retrocausal_principle_proven":False,
        "production_promotion":False,
        "claim_limit":"20x64 records are ordinary forward-time classical RNG experiments. A future route label is not a physical retroactive intervention. A small p-value would trigger audit, not proof."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--artifacts",type=Path,required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    if x.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    out=aggregate(x.artifacts,x.run_id)
    x.out.parent.mkdir(parents=True,exist_ok=True)
    x.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:out[k] for k in (
        "shards","unfiltered_total_trials",
        "difference_in_differences_addressing_effect",
        "paired_exact_p","shard_stratified_routing_permutation_p",
        "two_tests_bonferroni_min_p","physical_retrocausal_principle_proven"
    )},indent=2))


if __name__=="__main__":
    main()
