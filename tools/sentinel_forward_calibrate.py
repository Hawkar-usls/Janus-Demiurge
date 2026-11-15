#!/usr/bin/env python3
"""JANUS SENTINEL prospective GitHub-only continual self-calibration (temperature).

After the SAME frozen A/B model has made no changes, wait for 128 real,
completed workflow outcomes created AFTER its immutable Git checkpoint was
committed. Use first 64 strictly as temperature calibration, second 64 as
untouched forward evaluation. No future target label appears in input context.
Never evaluate a forward cohort twice: append a monotonic Git cursor.

This is operational calibration of a research-only watchdog, NOT
independent external validation, a new neural weight update, or production
model admission. The network weights do not change; only the calibration
temperature may improve under strict prospective gates.

Github-hosted jobs terminate. All state lives in the sentinel-state branch.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

from tools import sentinel_transformer as m

SCHEMA="janus.sentinel.forward_calibration/1.0"
STATE="janus.sentinel.forward_calibration_cursor/1.0"
FUTURE_CALIB_N=64
FUTURE_TEST_N=64
FUTURE_TOTAL=FUTURE_CALIB_N+FUTURE_TEST_N
MIN_WORKFLOW_FAMILIES=6
MAX_TEST_ECE=0.20
MIN_GAIN=0.001
TEMPERATURE_CHOICES=(0.25,)+m.TEMPERATURES


def require(ok,why):
    if not ok:raise ValueError(why)


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode()


def receipt(value):
    return dict(value,receipt_sha256=hashlib.sha256(canonical(value)).hexdigest())


def load_json(path):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and
            2<=p.stat().st_size<=1_000_000,"UNSAFE_CALIBRATION_INPUT")
    return json.loads(p.read_text("utf-8"))


def validate_cursor(cursor):
    if cursor is None:return None
    require(isinstance(cursor,dict) and cursor.get("schema")==STATE and
            cursor.get("research_only") is True and
            cursor.get("production_authority") is False and
            isinstance(cursor.get("last_target_utc"),str) and
            isinstance(cursor.get("last_target_id"),int) and
            cursor["last_target_id"]>0 and
            type(cursor.get("epoch")) is int and cursor["epoch"]>=1 and
            cursor.get("receipt_sha256")==hashlib.sha256(canonical({
              k:v for k,v in cursor.items() if k!="receipt_sha256"
            })).hexdigest(),
            "CALIBRATION_CURSOR_TAMPERED")
    m.timepoint(cursor["last_target_utc"])
    return cursor


def eligible(rows,checkpoint_commit_utc,cursor):
    cutoff=m.timepoint(checkpoint_commit_utc)
    if cursor is not None:
        cutoff=max(cutoff,m.timepoint(cursor["last_target_utc"]))
    require(rows and len(rows)<=m.MAX_RUNS,
            "MISSING_OR_UNBOUNDED_GITHUB_HISTORY")
    # If source page no longer covers our watermark we must not silently
    # claim the first available records to be a complete future cohort.
    earliest=m.timepoint(rows[0]["created_at"])
    require(earliest<=cutoff,
            "HISTORY_GAP_CANNOT_PROVE_NO_MISSING_FUTURE_TASKS")
    return [
       x for x in m.examples(rows)
       if m.timepoint(x[3])>cutoff
    ],cutoff


def test_diversity(selected):
    require(len(selected)==FUTURE_TOTAL,
            "NOT_ENOUGH_NEW_GITHUB_WORKFLOW_RUNS")
    calibr=selected[:FUTURE_CALIB_N]
    test=selected[FUTURE_CALIB_N:]
    require(all(x[2]!=y[2] for x in calibr for y in test),
            "FUTURE_LABEL_OVERLAP")
    require(set(x[3] for x in calibr) and set(x[3] for x in test),
            "NO_CALIBRATION_OR_TEST_TIMESTAMPS")
    # Outcome rates are often low; reject degenerate no-failure periods,
    # rather than announce quality based entirely on successes.
    require(any(x[1]==1 for x in calibr) and
            any(x[1]==1 for x in test),
            "FORWARD_COHORT_LACKS_FAIL_AND_SUCCESS_SIGNAL")
    require(any(x[1]==0 for x in calibr) and
            any(x[1]==0 for x in test),
            "FORWARD_COHORT_ALL_FAILURES")
    require(len(set(x[0][-1] for x in calibr+test))>=MIN_WORKFLOW_FAMILIES,
            "FORWARD_TARGET_WORKFLOW_DIVERSITY_TOO_LOW")
    return calibr,test


def choose_temperature(calibr_labels,calibr_logits,prior_temp):
    require(len(calibr_logits)==len(calibr_labels) and
            len(calibr_labels)==FUTURE_CALIB_N and
            math.isfinite(prior_temp),
            "INVALID_CALIBRATION_BATCH")
    temps=sorted(set(TEMPERATURE_CHOICES+(float(prior_temp),)))
    return min(temps,key=lambda t:(m.brier(
          calibr_labels,m.score_probs(calibr_logits,t)),abs(t-prior_temp)))


def evaluate(parent,forward_rows,*,logits=None):
    m.check_checkpoint(parent)
    require(len(forward_rows)==FUTURE_TOTAL,"INVALID_CHRONOLOGICAL_COHORT")
    calibration,test=test_diversity(forward_rows)
    if logits is None:
        import torch
        torch.set_num_threads(1)
        weights=parent["weights"]
        model=m.net(torch)
        expected=model.state_dict()
        require(set(weights)==set(expected),"NEURAL_SOURCE_WEIGHTS_INCOMPATIBLE")
        converted={}
        for name,old in expected.items():
            v=torch.tensor(weights[name],dtype=old.dtype)
            require(v.shape==old.shape and bool(torch.isfinite(v).all()),
                    "INVALID_SAVED_TRANSFORMER_TENSOR")
            converted[name]=v
        model.load_state_dict(converted,strict=True)
        model.eval()
        x=torch.tensor([x[0] for x in forward_rows],dtype=torch.long)
        with torch.inference_mode():
            logits=model(x).tolist()
    require(len(logits)==FUTURE_TOTAL and all(math.isfinite(v) for v in logits),
            "NONFINITE_CALIBRATION_FORWARD_PASS")
    oldtemp=float(parent["temperature"])
    labels=[v[1] for v in forward_rows]
    best=choose_temperature(labels[:FUTURE_CALIB_N],
                            logits[:FUTURE_CALIB_N],oldtemp)
    raw_test=logits[FUTURE_CALIB_N:]
    label_test=labels[FUTURE_CALIB_N:]
    baseline_probs=m.score_probs(raw_test,oldtemp)
    candidate_probs=m.score_probs(raw_test,best)
    baseline_brier=m.brier(label_test,baseline_probs)
    candidate_brier=m.brier(label_test,candidate_probs)
    baseline_ece=m.ece(label_test,baseline_probs)
    candidate_ece=m.ece(label_test,candidate_probs)
    gain=baseline_brier-candidate_brier
    accept=(
        best!=oldtemp and gain>=MIN_GAIN and
        candidate_ece<=min(MAX_TEST_ECE,baseline_ece+0.01)
    )
    result={
        "schema":SCHEMA,
        "status":"PASS_PROSPECTIVE_RESEARCH_TEMPERATURE_GAIN" if accept else
                 "HOLD_PROSPECTIVE_TEMPERATURE_NO_INDEPENDENT_GAIN",
        "parent_checkpoint_sha256":parent["checkpoint_sha256"],
        "calibration_temp_from_old_model":oldtemp,
        "proposed_temperature":best,
        "accepted":accept,
        "calibration_examples":FUTURE_CALIB_N,
        "evaluation_examples":FUTURE_TEST_N,
        "calibration_first_id":calibration[0][2],
        "calibration_last_id":calibration[-1][2],
        "test_first_id":test[0][2],
        "test_last_id":test[-1][2],
        "test_last_utc":test[-1][3],
        "calibration_failures":sum(x[1] for x in calibration),
        "evaluation_failures":sum(label_test),
        "baseline_forward_brier":baseline_brier,
        "candidate_forward_brier":candidate_brier,
        "baseline_forward_ece":baseline_ece,
        "candidate_forward_ece":candidate_ece,
        "paired_brier_gain":gain,
        "only_temperature_changed":True,
        "weights_identical_to_parent":True,
        "research_only":True,
        "production_authority":False,
        "dispatch_authority":False,
        "external_independent_validation":False,
    }
    return result


def new_parent(parent,result):
    m.check_checkpoint(parent)
    require(result["accepted"] and
            result["parent_checkpoint_sha256"]==parent["checkpoint_sha256"] and
            result["only_temperature_changed"] and
            result["weights_identical_to_parent"],
            "AUTO_TEMPERATURE_PARENT_GATE_DENIED")
    fresh=json.loads(json.dumps(parent))
    oldsha=fresh.pop("checkpoint_sha256")
    fresh["temperature"]=result["proposed_temperature"]
    fresh["parent_checkpoint_sha256"]=oldsha
    fresh["status"]="RESEARCH_PROSPECTIVE_TEMPERATURE_ADAPTED_NOT_PRODUCTION"
    fresh["forward_calibration"]={
        "receipt_sha256":result["receipt_sha256"],
        "test_last_utc":result["test_last_utc"],
        "first_test_id":result["test_first_id"],
        "last_test_id":result["test_last_id"]
    }
    fresh["checkpoint_sha256"]=m.digest(fresh)
    m.check_checkpoint(fresh)
    require(parent["weights"]==fresh["weights"],"WEIGHTS_DID_CHANGE")
    return fresh


def process(model_file,cursor_file,freeze_utc,output_dir,token):
    parent=m.check_checkpoint(load_json(model_file))
    cursor=validate_cursor(load_json(cursor_file)
        if Path(cursor_file).is_file() else None)
    rows=m.fetch_real(token,maxpages=8)
    candidates,cutoff=eligible(rows,freeze_utc,cursor)
    out=Path(output_dir)
    require(not out.exists(),"OUT_DIR_MUST_BE_NEW_FOR_IMMUTABLE_RECEIPT")
    out.mkdir(parents=True)
    if len(candidates)<FUTURE_TOTAL:
        record=receipt({
            "schema":SCHEMA,
            "status":"HOLD_NOT_ENOUGH_POST_FREEZE_REAL_GITHUB_RUNS",
            "post_freeze_eligible":len(candidates),
            "needed":FUTURE_TOTAL,
            "model_sha256":parent["checkpoint_sha256"],
            "cutoff_utc":cutoff.isoformat(),
            "research_only":True,
            "production_authority":False,
        })
        (out/"result.json").write_text(json.dumps(record,indent=2)+"\n")
        return record
    chosen=candidates[:FUTURE_TOTAL]
    try:
        record=evaluate(parent,chosen)
    except ValueError as error:
        # A full 128-run cohort, if unsuitable, is consumed exactly once.
        # Still record the real run IDs and timestamps: we may not
        # silently cherry-pick more favorable outcomes after inspecting.
        record={
          "schema":SCHEMA,
          "status":"HOLD_UNSUITABLE_FROZEN_FORWARD_COHORT",
          "error_code":str(error)[:100],
          "parent_checkpoint_sha256":parent["checkpoint_sha256"],
          "test_last_id":chosen[-1][2],
          "test_last_utc":chosen[-1][3],
          "calibration_examples":FUTURE_CALIB_N,
          "evaluation_examples":FUTURE_TEST_N,
          "accepted":False,
          "research_only":True,"production_authority":False,
          "external_independent_validation":False,
        }
    record=receipt(record)
    (out/"result.json").write_text(json.dumps(record,indent=2)+"\n")
    next_cursor={
        "schema":STATE,
        "epoch":cursor["epoch"]+1 if cursor else 1,
        "previous_receipt_sha256":(
           cursor["receipt_sha256"] if cursor else None),
        "evaluation_receipt_sha256":record["receipt_sha256"],
        "last_target_utc":chosen[-1][3],
        "last_target_id":chosen[-1][2],
        "research_only":True,
        "production_authority":False,
    }
    next_cursor=receipt(next_cursor)
    (out/"cursor.json").write_text(json.dumps(next_cursor,indent=2)+"\n")
    if record["status"]=="PASS_PROSPECTIVE_RESEARCH_TEMPERATURE_GAIN":
        upgraded=new_parent(parent,record)
        (out/"checkpoint.json").write_text(
            json.dumps(upgraded,sort_keys=True,indent=2)+"\n")
    return record


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--checkpoint",required=True)
    p.add_argument("--cursor",required=True)
    p.add_argument("--freeze-utc",required=True)
    p.add_argument("--out-dir",required=True)
    args=p.parse_args()
    output=process(args.checkpoint,args.cursor,args.freeze_utc,args.out_dir,
                   __import__("os").environ.get("GH_TOKEN",""))
    print(json.dumps({
       "status":output["status"],
       "accepted":output.get("accepted",False),
       "receipt_sha256":output["receipt_sha256"],
       "post_freeze":output.get("post_freeze_eligible"),
       "production_authority":False
    },sort_keys=True))


if __name__=="__main__":
    main()
