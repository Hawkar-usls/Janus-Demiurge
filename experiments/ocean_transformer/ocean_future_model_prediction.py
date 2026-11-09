#!/usr/bin/env python3
"""JANUS-OCEAN-FUTURE-004: actual frozen JanusTinyTransformer drand forecast.

EARLY job uses exactly the historical, SHA-pinned trained checkpoint from
GitHub Actions run 42596763409 (synthetic Born-rule training). No retraining.
Prediction tokens use only public pre-target metadata (target round + bit
index). It exports 256 probabilities AND 256 thresholded predictions before
the predeclared future beacon is published. These features have NO known
mechanistic link to drand randomness: chance performance is expected.

LATE job scores all unfiltered bits against a BLS-verified fixed future drand
Quicknet round, after verifying the GitHub artifact timestamp. No weights
change, postselection, failed-trial deletion, Wolfram call or physics claim.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import blind_drand_pilot as drand

EXPERIMENT_ID = "JANUS-OCEAN-FROZEN-TRANSFORMER-FUTURE-004"
SCHEMA = "janus.ocean.frozen_transformer_future_drand.v1"
SOURCE_RUN = 42596763409
SOURCE_ARTIFACT_ID = 13663149173
SOURCE_ARTIFACT_SHA256 = "45c8b063b08973b06b88ec843e9a5d16976c983a8e35b39ef33e9304201e5515"
N_BITS = 256
FUTURE_OFFSET = 80  # 4 minutes minus normal beacon lag, no repeated trials
EXPECTED_MODEL = "JanusTinyTransformer"

def canonical(item):
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()

def digest(item):
    return sha_bytes(canonical(item))

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def write_once(path, obj):
    dst=Path(path)
    if dst.exists():
        raise ValueError("REFUSE_OVERWRITE_PRECOMMITTED_MODEL_PREDICTION")
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def tokens_for_public_round(target, position):
    # Frozen feature encoder. No late bits, beacon output or labels supplied.
    if type(target) is not int or target<1 or type(position) is not int or not 0<=position<N_BITS:
        raise ValueError("INVALID_PUBLIC_FEATURE")
    theta=(target+position*3) % 5
    basis="Z" if ((target >> (position%19)) ^ position)&1 else "X"
    dephasing=(target//7+position*11)%3
    return theta,basis,dephasing

def validate_source_checkpoint(ckpt_path, report_path):
    import torch
    repo_root=str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0,repo_root)
    from janus_model.model import JanusModelConfig,JanusTinyTransformer
    from ocean_quantum_train import CONFIG
    p=Path(ckpt_path)
    rp=Path(report_path)
    report=read_json(rp)
    sha=sha_bytes(p.read_bytes())
    if (report.get("model")!=EXPECTED_MODEL
        or report.get("dataset_type")!="SYNTHETIC_STANDARD_QUANTUM_MEASUREMENT"
        or report.get("future_labels_seen_at_training") is not False
        or report.get("production_checkpoint_changed") is not False
        or report.get("ocean_candidate_sha256")!=sha):
        raise ValueError("FROZEN_TRAINING_SOURCE_OR_CHECKPOINT_MISMATCH")
    state=torch.load(p,map_location="cpu",weights_only=True)
    if (state.get("source")!="janus.ocean.quantum_measurement_priors.v1"
        or state.get("production_promotion") is not False
        or state.get("config")!=CONFIG.to_dict()
        or report.get("configuration")!=CONFIG.to_dict()):
        raise ValueError("FROZEN_MODEL_ARCHITECTURE_OR_SOURCE_MISMATCH")
    model=JanusTinyTransformer(JanusModelConfig.from_dict(state["config"]))
    model.load_state_dict(state["model"],strict=True)
    model.eval()
    torch.set_num_threads(1)
    return model,sha,sha_bytes(rp.read_bytes())

def early_forecast(latest, now_ms,model,ckpt_sha,report_sha):
    import torch
    import torch.nn.functional as F
    import measurement_priors as priors
    if (not isinstance(latest,dict)
        or latest.get("chain_hash")!=drand.CHAIN_HASH
        or latest.get("genesis_time")!=drand.QUICKNET_GENESIS_UNIX
        or latest.get("period")!=drand.QUICKNET_PERIOD_SECONDS
        or latest.get("signature_verified_by_pinned_client") is not True):
        raise ValueError("DRAND_PRIOR_ROUND_NOT_VERIFIED")
    previous=latest.get("round")
    if type(previous) is not int or previous<1:
        raise ValueError("DRAND_PREVIOUS_ROUND_NOT_INTEGER")
    if type(now_ms) is not int or now_ms<1:
        raise ValueError("EARLY_TIME_INVALID")
    target=previous+FUTURE_OFFSET
    release=(drand.QUICKNET_GENESIS_UNIX+(target-1)*drand.QUICKNET_PERIOD_SECONDS)*1000
    if not 180_000<=release-now_ms<=300_000:
        raise ValueError("FUTURE_ROUND_NOT_WITHIN_FROZEN_WINDOW")
    contexts=[priors.model_tokens(*tokens_for_public_round(target,i)) for i in range(N_BITS)]
    with torch.no_grad():
        logits,_=model(torch.tensor(contexts,dtype=torch.long))
        probabilities=F.softmax(logits[:,-1,:2],-1)[:,1].tolist()
    if len(probabilities)!=N_BITS or not all(math.isfinite(v) and 0<=v<=1 for v in probabilities):
        raise ValueError("MODEL_NONFINITE_PROBABILITY")
    # Normalize serialization to decimal precision before deriving decisions.
    probabilities=[round(v,8) for v in probabilities]
    predicted="".join("1" if v>=.5 else "0" for v in probabilities)
    obj={
        "schema":SCHEMA, "experiment_id":EXPERIMENT_ID,
        "phase":"EARLY_PRECOMMIT",
        "model_name":EXPECTED_MODEL,
        "model_training":"PREVIOUS_FROZEN_BORN_RULE_SYNTHETIC_ONLY",
        "trained_checkpoint_github_run":SOURCE_RUN,
        "trained_checkpoint_artifact_id":SOURCE_ARTIFACT_ID,
        "trained_checkpoint_artifact_sha256":SOURCE_ARTIFACT_SHA256,
        "trained_checkpoint_sha256":ckpt_sha,
        "trained_checkpoint_report_sha256":report_sha,
        "public_feature_encoder":"V1_TARGET_ROUND_AND_POSITION_TO_BORN_3_TOKENS",
        "features_from_future_labels":False,
        "round_picked_before_future_release":True,
        "future_beacon_result_seen_during_prediction":False,
        "training_or_calibration_used_target_beacon":False,
        "training_after_prediction":False,
        "early_recorded_at_unix_ms":now_ms,
        "latest_verified_round_at_prepare":previous,
        "beacon_chain_hash":drand.CHAIN_HASH,
        "beacon_period_seconds":drand.QUICKNET_PERIOD_SECONDS,
        "beacon_genesis_unix":drand.QUICKNET_GENESIS_UNIX,
        "predeclared_future_round":target,
        "predeclared_future_round_publication_unix_ms":release,
        "n_bits":N_BITS,
        "predicted_one_probabilities":probabilities,
        "early_bits":predicted,
        "prediction_threshold":.5,
        "postselection_allowed":False,
        "model_weights_modified":False,
        "source_class":"CROSS_DOMAIN_REUSE_OF_BORN_MODEL_EXPECT_CHANCE_ON_INDEPENDENT_DRAND",
        "physical_retrocausality_proven":False,
    }
    obj["early_receipt_sha256"]=digest(obj)
    return obj

def verify_early(obj):
    if not isinstance(obj,dict) or obj.get("schema")!=SCHEMA or obj.get("phase")!="EARLY_PRECOMMIT":
        raise ValueError("INVALID_MODEL_EARLY_SCHEMA")
    provided=obj.get("early_receipt_sha256")
    bare={k:v for k,v in obj.items() if k!="early_receipt_sha256"}
    if provided!=digest(bare):
        raise ValueError("MODEL_PREDICTION_PRECOMMIT_SHA_MISMATCH")
    if (obj.get("experiment_id")!=EXPERIMENT_ID
        or obj.get("model_name")!=EXPECTED_MODEL
        or obj.get("model_training")!="PREVIOUS_FROZEN_BORN_RULE_SYNTHETIC_ONLY"
        or obj.get("trained_checkpoint_github_run")!=SOURCE_RUN
        or obj.get("trained_checkpoint_artifact_id")!=SOURCE_ARTIFACT_ID
        or obj.get("trained_checkpoint_artifact_sha256")!=SOURCE_ARTIFACT_SHA256
        or obj.get("beacon_chain_hash")!=drand.CHAIN_HASH
        or obj.get("beacon_period_seconds")!=drand.QUICKNET_PERIOD_SECONDS
        or obj.get("beacon_genesis_unix")!=drand.QUICKNET_GENESIS_UNIX
        or obj.get("predeclared_future_round")!=obj.get("latest_verified_round_at_prepare",0)+FUTURE_OFFSET
        or obj.get("postselection_allowed") is not False
        or obj.get("features_from_future_labels") is not False
        or obj.get("future_beacon_result_seen_during_prediction") is not False
        or obj.get("training_or_calibration_used_target_beacon") is not False
        or obj.get("training_after_prediction") is not False
        or obj.get("model_weights_modified") is not False):
        raise ValueError("UNTRUSTED_MODEL_OR_TARGET_BOUNDARY")
    probs=obj.get("predicted_one_probabilities")
    bits=obj.get("early_bits")
    if (type(obj.get("n_bits")) is not int or obj["n_bits"]!=N_BITS
        or not isinstance(probs,list) or len(probs)!=N_BITS
        or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in probs)
        or not isinstance(bits,str) or len(bits)!=N_BITS
        or bits!="".join("1" if p>=.5 else "0" for p in probs)):
        raise ValueError("MODEL_PREDICTIONS_NOT_SELF_CONSISTENT")
    for sha_key in ("trained_checkpoint_sha256","trained_checkpoint_report_sha256"):
        value=obj.get(sha_key)
        if not isinstance(value,str) or len(value)!=64 or set(value)-set("0123456789abcdef"):
            raise ValueError("INVALID_FROZEN_MODEL_SHA")
    target_time=(drand.QUICKNET_GENESIS_UNIX+(obj["predeclared_future_round"]-1)*drand.QUICKNET_PERIOD_SECONDS)*1000
    if (obj.get("predeclared_future_round_publication_unix_ms")!=target_time
        or type(obj.get("early_recorded_at_unix_ms")) is not int
        or not 180_000<=target_time-obj["early_recorded_at_unix_ms"]<=300_000):
        raise ValueError("INVALID_FROZEN_FUTURE_TIMING")
    return provided

def parse_artifact_created_at(value):
    try:
        timestamp=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
        if timestamp.tzinfo is None: raise ValueError("OFFSET_MISSING")
        return int(timestamp.timestamp()*1000)
    except (TypeError,AttributeError,ValueError,OverflowError):
        raise ValueError("BAD_INDEPENDENT_GITHUB_ARTIFACT_TIME") from None

def assess(early, beacon, created_at, current_ms):
    receipt=verify_early(early)
    if (not isinstance(beacon,dict)
        or beacon.get("chain_hash")!=drand.CHAIN_HASH
        or beacon.get("round")!=early["predeclared_future_round"]
        or beacon.get("signature_verified_by_pinned_client") is not True):
        raise ValueError("WRONG_OR_UNSIGNED_FUTURE_ROUND")
    binary=beacon.get("randomness")
    if not isinstance(binary,str) or len(binary)!=64 or set(binary)-set("0123456789abcdef"):
        raise ValueError("INVALID_FUTURE_BEACON_BYTES")
    release=early["predeclared_future_round_publication_unix_ms"]
    published=parse_artifact_created_at(created_at)
    if not (early["early_recorded_at_unix_ms"]-15_000<=published<release-30_000):
        raise ValueError("FORECAST_NOT_INDEPENDENTLY_PUBLISHED_BEFORE_TARGET")
    if type(current_ms) is not int or current_ms<release:
        raise ValueError("FUTURE_TARGET_NOT_RELEASED")
    labels="".join(f"{b:08b}" for b in bytes.fromhex(binary))
    probs=early["predicted_one_probabilities"]
    predictions=early["early_bits"]
    if len(labels)!=N_BITS:
        raise ValueError("FUTURE_BEACON_LENGTH_CHANGED")
    matches=sum(a==b for a,b in zip(predictions,labels))
    brier=sum((p-int(y))**2 for p,y in zip(probs,labels))/N_BITS
    epsilon=1e-10
    logloss=-sum(int(y)*math.log(max(epsilon,p))+(1-int(y))*math.log(max(epsilon,1-p))
                 for p,y in zip(probs,labels))/N_BITS
    if not all(map(math.isfinite,(brier,logloss))):
        raise ValueError("MODEL_SCORE_NONFINITE")
    exact=drand.exact_two_sided_binomial_p(matches,N_BITS)
    return {
        "schema":SCHEMA,"experiment_id":EXPERIMENT_ID,
        "phase":"LATE_BLINDED_ASSESSMENT",
        "status":"FROZEN_OCEAN_TRANSFORMER_FORECAST_SCORED_AS_EXPLORATORY_CONTROL",
        "early_model_prediction_receipt_sha256":receipt,
        "early_github_artifact_created_at":created_at,
        "checkpoint_sha256":early["trained_checkpoint_sha256"],
        "target_beacon_round":early["predeclared_future_round"],
        "target_beacon_published_at_unix_ms":release,
        "signature_verified_by_pinned_drand_client":True,
        "future_beacon_sha256":sha_bytes(bytes.fromhex(binary)),
        "n_all_bits":N_BITS,
        "predicted_one_fraction":predictions.count("1")/N_BITS,
        "matches":matches,
        "accuracy":matches/N_BITS,
        "exact_two_sided_binomial_p_h0_fair_independent_beacon":exact,
        "brier_score_frozen_transformer":brier,
        "brier_score_uniform_half_baseline":.25,
        "brier_improvement_relative_uniform":.25-brier,
        "binary_logloss_transformer":logloss,
        "binary_logloss_uniform_half_baseline":math.log(2),
        "primary_predeclared_metric":"BRIER_RELATIVE_TO_PROBABILITY_0_5_BASELINE",
        "secondary_metric":"EXACT_TWO_SIDED_BINOMIAL_FOR_THRESHOLD_PREDICTIONS",
        "all_256_bits_scored":True,
        "postselection_used":False,
        "early_weights_retrained_after_target":False,
        "independent_external_late_choice":True,
        "independent_external_early_timestamp":"GITHUB_ARTIFACT_CREATED_AT",
        "independent_physical_early_receiver":False,
        "physical_retrocausal_signal_proven":False,
        "single_trial_is_not_confirmatory":True,
        "automatic_model_promotion":False,
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=("forecast","assess"))
    ap.add_argument("--latest")
    ap.add_argument("--checkpoint")
    ap.add_argument("--training-report")
    ap.add_argument("--early")
    ap.add_argument("--beacon")
    ap.add_argument("--artifact-created-at")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    if args.phase=="forecast":
        if not all((args.latest,args.checkpoint,args.training_report)):
            ap.error("forecast requires --latest --checkpoint --training-report")
        # All model bytes come from immutable pinned historic GitHub artifact.
        model,ckpt_sha,report_sha=validate_source_checkpoint(args.checkpoint,args.training_report)
        output=early_forecast(read_json(args.latest),int(time.time()*1000),model,ckpt_sha,report_sha)
    else:
        if not all((args.early,args.beacon,args.artifact_created_at)):
            ap.error("assess requires --early --beacon --artifact-created-at")
        output=assess(read_json(args.early),read_json(args.beacon),
                      args.artifact_created_at,int(time.time()*1000))
    write_once(args.output,output)
    # NEVER print 256 actual predictions before early GitHub upload;
    # actual bits and probabilities are already in SHA-committed artifact.
    print(json.dumps({
        "status":output["phase"],"experiment":EXPERIMENT_ID,
        "early_sha":output.get("early_receipt_sha256"),
        "prediction_accuracy":output.get("accuracy"),
        "brier_score":output.get("brier_score_frozen_transformer"),
        "physical_retrocausality_proven":False
    },sort_keys=True))

if __name__=="__main__":
    main()
