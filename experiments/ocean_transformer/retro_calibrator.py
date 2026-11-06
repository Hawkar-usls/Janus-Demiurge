#!/usr/bin/env python3
"""JANUS Retro Lab v2: strict history-only calibrated prediction head.

Read *only* already-completed early/future/comparison triplets whose future
generation preceded the current trial's calibration cutoff. A new candidate
head is fitted on past trials and tested on a non-overlapping, chronological
four-trial holdout. Every 12 completed trials forms one immutable decision
epoch; no retesting of the same holdout after every additional trial.

Never alter primary raw predictions; activate optional secondary predictions
only after an independent strong gain relative to both random chance and the
raw model. This is statistical model governance, not retrocausal communication.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

TRIAL_BITS = 256
EPOCH_TRIALS = 12
EPOCH_HOLDOUT_TRIALS = 4
MAX_TRIALS = 384
PRIMARY_ALPHA_BUDGET = 0.0001
MIN_BRIER_GAIN = 0.01
MODEL_SHA = "2c38788e8468a98e9377fcdb9058c488ec3ec17dfacfbf553402a9b1a86cd4ca"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def digest(b):
    return hashlib.sha256(b).hexdigest()


def logit(p):
    p=max(1e-6,min(1-1e-6,float(p)))
    return math.log(p/(1-p))


def sigmoid(z):
    return 1/(1+math.exp(-max(-60.,min(60.,z))))


def upper_tail(n,k):
    if not (0<=k<=n):raise RuntimeError("BAD_BINOMIAL_SCORE")
    return sum(math.comb(n,i) for i in range(k,n+1))/2**n


def check_complete(folder,cutoff):
    early=read(folder/"early.json")
    late=read(folder/"future.json")
    comp=read(folder/"comparison.json")
    ids=[r["trial_id"] for r in (early,late,comp)]
    if len(set(ids))!=1 or ids[0]!=folder.name:
        raise RuntimeError("TRIAL_ID_MISMATCH_"+folder.name)
    if early.get("schema")!="janus.retro.lab.model_precommit.v1" or late.get("schema")!="janus.retro.lab.independent_future_rng.v1":
        raise RuntimeError("UNKNOWN_TRIAL_SCHEMA")
    if early.get("model_sha256")!=MODEL_SHA:
        raise RuntimeError("MIXED_MODEL_CHECKPOINTS_ARE_NOT_EXCHANGEABLE")
    pred=early["predicted_bits"]
    future=late["future_bits"]
    if len(pred)!=TRIAL_BITS or len(future)!=TRIAL_BITS or set(pred+future)-{"0","1"}:
        raise RuntimeError("INVALID_BITSTRING")
    if digest(pred.encode())!=early["predicted_256_bits_sha256"]:
        raise RuntimeError("EARLY_DIGEST_FAIL")
    payload=bytes.fromhex(late["target_payload_hex"])
    if len(payload)!=32 or digest(payload)!=late["target_sha256"] or \
       "".join(f"{b:08b}" for b in payload)!=future:
        raise RuntimeError("FUTURE_DIGEST_FAIL")
    if comp.get("unconditional_matching_bits")!=sum(a==b for a,b in zip(pred,future)) or \
       comp.get("total_bits")!=TRIAL_BITS or \
       comp.get("late_random_sha256")!=late["target_sha256"]:
        raise RuntimeError("COMPARISON_RECOMPUTE_FAIL")
    issued=float(early["issued_at_epoch_utc"])
    confirmed=float(late["receiver_commit_confirmed_epoch"])
    generated=float(late["future_generated_epoch_utc"])
    if not (issued<=confirmed and confirmed+120<=generated):
        raise RuntimeError("BROKEN_CHRONOLOGY")
    if generated>cutoff:
        return None
    raw=early.get("raw_model_p1_probs",early.get("p1_model_probs"))
    if len(raw)!=TRIAL_BITS or any(not math.isfinite(float(x)) or not 0<=float(x)<=1 for x in raw):
        raise RuntimeError("INVALID_MODEL_PROBABILITIES")
    rows=[(logit(p),int(y)) for p,y in zip(raw,future)]
    return {"trial_id":ids[0],"issued_epoch":issued,
            "finished_epoch":generated,
            "early_file_sha256":digest((folder/"early.json").read_bytes()),
            "late_file_sha256":digest((folder/"future.json").read_bytes()),
            "rows":rows}


def brier(rows,slope,bias):
    if not rows:raise RuntimeError("EMPTY_EVALUATION")
    return sum((sigmoid(slope*x+bias)-y)**2 for x,y in rows)/len(rows)


def report(args):
    as_of=args.as_of_epoch if args.as_of_epoch is not None else time.time()
    if as_of>time.time()+60:
        raise RuntimeError("CALIBRATION_CUTOFF_IN_FUTURE")
    root=Path(args.history_root)
    if not root.exists() or not root.is_dir():
        raise RuntimeError("MISSING_PRIOR_TRIAL_LEDGER")
    files=sorted(root.glob("*/early.json"))
    completed=[];incomplete=0;post_cutoff=0
    for path in files:
        folder=path.parent
        if not all((folder/f).exists() for f in ("early.json","future.json","comparison.json")):
            incomplete+=1
            continue
        trial=check_complete(folder,as_of)
        if trial is None:
            post_cutoff+=1
        else:
            completed.append(trial)
    completed.sort(key=lambda v:(v["finished_epoch"],v["trial_id"]))
    if len(completed)>MAX_TRIALS:
        # Bounded-size historic window without allowing overflow.
        completed=completed[-MAX_TRIALS:]
    ids=[t["trial_id"] for t in completed]
    if len(ids)!=len(set(ids)):
        raise RuntimeError("DUPLICATE_HISTORY_TRIALS")
    epochs=len(completed)//EPOCH_TRIALS
    calibration={
        "schema":"janus.retro.lab.history_only_calibration.v2",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "as_of_epoch":as_of,
        "previous_completed_trials":len(completed),
        "previous_trial_ids":ids,
        "incomplete_trial_folders_skipped":incomplete,
        "trials_finished_after_cutoff_skipped":post_cutoff,
        "min_previous_trials_to_train":EPOCH_TRIALS,
        "decision_epoch_completed":epochs,
        "immutable_epoch_trial_count":EPOCH_TRIALS,
        "chronological_holdout_trial_count":EPOCH_HOLDOUT_TRIALS,
        "raw_checkpoint_sha256":MODEL_SHA,
        "only_past_completed_trials_used":True,
        "current_future_target_never_accessed":True,
        "no_repeated_testing_within_same_epoch":True,
        "statistical_error_control":"disjoint validation block per 12 completed trials; geometric alpha spending across epochs",
        "status":"HOLD_INSUFFICIENT_PRIOR_TRIALS",
        "activated":False,
        "slope":1.0,
        "bias":0.0,
        "physical_backwards_channel_connected":False,
    }
    if epochs:
        n=epochs*EPOCH_TRIALS
        series=completed[:n]
        training=series[:-EPOCH_HOLDOUT_TRIALS]
        validation=series[-EPOCH_HOLDOUT_TRIALS:]
        if len(training)<8 or len(validation)!=EPOCH_HOLDOUT_TRIALS:
            raise RuntimeError("BAD_TRAIN_VALIDATION_PARTITION")
        train_rows=[row for t in training for row in t["rows"]]
        valid_rows=[row for t in validation for row in t["rows"]]
        candidates=[(a,b) for a in (-2.,-1.,-.5,0.,.5,1.,2.)
                    for b in (-.5,-.25,0.,.25,.5)]
        best=min(candidates,key=lambda q:brier(train_rows,*q))
        raw_score=brier(valid_rows,1.,0.)
        random_score=.25
        calibrated=brier(valid_rows,*best)
        wins=sum((sigmoid(best[0]*x+best[1])>=.5)==bool(y) for x,y in valid_rows)
        p=upper_tail(len(valid_rows),wins)
        alpha=PRIMARY_ALPHA_BUDGET/(2**epochs)
        improves=calibrated<=min(raw_score,random_score)-MIN_BRIER_GAIN
        permitted=bool(improves and p<alpha)
        calibration.update({
            "training_trial_ids":[x["trial_id"] for x in training],
            "validation_trial_ids":[x["trial_id"] for x in validation],
            "training_bits":len(train_rows),
            "holdout_bits":len(valid_rows),
            "fitted_slope":best[0],
            "fitted_bias":best[1],
            "holdout_brier_raw_model":round(raw_score,8),
            "holdout_brier_uniform_0_5":random_score,
            "holdout_brier_candidate":round(calibrated,8),
            "holdout_brier_required_max":round(min(raw_score,random_score)-MIN_BRIER_GAIN,8),
            "holdout_correct_bits":wins,
            "holdout_one_sided_binomial_pvalue":p,
            "per_epoch_significance_alpha":alpha,
            "source_trials_used_for_candidate":len(training),
            "required_minimum_brier_gain":MIN_BRIER_GAIN,
            "status":"ACTIVATED_HISTORY_VALIDATED_CALIBRATION" if permitted else "HOLD_NO_INDEPENDENT_GAIN",
            "activated":permitted,
            "slope":best[0] if permitted else 1.,
            "bias":best[1] if permitted else 0.,
        })
    save(args.output,calibration)
    print(json.dumps({k:v for k,v in calibration.items() if k not in ("previous_trial_ids","training_trial_ids","validation_trial_ids")},indent=2))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--history-root",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--as-of-epoch",type=float,default=None,
                        help="Cutoff fixed by the runner before this calibration begins")
    args=parser.parse_args()
    report(args)


if __name__=="__main__":
    main()
