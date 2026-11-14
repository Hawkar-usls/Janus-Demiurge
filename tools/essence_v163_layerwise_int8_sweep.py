#!/usr/bin/env python3
"""ESSENCE v1.6.3 — bounded layerwise native CPU INT8 fidelity search.

A *development-only* 15-mask search on a pinned, original learned checkpoint.
No training, deployments, production writes or automatic model admission.
Each mask runs in an independent process against immutable public probes.
Reuse of public benchmark after seeing v1.6.1 results is NOT blind validation.
"""
from __future__ import annotations
import argparse
import copy
import gc
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import torch
from torch import nn
from tools import essence_v16_real_checkpoint_bench as v

SCHEMA="janus.essence.native_cpu_layer_search/1.6.3"
SUMMARY="janus.essence.native_cpu_layer_search_summary/1.6.3"
LAYERS=("blocks.layers.0.linear1","blocks.layers.0.linear2",
        "blocks.layers.1.linear1","blocks.layers.1.linear2")
N=15
TOP1=.97
LOSS=.005
MIN_PACKED_SAVING=.04
MAX_FORWARD_REGRESSION=.15

def choose(mask):
    if type(mask) is not int or not 1<=mask<=15:
        raise ValueError("UNTRUSTED_MASK")
    return tuple(name for j,name in enumerate(LAYERS) if mask&(1<<j))

def quantize_ffn_subset(model,mask):
    from torch.ao.quantization import quantize_dynamic
    torch.backends.mha.set_fastpath_enabled(False)
    result=copy.deepcopy(model)
    chosen=choose(mask)
    for name in chosen:
        parent=result
        *parts,attr=name.split(".")
        for p in parts:
            parent=parent[int(p)] if p.isdigit() else getattr(parent,p)
        old=getattr(parent,attr)
        if not isinstance(old,nn.Linear):raise ValueError("QUANT_NON_LINEAR_DENIED")
        # Wrapping is essential: quantize_dynamic on the *root* Linear alone
        # does not replace the root, whereas children of Sequential do.
        new=quantize_dynamic(nn.Sequential(copy.deepcopy(old)),
                             {nn.Linear},dtype=torch.qint8,inplace=False)[0]
        if not isinstance(new,torch.ao.nn.quantized.dynamic.Linear):
            raise ValueError("REAL_QUANTIZED_OPERATOR_NOT_INSTALLED")
        setattr(parent,attr,new)
    if not isinstance(result.lm_head,nn.Linear):
        raise ValueError("OUTPUT_HEAD_QUANTIZATION_DENIED")
    if result.lm_head.weight.data_ptr()!=result.token.weight.data_ptr():
        raise ValueError("TIED_OUTPUT_WEIGHT_ALIAS_LOST")
    count=sum(isinstance(mod,torch.ao.nn.quantized.dynamic.Linear)
              for mod in result.modules())
    if count!=len(chosen):raise ValueError("UNEXPECTED_INT8_LAYER_COUNT")
    return result,chosen

def serialized_state_bytes(model):
    sink=io.BytesIO()
    torch.save(model.state_dict(),sink)
    return sink.tell()

def read_reference(dest):
    b=v.json_read(dest/"baseline.json")
    if (b.get("mode")!="baseline"
         or b.get("source_checkpoint_sha256")!=v.CHECKPOINT_SHA256
         or b.get("receipt_sha256")!=v.seal({k:x for k,x in b.items() if k!="receipt_sha256"})
         or b.get("model_git_blob_sha1")!=v.MODEL_BLOB
         or b.get("frozen_probes_git_blob_sha1")!=v.FROZEN_BLOB):
        raise ValueError("BASELINE_IDENTITY_UNTRUSTED")
    reference=v.load_logits(dest/"baseline_logits.pt",b["baseline_logits_sha256"])
    return b,reference

def cpu_rss_peak():
    try:
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    except Exception:
        return None

def case(mask,dest):
    frozen,_,_=v.require_source()
    torch.set_num_threads(1)
    torch.manual_seed(61616)
    baseline,reference=read_reference(dest)
    old_checkpoint=v.file_sha(v.CHECKPOINT)
    model,_=v.load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
    model.eval()
    original_model_bytes=serialized_state_bytes(model)
    qmodel,layers=quantize_ffn_subset(model,mask)
    qmodel.eval()
    actual_model_bytes=serialized_state_bytes(qmodel)
    del model
    gc.collect()
    rss_after_conversion=v.cpu_rss()
    datasets=v.build_inputs(frozen)
    quality,_=v.evaluate(qmodel,datasets,reference)
    speed=v.time_forward(qmodel,datasets,frozen)
    rss_after_forward=v.cpu_rss()
    if v.file_sha(v.CHECKPOINT)!=old_checkpoint or old_checkpoint!=v.CHECKPOINT_SHA256:
        raise ValueError("ORIGINAL_MODEL_WEIGHTS_CHANGED")
    agree=True
    changes={}
    for cohort in ("historical_anchor","public_fixed_probes"):
        ref=baseline["quality"][cohort]["mean_cross_entropy"]
        now=quality[cohort]["mean_cross_entropy"]
        top=quality[cohort]["top1_agreement"]
        delta=now/ref-1
        changes[cohort]={"cross_entropy_relative_delta":round(delta,8),
                         "argmax_agreement":top}
        if not math.isfinite(delta) or delta>LOSS or top is None or top<TOP1:
            agree=False
    saving=1-actual_model_bytes/original_model_bytes
    latency_regression=speed["median_forward_ms"]/baseline["cpu_latency"]["median_forward_ms"]-1
    within=(agree and saving>=MIN_PACKED_SAVING
            and latency_regression<=MAX_FORWARD_REGRESSION)
    report={
      "schema":SCHEMA,"mask":mask,"layer_names":list(layers),
      "operator_backend":"torch.ao.quantization.dynamic.Linear",
      "real_cpu_int8_operator_count":len(layers),
      "tensor_output_head_fp32":True,
      "weight_embedding_output_tie_preserved":True,
      "quantized_checkpoint_unmodified":True,
      "source_checkpoint_sha256":v.CHECKPOINT_SHA256,
      "reference_baseline_receipt_sha256":baseline["receipt_sha256"],
      "frozen_public_probe_git_blob_sha1":v.FROZEN_BLOB,
      "baseline_checkpoint_blob_sha1":v.CHECKPOINT_GIT_BLOB,
      "metrics_development_only":True,"independent_external_holdout":False,
      "original_serialized_model_bytes":original_model_bytes,
      "quantized_serialized_model_bytes":actual_model_bytes,
      "saved_model_bytes":original_model_bytes-actual_model_bytes,
      "serialized_model_saving_fraction":round(saving,7),
      "quality":quality,"quality_deltas":changes,
      "cpu_forward_latency":speed,
      "median_forward_regression_fraction":round(latency_regression,7),
      "memory":{"resident_after_conversion_bytes":rss_after_conversion,
                "resident_after_inference_bytes":rss_after_forward,
                "peak_process_rss_bytes":cpu_rss_peak(),
                "allocator_confounded":True,
                "cuda_vram_bytes":None},
      "research_eligibility":bool(within),
      "no_model_training":True,"no_production_weights_changed":True,
      "auto_promote":False,
      "gate":"RESEARCH_LAYER_SUBSET_CANDIDATE_ONLY_HOLD_EXTERNAL_BLIND"
              if within else "HOLD_FIDELITY_STORAGE_OR_FORWARD_REGRESSION",
    }
    report["receipt_sha256"]=v.seal(report)
    p=dest/(f"mask_{mask:02d}.json")
    if p.exists():raise FileExistsError("REFUSE_RESEARCH_RESULT_OVERWRITE")
    p.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"mask":mask,"layers":len(layers),
                      "top1_anchor":quality["historical_anchor"]["top1_agreement"],
                      "top1_probes":quality["public_fixed_probes"]["top1_agreement"],
                      "saving":report["serialized_model_saving_fraction"],
                      "median_ms":speed["median_forward_ms"],
                      "eligible":within,"gate":report["gate"],
                      "receipt_sha256":report["receipt_sha256"]},sort_keys=True))

def summarize(dest):
    baseline,ref=read_reference(dest)
    if not ref:raise ValueError("BASELINE_MISSING")
    results=[]
    for mask in range(1,N+1):
        r=v.json_read(dest/(f"mask_{mask:02d}.json"))
        if (r.get("schema")!=SCHEMA or r.get("mask")!=mask
          or r.get("layer_names")!=list(choose(mask))
          or r.get("source_checkpoint_sha256")!=v.CHECKPOINT_SHA256
          or r.get("reference_baseline_receipt_sha256")!=baseline["receipt_sha256"]
          or r.get("frozen_public_probe_git_blob_sha1")!=v.FROZEN_BLOB
          or r.get("auto_promote") is not False
          or r.get("no_production_weights_changed") is not True
          or r.get("receipt_sha256")!=v.seal({k:w for k,w in r.items() if k!="receipt_sha256"})):
            raise ValueError("UNTRUSTED_SWEEP_RESULT")
        # Revalidate claim without trusting the self-reported gate.
        good=all(r["quality_deltas"][name]["argmax_agreement"]>=TOP1
                 and r["quality_deltas"][name]["cross_entropy_relative_delta"]<=LOSS
                 for name in ("historical_anchor","public_fixed_probes"))
        good=good and r["serialized_model_saving_fraction"]>=MIN_PACKED_SAVING \
             and r["median_forward_regression_fraction"]<=MAX_FORWARD_REGRESSION
        if bool(good)!=r.get("research_eligibility"):
            raise ValueError("FABRICATED_CANDIDATE_ADMISSION")
        results.append(r)
    # Deterministic primary goal: maximize serialized saving then minimize
    # worst-case loss deterioration, never treat it as external validation.
    good=[r for r in results if r["research_eligibility"]]
    ranked=sorted(good,key=lambda r:(-r["serialized_model_saving_fraction"],
                    max(r["quality_deltas"][c]["cross_entropy_relative_delta"]
                        for c in ("historical_anchor","public_fixed_probes")),
                    r["mask"]))
    best=ranked[0] if ranked else None
    report={
       "schema":SUMMARY,"baseline_receipt_sha256":baseline["receipt_sha256"],
       "source_checkpoint_sha256":v.CHECKPOINT_SHA256,
       "known_model_weights_modified":False,
       "experiments":N,
       "experiment_mask_set":list(range(1,N+1)),
       "successful_development_candidates":len(good),
       "recommended_development_mask":best["mask"] if best else None,
       "recommended_development_layers":best["layer_names"] if best else [],
       "recommended_serialized_saving_fraction":best["serialized_model_saving_fraction"] if best else None,
       "best_result_receipt_sha256":best["receipt_sha256"] if best else None,
       "development_probe_overfit_risk":"HIGH_ALREADY_SEEN_PREVIOUS_V161_V162_RESULTS",
       "independent_blind_quality_proven":False,
       "real_live_service_rollback_proven":False,
       "automatic_production_admission":False,
       "candidate_authority":"RESEARCH_ONLY",
       "production_gate":"HOLD_INDEPENDENT_BLIND_AND_REAL_ROLLBACK",
       "all_mask_sha256":[r["receipt_sha256"] for r in results],
    }
    report["receipt_sha256"]=v.seal(report)
    f=dest/"sweep_summary.json"
    if f.exists():raise FileExistsError("SUMMARY_OVERWRITE_DENIED")
    f.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"experiments":15,"eligible":len(good),
                      "best_mask":report["recommended_development_mask"],
                      "best_saving":report["recommended_serialized_saving_fraction"],
                      "gate":report["production_gate"],
                      "receipt_sha256":report["receipt_sha256"]},sort_keys=True))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline",action="store_true")
    p.add_argument("--mask",type=int)
    p.add_argument("--summarize",action="store_true")
    p.add_argument("--out-dir",default="runtime/essence_v163")
    a=p.parse_args()
    if sum((a.baseline,a.mask is not None,a.summarize))!=1:
        raise SystemExit("CHOOSE_EXACTLY_ONE_OPERATION")
    dest=Path(a.out_dir);dest.mkdir(parents=True,exist_ok=True)
    if a.baseline:v.worker("baseline",dest)
    elif a.summarize:summarize(dest)
    else:case(a.mask,dest)

if __name__=="__main__":main()
