#!/usr/bin/env python3
"""ESSENCE v1.6.6 shadow-only native INT8 canary and injected-fault fallback.

Exercises real JANUS GPT forward calls with the researched 3-FFN dynamic
INT8 candidate, but routes all real outputs to the original FP32 model.
The forced fault verifies exact *in-memory research shadow* fallback only.
NOT A PRODUCTION SERVICE CANARY OR OPERATIONAL ROLLBACK.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import torch
from tools import essence_v16_real_checkpoint_bench as bench
from tools import essence_v163_layerwise_int8_sweep as subset
from janus_model.train_registry import load_checkpoint

RISK=ROOT/"research"/"essence"/"v166"/"locked_admission_evidence.json"
RISK_BLOB="6acaf2bbec6f3885466be8657e37f40c89fcb3a2"
SCHEMA="janus.essence.shadow_canary_for_native_int8/1.6.6"
EXPECTED_CKPT="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"

def git_blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def seal(o):
    return hashlib.sha256(json.dumps(o,sort_keys=True,ensure_ascii=False,
                       separators=(",",":"),allow_nan=False).encode()).hexdigest()

def check_risk():
    if git_blob(RISK.read_bytes())!=RISK_BLOB:
        raise ValueError("SHADOW_EVIDENCE_GIT_BLOB_MISMATCH")
    obj=json.loads(RISK.read_text())
    auth=obj.get("authority") or {}
    if (obj.get("schema")!="janus.essence.native_int8_three_ffn_prospective_and_risk/1.6.5"
        or obj.get("source",{}).get("checkpoint_sha256")!=EXPECTED_CKPT
        or obj.get("algorithm",{}).get("native_int8_linear_operator_count")!=3
        or obj.get("development",{}).get("chosen_mask")!=7
        or obj.get("risk",{}).get("statistical_lower_bound_gate")!="HOLD"
        or auth.get("production_weights_change_allowed") is not False
        or auth.get("automatic_model_swap_allowed") is not False):
        raise ValueError("SHADOW_UNAUTHORIZED_PRODUCTION_PROMOTION")
    return obj

def router(baseline_logits,candidate_logits,policy,*,fault=False):
    """Explicit outcome, never changes a live model or shared checkpoint."""
    if policy.get("production_weights_change_allowed") is not False \
       or policy.get("automatic_model_swap_allowed") is not False:
        raise PermissionError("EXTERNAL_MODEL_AUTHORITY_REQUIRED")
    if (not torch.isfinite(baseline_logits).all()
        or baseline_logits.ndim!=3
        or baseline_logits.shape[-1]!=258):
        raise ValueError("INVALID_SAFE_FP32_BASELINE")
    if candidate_logits.shape!=baseline_logits.shape:
        raise ValueError("UNSAFE_CANDIDATE_SHAPE")
    # Simulated forced error: makes EOS overwhelmingly likely. Uses a copy.
    if fault:
        candidate_logits=candidate_logits.clone()
        candidate_logits.fill_(-1000.)
        candidate_logits[...,257]=1000.
    mismatch=int((baseline_logits.argmax(-1)!=candidate_logits.argmax(-1)).sum())
    # Even a healthy candidate is only shadowed because authority is HOLD.
    served=baseline_logits
    if not torch.equal(served,baseline_logits):
        raise AssertionError("SHADOW_FALLBACK_NOT_EXACT")
    return {"route":"FP32_BASELINE_ONLY",
            "candidate_was_executed_but_never_served":True,
            "injected_fault":fault,
            "argmax_mismatched_positions":mismatch,
            "exact_original_fallback":True,
            "gate":"HOLD_INJECTED_CORRUPTION" if fault else "HOLD_PRODUCTION_AUTHORITY"},served

def run(out):
    frozen,_,_=bench.require_source()
    risk=check_risk()
    initial=bench.file_sha(bench.CHECKPOINT)
    if initial!=EXPECTED_CKPT:raise ValueError("UNTRUSTED_CHECKPOINT")
    torch.manual_seed(61616)
    torch.set_num_threads(1)
    original,_=load_checkpoint(bench.CHECKPOINT,expected_sha256=EXPECTED_CKPT)
    original.eval()
    candidate,names=subset.quantize_ffn_subset(original,mask=7)
    candidate.eval()
    if names!=subset.choose(7) or len(names)!=3:
        raise ValueError("SHADOW_QUANTIZED_SUBSET_INVALID")
    batches=bench.build_inputs(frozen)
    total=0;measured_agreement={};mismatches=0
    with torch.inference_mode():
        for label,paired in batches.items():
            matched=0;seen=0
            for x,y in paired:
                logits,_=original(x,y)
                other,_=candidate(x,y)
                verdict,served=router(logits,other,risk["authority"],fault=False)
                fault_verdict,recovered=router(logits,other,risk["authority"],fault=True)
                if fault_verdict["argmax_mismatched_positions"]<1:
                    raise AssertionError("INJECTED_FAULT_NOT_DETECTED")
                if not torch.equal(served,logits) or not torch.equal(recovered,logits):
                    raise AssertionError("ORIGINAL_FALLBACK_MISMATCH")
                matched+=int((logits.argmax(-1)==other.argmax(-1)).sum())
                seen+=logits.shape[0]*logits.shape[1]
                mismatches+=fault_verdict["argmax_mismatched_positions"]
            measured_agreement[label]={"matching":matched,"total":seen,
                                        "top1_agreement":round(matched/seen,7)}
            total+=seen
    if bench.file_sha(bench.CHECKPOINT)!=initial:
        raise ValueError("ORIGINAL_CHECKPOINT_CHANGED_IN_SHADOW")
    report={
      "schema":SCHEMA,"origin_checkpoint_sha256":initial,
      "origin_evidence_git_blob_sha1":RISK_BLOB,
      "native_int8_layers":list(names),
      "real_original_fp32_outputs_served_on_every_trial":True,
      "real_candidate_native_cpu_forward_executed":True,
      "runtime_lowbit_operator_count":len(names),
      "checked_position_count":total,
      "detected_injected_fault_positions":mismatches,
      "shadow_fallback_reproduced_original_logits_exactly":True,
      "shadow_test_quality":measured_agreement,
      "original_checkpoint_hash_unchanged":True,
      "production_service_connected":False,
      "real_service_canary_rollout_executed":False,
      "real_production_rollback_executed":False,
      "independent_external_approval_received":False,
      "production_model_mutated":False,
      "automatic_model_swap_authority":False,
      "gate":"RESEARCH_SHADOW_FALLBACK_PASS_PRODUCTION_HOLD"}
    report["receipt_sha256"]=seal(report)
    p=Path(out)
    if p.exists():raise FileExistsError("NO_RECEIPT_OVERWRITE")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"shadow_fallback":True,"positions":total,
                      "faults_detected":mismatches,"gate":report["gate"],
                      "receipt_sha256":report["receipt_sha256"]},sort_keys=True))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",default="runtime/essence_v166/shadow_canary.json")
    a=p.parse_args()
    run(a.out)

if __name__=="__main__":main()
