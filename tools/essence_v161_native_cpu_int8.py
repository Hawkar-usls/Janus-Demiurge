"""ESSENCE v1.6.1: actual CPU dynamic INT8 operators on a SHA-pinned JANUS GPT.

This is *not* a promotion or an update to promoted.pt. Quantizes only supported
nn.Linear modules in a disposable copy; embeddings, layer norms and other
modules remain their original precision. Reads benchmark-proven baseline logits.
"""
from __future__ import annotations
import gc
import copy
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import torch
import torch.nn as nn

from tools import essence_v16_real_checkpoint_bench as v
from janus_model.train_registry import load_checkpoint

MODE="dynamic_int8_cpu"
SCHEMA="janus.essence.native_cpu_int8_experiment/1.6.1"

def byte_size_state_dict(model):
    out=io.BytesIO()
    torch.save(model.state_dict(),out)
    return len(out.getvalue())

def make_native_quantized(model,policy="all_linear"):
    from torch.ao.quantization import quantize_dynamic
    # TransformerEncoderLayer fastpath introspects .weight as a Tensor, while
    # native dynamic QuantizedLinear exposes weight() as a method. Disable
    # this incompatible optional fusion path for this *research process*.
    torch.backends.mha.set_fastpath_enabled(False)
    if policy=="all_linear":
        qmodel=quantize_dynamic(model,{nn.Linear},dtype=torch.qint8,inplace=False)
    elif policy=="ffn_only":
        qmodel=copy.deepcopy(model)
        quantize_dynamic(qmodel.blocks,{nn.Linear},dtype=torch.qint8,inplace=True)
    else:
        raise ValueError("UNKNOWN_QUANTIZATION_POLICY")
    qtypes=(torch.ao.nn.quantized.dynamic.Linear,)
    count=sum(isinstance(module,qtypes) for module in qmodel.modules())
    if count<1:
        raise ValueError("NO_REAL_NATIVE_INT8_LINEAR_KERNELS")
    return qmodel,count

def run(out_dir="runtime/essence_v161",policy="all_linear"):
    dest=Path(out_dir)
    dest.mkdir(parents=True,exist_ok=True)
    frozen,state,actual=v.require_source()
    torch.set_num_threads(1)
    torch.manual_seed(61616)
    before=v.file_sha(v.CHECKPOINT)
    model,_=load_checkpoint(v.CHECKPOINT,expected_sha256=v.CHECKPOINT_SHA256)
    model.eval()
    source_state_bytes=byte_size_state_dict(model)
    original_cpu_rss=v.cpu_rss()
    qmodel,native_modules=make_native_quantized(model,policy=policy)
    qmodel.eval()
    quantized_state_bytes=byte_size_state_dict(qmodel)
    del model
    gc.collect()
    resident=v.cpu_rss()
    baseline=v.json_read(dest/"baseline.json")
    if (baseline.get("source_checkpoint_sha256")!=v.CHECKPOINT_SHA256
        or baseline.get("receipt_sha256")!=v.seal({k:w for k,w in baseline.items() if k!="receipt_sha256"})):
        raise ValueError("BASELINE_PROVENANCE_REJECTED")
    reference=v.load_logits(dest/"baseline_logits.pt",baseline["baseline_logits_sha256"])
    datasets=v.build_inputs(frozen)
    quality,_=v.evaluate(qmodel,datasets,reference)
    latency=v.time_forward(qmodel,datasets,frozen)
    post=v.cpu_rss()
    peak=None
    try:
        import resource
        peak=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024
    except (ImportError,OSError):
        pass
    if v.file_sha(v.CHECKPOINT)!=before:
        raise ValueError("REAL_PROMOTED_CHECKPOINT_MUTATED")
    deltas={}
    allowed=True
    for name in ("historical_anchor","public_fixed_probes"):
        old=baseline["quality"][name]["mean_cross_entropy"]
        new=quality[name]["mean_cross_entropy"]
        agreement=quality[name]["top1_agreement"]
        delta=(new/old-1)
        deltas[name]={"relative_loss_change_pct":round(delta*100,6),
                      "top1_agreement":agreement}
        if delta>v.LOSS_HOLD_LIMIT or agreement<v.TOP1_HOLD_LIMIT:
            allowed=False
    output={
        "schema":SCHEMA,"status":"REAL_CPU_DYNAMIC_INT8_TESTED_NO_PROMOTION",
        "checkpoint_sha256":before,
        "checkpoint_git_blob_sha1":v.CHECKPOINT_GIT_BLOB,
        "source_reference_receipt_sha256":baseline["receipt_sha256"],
        "frozen_public_probe_blob_sha1":v.FROZEN_BLOB,
        "pytorch_version":torch.__version__,
        "quantization_backend":"PYTORCH_DYNAMIC_INT8_CPU_NN_LINEAR",
        "selection_policy":policy,
        "output_lm_head_retained_fp32":policy=="ffn_only",
        "native_int8_linear_module_count":native_modules,
        "modules_not_quantized":"EMBEDDINGS_LAYER_NORMS_OTHER_NON_LINEAR",
        "cpu_only":True,"cuda_vram":"NOT_AVAILABLE_CPU_ONLY",
        "serialized_original_state_dict_bytes":source_state_bytes,
        "serialized_dynamic_int8_state_dict_bytes":quantized_state_bytes,
        "serialized_state_dict_saving_fraction":round(1-quantized_state_bytes/source_state_bytes,6),
        "original_float32_model_resident_process_rss_bytes":original_cpu_rss,
        "quantized_cpu_model_resident_process_rss_bytes":resident,
        "post_inference_process_rss_bytes":post,
        "peak_process_rss_bytes":peak,
        "rss_caveat":"MODEL_WAS_CONVERTED_AFTER_LOADING_ORIGINAL_IN_SAME_PROCESS_CPU_ALLOCATOR_MAY_RETAIN_PAGES",
        "baseline_cpu_median_forward_ms":baseline["cpu_latency"]["median_forward_ms"],
        "native_int8_cpu_forward":latency,
        "quality":quality,
        "comparison":deltas,
        "fidelity_preliminary_pass":allowed,
        "native_runtime_quantization_executed":True,
        "training_occurred":False,
        "checkpoint_file_modified":False,
        "production_service_rollback_tested":False,
        "external_blind_quality_attested":False,
        "automatic_model_promotion":False,
        "production_authority":False,
        "gate":"RESEARCH_NATIVE_CPU_INT8_FIDELITY_PASS_REQUIRE_REAL_CANARY_AND_EXTERNAL_VALIDATION" if allowed
               else "HOLD_NATIVE_INT8_QUALITY_REGRESSION",
    }
    output["receipt_sha256"]=v.seal(output)
    target=dest/("dynamic_int8_cpu.json" if policy=="all_linear" else "selective_ffn_int8_cpu.json")
    if target.exists():raise FileExistsError("NO_OVERWRITE")
    target.write_text(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "native_linear_layers":native_modules,
        "anchor_loss":quality["historical_anchor"]["mean_cross_entropy"],
        "probe_loss":quality["public_fixed_probes"]["mean_cross_entropy"],
        "median_cpu_forward_ms":latency["median_forward_ms"],
        "original_state_bytes":source_state_bytes,
        "int8_state_bytes":quantized_state_bytes,
        "post_rss_bytes":post,
        "fidelity_pass":allowed,
        "gate":output["gate"],
        "receipt_sha256":output["receipt_sha256"],
    },sort_keys=True))

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out-dir",default="runtime/essence_v161")
    p.add_argument("--policy",choices=("all_linear","ffn_only"),default="all_linear")
    opts=p.parse_args()
    run(opts.out_dir,policy=opts.policy)
