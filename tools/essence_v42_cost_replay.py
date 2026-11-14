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
from tools import essence_v42_physarum_full_cost as costmatch

SCHEMA="janus.essence.physarum_full_cost_replay/4.2"
EXPECTED_WEIGHTS={
    "control":"a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b",
    "physarum":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
}
EXPECTED_BUDGET14_SHA = "a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174"
EXPECTED_BUDGET14_MANIFEST = "49158892f8dc1674897465d84e45ecf02f19d96d79b72ae3aceb167599c61f5a"
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
            # Fully budget-matched fixed 14-step baseline from sealed G3.
            # Crucially this is a separate 14-step continuous trainer;
            # original Physarum's per-call 8-step cap remains untouched.
            freeze, g3_parent, _ = phys.load_g3(
                g3_dir,freeze_path,torch)
            train,_=previous.train_bytes(root,freeze)
            budget=costmatch.clone(torch,g3_parent)
            budget_start_cpu=time.process_time_ns()
            budget_start_wall=time.perf_counter_ns()
            rejects=costmatch.train_fixed_fourteen(
                torch,budget,train,seed=costmatch.BASELINE_SEED)
            budget_cpu=(time.process_time_ns()-budget_start_cpu)/1e9
            budget_wall=(time.perf_counter_ns()-budget_start_wall)/1e9
            budget_raw,_=previous.weight_bytes(torch,budget)
            budget_hash=hashlib.sha256(budget_raw).hexdigest()
            require(budget_hash==EXPECTED_BUDGET14_SHA,
                    "COSTMATCHED_14_WEIGHT_HASH_MISMATCH")
            require(rejects<14, "COSTMATCHED_14_NO_VALID_UPDATE")
            # The original v4.2 costmatched experiment trained its 14-step
            # control BEFORE the Physarum probes; preserve this order in replay.
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
            additional=full_cpu-cpu_train-timed_search["cpu_seconds"]-budget_cpu
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
                "budget14":{"train_steps":14,
                            "training_cpu_seconds":budget_cpu,
                            "training_wall_seconds":budget_wall,
                            "weights_sha256":budget_hash,
                            "manifest_sha256":EXPECTED_BUDGET14_MANIFEST},
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
        "costmatched_14_weights_sha256":EXPECTED_BUDGET14_SHA,
        "costmatched_14_manifest_sha256":EXPECTED_BUDGET14_MANIFEST,
        "repetitions":repetitions,
        "mean_full_trial_cpu_seconds":mean("entire_trial_cpu_seconds"),
        "mean_full_trial_wall_seconds":mean("entire_trial_wall_seconds"),
        "measurements":reports,
        "total_each_replay_training_steps":36,
        "original_v40_physarum_and_control8_steps":22,
        "probe_train_steps":6,
        "control_train_steps":8,
        "costmatched_fixed_train_steps":14,
        "physarum_candidate_train_steps":8,
        "hidden_exam_inference_cpu_seconds":"MUST_MEASURE_AT_EXTERNAL_CUSTODIAN",
        "costmatched_14_must_be_checked_against_physarum":True,
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
