#!/usr/bin/env python3
"""OPEN-009F exact no-signalling diagnostic with likelihood-ratio e-process.

If the late bits Y_i are independent fair random variables conditional on
all pre-choice history H, any predictable probability p_i(H) has
E[2*P_model(Y_i|H)|H]=1. Therefore E_t=product_{i<=t} 2*P_model(Y_i|H)
is a nonnegative martingale under H0 and P(max_t E_t >= 1/alpha)<=alpha.
This is a mathematical null test, not a retrocausal emulator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def write_once(path,obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x") as f:
        json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def bits(raw):
    return [(v>>i)&1 for v in raw for i in range(7,-1,-1)]


def mle_conditional_markov(data):
    """Maximum likelihood conditional Bernoulli transition estimates."""
    counts=[[0,0],[0,0]]
    for a,b in zip(data[:-1],data[1:]):
        counts[a][b]+=1
    if any(sum(r)==0 for r in counts):
        raise ValueError("UNIDENTIFIED_MARKOV_TRANSITION")
    # Ordinary MLE; no smoothing prior, invented advantage, or tuned threshold.
    p_one=[r[1]/sum(r) for r in counts]
    if any(not 0<p<1 for p in p_one):
        raise ValueError("DEGENERATE_MLE_OUT_OF_OPEN_INTERVAL")
    return counts,p_one


def evaluate(probs, actual):
    if len(probs)!=len(actual):
        raise ValueError("LENGTH_MISMATCH")
    log_e=0.0
    max_log_e=0.0
    brier=0.0
    correct=0
    for p,y in zip(probs,actual):
        if not 0<p<1 or y not in (0,1):
            raise ValueError("BAD_PROBABILITY_OR_BIT")
        log_e+=math.log(2*(p if y else 1-p))
        max_log_e=max(max_log_e,log_e)
        brier+=(p-y)**2
        correct+=int((p>=0.5)==y)
    return {"n":len(actual),"matches":correct,"accuracy":correct/len(actual),
            "brier":brier/len(actual), "log_e_final":log_e,
            "log_e_running_max":max_log_e,
            "anytime_valid_p_upper_bound":min(1.0,math.exp(-max_log_e)),
            "significance_rule":"e_process_running_max >= 1000 for alpha=0.001",
            "threshold_crossed":max_log_e>=math.log(1000)}


def main(out):
    # Phase 1: model learned only from before the late-choice phase.
    training=bits(secrets.token_bytes(512))
    counts,p_one=mle_conditional_markov(training)
    # Context is known and generated *before* the late choices; it is not
    # secretly chosen based on outcomes. Conditional source is independent.
    contexts=bits(secrets.token_bytes(128))
    p=[p_one[x] for x in contexts]
    early={"schema":"janus.open009f.exact_independence_prechoice.v1",
           "n":1024,
           "n_train":4096,
           "frozen_model":"Conditional Bernoulli maximum-likelihood, transition counts",
           "transition_counts":counts,
           "p_one_given_prev0_prev1":p_one,
           "forecasts_p_one":p,
           "context_bits":contexts,
           "late_bits_generated":False,
           "unconditional_null":"Y_i iid Bernoulli(1/2), independent of early sigma-field",
           "no_signal_theorem":"For predictable p_i, E[2*P_model(Y_i|history)|history]=1",
           "future_correlated_data_excluded":True}
    write_once(out/"no_signalling_early_009f.json",early)
    # Phase 2, generated only after separate early evidence has been fsynced.
    late_raw=secrets.token_bytes(128)
    actual=bits(late_raw)
    report={"schema":"janus.open009f.exact_independence_result.v1",
            "early_sha256":sha(early),
            "late_bits_sha256":hashlib.sha256(late_raw).hexdigest(),
            "result":evaluate(p,actual),
            "late_bits_hex":late_raw.hex(),
            "source":"LOCAL_OS_CSPRNG_INDEPENDENCE_DIAGNOSTIC",
            "original_janustinytransformer_used":False,
            "physically_independent_late_free_choice":False,
            "external_timestamps_obtained":False,
            "experimental_retrocausality_proven":False}
    write_once(out/"no_signalling_result_009f.json",report)
    print("NO_SIGNALLING_009F "+json.dumps(report["result"],sort_keys=True),flush=True)


if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--out-dir",required=True)
    args=a.parse_args()
    main(Path(args.out_dir))
