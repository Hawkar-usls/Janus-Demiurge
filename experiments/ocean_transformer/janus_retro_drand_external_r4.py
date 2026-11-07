#!/usr/bin/env python3
"""JANUS R4: independent PUBLIC future beacon challenge on ordinary CPUs.

A 256-bit early forecast is frozen before a FUTURE drand Quicknet round.
Late data is BLS-signature verified by drand-client on another GitHub runner.

EARLY forecast in this minimal pilot is a fixed cryptographic hash-control,
not the JANUS trained model; it tests the physical/cryptographic provenance
of the later target, NOT whether a particular learned algorithm has ability.

The chain's scheduled signing time must be > 180 seconds after the early job
starts. The future job reads only a plan containing a round number and
forecast commitment; not the early bitstring. The signed beacon randomness
is SHA256(signature), published by external drand threshold signers.

GitHub timestamps are user-space assertions, not an external precommit seal.
BLS threshold security does not prove physically free future entropy.
No physically backward-time signal or quantum hardware is implemented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import secrets
import time

CHAIN_HASH="52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
CHAIN_ID="quicknet"
GENESIS_EPOCH=1692803367
PERIOD_SECONDS=3
MIN_FUTURE_GAP_SECONDS=180
FORECAST_NBITS=256


def req(x,reason):
    if not x:
        raise ValueError(reason)


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def safe_bits(bits):
    req(type(bits) is str and len(bits)==FORECAST_NBITS and
        set(bits)<=set("01"),"INVALID_EARLY_BITS")
    return bits


def round_release_epoch(roundnum):
    req(type(roundnum) is int and roundnum>0,"INVALID_BEACON_ROUND")
    return GENESIS_EPOCH+(roundnum-1)*PERIOD_SECONDS


def future_round(now):
    req(type(now) in (float,int) and math.isfinite(now),"INVALID_CLOCK")
    target=math.ceil((now+MIN_FUTURE_GAP_SECONDS-GENESIS_EPOCH)/
                     PERIOD_SECONDS)+1
    req(round_release_epoch(target)>=now+MIN_FUTURE_GAP_SECONDS,
        "FUTURE_ROUND_NOT_AT_LEAST_180_SECONDS_AHEAD")
    return target


def early(trial_id,now=None,nonce=None):
    req(type(trial_id) is str and trial_id.isdigit() and len(trial_id)<30,
        "INVALID_TRIAL_ID")
    now=float(time.time() if now is None else now)
    roundnum=future_round(now)
    nonce=nonce or secrets.token_hex(32)
    req(type(nonce) is str and len(nonce)==64 and
        all(c in "0123456789abcdef" for c in nonce),
        "INVALID_EARLY_NONCE")
    # Negative-control forecast only. No knowledge of a later signature.
    forecast=sha(
        f"JANUS|R4|HASH_CONTROL|{trial_id}|{roundnum}|{nonce}".encode("ascii")
    )
    bits="".join(f"{i:08b}" for i in bytes.fromhex(forecast))
    forecast_commit=sha(bits.encode("ascii"))
    plan={
        "schema":"janus.external_beacon.plan.r4",
        "trial_id":trial_id,
        "beacon_chain_id":CHAIN_ID,
        "beacon_chain_hash":CHAIN_HASH,
        "target_round":roundnum,
        "target_release_epoch":round_release_epoch(roundnum),
        "early_created_epoch":now,
        "forecast_sha256":forecast_commit,
        "minimum_gap_seconds":MIN_FUTURE_GAP_SECONDS,
        "forecast_string_not_in_plan":True,
        "actual_model_is_trained_janus":False
    }
    early_record={
        "schema":"janus.external_beacon.early.r4",
        "trial_id":trial_id,
        "forecast_bits":bits,
        "forecast_sha256":forecast_commit,
        "target_round":roundnum,
        "source":"SHA256_PRECOMMITTED_BASELINE_CONTROL__NOT_JANUS_TRAINED_MODEL",
        "created_epoch":now,
        "future_beacon_not_yet_available_by_schedule":True,
        "actual_future_entropy_known":False,
        "physical_retrocausality_proven":False
    }
    return early_record,plan


def binomial_p(n,k):
    req(type(n) is int and type(k) is int and 0<=k<=n<=256,
        "INVALID_BIT_SCORE")
    return sum(math.comb(n,j) for j in range(k,n+1))/(1<<n)


def score(e,p,f):
    req(type(e) is dict and type(p) is dict and type(f) is dict,
        "INVALID_RECORD_TYPE")
    req(e.get("schema")=="janus.external_beacon.early.r4" and
        p.get("schema")=="janus.external_beacon.plan.r4" and
        f.get("schema")=="janus.external_beacon.future.r4",
        "SCHEMA_MISMATCH")
    tid=e.get("trial_id")
    req(tid==p.get("trial_id")==f.get("trial_id"),"TRIAL_ID_MISMATCH")
    bits=safe_bits(e.get("forecast_bits"))
    req(sha(bits.encode("ascii"))==e.get("forecast_sha256")==
        p.get("forecast_sha256"),"EARLY_COMMITMENT_MISMATCH")
    r=p.get("target_round")
    req(type(r) is int and r==e.get("target_round")==f.get("target_round") and
        p.get("beacon_chain_hash")==CHAIN_HASH and
        f.get("beacon_chain_hash")==CHAIN_HASH and
        p.get("beacon_chain_id")==CHAIN_ID and
        f.get("beacon_chain_id")==CHAIN_ID,
        "ROUND_OR_CHAIN_CHANGED")
    now=e.get("created_epoch")
    req(type(now) in (int,float) and math.isfinite(now) and
        p.get("early_created_epoch")==now and
        p.get("target_release_epoch")==round_release_epoch(r) and
        round_release_epoch(r)>=now+MIN_FUTURE_GAP_SECONDS,
        "TIME_GATE_FAILED")
    digest=f.get("randomness")
    signature=f.get("signature")
    req(type(signature) is str and len(signature)==96 and
        all(c in "0123456789abcdef" for c in signature),
        "INVALID_QUICKNET_G1_SIGNATURE")
    req(type(digest) is str and len(digest)==64 and
        all(c in "0123456789abcdef" for c in digest) and
        sha(bytes.fromhex(signature))==digest,
        "SIGNATURE_TO_RANDOMNESS_SHA256_MISMATCH")
    req(f.get("cryptographic_bls_verification")==True and
        f.get("verified_by")=="drand-client@1.4.2" and
        f.get("read_early_forecast_bits")==False,
        "MISSING_BLS_VERIFICATION_EVIDENCE")
    retrieved=f.get("retrieved_epoch")
    req(type(retrieved) in (int,float) and math.isfinite(retrieved)
        and retrieved >= round_release_epoch(r),
        "BEACON_RETRIEVED_BEFORE_PUBLIC_RELEASE")
    future_bits="".join(f"{byte:08b}" for byte in bytes.fromhex(digest))
    hits=sum(x==y for x,y in zip(bits,future_bits))
    return {
        "schema":"janus.external_beacon.score.r4",
        "trial_id":tid,
        "target_round":r,
        "forecast_sha256":e["forecast_sha256"],
        "future_beacon_randomness":digest,
        "future_beacon_signature":signature,
        "correct_bits":hits,
        "total_bits":FORECAST_NBITS,
        "accuracy":hits/FORECAST_NBITS,
        "one_sided_exact_fair_bit_p":binomial_p(FORECAST_NBITS,hits),
        "identical_full_256_bit_forecast":hits==FORECAST_NBITS,
        "source":"SHA256_CONTROL_NOT_TRAINED_JANUS",
        "precommit_gap_seconds":round_release_epoch(r)-now,
        "future_independent_threshold_beacon_signature_verified_by_client":True,
        "external_public_future_randomness_replayable":True,
        "all_256_bits_scored":True,
        "no_postselection":True,
        "independent_physical_clock_and_outcome_attested":False,
        "externally_independent_hardware_entropy_certified":False,
        "physical_retrocausality_proven":False,
        "production_promotion":False,
        "interpretation":"Cryptographically verifiable future public beacon removes GitHub-local future-bit generation from this null pilot. One drand signature hash supplies 256 computationally pseudorandom bits, not independently measured physical bits. Hash-control is not trained JANUS. No physical backwards signal."
    }


def write_new(path,obj):
    target=Path(path)
    if target.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",
                      encoding="utf-8")


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="mode",required=True)
    x=sub.add_parser("early")
    x.add_argument("--trial-id",required=True)
    x.add_argument("--early-out",required=True)
    x.add_argument("--plan-out",required=True)
    y=sub.add_parser("score")
    y.add_argument("--early",required=True)
    y.add_argument("--plan",required=True)
    y.add_argument("--future",required=True)
    y.add_argument("--out",required=True)
    z=ap.parse_args()
    if z.mode=="early":
        e,p=early(z.trial_id)
        write_new(z.early_out,e)
        write_new(z.plan_out,p)
        print(json.dumps({"trial":z.trial_id,"round":p["target_round"],
                          "release_epoch":p["target_release_epoch"],
                          "initial_gap":p["target_release_epoch"]-p["early_created_epoch"]}))
    else:
        load=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
        result=score(load(z.early),load(z.plan),load(z.future))
        write_new(z.out,result)
        print(json.dumps({"correct_bits":result["correct_bits"],
                          "total_bits":256,"p":result["one_sided_exact_fair_bit_p"],
                          "physical_retrocausality_proven":False}))


if __name__=="__main__":
    main()
