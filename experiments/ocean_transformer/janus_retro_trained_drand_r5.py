#!/usr/bin/env python3
"""JANUS R5: run the REAL frozen JANUS weather Transformer against drand.

EARLY:
- Accept only the actual 40-river JanusTinyTransformer prediction from
  retro_channel_trial.py with pinned model and snapshot SHA256.
- Freeze ALL 256 forecast bits + three alternate EARLY-ONLY decoders that
  were specified on 2026-11-07 before this new future challenge.
- Precommit one externally signed Quicknet round >= 180 s in the future.
- Upload plan without any predicted bits. Never download early forecasts
  in the late drand fetch worker.

SCORE:
- Re-verify immutable model prediction hash, drand Quicknet chain, exact
  future round and signature hash. An independent Node.js worker first
  verifies its actual BLS signature using drand-client.
- Score all four precommitted decoders over ALL bits, with Bonferroni.
- Never interpret any mathematical anomaly as proof of physical time travel.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

from janus_retro_drand_external_r4 import (
    CHAIN_HASH, CHAIN_ID, FORECAST_NBITS, MIN_FUTURE_GAP_SECONDS,
    round_release_epoch, future_round, safe_bits, binomial_p, write_new
)

MODEL_SHA="2c38788e8468a98e9377fcdb9058c488ec3ec17dfacfbf553402a9b1a86cd4ca"
SNAPSHOT_SHA="1d7259bd6429fe5f29d2ad573c05822f8c8ed6686a254e643b32be8c9d56e1cd"
TRAINED_RUN=42125238873
IDS=("RAW","INVERTED","CONFIDENCE_HIGH_FLIP","CONFIDENCE_LOW_FLIP")
FAMILYWISE_ALPHA=1e-4


def demand(predicate,reason):
    if not predicate:
        raise ValueError(reason)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decoders(bits,confidence):
    safe_bits(bits)
    demand(type(confidence) is list and len(confidence)==FORECAST_NBITS and
           all(type(p) in (float,int) and math.isfinite(p) and
               0<=p<=1 for p in confidence),
           "INVALID_FROZEN_CONFIDENCE")
    class_bit=[int(abs(p-.5)>=.25) for p in confidence]
    raw=[int(i) for i in bits]
    return {
       "RAW":bits,
       "INVERTED":"".join(str(i^1) for i in raw),
       "CONFIDENCE_HIGH_FLIP":"".join(str(i^c) for i,c in zip(raw,class_bit)),
       "CONFIDENCE_LOW_FLIP":"".join(str(i^(1^c)) for i,c in zip(raw,class_bit))
    }


def validate_model_early(model_record,trial_id):
    demand(type(model_record) is dict and
           model_record.get("schema")=="janus.retro.lab.model_precommit.v1",
           "INVALID_MODEL_RECORD_SCHEMA")
    demand(model_record.get("trial_id")==f"janus-retro-{trial_id}" and
           model_record.get("model_sha256")==MODEL_SHA and
           model_record.get("source_snapshot_sha256")==SNAPSHOT_SHA and
           model_record.get("source_trained_JANUS_run")==TRAINED_RUN and
           model_record.get("number_bits")==FORECAST_NBITS and
           model_record.get("future_target_not_generated_yet") is True and
           model_record.get("real_physical_retrocausal_interface") is False,
           "INVALID_TRAINED_MODEL_PROVENANCE")
    bits=safe_bits(model_record.get("predicted_bits"))
    confidence=model_record.get("p1_model_probs")
    predictors=decoders(bits,confidence)
    demand(sha_bytes(bits.encode("ascii"))==
           model_record.get("predicted_256_bits_sha256"),
           "TRAINED_FORECAST_HASH_MISMATCH")
    # An actual JanusTinyTransformer prediction uses p>=.5 for its bits.
    demand("".join("1" if p>=.5 else "0" for p in confidence)==bits,
           "PREDICTOR_CONFLICT_WITH_FROZEN_PROBABILITIES")
    stamp=model_record.get("issued_at_epoch_utc")
    demand(type(stamp) in (float,int) and math.isfinite(stamp),
           "INVALID_ORIGINAL_EARLY_TIMESTAMP")
    return predictors,stamp


def freeze(model_path,trial_id,now=None):
    demand(type(trial_id) is str and trial_id.isdigit() and
           len(trial_id)<=29,"BAD_TRIAL_ID")
    model_bytes=Path(model_path).read_bytes()
    original=json.loads(model_bytes)
    predictors,stamp=validate_model_early(original,trial_id)
    now=float(time.time() if now is None else now)
    demand(math.isfinite(now) and now>=stamp,"EARLY_MODEL_AFTER_PLAN_TIME")
    target=future_round(now)
    release=round_release_epoch(target)
    demand(release >= now+MIN_FUTURE_GAP_SECONDS,
           "TARGET_TOO_EARLY")
    early={
      "schema":"janus.external_beacon.trained_early.r5",
      "trial_id":trial_id,
      "source":"ACTUAL_TRAINED_JANUS_40_RIVER_V3",
      "source_model_record_sha256":sha_bytes(model_bytes),
      "trained_model_sha256":MODEL_SHA,
      "snapshot_sha256":SNAPSHOT_SHA,
      "trained_source_run":TRAINED_RUN,
      "original_model_issued_epoch":stamp,
      "frozen_epoch":now,
      "target_round":target,
      "frozen_predictors":predictors,
      "prediction_family":list(IDS),
      "familywise_one_sided_alpha":FAMILYWISE_ALPHA,
      "primary_predeclared_candidate":"RAW",
      "all_four_guesses_created_before_future":True,
      "past_physical_channel_connected":False,
    }
    plan={
      "schema":"janus.external_beacon.plan.r4",
      "trial_id":trial_id,
      "beacon_chain_id":CHAIN_ID,
      "beacon_chain_hash":CHAIN_HASH,
      "target_round":target,
      "target_release_epoch":release,
      "early_created_epoch":now,
      "forecast_sha256":sha_bytes(predictors["RAW"].encode("ascii")),
      "minimum_gap_seconds":MIN_FUTURE_GAP_SECONDS,
      "forecast_string_not_in_plan":True,
      "actual_model_is_trained_janus":True,
      "precommitted_decoder_family":list(IDS),
      "physical_retrocausality_proven":False
    }
    return early,plan


def score(early,plan,future,original_raw):
    demand(all(type(x) is dict for x in (early,plan,future)) and
           type(original_raw) is tuple and len(original_raw)==2 and
           type(original_raw[0]) is dict and type(original_raw[1]) is bytes,
           "INVALID_SCORE_RECORDS")
    demand(early.get("schema")=="janus.external_beacon.trained_early.r5" and
           plan.get("schema")=="janus.external_beacon.plan.r4" and
           future.get("schema")=="janus.external_beacon.future.r4",
           "BAD_SCHEMAS")
    tid=early.get("trial_id")
    demand(type(tid) is str and tid.isdigit() and
           plan.get("trial_id")==future.get("trial_id")==tid,
           "TRIAL_ID_MISMATCH")
    demand(early.get("trained_model_sha256")==MODEL_SHA and
           early.get("snapshot_sha256")==SNAPSHOT_SHA and
           early.get("trained_source_run")==TRAINED_RUN and
           early.get("source")=="ACTUAL_TRAINED_JANUS_40_RIVER_V3",
           "MODEL_SOURCE_CHANGED")
    original,raw_bytes=original_raw
    demand(sha_bytes(raw_bytes)==early.get("source_model_record_sha256"),
           "MODEL_FILE_DIGEST_CHANGED")
    expected,t0=validate_model_early(original,tid)
    guesses=early.get("frozen_predictors")
    demand(type(guesses) is dict and
           tuple(guesses.keys())==IDS and expected==guesses and
           early.get("prediction_family")==list(IDS) and
           plan.get("precommitted_decoder_family")==list(IDS) and
           early.get("all_four_guesses_created_before_future") is True and
           early.get("familywise_one_sided_alpha")==FAMILYWISE_ALPHA and
           early.get("primary_predeclared_candidate")=="RAW",
           "EARLY_DECODERS_MODIFIED")
    roundnum=plan.get("target_round")
    t1=early.get("frozen_epoch")
    demand(type(t1) in (int,float) and math.isfinite(t1) and
           t1>=t0 and plan.get("early_created_epoch")==t1 and
           type(roundnum) is int and
           roundnum==future.get("target_round")==early.get("target_round") and
           plan.get("target_release_epoch")==round_release_epoch(roundnum) and
           plan.get("beacon_chain_hash")==future.get("beacon_chain_hash")==CHAIN_HASH and
           plan.get("beacon_chain_id")==future.get("beacon_chain_id")==CHAIN_ID and
           round_release_epoch(roundnum)>=t1+MIN_FUTURE_GAP_SECONDS,
           "FUTURE_BEACON_OR_TIME_NOT_FROZEN")
    demand(plan.get("forecast_sha256")==sha_bytes(guesses["RAW"].encode()) and
           plan.get("forecast_string_not_in_plan") is True and
           not "forecast_bits" in plan and
           plan.get("actual_model_is_trained_janus") is True,
           "PLAN_LEAK_OR_HASH_CHANGED")
    sign=future.get("signature")
    target=future.get("randomness")
    demand(type(sign) is str and len(sign)==96 and
           all(c in "0123456789abcdef" for c in sign) and
           type(target) is str and len(target)==64 and
           all(c in "0123456789abcdef" for c in target) and
           sha_bytes(bytes.fromhex(sign))==target,
           "INVALID_SIGNED_FUTURE_PAYLOAD")
    demand(future.get("cryptographic_bls_verification") is True and
           future.get("verified_by")=="drand-client@1.4.2" and
           future.get("read_early_forecast_bits") is False and
           isinstance(future.get("retrieved_epoch"),(float,int)) and
           future["retrieved_epoch"]>=round_release_epoch(roundnum),
           "MISSING_VERIFIED_FUTURE_PROVENANCE")
    future_bits="".join(f"{x:08b}" for x in bytes.fromhex(target))
    results={}
    for name in IDS:
        hits=sum(a==b for a,b in zip(guesses[name],future_bits))
        results[name]={
          "correct":hits,"total":FORECAST_NBITS,
          "accuracy":hits/FORECAST_NBITS,
          "nominal_upper_tail":binomial_p(FORECAST_NBITS,hits)
        }
    corrected=min(1.,4*min(x["nominal_upper_tail"] for x in results.values()))
    return {
      "schema":"janus.external_beacon.trained_score.r5",
      "trial_id":tid,
      "model_sha256":MODEL_SHA,
      "source":"ACTUAL_TRAINED_JANUS_40_RIVER_V3",
      "beacon_round":roundnum,
      "separation_seconds":round_release_epoch(roundnum)-t1,
      "signed_future_hash":target,
      "all_precommitted_candidates":results,
      "primary_RAW_correct_bits":results["RAW"]["correct"],
      "familywise_bonferroni_upper_tail_p":corrected,
      "alpha_familywise":FAMILYWISE_ALPHA,
      "exploratory_single_round_above_threshold":corrected<FAMILYWISE_ALPHA,
      "multi_round_independent_replication_completed":False,
      "single_drand_signature_is_not_256_independent_physical_trials":True,
      "trained_model_is_weather_forecaster_not_future_beacon_predictor":True,
      "external_BLS_verified_by_official_client":True,
      "all_256_bits_and_all_4_decoders_scored":True,
      "late_outcome_postselection":False,
      "physical_early_clock_attested_externally":False,
      "drand_threshold_independence_cryptographically_assumed":True,
      "physical_retrocausality_proven":False,
      "production_promotion":False,
      "conclusion":"ONE_PROSPECTIVE_TRAINED_JANUS_VS_EXTERNAL_DRAND_CHALLENGE__DOES_NOT_CREATE_PHYSICAL_BACKWARD_INFORMATION"
    }


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="mode",required=True)
    p=sub.add_parser("freeze")
    p.add_argument("--model-prediction",type=Path,required=True)
    p.add_argument("--trial-id",required=True)
    p.add_argument("--early-out",type=Path,required=True)
    p.add_argument("--plan-out",type=Path,required=True)
    s=sub.add_parser("score")
    s.add_argument("--early",type=Path,required=True)
    s.add_argument("--plan",type=Path,required=True)
    s.add_argument("--future",type=Path,required=True)
    s.add_argument("--model-prediction",type=Path,required=True)
    s.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.mode=="freeze":
       early,plan=freeze(args.model_prediction,args.trial_id)
       write_new(args.early_out,early)
       write_new(args.plan_out,plan)
       print(json.dumps({"stage":"early_frozen","target_round":plan["target_round"],
         "source":early["source"],"physical_signal":False}))
    else:
       model_bytes=args.model_prediction.read_bytes()
       out=score(read(args.early),read(args.plan),read(args.future),
                 (json.loads(model_bytes),model_bytes))
       write_new(args.out,out)
       print(json.dumps({"stage":"all_bit_scored","raw_hits":out["primary_RAW_correct_bits"],
         "bonferroni":out["familywise_bonferroni_upper_tail_p"],
         "physical_signal":False}))


if __name__=="__main__":
    main()
