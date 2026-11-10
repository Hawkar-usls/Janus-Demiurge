"""Prove that a verified source marker reaches the real native model input window.

This does not claim semantic understanding; actual checkpoint inference remains
the existing janus_model.cli run and weight promotion the existing training gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from janus_model.cli import _augment_prompt
from janus_model.memory_admission import digest

MARKER = re.compile(r"^\|M[0-9a-f]{5}$")

def binding(admission: dict, organ_path: Path, model_state: dict, prompt: str) -> tuple[str, dict]:
    claimed = admission.get("receipt_sha256")
    if claimed != digest({k:v for k,v in admission.items() if k != "receipt_sha256"}):
        raise RuntimeError("MEMORY_ADMISSION_RECEIPT_SHA_HOLD")
    if admission.get("source_bytes_checked") is not True:
        raise RuntimeError("SOURCE_BYTES_NOT_VERIFIED_HOLD")
    status = admission.get("status")
    if status not in ("ADMITTED_TRAIN_SOURCE_CANDIDATES", "CONTEXT_ONLY_NO_NEW_TRAIN_SOURCE", "EMPTY_SEARCH"):
        raise RuntimeError("INVALID_MEMORY_ADMISSION_STATUS")
    safeguards = admission.get("safeguards") or {}
    if safeguards.get("preserve_holdout") is not True or safeguards.get("checkpoint_admission_bypassed") is not False or safeguards.get("authority_delta") != 0:
        raise RuntimeError("MEMORY_AUTHORITY_FIREWALL_HOLD")
    marker=admission.get("prompt_marker")
    if status == "EMPTY_SEARCH":
        if marker:
            raise RuntimeError("EMPTY_SEARCH_SHOULD_NOT_PRODUCE_MARKER")
        return "", {"schema":"janus.native.memory_v2_inference_binding.v1","status":"NO_MEMORY_SEARCH_MATCH",
                    "native_model_prompt_modified":False,"source_text_truth_claimed":False}
    if not isinstance(marker,str) or not MARKER.fullmatch(marker):
        raise RuntimeError("MEMORY_MARKER_INVALID")
    config=model_state.get("config") or {}
    context=config.get("context_length")
    if type(context) is not int or context not in (128, 256, 512):
        raise RuntimeError("NATIVE_MODEL_CONTEXT_UNSUPPORTED")
    packed=_augment_prompt(prompt+marker, str(organ_path),context)
    if marker not in packed:
        raise RuntimeError("NATIVE_MEMORY_MARKER_EVICTED_FROM_MODEL_CONTEXT")
    return marker, {
        "schema":"janus.native.memory_v2_inference_binding.v1",
        "status":"MODEL_INPUT_MEMORY_REFERENCE_VERIFIED",
        "source_marker":marker,
        "admission_receipt_sha256":claimed,
        "packed_prompt_sha256":hashlib.sha256(packed.encode("utf-8")).hexdigest(),
        "context_length":context,
        "source_full_text_in_prompt":False,
        "claim_of_semantic_comprehension":False,
        "model_weights_modified_by_prompt":False,
    }

def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--admission",type=Path,required=True)
    ap.add_argument("--organ-context",type=Path,required=True)
    ap.add_argument("--model-state",type=Path,required=True)
    ap.add_argument("--prompt",default="JANUS native checkpoint memory provenance")
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    admission=json.loads(a.admission.read_text(encoding="utf-8"))
    state=json.loads(a.model_state.read_text(encoding="utf-8"))
    marker,report=binding(admission,a.organ_context,state,a.prompt)
    if a.report.exists():
        raise FileExistsError("MEMORY_BINDING_REPORT_EXISTS")
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(marker)
if __name__=="__main__":
    main()
