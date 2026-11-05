#!/usr/bin/env python3
"""History-only calibration of JANUS Retro Lab predictions.

Prior finished experiments only. A held-out group of complete prior
experiments must show strong improvement; otherwise activation is refused.
Independent future OS CSPRNG bits have no known predictable structure.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

MIN_PRIOR_TRIALS=8
MIN_VALIDATION_BITS=768
GATE_P=1e-4
GATE_BRIER_IMPROVEMENT=.01


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def logit(p):
    p=min(.999999,max(.000001,float(p)))
    return math.log(p/(1-p))


def sigmoid(z):
    return 1/(1+math.exp(-max(-50,min(50,z))))


def exact_tail(n,k):
    return sum(math.comb(n,i) for i in range(k,n+1))/2**n


def read_finished_trial(folder):
    early=read(folder/"early.json")
    later=read(folder/"future.json")
    comp=read(folder/"comparison.json")
    if early["trial_id"]!=later["trial_id"] or comp["trial_id"]!=early["trial_id"]:
        raise RuntimeError("PAST_TRIAL_ID_FAIL")
    p1=early.get("raw_model_p1_probs",early["p1_model_probs"])
    bits=later["future_bits"]
    if len(p1)!=256 or len(bits)!=256 or any(z not in "01" for z in bits):
        raise RuntimeError("PAST_TRIAL_WRONG_SHAPE")
    payload=bytes.fromhex(later["target_payload_hex"])
    if hashlib.sha256(payload).hexdigest()!=later["target_sha256"]:
        raise RuntimeError("PAST_TRIAL_BAD_DIGEST")
    if later["future_generated_epoch_utc"]<early["issued_at_epoch_utc"]+120:
        raise RuntimeError("PAST_TRIAL_BAD_TIME")
    return early["trial_id"], early["issued_at_epoch_utc"], [
        (logit(p),int(bit)) for p,bit in zip(p1,bits)
    ]


def brier(rows,slope,bias):
    return sum((sigmoid(slope*x+bias)-y)**2 for x,y in rows)/len(rows)


def train(args):
    completed=[]
    for path in sorted(Path(args.history_root).glob("*/early.json")):
        directory=path.parent
        if (directory/"future.json").exists() and (directory/"comparison.json").exists():
            completed.append(read_finished_trial(directory))
    now=datetime.now(timezone.utc).timestamp()
    completed=[x for x in sorted(completed,key=lambda t:t[1]) if x[1]<now-1][-256:]
    report={
        "schema":"janus.retro.lab.history_only_calibration.v1",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "previous_completed_trials":len(completed),
        "previous_trial_ids":[x[0] for x in completed],
        "min_previous_trials_to_train":MIN_PRIOR_TRIALS,
        "only_past_completed_trials_used":True,
        "current_future_target_never_accessed":True,
        "status":"HOLD_INSUFFICIENT_PRIOR_TRIALS",
        "activated":False,
        "slope":1.,"bias":0.,
        "physical_backwards_channel_connected":False,
    }
    if len(completed)>=MIN_PRIOR_TRIALS:
        pivot=int(len(completed)*.7)
        trainset=[pair for trial in completed[:pivot] for pair in trial[2]]
        holdout=[pair for trial in completed[pivot:] for pair in trial[2]]
        choices=[(a,b) for a in (-2.,-1.,-.5,0.,.5,1.,2.)
                 for b in (-.5,-.25,0.,.25,.5)]
        best=min(choices,key=lambda ab:brier(trainset,*ab))
        a,b=best
        holdout_brier=brier(holdout,a,b)
        wins=sum((sigmoid(a*x+b)>=.5)==bool(y) for x,y in holdout)
        p=exact_tail(len(holdout),wins)
        permitted=(len(holdout)>=MIN_VALIDATION_BITS
                   and holdout_brier<=.25-GATE_BRIER_IMPROVEMENT
                   and p<GATE_P)
        report.update({
            "training_bits":len(trainset),
            "holdout_bits":len(holdout),
            "fitted_slope":a,"fitted_bias":b,
            "holdout_brier":round(holdout_brier,7),
            "holdout_uniform_brier":.25,
            "holdout_correct_bits":wins,
            "holdout_binomial_pvalue":p,
            "activation_gate":{
                "minimum_holdout_bits":MIN_VALIDATION_BITS,
                "required_brier_improvement":GATE_BRIER_IMPROVEMENT,
                "maximum_pvalue":GATE_P,
            },
            "status":"ACTIVATED_HISTORY_VALIDATED_CALIBRATION" if permitted else "HOLD_INSUFFICIENT_INDEPENDENT_GAIN",
            "activated":permitted,
            "slope":a if permitted else 1.,
            "bias":b if permitted else 0.,
        })
    save(args.output,report)
    print(json.dumps({k:v for k,v in report.items() if k!="previous_trial_ids"},indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history-root",required=True)
    p.add_argument("--output",required=True)
    train(p.parse_args())


if __name__=="__main__":
    main()
