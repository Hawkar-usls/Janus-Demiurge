"""ESSENCE v1.6: real JANUS native checkpoint quantization, CPU inference and provenance.

Runs exclusively on a disposable copy in GitHub Actions. Does not train, promote,
write a checkpoint or change any live module. INT4/INT8/FP16 are PACKED STORAGE
candidates, reconstructed to FP32 for CPU forward (not native low-bit inference).
Measures honest process RSS and CPU latency, and reports CUDA VRAM unavailable.
"""
from __future__ import annotations
import argparse
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import statistics
import struct
import sys
import time

import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/".janus"/"essence"))
import adaptive_quantization_v15 as quant
from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint
from janus_model.checkpoint_admission import sha256_file

SCHEMA="janus.essence.real_checkpoint_quantization/1.6"
FROZEN_BLOB="86f1d41aee5b3bffa488ee7ff523f0a62bca1873"
MODEL_BLOB="11e359e89d3946895b2e0d6817c54253f09dfed1"
CHECKPOINT_GIT_BLOB="88cad884b437dd0ab655d913b1c83d6a6d669735"
STATE_GIT_BLOB="7ac1aba026c21bbb95e7023de5eee0e31a4f78ff"
ANCHOR_BLOB="63633267137d0130db3c3cde045f91fef895b38f"
CHECKPOINT_SHA256="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
CHECKPOINT=ROOT/"janus_model"/"checkpoints"/"promoted.pt"
STATE=ROOT/"janus_model"/"state"/"JANUS_MODEL_STATE.json"
ANCHOR=ROOT/"janus_model"/"eval"/"JANUS_ANCHOR_EVAL-v1.txt"
FROZEN=ROOT/"research"/"essence"/"v16"/"frozen_probes.json"
ROOT_MANIFEST=ROOT/".janus"/"essence"/"manifest.json"
ROOT_FIXTURE=ROOT/".janus"/"essence"/"fixture.json"
MODES=("baseline","fp16","int8","int4","adaptive","restored")
SAMPLE_MODE=("baseline","fp16","int8","int4","adaptive")
LOSS_HOLD_LIMIT=.005
TOP1_HOLD_LIMIT=.97
MAX_INPUT_BYTES=300000

def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def seal(o):
    return hashlib.sha256(canonical(o)).hexdigest()

def file_sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""):h.update(part)
    return h.hexdigest()

def blob_sha(p):
    raw=Path(p).read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def json_read(p):
    f=Path(p)
    if f.is_symlink() or not f.is_file() or not 2<=f.stat().st_size<=MAX_INPUT_BYTES:
        raise ValueError("V16_UNSAFE_JSON_SOURCE")
    return json.loads(f.read_text(encoding="utf-8"),
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError("NONFINITE_JSON")))

def require_source():
    actual={
        "model":blob_sha(ROOT/"janus_model"/"model.py"),
        "state":blob_sha(STATE),
        "anchor":blob_sha(ANCHOR),
        "fixture":blob_sha(FROZEN),
        "checkpoint_git":blob_sha(CHECKPOINT),
        "checkpoint_sha256":file_sha(CHECKPOINT)
    }
    expected={"model":MODEL_BLOB,"state":STATE_GIT_BLOB,"anchor":ANCHOR_BLOB,
              "fixture":FROZEN_BLOB,"checkpoint_git":CHECKPOINT_GIT_BLOB,
              "checkpoint_sha256":CHECKPOINT_SHA256}
    if actual!=expected:raise ValueError("V16_PINNED_SOURCE_OR_CHECKPOINT_MISMATCH")
    state=json_read(STATE)
    frozen=json_read(FROZEN)
    if (state.get("checkpoint_sha256")!=CHECKPOINT_SHA256
            or frozen.get("schema")!="janus.essence.v16_real_checkpoint_probe_corpus/1.0"
            or frozen.get("checkpoint_sha256_from_repository_model_state")!=CHECKPOINT_SHA256
            or frozen.get("external_blind_holdout") is not False
            or frozen.get("evaluation_batches_per_cohort")!=8
            or frozen.get("probe_sequence_length")!=48
            or frozen.get("batch_size")!=2
            or len(frozen.get("public_probes",[]))!=12):
        raise ValueError("V16_INVALID_FROZEN_OR_STATE_METADATA")
    return frozen,state,actual

def role_for(name):
    if name.startswith(("token.","pos.","lm_head.")):return "memory"
    if name.endswith(("norm1.weight","norm2.weight","norm.weight")):return "verification"
    if name.endswith(("norm1.bias","norm2.bias","norm.bias")):return "recovery"
    if ".linear1." in name:return "planning"
    if ".linear2." in name:return "coding"
    return "sensing"

def compress_tensor(tensor,mode,role):
    if not isinstance(tensor,torch.Tensor) or tensor.dtype!=torch.float32:
        raise ValueError("FP32_TENSOR_REQUIRED")
    flat=tensor.detach().contiguous().view(-1).tolist()
    payload_bytes=0;decoded=[];modes=[]
    for i in range(0,len(flat),4096):
        block=flat[i:i+4096]
        if mode=="adaptive":
            opt=quant.choose(block,role)
            packet=opt["packet"];modes.append(opt["mode"])
        else:
            bits={"fp16":16,"int8":8,"int4":4}[mode]
            packet=quant.encode(block,bits);modes.append(mode.upper())
        decoded.extend(quant.decode(packet))
        payload_bytes+=len(packet)
    ret=torch.tensor(decoded,dtype=torch.float32).reshape(tensor.shape)
    if not torch.isfinite(ret).all():raise ValueError("NONFINITE_QUANTIZED_WEIGHTS")
    return ret,payload_bytes,modes,float((tensor-ret).abs().max().item())

def quantize_copy(model,mode):
    if mode in ("baseline","restored"):
        return {"float32_unique_bytes":sum(p.numel()*p.element_size() for p in model.parameters()),
                "packed_payload_bytes":None,"unique_tensors":len(list(model.parameters())),
                "changed_tensors":0,"max_abs_weight_error":0.0,
                "reconstructed_forward_dtype":"float32","quantized_compute_kernel":False}
    tensors=model.state_dict()
    alias_cache={};new_state={};actual_bytes=0;raw_bytes=0
    max_error=0.;modes={};n=0
    for name,tensor in tensors.items():
        if tensor.dtype!=torch.float32:raise ValueError("UNEXPECTED_TENSOR_DTYPE")
        identity=(tensor.untyped_storage().data_ptr(),tensor.storage_offset(),
                  tuple(tensor.shape),tuple(tensor.stride()))
        if identity not in alias_cache:
            decoded,size,packed_modes,err=compress_tensor(tensor,mode,role_for(name))
            alias_cache[identity]=(decoded,size,packed_modes,err)
            raw_bytes+=tensor.numel()*tensor.element_size()
            actual_bytes+=size
            max_error=max(max_error,err)
            n+=1
            for m in packed_modes:modes[m]=modes.get(m,0)+1
        new_state[name]=alias_cache[identity][0]
    if set(new_state)!=set(tensors):raise ValueError("STATE_KEY_LOSS")
    model.load_state_dict(new_state,strict=True)
    del new_state,tensors,alias_cache
    gc.collect()
    return {"float32_unique_bytes":raw_bytes,"packed_payload_bytes":actual_bytes,
            "packed_saving_fraction":round(1-actual_bytes/raw_bytes,6),
            "unique_tensors":n,"changed_tensors":n,
            "packing_modes":modes,"max_abs_weight_error":round(max_error,8),
            "reconstructed_forward_dtype":"float32","quantized_compute_kernel":False}

def build_inputs(frozen):
    length=frozen["probe_sequence_length"]
    batch=frozen["batch_size"]
    count=frozen["evaluation_batches_per_cohort"]
    streams={
        "historical_anchor":ANCHOR.read_text(encoding="utf-8"),
        "public_fixed_probes":"\n".join(frozen["public_probes"])*3,
    }
    result={}
    for k,body in streams.items():
        ids=ByteTokenizer.encode(body,bos=True,eos=True)
        if len(ids)<length+2:raise ValueError("TOO_SHORT_EVAL_SOURCE")
        rnd=random.Random(frozen["metric_probe_seed"]+(0 if k=="historical_anchor" else 71))
        rows=[]
        for _ in range(count):
            x=[];y=[]
            for _ in range(batch):
                start=rnd.randrange(0,len(ids)-length-1)
                x.append(ids[start:start+length])
                y.append(ids[start+1:start+1+length])
            rows.append((torch.tensor(x,dtype=torch.long),
                         torch.tensor(y,dtype=torch.long)))
        result[k]=rows
    return result

def cpu_rss():
    try:
        parts=Path("/proc/self/statm").read_text().split()
        return int(parts[1])*os.sysconf("SC_PAGE_SIZE")
    except (OSError,IndexError,ValueError):
        return None

@torch.inference_mode()
def evaluate(model,datasets,reference=None):
    aggregate={};store={}
    for name,batches in datasets.items():
        losses=[];logit_store=[];top1_num=0;top1_den=0
        maxdiff=0.;sumdiff=0.;numdiff=0
        for idx,(x,y) in enumerate(batches):
            logits,loss=model(x,y)
            logits=logits.float()
            losses.append(float(loss.item()))
            if reference is not None:
                ref=reference[name][idx].float()
                if logits.shape!=ref.shape:raise ValueError("REFERENCE_LOGIT_SHAPE_CHANGED")
                diff=(logits-ref).abs()
                maxdiff=max(maxdiff,float(diff.max()))
                sumdiff+=float(diff.sum())
                numdiff+=diff.numel()
                top1_num+=int((logits.argmax(-1)==ref.argmax(-1)).sum())
                top1_den+=int(ref.shape[0]*ref.shape[1])
            logit_store.append(logits.detach().cpu())
        avg=statistics.mean(losses)
        aggregate[name]={"mean_cross_entropy":round(avg,9),
                         "perplexity":round(math.exp(min(avg,100)),7),
                         "batches":len(batches),
                         "top1_agreement":round(top1_num/top1_den,7) if top1_den else None,
                         "max_abs_logits_error":round(maxdiff,8) if reference is not None else None,
                         "mean_abs_logits_error":round(sumdiff/numdiff,9) if numdiff else None}
        store[name]=logit_store
    return aggregate,store

@torch.inference_mode()
def time_forward(model,datasets,frozen):
    x,y=datasets["historical_anchor"][0]
    for _ in range(frozen["latency_warmup_batches"]):
        model(x,y)
    times=[]
    for _ in range(frozen["latency_timed_batches"]):
        start=time.perf_counter_ns()
        model(x,y)
        times.append((time.perf_counter_ns()-start)/1e6)
    return {"median_forward_ms":round(statistics.median(times),5),
            "min_forward_ms":round(min(times),5),
            "max_forward_ms":round(max(times),5),
            "samples":len(times),"batch_size":int(x.shape[0]),
            "sequence_length":int(x.shape[1]),
            "torch_cpu_threads":torch.get_num_threads(),
            "method":"CPU_PERF_COUNTER_SEPARATE_PROCESS_NO_KERNEL_QUANTIZATION"}

def load_logits(path,expected_sha):
    p=Path(path)
    if not p.is_file() or p.is_symlink() or file_sha(p)!=expected_sha:
        raise ValueError("REFERENCE_LOGITS_HASH_MISMATCH")
    raw=torch.load(p,map_location="cpu",weights_only=True)
    if set(raw)!={"historical_anchor","public_fixed_probes"}:raise ValueError("REFERENCE_LOGITS_SCHEMA_HOLD")
    for v in raw.values():
        if len(v)!=8 or any(not isinstance(x,torch.Tensor) or not torch.isfinite(x).all() for x in v):
            raise ValueError("BAD_REFERENCE_LOGITS")
    return raw

def metric_vectors_from_history(root,frozen,state):
    """Recorded loss observations, NOT actual live microkernel weights."""
    history=state.get("history")
    if not isinstance(history,list):raise ValueError("NO_HISTORICAL_LEARNING_DATA")
    rows=[x for x in history if isinstance(x,dict)
          and all(type(x.get(k)) in (float,int) and math.isfinite(x[k]) for k in (
             "candidate_eval_loss","incumbent_eval_loss","candidate_anchor_eval_loss",
             "incumbent_anchor_eval_loss"))]
    if len(rows)<16:raise ValueError("INSUFFICIENT_REAL_HISTORY")
    sample=rows[-min(128,len(rows)):]
    fields=("candidate_eval_loss","incumbent_eval_loss",
            "candidate_anchor_eval_loss","incumbent_anchor_eval_loss")
    v={
      "sensing":[float(x[fields[0]]) for x in sample],
      "memory":[float(x[fields[1]]) for x in sample],
      "planning":[float(x[fields[2]]) for x in sample],
      "verification":[float(x[fields[3]]) for x in sample],
      "recovery":[float(abs(x[fields[0]]-x[fields[1]])) for x in sample],
      "coding":[float(abs(x[fields[2]]-x[fields[3]])) for x in sample],
      "essence_self":[float((x[fields[0]]+x[fields[1]])/2) for x in sample],
    }
    source={"schema":"janus.essence.numeric_state/1.5",
            "repository":root["repository"],
            "source_class":"DECLARED_NUMERIC_STATE_UNVERIFIED",
            "vectors":v}
    report,compressed,snapshot=quant.run(root,json_read(ROOT_FIXTURE),
                   allow_readonly=True,source=source)
    quant.verify(report,compressed,snapshot)
    return {"origin":"RECORDED_JANUS_NATIVE_MODEL_LOSS_HISTORY_NOT_MICROKERNEL_INTERNAL_WEIGHTS",
            "record_count_used":len(sample),
            "training_state_git_blob_sha1":STATE_GIT_BLOB,
            "training_state_sha256":file_sha(STATE),
            "quantized_bytes":len(compressed),"original_fp32_bytes":len(snapshot),
            "packed_binary_saving_fraction":report["storage_saving_fraction"],
            "modes":{r["role"]:r["mode"] for r in report["lanes"]},
            "quantization_receipt_sha256":report["receipt_sha256"],
            "exact_snapshot_sha256":report["snapshot_bundle_sha256"],
            "real_model_weights_modified":False}

def worker(mode,ref_dir):
    frozen,state,identity=require_source()
    if mode not in MODES:raise ValueError("UNSUPPORTED_EXPERIMENT_MODE")
    torch.set_num_threads(1)
    torch.manual_seed(61616)
    before=file_sha(CHECKPOINT)
    model,obj=load_checkpoint(CHECKPOINT,expected_sha256=CHECKPOINT_SHA256)
    model.eval()
    config=obj.get("config")
    pre_rss=cpu_rss()
    weight=quantize_copy(model,mode)
    gc.collect()
    model.eval()
    loaded_rss=cpu_rss()
    datasets=build_inputs(frozen)
    reference=None
    if mode!="baseline":
        baseline_meta=json_read(ref_dir/"baseline.json")
        if baseline_meta.get("source_checkpoint_sha256")!=CHECKPOINT_SHA256:
            raise ValueError("BASELINE_CHECKPOINT_PROVENANCE_CHANGED")
        reference=load_logits(ref_dir/"baseline_logits.pt",
                              baseline_meta["baseline_logits_sha256"])
    quality,logits=evaluate(model,datasets,reference)
    latency=time_forward(model,datasets,frozen)
    end_rss=cpu_rss()
    peak=None
    try:
        import resource
        peak=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    except (ImportError,OSError):pass
    if mode=="baseline":
        torch.save(logits,ref_dir/"baseline_logits.pt")
        baseline_logits_sha=file_sha(ref_dir/"baseline_logits.pt")
        observations=metric_vectors_from_history(json_read(ROOT_MANIFEST),frozen,state)
    else:
        baseline_logits_sha=None;observations=None
    after=file_sha(CHECKPOINT)
    if after!=before or before!=CHECKPOINT_SHA256:
        raise ValueError("CHECKPOINT_MODIFIED_IN_RESEARCH_RUN")
    report={
      "schema":SCHEMA,"mode":mode,"research_read_only":True,
      "checkpoint_git_blob_sha1":CHECKPOINT_GIT_BLOB,
      "source_checkpoint_sha256":before,"source_checkpoint_unchanged":True,
      "checkpoint_provenance":"COMMITTED_NATIVE_PROMOTED_CHECKPOINT_NOT_EXTERNAL_BLIND",
      "model_git_blob_sha1":MODEL_BLOB,"state_git_blob_sha1":STATE_GIT_BLOB,
      "frozen_probes_git_blob_sha1":FROZEN_BLOB,
      "anchor_git_blob_sha1":ANCHOR_BLOB,
      "weight_storage":weight,"quality":quality,"cpu_latency":latency,
      "memory":{"loaded_model_rss_bytes":loaded_rss,
                "post_inference_process_rss_bytes":end_rss,
                "linux_process_peak_rss_bytes":peak,
                "measurement":"LINUX_PROC_STATM_CURRENT_AND_RESOURCE_PEAK_SEPARATE_RUNNER_PROCESS",
                "runtime_weight_memory_is_float32":True,
                "gpu_vram_status":"NOT_AVAILABLE_CPU_ONLY",
                "gpu_vram_bytes":None},
      "model_config":config,"torch_version":torch.__version__,
      "baseline_logits_sha256":baseline_logits_sha,
      "historical_metric_state":observations,
      "training_performed":False,"live_checkpoint_replaced":False,
      "production_model_promoted":False,
      "external_independent_blind_validation":False,
      "real_runtime_low_bit_kernel":False,
      "operational_service_rollback_tested":False,
      "gate":"RESEARCH_CHECKPOINT_FIDELITY_AND_CPU_RESOURCE_MEASUREMENT_ONLY"}
    report["receipt_sha256"]=seal(report)
    dest=ref_dir/(mode+".json")
    if dest.exists():raise FileExistsError("REFUSE_OVERWRITE_RESEARCH_REPORT")
    dest.write_text(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":mode,"anchor_ce":quality["historical_anchor"]["mean_cross_entropy"],
      "probe_ce":quality["public_fixed_probes"]["mean_cross_entropy"],
      "packed_bytes":weight.get("packed_payload_bytes"),
      "median_forward_ms":latency["median_forward_ms"],
      "rss_after_bytes":end_rss,"gpu_vram":None,
      "receipt_sha256":report["receipt_sha256"]},sort_keys=True))

def combine(ref_dir):
    runs={m:json_read(ref_dir/(m+".json")) for m in MODES}
    ref=runs["baseline"]
    if file_sha(CHECKPOINT)!=CHECKPOINT_SHA256:raise ValueError("FINAL_CHECKPOINT_CHANGED")
    summary=[]
    for name in MODES:
        obj=runs[name]
        if obj.get("source_checkpoint_sha256")!=CHECKPOINT_SHA256 or obj.get("source_checkpoint_unchanged") is not True:
            raise ValueError("INCONSISTENT_EXPERIMENT_PROVENANCE")
        if obj.get("receipt_sha256")!=seal({k:v for k,v in obj.items() if k!="receipt_sha256"}):
            raise ValueError("FORGED_EXPERIMENT_RECEIPT")
        diffs={}
        for cohort in ("historical_anchor","public_fixed_probes"):
            v=obj["quality"][cohort]["mean_cross_entropy"]
            b=ref["quality"][cohort]["mean_cross_entropy"]
            diffs[cohort]={"cross_entropy_delta":round(v-b,9),
                           "relative_delta_pct":round(100*(v/b-1),5),
                           "top1_agreement":obj["quality"][cohort]["top1_agreement"]}
        w=obj["weight_storage"]
        fidelity=(name in ("baseline","restored")
                  or all(diffs[c]["relative_delta_pct"]<=100*LOSS_HOLD_LIMIT
                         and (diffs[c]["top1_agreement"] is not None
                              and diffs[c]["top1_agreement"]>=TOP1_HOLD_LIMIT)
                         for c in diffs))
        packing=(name not in ("baseline","restored") and
                 w["packed_payload_bytes"]<.9*w["float32_unique_bytes"])
        summary.append({"mode":name,"fidelity_gate_pass":bool(fidelity),
            "packed_storage_gate_pass":bool(packing),
            "candidate_research_status":("STAGED_RESEARCH_CANDIDATE_ONLY" if fidelity and packing
                                         else "HOLD_FIDELITY_OR_PACKING"),
            "quality_delta":diffs,
            "packed_bytes":w["packed_payload_bytes"],
            "unique_fp32_parameter_bytes":w["float32_unique_bytes"],
            "rss_after_inference_bytes":obj["memory"]["post_inference_process_rss_bytes"],
            "peak_rss_bytes":obj["memory"]["linux_process_peak_rss_bytes"],
            "median_cpu_forward_ms":obj["cpu_latency"]["median_forward_ms"],
            "real_quantized_runtime":False,
            "source_receipt_sha256":obj["receipt_sha256"]})
    baseline=ref["quality"]
    restored=runs["restored"]["quality"]
    if any(abs(baseline[k]["mean_cross_entropy"]-restored[k]["mean_cross_entropy"])>1e-8
           or restored[k]["top1_agreement"]!=1 for k in baseline):
        raise ValueError("BASELINE_RELOAD_ROLLBACK_DRILL_FAIL")
    result={
     "schema":"janus.essence.v16_real_checkpoint_benchmark_summary",
     "checkpoint_sha256":CHECKPOINT_SHA256,
     "checkpoint_git_blob_sha1":CHECKPOINT_GIT_BLOB,
     "frozen_probes_git_blob_sha1":FROZEN_BLOB,
     "anchor_git_blob_sha1":ANCHOR_BLOB,
     "real_checkpoint_evaluated":True,
     "real_training_performed":False,
     "numerical_observations_derived_from_training_ledger":True,
     "actual_live_microkernel_numeric_states_accessed":False,
     "cpu_only":True,"vram":"NOT_AVAILABLE",
     "loss_regression_threshold_fraction":LOSS_HOLD_LIMIT,
     "top1_agreement_minimum":TOP1_HOLD_LIMIT,
     "round_trip_checkpoint_reload_matches_baseline":True,
     "full_production_service_rollback_tested":False,
     "live_weights_modified":False,
     "independent_external_blind_gain_proven":False,
     "automatic_model_change_authorized":False,
     "model_execution_dtype_after_lowbit_reconstruction":"FP32",
     "measurements":summary,
     "gate":"RESEARCH_ONLY_HOLD_REAL_LOWBIT_KERNEL_EXTERNAL_BLIND_AND_CANARY"
    }
    result["receipt_sha256"]=seal(result)
    (ref_dir/"summary.json").write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"gate":result["gate"],"checkpoints":1,
        "modes":len(summary),"reference_restored":True,
        "candidates":[x["mode"] for x in summary if x["candidate_research_status"]=="STAGED_RESEARCH_CANDIDATE_ONLY"],
        "receipt_sha256":result["receipt_sha256"]},sort_keys=True))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=MODES)
    p.add_argument("--combine",action="store_true")
    p.add_argument("--out-dir",default="runtime/essence_v16")
    a=p.parse_args()
    if not a.mode and not a.combine:p.error("MODE_OR_COMBINE_REQUIRED")
    if a.mode and a.combine:p.error("MODE_OR_COMBINE_EXCLUSIVE")
    root=Path(a.out_dir)
    root.mkdir(parents=True,exist_ok=True)
    if a.combine:combine(root)
    else:worker(a.mode,root)

if __name__=="__main__":main()
