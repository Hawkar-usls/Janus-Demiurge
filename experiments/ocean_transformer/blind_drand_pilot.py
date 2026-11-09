#!/usr/bin/env python3
"""JANUS-ZENO-TEMPORAL-003: two-stage blind *null* pilot with future drand.

PREPARE: Freeze OS-random 256 early bits and the target future Quicknet round
into a SHA-bound GitHub Actions artifact BEFORE that round's publication.

ASSESS: Only later, read exactly that round from drand-client with cryptographic
signature verification and the official pinned chain public key. Require the
GitHub artifact creation timestamp to precede the future round's public time.
Compare all 256 bits; no conditional filtering, retries, training, or backdated
modification. No physical receiver or retrocausal quantum channel is involved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import secrets
import time
from pathlib import Path

from zeno_retro_control import exact_two_sided_binomial_p

SCHEMA="janus.ocean.blin d_drand_v1".replace(" ","")
EXPERIMENT_ID="JANUS-ZENO-TEMPORAL-003"
N_BITS=256
CHAIN_HASH="52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
QUICKNET_PERIOD_SECONDS=3
QUICKNET_GENESIS_UNIX=1692803367
FUTURE_ROUND_OFFSET=45

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def receipt_hash(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_once(path,obj):
    p=Path(path)
    if p.exists():
        raise ValueError("REFUSE_OVERWRITE_EARLY_OR_LATE_EVIDENCE")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def _valid_bits(bits):
    return isinstance(bits,str) and len(bits)==N_BITS and not (set(bits)-{"0","1"})

def prepare(latest:dict,when_ms:int,early_bits:str=None):
    if (not isinstance(latest,dict) or latest.get("chain_hash")!=CHAIN_HASH
        or latest.get("genesis_time")!=QUICKNET_GENESIS_UNIX
        or latest.get("period")!=QUICKNET_PERIOD_SECONDS
        or latest.get("signature_verified_by_pinned_client") is not True):
        raise ValueError("UNTRUSTED_DRAND_CHAIN_INFO")
    latest_round=latest.get("round")
    if type(latest_round) is not int or latest_round<1:
        raise ValueError("INVALID_PUBLISHED_LATEST_ROUND")
    if type(when_ms) is not int or when_ms<1:
        raise ValueError("INVALID_EARLY_WALLCLOCK")
    target_round=latest_round+FUTURE_ROUND_OFFSET
    published_at_ms=(QUICKNET_GENESIS_UNIX+(target_round-1)*QUICKNET_PERIOD_SECONDS)*1000
    if not (90000 <= published_at_ms-when_ms <= 180000):
        raise ValueError("EARLY_BEACON_NOT_SUFFICIENTLY_IN_FUTURE")
    if early_bits is None:
        early_bits="".join(f"{b:08b}" for b in secrets.token_bytes(N_BITS//8))
    if not _valid_bits(early_bits):
        raise ValueError("INVALID_EARLY_BITS")
    obj={
        "schema":SCHEMA,"experiment_id":EXPERIMENT_ID,"phase":"EARLY_PRECOMMIT",
        "source":"OS_CSPRNG_EARLY_BITS",
        "early_bits":early_bits,
        "early_recorded_at_unix_ms":when_ms,
        "n_bits":N_BITS,
        "beacon_chain_hash":CHAIN_HASH,
        "beacon_network":"quicknet",
        "beacon_period_seconds":QUICKNET_PERIOD_SECONDS,
        "beacon_genesis_unix":QUICKNET_GENESIS_UNIX,
        "latest_verified_round_at_prepare":latest_round,
        "predeclared_future_round":target_round,
        "predeclared_future_round_publication_unix_ms":published_at_ms,
        "future_randomness_already_read":False,
        "no_postselection":True,
        "experiment_is_software_negative_control":True,
    }
    obj["early_receipt_sha256"]=receipt_hash(obj)
    return obj

def check_early(obj):
    if not isinstance(obj,dict):
        raise ValueError("INVALID_RECEIVER")
    expected_sha=obj.get("early_receipt_sha256")
    bare={k:v for k,v in obj.items() if k!="early_receipt_sha256"}
    if expected_sha!=receipt_hash(bare):
        raise ValueError("EARLY_SHA256_MISMATCH")
    if (obj.get("schema")!=SCHEMA or obj.get("experiment_id")!=EXPERIMENT_ID
        or obj.get("phase")!="EARLY_PRECOMMIT" or obj.get("n_bits")!=N_BITS
        or not _valid_bits(obj.get("early_bits"))
        or obj.get("beacon_chain_hash")!=CHAIN_HASH
        or obj.get("beacon_period_seconds")!=QUICKNET_PERIOD_SECONDS
        or obj.get("beacon_genesis_unix")!=QUICKNET_GENESIS_UNIX
        or obj.get("predeclared_future_round")!=obj.get("latest_verified_round_at_prepare",0)+FUTURE_ROUND_OFFSET
        or obj.get("future_randomness_already_read") is not False
        or obj.get("no_postselection") is not True):
        raise ValueError("EARLY_RECEIPT_SCOPE_INVALID")
    target_at=(QUICKNET_GENESIS_UNIX+(obj["predeclared_future_round"]-1)*QUICKNET_PERIOD_SECONDS)*1000
    if obj.get("predeclared_future_round_publication_unix_ms")!=target_at:
        raise ValueError("EARLY_TARGET_TIME_CHANGED")
    if obj["early_recorded_at_unix_ms"]>=target_at-90000:
        raise ValueError("EARLY_RECORD_TOO_LATE")
    return expected_sha

def _parse_iso_ms(value):
    try:
        x=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        if x.tzinfo is None: raise ValueError("NO_UTC_OFFSET")
        return int(x.timestamp()*1000)
    except (TypeError,AttributeError,ValueError,OverflowError):
        raise ValueError("UNTRUSTED_GITHUB_ARTIFACT_TIMESTAMP") from None

def assess(early,beacon,github_artifact_created_at:str,after_ms:int):
    early_hash=check_early(early)
    if not isinstance(beacon,dict):
        raise ValueError("INVALID_DRAND_BEACON_RECEIPT")
    if (beacon.get("round")!=early["predeclared_future_round"]
        or beacon.get("chain_hash")!=CHAIN_HASH
        or beacon.get("signature_verified_by_pinned_client") is not True):
        raise ValueError("FUTURE_ROUND_OR_SIGNATURE_UNVERIFIED")
    hexrand=beacon.get("randomness")
    if not isinstance(hexrand,str) or len(hexrand)!=64 or any(c not in "0123456789abcdef" for c in hexrand):
        raise ValueError("INVALID_SIGNED_BEACON_RANDOMNESS")
    target_at=early["predeclared_future_round_publication_unix_ms"]
    early_artifact_created_at=_parse_iso_ms(github_artifact_created_at)
    if early_artifact_created_at <= early["early_recorded_at_unix_ms"]-15000:
        raise ValueError("PRECOMMIT_TIME_INCONSISTENT")
    if early_artifact_created_at >= target_at-15000:
        raise ValueError("NO_INDEPENDENT_EARLY_ARTIFACT_TIMING_MARGIN")
    if type(after_ms) is not int or after_ms<target_at:
        raise ValueError("BEACON_PRE_PUBLICATION_LOOKUP_REFUSED")
    late_bits="".join(f"{b:08b}" for b in bytes.fromhex(hexrand))
    assert len(late_bits)==N_BITS
    matches=sum(a==b for a,b in zip(early["early_bits"],late_bits))
    exact_p=exact_two_sided_binomial_p(matches,N_BITS)
    return {
        "schema":SCHEMA,"experiment_id":EXPERIMENT_ID,
        "phase":"LATE_INDEPENDENT_BEACON_ASSESSMENT",
        "status":"BLIND_PUBLIC_BEACON_NEGATIVE_CONTROL_COMPLETE",
        "early_precommit_sha256":early_hash,
        "early_github_artifact_created_at":github_artifact_created_at,
        "predeclared_target_round":early["predeclared_future_round"],
        "beacon_round_published_unix_ms":target_at,
        "beacon_signature_checked_by_pinned_drand_client":True,
        "beacon_randomness_sha256":hashlib.sha256(bytes.fromhex(hexrand)).hexdigest(),
        "late_choice_source":"SIGNED_PUBLIC_DRAND_QUICKNET_RANDOMNESS",
        "n_all_raw_bits":N_BITS,
        "matches":matches,
        "raw_accuracy":matches/N_BITS,
        "exact_two_sided_binomial_p_under_independent_fair_bit_null":exact_p,
        "unplanned_outlier_below_0_05":exact_p<.05,
        "outlier_is_not_physical_retrocausality":True,
        "no_postselection_or_early_retraining":True,
        "independent_external_randomness_source":True,
        "independent_external_early_timestamp_source":"GITHUB_ACTIONS_ARTIFACT_CREATED_AT",
        "independent_physical_early_receiver":False,
        "physical_retrocausal_signal_proven":False,
        "quantum_lab_experiment_performed":False,
        "production_model_modified":False,
        "one_trial_not_confirmatory_significance":True,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("prepare","assess"))
    parser.add_argument("--latest")
    parser.add_argument("--receiver")
    parser.add_argument("--beacon")
    parser.add_argument("--artifact-created-at")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.phase=="prepare":
        if not args.latest:parser.error("--latest needed")
        result=prepare(_read_json(args.latest),int(time.time()*1000))
    else:
        if not all((args.receiver,args.beacon,args.artifact_created_at)):
            parser.error("--receiver/--beacon/--artifact-created-at needed")
        result=assess(_read_json(args.receiver),_read_json(args.beacon),args.artifact_created_at,int(time.time()*1000))
    write_once(args.output,result)
    summary={"status":result.get("status",result.get("phase")),
             "experiment":EXPERIMENT_ID,"physical_retrocausal_signal_proven":False}
    if args.phase=="prepare":
        summary["predeclared_future_round"]=result["predeclared_future_round"]
        summary["future_release_unix_ms"]=result["predeclared_future_round_publication_unix_ms"]
        summary["early_receipt_sha256"]=result["early_receipt_sha256"]
    else:
        summary["raw_accuracy"]=result["raw_accuracy"]
        summary["exact_null_p"]=result["exact_two_sided_binomial_p_under_independent_fair_bit_null"]
    print(json.dumps(summary,sort_keys=True))


if __name__=="__main__":
    main()
