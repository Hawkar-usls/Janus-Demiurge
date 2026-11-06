#!/usr/bin/env python3
"""JANUS Retro Lab: genuinely early predictions versus future OS randomness.

Uses the real JanusTinyTransformer trained in JANUS Ocean v3 (40 rivers).
Early bits are fixed before late random bits are sampled. A PCTC-inspired
postselection toy is included only to diagnose selection bias, NOT to claim
physical closed timelike curves, quantum hardware, or backward signaling.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import secrets
import time

N_BITS = 256
PRIOR_RUN = 42125238873
PRIOR_SNAPSHOT_SHA = "1d7259bd6429fe5f29d2ad573c05822f8c8ed6686a254e643b32be8c9d56e1cd"
PRIOR_MODEL_SHA = "2c38788e8468a98e9377fcdb9058c488ec3ec17dfacfbf553402a9b1a86cd4ca"


def save(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bits_of(data):
    return "".join(f"{byte:08b}" for byte in data)


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def prediction(args):
    import torch
    from janus_model.model import JanusTinyTransformer, JanusModelConfig, parameter_count
    import real_weather_forecast as weather
    torch.set_num_threads(1)
    if filehash(args.model) != PRIOR_MODEL_SHA or filehash(args.snapshot) != PRIOR_SNAPSHOT_SHA:
        raise RuntimeError("WRONG_PRETRAINED_MODEL_OR_DATA_SHA")
    ckpt = torch.load(args.model, map_location="cpu", weights_only=True)
    if ckpt["source_sha256"] != PRIOR_SNAPSHOT_SHA:
        raise RuntimeError("WEATHER_CHECKPOINT_PROVENANCE_MISMATCH")
    cfg = JanusModelConfig.from_dict(ckpt["config"])
    if cfg.context_length != 48 or cfg.vocab_size != 122:
        raise RuntimeError("UNEXPECTED_JANUS_WEATHER_MODEL_CONFIG")
    model = JanusTinyTransformer(cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()
    past = load(args.snapshot)["kyiv"]["temp"]
    values = torch.tensor(past, dtype=torch.float32)
    cutoff = int(len(past) * .70)
    if cutoff < 1000:
        raise RuntimeError("INSUFFICIENT_HISTORICAL_CONTEXT")
    inputs = []
    for i in range(N_BITS):
        token = hashlib.sha256((args.trial_id+"|context|"+str(i)).encode()).digest()
        start = int.from_bytes(token[:8], "big") % (cutoff-24)
        inputs.append(weather.allstar_weather_features(values[start:start+24]))
    contexts = torch.stack(inputs)
    probs = []
    with torch.no_grad():
        for k in range(0, N_BITS, 64):
            logits, _ = model(contexts[k:k+64])
            classes = torch.softmax(logits[:, -1, :61].float(), dim=-1)
            probs.extend(float(x) for x in classes[:, 1::2].sum(dim=-1))
    early_bits = "".join("1" if p >= .5 else "0" for p in probs)
    # Only completed PREVIOUS trials may update a calibration head.
    # The primary early bit string remains the raw pretrained model output.
    cal = load(args.calibration) if args.calibration else {
        "status": "NO_PRIOR_HISTORY_AVAILABLE", "activated": False,
        "previous_completed_trials": 0,
    }
    if cal.get("activated", False):
        slope, bias = cal["slope"], cal["bias"]
        def calibrate(q):
            q = min(.999999, max(.000001, float(q)))
            z = slope * math.log(q / (1-q)) + bias
            return 1/(1+math.exp(-max(-50, min(50, z))))
        probs_calibrated = [calibrate(p) for p in probs]
        secondary_bits = "".join("1" if q >= .5 else "0" for q in probs_calibrated)
    else:
        probs_calibrated = probs
        secondary_bits = None
    epoch = time.time()
    record = {
        "schema": "janus.retro.lab.model_precommit.v1",
        "trial_id": args.trial_id,
        "issued_at_epoch_utc": epoch,
        "issued_at_utc": utc(epoch),
        "number_bits": N_BITS,
        "predicted_bits": early_bits,
        "predicted_256_bits_sha256": hashlib.sha256(early_bits.encode()).hexdigest(),
        "p1_model_probs": [round(x, 7) for x in probs],
        "raw_model_p1_probs": [round(x, 7) for x in probs],
        "secondary_calibrated_predicted_bits": secondary_bits,
        "secondary_calibrated_p1_probs": [round(x,7) for x in probs_calibrated] if secondary_bits else None,
        "prior_only_calibration": {
            "status": cal.get("status"),
            "activated": bool(cal.get("activated",False)),
            "past_completed_trials": cal.get("previous_completed_trials",0),
            "source_sha256": filehash(args.calibration) if args.calibration else None,
        },
        "source_trained_JANUS_run": PRIOR_RUN,
        "model": "JanusTinyTransformer actual trained 40-river v3 checkpoint",
        "model_parameters": parameter_count(model),
        "model_sha256": PRIOR_MODEL_SHA,
        "source_snapshot_sha256": PRIOR_SNAPSHOT_SHA,
        "context_rule": "SHA256(trial_id|context|index) selects past ERA5 windows; first/second weather-model output parity is a preregistered random-bit guess",
        "future_target_not_generated_yet": True,
        "real_physical_retrocausal_interface": False,
        "primary_endpoint": "unconditional 256 bit match count, one-sided exact binomial upper tail versus H0 p=0.5",
        "protocol": "EARLY_PRECOMMIT_BEFORE_FUTURE_OS_CSPRNG"
    }
    save(args.output, record)
    print(json.dumps({
        "stage":"EARLY_PREDICTION_FIXED",
        "trial": args.trial_id,
        "prediction_sha256": record["predicted_256_bits_sha256"],
        "model_sha256": PRIOR_MODEL_SHA,
        "issued_at_utc": record["issued_at_utc"]
    }, indent=2))


def future(args):
    confirmed = args.receiver_commit_confirmed_epoch
    boundary = confirmed + 120.
    now = time.time()
    if now < boundary:
        time.sleep(boundary-now)
    # Critical: no earlier prediction file is accessed before this operation.
    payload = secrets.token_bytes(32)
    generated = time.time()
    if generated < boundary:
        raise RuntimeError("VIOLATED_TWO_MINUTE_BOUNDARY")
    row = {
        "schema": "janus.retro.lab.independent_future_rng.v1",
        "trial_id": args.trial_id,
        "receiver_commit_confirmed_epoch": confirmed,
        "future_generated_epoch_utc": generated,
        "future_generated_utc": utc(generated),
        "minimum_separation_seconds": 120,
        "target_payload_hex": payload.hex(),
        "target_sha256": hashlib.sha256(payload).hexdigest(),
        "future_bits": bits_of(payload),
        "source_of_randomness": "secrets.token_bytes on GitHub hosted OS",
        "earlier_prediction_not_read_before_generation": True,
        "physical_backward_channel_connected": False,
    }
    save(args.output, row)
    print(json.dumps({"stage":"FUTURE_OS_RANDOM_CREATED", "target_sha256":row["target_sha256"],
                      "utc":row["future_generated_utc"]}, indent=2))


def binomial_upper_tail(n, score):
    return sum(math.comb(n, k) for k in range(score, n+1)) / (2**n)


def compare(args):
    early = load(args.early)
    later = load(args.later)
    if early.get("schema")!="janus.retro.lab.model_precommit.v1" or later.get("schema")!="janus.retro.lab.independent_future_rng.v1":
        raise RuntimeError("REJECT_UNKNOWN_SCHEMA")
    if early["trial_id"] != later["trial_id"]:
        raise RuntimeError("TRIAL_ID_MISMATCH")
    a,b = early["predicted_bits"],later["future_bits"]
    if len(a)!=N_BITS or len(b)!=N_BITS or set(a+b) - {"0","1"}:
        raise RuntimeError("BAD_BINARY_LENGTH_OR_CONTENT")
    if hashlib.sha256(a.encode()).hexdigest()!=early["predicted_256_bits_sha256"]:
        raise RuntimeError("EARLY_SHA_INVALID")
    decoded=bytes.fromhex(later["target_payload_hex"])
    if bits_of(decoded)!=b or hashlib.sha256(decoded).hexdigest()!=later["target_sha256"]:
        raise RuntimeError("FUTURE_PAYLOAD_SHA_INVALID")
    confirmed=later["receiver_commit_confirmed_epoch"]
    future_epoch=later["future_generated_epoch_utc"]
    if confirmed < early["issued_at_epoch_utc"] or future_epoch < confirmed+120:
        raise RuntimeError("TIME_ORDER_ERROR")
    ncorrect=sum(x==y for x,y in zip(a,b))
    p1=early["p1_model_probs"]
    if len(p1)!=N_BITS or any(not 0<=p<=1 for p in p1):
        raise RuntimeError("INVALID_EARLY_CONFIDENCE")
    brier=sum((float(p)-int(y))**2 for p,y in zip(p1,b))/N_BITS
    # A complete eight-bit match is much rarer than a bit match, but expected
    # to occur randomly once per 256 independent guesses. This statistic is
    # always computed over ALL 32 precommitted bytes, never selected successes.
    byte_count=N_BITS//8
    matching_byte_indices=[i for i in range(byte_count)
                           if a[8*i:8*(i+1)]==b[8*i:8*(i+1)]]
    matching_byte_hex=[f"{int(a[8*i:8*(i+1)],2):02x}"
                       for i in matching_byte_indices]
    byte_hits=len(matching_byte_indices)
    byte_right_tail=(1.0 if byte_hits==0 else
                     sum(math.comb(byte_count,j)
                         * (1/256)**j * (255/256)**(byte_count-j)
                         for j in range(byte_hits,byte_count+1)))
    # Postselection-inspired classical statistical control:
    # early A and future choice X are unrelated; final B=A XOR X.
    # If we keep only B=0, conditional agreement A=X is 100%.
    # It is physically nonretrocausal; postselection result known later only.
    selection={
        "name":"IDEALIZED_BELL_Z_POSTSELECTION_STATISTICS_CLASSICAL_TOY",
        "rule":"retain only trials where later B=A XOR X is 0",
        "accepted":ncorrect, "total":N_BITS,
        "fraction_accepted":round(ncorrect/N_BITS,6),
        "selected_accuracy":1. if ncorrect else None,
        "all_records_unconditional_accuracy":round(ncorrect/N_BITS,6),
        "note":"Perfect conditional agreement is selection bias, not receipt of information at the earlier time."
    }
    secondary = None
    if early.get("secondary_calibrated_predicted_bits") is not None:
        adjusted = early["secondary_calibrated_predicted_bits"]
        if len(adjusted) != N_BITS or set(adjusted)-{"0","1"}:
            raise RuntimeError("BAD_SECONDARY_CALIBRATED_PREDICTIONS")
        sc = sum(a==b for a,b in zip(adjusted,b))
        ps = early["secondary_calibrated_p1_probs"]
        if len(ps)!=N_BITS: raise RuntimeError("BAD_SECONDARY_PROBABILITIES")
        secondary={
            "role":"SECONDARY_EXPLORATORY_NOT_PRIMARY_PVALUE",
            "correct_bits":sc,
            "accuracy":round(sc/N_BITS,7),
            "one_sided_binomial_pvalue":binomial_upper_tail(N_BITS,sc),
            "brier":round(sum((float(p)-int(bit))**2 for p,bit in zip(ps,b))/N_BITS,8),
            "prior_history_only_head":early.get("prior_only_calibration"),
        }
    result={
        "schema":"janus.retro.lab.result.v1",
        "trial_id":early["trial_id"],
        "real_trained_transformer_source_run":PRIOR_RUN,
        "early_model_sha256":PRIOR_MODEL_SHA,
        "early_commit_content_sha256":filehash(args.early),
        "predicted_bits_sha256":early["predicted_256_bits_sha256"],
        "late_random_sha256":later["target_sha256"],
        "full_256_bit_exact_match":a==b,
        "unconditional_full_byte_matches":{
            "count":byte_hits,
            "total_bytes":byte_count,
            "indices_zero_based":matching_byte_indices,
            "matched_byte_hex":matching_byte_hex,
            "expected_random_matches":byte_count/256,
            "null_exact_byte_match_probability":1/256,
            "exact_binomial_one_sided_pvalue":byte_right_tail,
            "full_population_included":True,
            "operational_retrocausal_byte_message_proven":False,
            "note":"A matched byte from 32 independent guesses can occur by chance and cannot be selected retroactively as a channel."
        },
        "unconditional_matching_bits":ncorrect,
        "total_bits":N_BITS,
        "unconditional_accuracy":round(ncorrect/N_BITS,7),
        "exact_one_sided_binomial_pvalue":binomial_upper_tail(N_BITS,ncorrect),
        "probabilistic_brier":round(brier,8),
        "uniform_prior_baseline_brier":0.25,
        "seconds_between_commit_confirmation_and_future_generation":round(future_epoch-confirmed,6),
        "postselection_control":selection,
        "secondary_history_calibrated_performance":secondary,
        "history_calibration_gate":early.get("prior_only_calibration"),
        "null_hypothesis":"OS cryptographic random future target is independent of early model prediction",
        "physical_retrocausality_proven":False,
        "physical_channel_connected":False,
        "research_status":"INDEPENDENT_FUTURE_RNG_BLIND_TEST_COMPLETE__NOT_A_PHYSICAL_BACKWARD_CHANNEL",
        "warning":"Any unexpected success requires independent replication, timestamp and leakage audit before physical claims."
    }
    save(args.output,result)
    print(json.dumps(result,indent=2))


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("predict")
    a.add_argument("--trial-id",required=True);a.add_argument("--model",required=True)
    a.add_argument("--snapshot",required=True);a.add_argument("--output",required=True)
    a.add_argument("--calibration",required=False,default=None)
    b=sub.add_parser("future")
    b.add_argument("--trial-id",required=True)
    b.add_argument("--receiver-commit-confirmed-epoch",type=float,required=True)
    b.add_argument("--output",required=True)
    c=sub.add_parser("compare")
    c.add_argument("--early",required=True);c.add_argument("--later",required=True)
    c.add_argument("--output",required=True)
    args=p.parse_args()
    if args.mode=="predict":prediction(args)
    elif args.mode=="future":future(args)
    else:compare(args)


if __name__ == "__main__":
    main()
