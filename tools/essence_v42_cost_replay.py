#!/usr/bin/env python3
"""ESSENCE v4.2: source-faithful cost REPLAY with sealed G4 weight equality.

Runs the original Physarum+CODEX v4.0 development trial again on the same
frozen G3 weights and frozen train/validation corpus and observes actual
process CPU/wall-clock (3 two-step probes + search + two eight-step siblings).
For independent evaluation, an outside custodian must repeat this replay on
its target hardware, then sign the measured ledger. This self-run artifact
NEVER suffices for scientific admission; inference cost is independently
measured later by clean-room examiner on held-out examples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import shutil
import time

from tools import essence_v40_physarum_bridge as phys
from tools import essence_v38_inheritance as previous

SCHEMA="janus.essence.physarum_full_cost_replay/4.2"
EXPECTED_WEIGHTS={
    "control":"a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b",
    "physarum":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
}
EXPECTED_MANIFESTS={
    "control":"563bcf05a97c67f5723c4f5414bf7621197105eae654a8133a439c91fe4575f0",
    "physarum":"a8397385b2703d5cca7b15b9b12626960d8105e976f10b628451fe330dbcf003",
}
SEGMENTS=("probe_1","probe_2","probe_3","control_training",
          "physarum_training")


def require(ok,code):
    if not ok:
        raise ValueError(code)


def bench(root,g3_dir,freeze_path,out_dir,repetitions=1):
    require(type(repetitions) is int and 1<=repetitions<=3,
            "UNBOUNDED_COST_REPLAY")
    out=Path(out_dir)
    require(not out.exists() and not out.is_symlink(),
            "COST_REPLAY_OUTPUT_ALREADY_EXISTS")
    import torch
    torch.set_num_threads(1)
    historical_train=phys.train_steps
    historical_choose=phys.choose_physarum
    reports=[]
    try:
        for repeat in range(repetitions):
            seen=[]
            timed_search={}
            def timed_train(*args,**kwargs):
                index=len(seen)
                require(index<5,"EXTRA_HIDDEN_TRAINING_STEPS")
                start_cpu=time.process_time_ns()
                start_wall=time.perf_counter_ns()
                rejected=historical_train(*args,**kwargs)
                seen.append({
                    "segment":SEGMENTS[index],
                    "steps":kwargs.get("steps"),
                    "cpu_seconds":(time.process_time_ns()-start_cpu)/1e9,
                    "wall_seconds":(time.perf_counter_ns()-start_wall)/1e9,
                    "rejected_gradients":rejected,
                })
                return rejected
            def timed_choose(values):
                start_cpu=time.process_time_ns()
                start_wall=time.perf_counter_ns()
                result=historical_choose(values)
                timed_search.update({
                    "cpu_seconds":(time.process_time_ns()-start_cpu)/1e9,
                    "wall_seconds":(time.perf_counter_ns()-start_wall)/1e9,
                })
                return result
            phys.train_steps=timed_train
            phys.choose_physarum=timed_choose
            start_cpu=time.process_time_ns()
            start_wall=time.perf_counter_ns()
            target=out/("replay_"+str(repeat))
            receipt=phys.run(root,g3_dir,freeze_path,target)
            full_cpu=(time.process_time_ns()-start_cpu)/1e9
            full_wall=(time.perf_counter_ns()-start_wall)/1e9
            for label in EXPECTED_WEIGHTS:
                require(receipt["sibling_results"][label]["weights_sha256"]==
                        EXPECTED_WEIGHTS[label], "COST_REPLAY_WEIGHT_SHA_MISMATCH")
                require(receipt["sibling_results"][label]["checkpoint_manifest_sha256"]==
                        EXPECTED_MANIFESTS[label], "COST_REPLAY_MANIFEST_DRIFT")
            require([v["steps"] for v in seen]==[2,2,2,8,8] and
                    len(seen)==5 and len(timed_search)==2,
                    "INCOMPLETE_ACTUAL_FULL_SEARCH_COST")
            require(receipt["measured_train_steps_including_probes"]==22,
                    "REPORTED_SEARCH_COST_OMITS_PROBES")
            cpu_train=sum(x["cpu_seconds"] for x in seen)
            additional=full_cpu-cpu_train-timed_search["cpu_seconds"]
            require(additional>=-0.1 and all(
                math.isfinite(v) and v>=0 for v in (
                    full_cpu,full_wall,cpu_train,
                    timed_search["cpu_seconds"])),
                "NONFINITE_OR_INCONSISTENT_PROCESS_CPU")
            reports.append({
                "repeat":repeat+1,
                "source_receipt_sha256":receipt["receipt_sha256"],
                "segments":seen,
                "physarum_network_search":timed_search,
                "entire_trial_cpu_seconds":full_cpu,
                "entire_trial_wall_seconds":full_wall,
                "non_training_overhead_cpu_seconds":max(0.0,additional),
                "peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "actual_weight_shas_replayed":EXPECTED_WEIGHTS,
                "external_hidden_data_accessed":False,
            })
            # Keep receipts but avoid accidental duplication of large models.
            for label in EXPECTED_WEIGHTS:
                p=target/label/"weights.f32"
                if p.is_file():
                    p.unlink()
    finally:
        phys.train_steps=historical_train
        phys.choose_physarum=historical_choose
    def mean(key):
        return sum(v[key] for v in reports)/len(reports)
    summary={
        "schema":SCHEMA,
        "status":"SELF_VERIFIED_SAME_WEIGHTS_CPU_COST_REPLAY",
        "source_original_code_sha256":phys.PHYSARUM_ORIGIN["sha256"],
        "g3_source_weight_sha256":phys.G3_WEIGHTS_SHA256,
        "g4_exact_weight_sha256":EXPECTED_WEIGHTS,
        "g4_exact_manifest_sha256":EXPECTED_MANIFESTS,
        "repetitions":repetitions,
        "mean_full_trial_cpu_seconds":mean("entire_trial_cpu_seconds"),
        "mean_full_trial_wall_seconds":mean("entire_trial_wall_seconds"),
        "measurements":reports,
        "total_each_replay_training_steps":22,
        "probe_train_steps":6,
        "control_train_steps":8,
        "physarum_candidate_train_steps":8,
        "hidden_exam_inference_cpu_seconds":"MUST_MEASURE_AT_EXTERNAL_CUSTODIAN",
        "external_custodian_identity_verified":False,
        "external_hidden_source_exam_complete":False,
        "production_authority":False
    }
    summary["receipt_sha256"]=previous.sha(summary)
    previous.immutable_json(out/"full-cost-replay.json",summary)
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    p.add_argument("--g3-dir",required=True)
    p.add_argument("--freeze",required=True)
    p.add_argument("--out-dir",required=True)
    p.add_argument("--repetitions",type=int,default=1)
    a=p.parse_args()
    result=bench(a.root,a.g3_dir,a.freeze,
                 a.out_dir,repetitions=a.repetitions)
    print(json.dumps({
        "status":result["status"],
        "full_trial_cpu_seconds":result["mean_full_trial_cpu_seconds"],
        "full_trial_wall_seconds":result["mean_full_trial_wall_seconds"],
        "included_probe_steps":result["probe_train_steps"],
        "external_validation_proven":False,
        "receipt_sha256":result["receipt_sha256"],
    },sort_keys=True))


if __name__=="__main__":
    main()
