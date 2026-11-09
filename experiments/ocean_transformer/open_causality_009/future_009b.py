#!/usr/bin/env python3
"""OPEN-FUTURE-009B: Frozen JANUS model predicts 128 *distinct* future drand rounds.

No actual future beacon may enter PREPARE. Actual BLS signatures of all fixed
rounds MUST be checked in the separate drand-client verification program.
This is a software negative-control for time-ordered predictions, not a
physical future-to-past communication experiment.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys

OCEAN=Path(__file__).resolve().parents[1]
if str(OCEAN) not in sys.path: sys.path.insert(0,str(OCEAN))
from zeno_retro_control import exact_two_sided_binomial_p
import blind_drand_pilot as prior

SCHEMA="janus.ocean.open_future_009b.v1"
CHAIN=prior.CHAIN_HASH
GENESIS=prior.QUICKNET_GENESIS_UNIX
PERIOD=3
COUNT=128
SPACING_SEC=60

def canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(canon(x)).hexdigest()

def utc(x):
    v=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
    if v.tzinfo is None or v.utcoffset()!=dt.timedelta(0):raise ValueError("UTC_REQUIRED")
    return v

def time_for_round(n):
    return GENESIS+(n-1)*PERIOD

def round_at_or_after(epoch):
    # Round 1 released exactly at GENESIS.
    return max(1,(int(epoch)-GENESIS+PERIOD-1)//PERIOD+1)

def fixed_rounds(target_date):
    timestamp=dt.datetime.combine(target_date,dt.time(hour=8),tzinfo=dt.timezone.utc).timestamp()
    start=round_at_or_after(timestamp)
    return [start+i*SPACING_SEC//PERIOD for i in range(COUNT)]

def write_once(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        f.write(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n")

def valid_prior(latest):
    if (not isinstance(latest,dict) or latest.get("chain_hash")!=CHAIN
        or latest.get("genesis_time")!=GENESIS or latest.get("period")!=PERIOD
        or latest.get("signature_verified_by_pinned_client") is not True
        or type(latest.get("round")) is not int):
        raise ValueError("LATEST_DRAND_BEACON_NOT_BLS_VERIFIED")
    return latest["round"]

def predict(model,rounds):
    import torch
    import torch.nn.functional as F
    import ocean_future_model_prediction as frozen
    import measurement_priors as priors
    tokens=[priors.model_tokens(*frozen.tokens_for_public_round(r,i)) for i,r in enumerate(rounds)]
    with torch.no_grad():
        logits,_=model(torch.tensor(tokens,dtype=torch.long))
        probs=F.softmax(logits[:,-1,:2],dim=-1)[:,1].tolist()
    if len(probs)!=len(rounds) or any(not math.isfinite(p) or not 0<=p<=1 for p in probs):
        raise ValueError("INVALID_FROZEN_MODEL_OUTPUT")
    return [round(p,8) for p in probs]

def prepare(date,latest,model,checkpoint_sha,report_sha,now):
    previous=valid_prior(latest)
    rounds=fixed_rounds(date)
    if not dt.timedelta(hours=6)<(dt.datetime.fromtimestamp(time_for_round(rounds[0]),dt.timezone.utc)-now):
        raise ValueError("DRAND_TARGETS_INSUFFICIENTLY_FUTURE")
    if previous>=rounds[0]:raise ValueError("FUTURE_ROUND_ALREADY_KNOWN")
    probabilities=predict(model,rounds)
    data={
        "schema":SCHEMA,"lane":"OPEN-FUTURE-009B","phase":"EARLY_PRECOMMIT",
        "timestamp_self_reported":now.isoformat(),
        "target_date":date.isoformat(),"n_distinct_rounds":COUNT,
        "quicknet_hash":CHAIN,"quicknet_genesis_unix":GENESIS,"quicknet_period_seconds":PERIOD,
        "target_rounds":rounds,"first_release_unix":time_for_round(rounds[0]),
        "last_release_unix":time_for_round(rounds[-1]),
        "latest_bls_verified_round_at_preparation":previous,
        "forecast_model":"HISTORIC_FROZEN_JANUS_TINY_TRANSFORMER_004_BORN_TRAINED_NOT_DRAND_TRAINED",
        "frozen_checkpoint_sha256":checkpoint_sha,
        "frozen_training_report_sha256":report_sha,
        "checkpoint_artifact_id":13663149173,
        "forecast_encoding":"MODEL_PUBLIC_ROUND_AND_POSITION_ONLY",
        "probability_1":probabilities,
        "bits":["1" if p>=.5 else "0" for p in probabilities],
        "future_results_seen":False,"postselection_allowed":False,
        "training_after_precommit":False,
        "no_physical_receiver":True,"retrocausality_proven":False,
        "workflow_run_id":os.environ.get("GITHUB_RUN_ID","OFFLINE_TEST"),
    }
    return {"payload":data,"sha256":digest(data)}

def assess(precommit,signed_beacons,github_timestamp,now):
    p=precommit.get("payload")
    if not isinstance(p,dict) or precommit.get("sha256")!=digest(p) or p.get("lane")!="OPEN-FUTURE-009B":
        raise ValueError("FROZEN_MODEL_FORECAST_HASH_MISMATCH")
    rounds=fixed_rounds(dt.date.fromisoformat(p["target_date"]))
    if (p.get("target_rounds")!=rounds or p.get("n_distinct_rounds")!=COUNT or
        p.get("quicknet_hash")!=CHAIN or p.get("future_results_seen") is not False or
        p.get("postselection_allowed") is not False or p.get("training_after_precommit") is not False):
        raise ValueError("FUTURE_ROUNDS_OR_NO_LEAK_CONTRACT_CHANGED")
    if utc(github_timestamp).timestamp()>=time_for_round(rounds[0])-60:
        raise ValueError("INDEPENDENT_GITHUB_ARTIFACT_NOT_BEFORE_FUTURE_ROUNDS")
    if now.timestamp()<time_for_round(rounds[-1])+15:
        raise ValueError("ALL_FUTURE_ROUNDS_NOT_YET_PUBLISHED")
    if (signed_beacons.get("chain_hash")!=CHAIN or
        signed_beacons.get("signature_verification")!="DRAND_CLIENT_BLS_PINNED" or
        signed_beacons.get("target_rounds")!=rounds or
        signed_beacons.get("verifier_package")!="drand-client@1.4.2"):
        raise ValueError("UNVERIFIED_FUTURE_BEACON_RECEIPT")
    signed=signed_beacons.get("beacons")
    if not isinstance(signed,list) or len(signed)!=COUNT:
        raise ValueError("MISSING_FUTURE_ROUNDS_NO_POSTSELECTION")
    labels=[]
    for r,beacon in zip(rounds,signed):
        if (beacon.get("round")!=r or beacon.get("signature_verified_by_pinned_client") is not True
             or not isinstance(beacon.get("randomness"),str) or len(beacon["randomness"])!=64):
            raise ValueError("INVALID_OR_WRONG_FUTURE_ROUND")
        sig=beacon.get("signature")
        try:
            derived=hashlib.sha256(bytes.fromhex(sig)).hexdigest()
        except (TypeError,ValueError):
            raise ValueError("INVALID_SIGNED_BEACON_SIGNATURE_FORMAT") from None
        if derived!=beacon["randomness"]:
            raise ValueError("DRAND_SIGNATURE_RANDOMNESS_DIGEST_MISMATCH")
        labels.append(int(beacon["randomness"][0],16)>>3)  # Most-significant bit of SHA-256(signature)
    predictions=p.get("bits")
    probs=p.get("probability_1")
    if (not isinstance(predictions,list) or len(predictions)!=COUNT or
        not isinstance(probs,list) or len(probs)!=COUNT or
        any(type(x) not in (int,float) or not 0<=x<=1 for x in probs) or
        predictions!=["1" if x>=.5 else "0" for x in probs]):
        raise ValueError("INVALID_FROZEN_128_MODEL_PREDICTIONS")
    correct=sum(int(b)==label for b,label in zip(predictions,labels))
    brier=sum((pp-label)**2 for pp,label in zip(probs,labels))/COUNT
    pval=exact_two_sided_binomial_p(correct,COUNT)
    return {
        "schema":SCHEMA,"lane":"OPEN-FUTURE-009B",
        "status":"ALL_SIGNED_INDEPENDENT_DRAND_ROUNDS_SCORED",
        "precommitted_sha256":precommit["sha256"],
        "github_server_artifact_timestamp":github_timestamp,
        "n_distinct_rounds":COUNT,"target_date":p["target_date"],
        "beacon_receipt_sha256":digest(signed_beacons),
        "matches":correct,"accuracy":round(correct/COUNT,8),
        "exact_two_sided_binomial_p":pval,
        "brier":round(brier,8),"fair_baseline_brier":0.25,
        "better_brier_than_fair":brier<.25,
        "time_separation_externally_timestamped":True,
        "randomness_bls_verified":True,
        "no_late_outcomes_filtered":True,
        "real_physical_early_receiver":False,"retrocausality_proven":False,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=("prepare","assess"))
    ap.add_argument("--date",required=True)
    ap.add_argument("--latest")
    ap.add_argument("--checkpoint")
    ap.add_argument("--training-report")
    ap.add_argument("--precommit")
    ap.add_argument("--beacons")
    ap.add_argument("--artifact-created-at")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    date=dt.date.fromisoformat(args.date)
    if args.phase=="prepare":
        if not (args.latest and args.checkpoint and args.training_report):ap.error("prepare needs historical checkpoint and BLS latest")
        import ocean_future_model_prediction as frozen
        model,ckpt_sha,report_sha=frozen.validate_source_checkpoint(args.checkpoint,args.training_report)
        output=prepare(date,json.loads(Path(args.latest).read_text()),model,ckpt_sha,report_sha,dt.datetime.now(dt.timezone.utc))
    else:
        if not (args.precommit and args.beacons and args.artifact_created_at):ap.error("assess needs precommit, BLS-verified beacons, github server timestamp")
        output=assess(json.loads(Path(args.precommit).read_text()),
                      json.loads(Path(args.beacons).read_text()),args.artifact_created_at,dt.datetime.now(dt.timezone.utc))
    write_once(args.output,output)
    print(json.dumps({"status":output.get("status","EARLY_PRECOMMIT"),"sha256":digest(output),
                      "date":args.date,"retrocausality_proven":False}))
if __name__=="__main__":main()
