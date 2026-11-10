#!/usr/bin/env python3
"""JANUS OPEN-009F: physical-geometry + likelihood, not arbitrary forecast blending.

Retrospective, chronological holdout: 2025-12-01..08; does not modify
sealed 009A/B/C/D future target protocols. Predict all target days from only
older NOAA SURFRAD Bondville training days T-33..T-6. The model is
GHI(t) = tau * E_TOA_horizontal(t) + Gaussian observation error.
tau is fitted by closed-form constrained maximum likelihood; residual variance
is fitted by likelihood, never manually selected. Model limitations and 90%
Gaussian predictive interval are logged. This is NOT a numerical weather model.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from statistics import NormalDist

import noaa_009a as noaa

SOLAR_CONSTANT_WM2 = 1361.0  # Physical reference mean total solar irradiance
TEST_DATES = tuple(dt.date(2025, 12, d) for d in range(1, 9))
TRAIN_DAYS = 28
LAST_TRAIN_GAP = 6
PREDICTION_LEVEL = 0.90
MODEL_ID = "NOAA_TOA_OLS_MLE_NO_MANUAL_BLEND_V1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def write_new(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def physical_toa_horizontal(day, hour, lat, lon):
    # Geometry is computed using the existing NOAA solar position routine.
    # Solar constant is a physical reference, not a fitted blending weight.
    return SOLAR_CONSTANT_WM2 * noaa.solar_cos_zen(day, hour, lat, lon)


def mle_fit(history):
    """Closed-form constrained Gaussian MLE of tau in y = tau*E0 + epsilon.

    E0 is extraterrestrial horizontal irradiance. tau assumes constant
    mean atmospheric transmission over the fixed training window.
    Measurement/meteorological error is NOT guaranteed iid Gaussian.
    """
    if not history:
        raise ValueError("EMPTY_TRAIN_SET")
    rows = []
    lat,lon = history[0]["latitude"], history[0]["longitude"]
    for day in history:
        date = dt.date.fromisoformat(day["date"])
        if abs(day["latitude"]-lat) > 0.1 or abs(day["longitude"]-lon)>0.1:
            raise ValueError("STATION_COORDS_CHANGED")
        y = day["hourly_ghi"]
        if len(y)!=24 or any(v is None or not math.isfinite(v) for v in y):
            raise ValueError("TRAIN_QC_FAILED_NO_IMPUTATION")
        for h in range(24):
            rows.append((physical_toa_horizontal(date,h,lat,lon), y[h]))
    sxx = sum(x*x for x,y in rows)
    if sxx<=0:raise ValueError("NO_DAYLIGHT_TRAINING")
    sxy = sum(x*y for x,y in rows)
    tau_unconstrained = sxy/sxx
    tau = max(0.0,min(1.0,tau_unconstrained))
    residuals = [y-tau*x for x,y in rows]
    sigma2 = sum(r*r for r in residuals)/len(rows)  # Gaussian MLE, not unbiased estimator
    if not math.isfinite(sigma2):raise ValueError("NONFINITE_FIT")
    return {"tau":tau,"tau_unconstrained":tau_unconstrained,"sigma2":sigma2,
            "sxx":sxx,"n_hours":len(rows),"station_lat":lat,"station_lon":lon}


def predict(fit, date):
    z = NormalDist().inv_cdf(0.5 + PREDICTION_LEVEL/2)
    pred, lower, upper = [],[],[]
    for h in range(24):
        x = physical_toa_horizontal(date,h,fit["station_lat"],fit["station_lon"])
        mu = max(0.0, fit["tau"]*x)
        # Gaussian plug-in prediction interval, ignoring estimation of sigma2.
        variance = fit["sigma2"]*(1 + x*x/fit["sxx"])
        half = z*math.sqrt(variance)
        pred.append(mu)
        lower.append(max(0.0,mu-half))
        upper.append(mu+half)
    return {"prediction_w_m2":pred, "lower90_w_m2":lower,"upper90_w_m2":upper}


def training_days(target):
    # Target dates are never included: T-33..T-6 inclusive.
    return [target-dt.timedelta(days=i) for i in range(
        LAST_TRAIN_GAP+TRAIN_DAYS-1,LAST_TRAIN_GAP-1,-1)]


def exact_sign_flip_p(differences):
    # Day-level paired sign-flip test, ONLY valid under sign-symmetry of
    # differences. Pre-declared n=8 and one-sided improvement.
    n=len(differences)
    if not n:return None
    observed=sum(differences)
    count=0
    for mask in range(1<<n):
        candidate=sum((-v if mask>>i & 1 else v) for i,v in enumerate(differences))
        if candidate>=observed-1e-10:count+=1
    return count/(1<<n)


def backtest(out):
    memo={}
    def fetch(d):
        k=d.isoformat()
        if k not in memo:
            memo[k]=noaa.fetch(d)
        return memo[k]

    frozen=[]
    for target in TEST_DATES:
        dates=training_days(target)
        history=[fetch(d) for d in dates]
        fit=mle_fit(history)
        forecast=predict(fit,target)
        # Ordinary baseline estimators: sample mean and last available
        # observation; Haurwitz included as an independently published model.
        seasonal_mean=[sum(row["hourly_ghi"][h] for row in history)/len(history)
                       for h in range(24)]
        persistence=history[-1]["hourly_ghi"]
        sky=[noaa.haurwitz(target,h,fit["station_lat"],fit["station_lon"]) for h in range(24)]
        frozen.append({
            "target":target.isoformat(),
            "training_days":[x.isoformat() for x in dates],
            "training_source_sha256":[r["raw_sha256"] for r in history],
            "fit":fit, "forecast":forecast,
            "baselines":{"sample_mean_28day":seasonal_mean,
                         "persistence_T_minus_6":persistence,
                         "Haurwitz_clear_sky_reference":sky}
        })

    early={"schema":"janus.open009f.physical_mle_early.v1",
           "kind":"RETROSPECTIVE_CHRONOLOGICAL_HOLDOUT_NOT_GENUINE_PROSPECTIVE",
           "prediction_model":MODEL_ID,
           "model_equation":"GHI = tau * 1361 * max(0,cos(solar_zenith)) + residual",
           "maximum_likelihood_fit":"tau = clamp(sum(E0*y)/sum(E0^2),0,1); sigma2=sum(resid^2)/n",
           "no_hand_tuned_blend":True,
           "target_dates":[t.isoformat() for t in TEST_DATES],
           "targets_read_before_local_precommit":False,
           "frozen_predictions":frozen}
    write_new(out/"physical_mle_early_009f.json",early)
    early_sha=sha(early)
    daily=[]
    for entry in frozen:
        day=fetch(dt.date.fromisoformat(entry["target"]))
        y=day["hourly_ghi"]
        row={"target":entry["target"], "target_raw_sha256":day["raw_sha256"],
             "pre_target_local_prediction_sha256":early_sha,
             "valid_hours":sum(v is not None and math.isfinite(v) for v in y),
             "status":"SCORED"}
        if len(y)!=24 or any(v is None or not math.isfinite(v) for v in y):
            row["status"]="INCOMPLETE_NO_SCORE"
        else:
            all_preds={MODEL_ID:entry["forecast"]["prediction_w_m2"],**entry["baselines"]}
            row["mae_w_m2"]={k:sum(abs(a-b) for a,b in zip(vals,y))/24 for k,vals in all_preds.items()}
            low,high=entry["forecast"]["lower90_w_m2"],entry["forecast"]["upper90_w_m2"]
            row["prediction_interval_90_coverage"]=sum(a<=v<=b for a,v,b in zip(low,y,high))/24
        daily.append(row)
        print("PHYSICAL_009F_DAY "+json.dumps(row,sort_keys=True),flush=True)

    complete=all(x["status"]=="SCORED" for x in daily)
    result={"schema":"janus.open009f.physical_mle_result.v1",
            "target_class":"REAL_HISTORICAL_NOAA",
            "historical_not_prospective":True,
            "original_sealed_OPEN009_unchanged":True,
            "target_read_only_after_local_early_file_fsync":True,
            "local_early_sha256":early_sha,
            "days":daily,"status":"COMPLETE_8_OF_8" if complete else "INCOMPLETE_NO_POOLED_SCORE",
            "model_limitations":["Gaussian residual assumptions unverified",
               "Mean atmospheric transmission assumed constant within 28 past days",
               "Solar geometry approximate, solar constant reference not real-time",
               "No weather input or cloud forecast",
               "Historical evaluation not independent prospective timestamp"],
            "retrocausality_proven":False}
    if complete:
        names=list(daily[0]["mae_w_m2"])
        pooled={k:sum(row["mae_w_m2"][k] for row in daily)/len(daily) for k in names}
        pvalues={}
        for baseline in names:
            if baseline==MODEL_ID:continue
            differences=[row["mae_w_m2"][baseline]-row["mae_w_m2"][MODEL_ID] for row in daily]
            pvalues[baseline]=exact_sign_flip_p(differences)
        result["pooled_mae_w_m2"]=pooled
        result["paired_exact_sign_flip_p_one_sided"] = pvalues
        result["mean_interval_90_coverage"]=statistics.mean(x["prediction_interval_90_coverage"] for x in daily)
        print("PHYSICAL_009F_POOLED "+json.dumps({k:v for k,v in result.items() if k.startswith("pooled_") or k.startswith("paired_") or k.startswith("mean_interval")},sort_keys=True),flush=True)
    write_new(out/"physical_mle_result_009f.json",result)
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-dir",required=True)
    args=ap.parse_args()
    backtest(Path(args.out_dir))


if __name__=="__main__":
    main()
