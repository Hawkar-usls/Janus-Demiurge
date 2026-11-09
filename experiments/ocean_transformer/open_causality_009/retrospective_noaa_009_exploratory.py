#!/usr/bin/env python3
"""Independent post-hoc NOAA OPEN-009 exploratory backtest, not a prospective result.

FIXED external historical set: Nov 2-5, 2026 (four days, 96 hours).
Each date's prediction references ONLY its preceding NOAA days 9..6 days
before target. No source test observations enter forecasting code.
There is NO genuine early external precommit or future information channel.
Original 009A/009B prereg and QPU-005 remain unchanged.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
import noaa_009a as noaa
import glow_009c as glow

DATES=[dt.date(2026,11,d) for d in (2,3,4,5)]
MODELS=("JANUS_PHYSICS_HEURISTIC","persistence","diurnal","clear_sky")
SCHEMA="janus.ocean.open009_noaa_retrospective_nov2_nov5.v1"


def aggregate_day(history,target):
    if len(history)!=4 or [x["date"] for x in history]!=[
       (target-dt.timedelta(days=i)).isoformat() for i in (9,8,7,6)]:
        raise ValueError("NOAA_HISTORY_NOT_CHRONOLOGICALLY_PRIOR_TO_TARGET")
    if (not all(x["date"]<target.isoformat() for x in history)
        or target.isoformat() in [x["date"] for x in history]):
        raise ValueError("TARGET_DATA_LEAK_IN_HISTORY")
    predictors,baselines=noaa.forecast(history,target)
    assert len(predictors)==24
    scores={"JANUS_PHYSICS_HEURISTIC":predictors,**baselines}
    assert set(scores)==set(MODELS)
    return scores


def assess_day(history,observed):
    target=dt.date.fromisoformat(observed["date"])
    predicted=aggregate_day(history,target)
    actual=observed["hourly_ghi"]
    if len(actual)!=24 or any(x is None or not math.isfinite(x) for x in actual):
        raise ValueError("NOAA_INCOMPLETE_TARGET_NO_POSTHOC_IMPUTATION")
    if any(not all(x is not None and math.isfinite(x) for x in vector)
           for vector in predicted.values()):
        raise ValueError("NOAA_NONFINITE_PREDICTION")
    mae={k:sum(abs(p-o) for p,o in zip(vals,actual))/24
         for k,vals in predicted.items()}
    glow_pred=glow.sun_drive(predicted["JANUS_PHYSICS_HEURISTIC"])
    glow_model_truth=glow.sun_drive(actual)
    return {
       "date":observed["date"],"source_uri":observed["url"],
       "source_raw_sha256":observed["raw_sha256"],
       "historical_training_dates":[x["date"] for x in history],
       "historical_training_raw_sha256":[x["raw_sha256"] for x in history],
       "n_hours":24,
       "mae_w_m2":{k:round(v,7) for k,v in mae.items()},
       "virtual_glow_mae_microwatt":round(
         sum(abs(a-b) for a,b in zip(glow_pred,glow_model_truth))/24,8),
       "glow_observed_by_real_sensor":False,
       "forecast_has_independent_time_witness":False
    }


def run():
    sources={}
    for day in DATES:
        for training in [day-dt.timedelta(days=i) for i in (9,8,7,6)]:
            sources.setdefault(training,None)
        sources.setdefault(day,None)
    for day in sorted(sources):
        sources[day]=noaa.fetch(day)
    outcomes=[]
    for day in DATES:
        hist=[sources[day-dt.timedelta(days=i)] for i in (9,8,7,6)]
        missing_training={
          h["date"]:[i for i,point in enumerate(h["hourly_ghi"]) if point is None]
          for h in hist if any(point is None for point in h["hourly_ghi"])
        }
        missing_target=[i for i,v in enumerate(sources[day]["hourly_ghi"]) if v is None]
        if missing_training or missing_target:
            outcomes.append({
               "date":day.isoformat(),
               "status":"NOT_SCORABLE_QC_FAIL",
               "missing_training_hours_utc":missing_training,
               "missing_target_hours_utc":missing_target,
               "training_source_sha256":{h["date"]:h["raw_sha256"] for h in hist},
               "target_source_sha256":sources[day]["raw_sha256"],
               "reason":"NOAA_QC_HOURLY_INCOMPLETE_NO_IMPUTATION",
            })
        else:
            result=assess_day(hist,sources[day])
            result["status"]="VALID_EXPLORATORY_DAY"
            outcomes.append(result)
    valid=[x for x in outcomes if x["status"]=="VALID_EXPLORATORY_DAY"]
    mean={model:round(sum(r["mae_w_m2"][model] for r in valid)/len(valid),7)
          for model in MODELS} if valid else None
    return {
      "schema":SCHEMA,
      "record_type":"RETROSPECTIVE_REAL_PUBLIC_NOAA_EXPLORATORY",
      "dates":[x.isoformat() for x in DATES],
      "planned_n_hours":96,
      "valid_n_hours":24*len(valid),
      "n_fixed_days":4,
      "n_valid_days":len(valid),
      "n_qc_failed_days":4-len(valid),
      "dataset_conditions":"bondville SURFRAD minute GHI with QC==0 and 45/60 per hour",
      "chronological_no_future_feature_check":"PASS_IN_SOFTWARE",
      "independent_early_forecast_commitment":False,
      "noaa_source_fetches":len(sources),
      "original_noaa_009a_prereg_unchanged":True,
      "real_solar_observations_used":True,
      "real_phosphor_measurements_collected":0,
      "mean_mae_w_m2":mean,
      "model_beats_each_baseline_on_valid_subset_only":(
         all(mean["JANUS_PHYSICS_HEURISTIC"]<mean[k] for k in MODELS
             if k!="JANUS_PHYSICS_HEURISTIC") if valid else None),
      "virtual_glow_mae_microwatt_mean":(
         round(sum(x["virtual_glow_mae_microwatt"] for x in valid)/len(valid),8)
         if valid else None),
      "status":("ALL_FOUR_RETROSPECTIVE_DAYS_SCORED" if len(valid)==4
                else "PARTIAL_RETROSPECTIVE_QC_FAILURES_RETAINED"),
      "no_causal_retrocausality_inference":True,
      "per_date":outcomes,
      "cohort_scientifically_complete":len(valid)==4,
      "limitations":[
        "Historical target labels already existed when this exploratory code ran.",
        "The 009A fixed hybrid is not a trained JanusTinyTransformer.",
        "GLOW virtual outputs are transformations of actual NOAA sunlight through unmeasured material parameters, not measured afterglow.",
        "Four selected historical dates and small sample cannot support confirmatory external generalization claims.",
        "Any QC-failing dates remain in the ledger as missing, not dropped or replaced.",
        "Prespecified prospective 009A target dates Nov12-19 are reserved and analyzed separately."
      ]
    }


def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    data=run()
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        f.write(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":data["status"],"planned_n_hours":data["planned_n_hours"],
      "valid_n_hours":data["valid_n_hours"],"qc_failed_days":data["n_qc_failed_days"],
      "mae_w_m2":data["mean_mae_w_m2"],
      "virtual_glow_mae_microwatt_mean":data["virtual_glow_mae_microwatt_mean"],
      "sha256":hashlib.sha256(p.read_bytes()).hexdigest()},
      sort_keys=True))
if __name__=="__main__":
    main()
