#!/usr/bin/env python3
"""Replay ESSENCE v1.8 on real, historically recorded GPT loss numbers.

A frozen public JANUS_MODEL_STATE training journal is input; these are NOT
actual internal microkernel tensors, not unseen scores, and not live weights.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/".janus"/"essence"))
import adaptive_quantization_v15 as q15
import block_quantization_v18 as q18

STATE=ROOT/"janus_model"/"state"/"JANUS_MODEL_STATE.json"
MODEL=ROOT/"janus_model"/"checkpoints"/"promoted.pt"
ROOT_MANIFEST=ROOT/".janus"/"essence"/"manifest.json"
FIXTURE=ROOT/".janus"/"essence"/"fixture.json"
PINNED_STATE_BLOB="7ac1aba026c21bbb95e7023de5eee0e31a4f78ff"
PINNED_MODEL_BLOB="88cad884b437dd0ab655d913b1c83d6a6d669735"
PINNED_MODEL_SHA256="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
FIELDS=("candidate_eval_loss","incumbent_eval_loss",
        "candidate_anchor_eval_loss","incumbent_anchor_eval_loss")

def git_blob(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def check_files():
    if STATE.is_symlink() or MODEL.is_symlink():
        raise ValueError("UNSAFE_MODEL_OR_LEDGER_PATH")
    raw=STATE.read_bytes()
    weights=MODEL.read_bytes()
    if (not 100<=len(raw)<=300000
        or git_blob(raw)!=PINNED_STATE_BLOB
        or git_blob(weights)!=PINNED_MODEL_BLOB
        or hashlib.sha256(weights).hexdigest()!=PINNED_MODEL_SHA256):
        raise ValueError("SOURCE_ORIGINAL_CHECKPOINT_PIN_MISMATCH")
    state=json.loads(raw.decode("utf8"),parse_constant=lambda _: (_ for _ in ()).throw(ValueError("BAD_JSON")))
    if state.get("checkpoint_sha256")!=PINNED_MODEL_SHA256:
        raise ValueError("STATE_CHECKPOINT_IDENTITY_MISMATCH")
    return state,hashlib.sha256(raw).hexdigest()

def make_source(state,root):
    rows=state.get("history")
    if not isinstance(rows,list) or not 16<=len(rows)<=10000:
        raise ValueError("INSUFFICIENT_REAL_HISTORY")
    sample=[]
    for row in rows:
        if (not isinstance(row,dict)
            or any(type(row.get(k)) not in (float,int)
                   or not math.isfinite(row[k]) for k in FIELDS)):
            continue
        sample.append(row)
    if len(sample)<16:raise ValueError("INSUFFICIENT_REAL_OBSERVATIONS")
    sample=sample[-128:]
    a,b,c,d=FIELDS
    vectors={
        "sensing":[float(x[a]) for x in sample],
        "memory":[float(x[b]) for x in sample],
        "planning":[float(x[c]) for x in sample],
        "verification":[float(x[d]) for x in sample],
        "recovery":[float(abs(x[a]-x[b])) for x in sample],
        "coding":[float(abs(x[c]-x[d])) for x in sample],
        "essence_self":[float((x[a]+x[b])/2) for x in sample]
    }
    result={"schema":"janus.essence.numeric_state/1.5",
            "repository":root["repository"],
            "source_class":"DECLARED_NUMERIC_STATE_UNVERIFIED",
            "vectors":vectors}
    return result,len(sample)

def replay(*,verify_pins=True):
    root=q15.load(ROOT_MANIFEST)
    fixture=q15.load(FIXTURE)
    state,source_sha=check_files() if verify_pins else (q15.load(STATE),"NOT_PINNED_TEST_ONLY")
    source,n=make_source(state,root)
    report,pack,backup=q18.run(root,fixture,source=source,explicit_readonly=True)
    return {
        "schema":"janus.essence.recorded_training_history_quantization/1.8",
        "source_class":"RECORDED_MODEL_LOSS_JOURNAL_NOT_LIVE_MICROKERNEL_TENSORS",
        "ledger_source_sha256":source_sha,
        "ledger_git_blob_sha1":PINNED_STATE_BLOB,
        "locked_original_model_sha256":PINNED_MODEL_SHA256,
        "observations":n,
        "numeric_state_sha256":report["numeric_state_sha256"],
        "precision_receipt_sha256":report["receipt_sha256"],
        "v15_packed_bytes":report["v15_packed_bytes"],
        "v18_packed_bytes":report["v18_packed_bytes"],
        "exact_fp32_backup_bytes":len(backup),
        "added_saving_bytes":report["additional_storage_saving_bytes"],
        "packed_sha256":hashlib.sha256(pack).hexdigest(),
        "original_fp32_sha256":hashlib.sha256(backup).hexdigest(),
        "working_checkpoint_changed":False,
        "model_training_performed":False,
        "independent_holdout_achieved":False,
        "target_hardware_benchmarked":False,
        "live_service_rollback_tested":False,
        "production_authority":False,
        "research_only":True
    }

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=replay()
    dst=Path(args.out)
    if dst.exists():raise FileExistsError("NO_RECORDED_EVIDENCE_OVERWRITE")
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({"recorded_observations":result["observations"],
                      "v15_bytes":result["v15_packed_bytes"],
                      "v18_bytes":result["v18_packed_bytes"],
                      "extra_saved_bytes":result["added_saving_bytes"],
                      "production_authority":False},sort_keys=True))
