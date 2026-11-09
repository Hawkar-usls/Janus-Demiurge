#!/usr/bin/env python3
"""GLOW-010 open-lab REAL nanosecond photoluminescence decay comparison.

Source: Delgado et al., Advanced Photonics Research 3 (2022) 2100179,
CC BY 4.0, Zenodo 10.5281/zenodo.6991932/loadingcurve.zip, fixed MD5.

Distinguish these FAST excited-state decay observations in NANOSECONDS from
persistent phosphor afterglow in SECONDS/HOURS. They do NOT measure SUNLU
composite filaments or establish future-to-past transmission.

Three functional families fitted on first 264/441 rows ONLY:
mono:  background + A exp(-t/tau)
bi:    background + A1 exp(-t/tau1) + A2 exp(-t/tau2)
power: background + A (1+t/t0)^(-alpha)
Weighted training squared residual / sqrt(max(Iobs,25)).
Holdout: last 177 rows, all included even if negative background corrected.
Compare test MAE in original intensity/counts, never model selection in train
followed by reinterpretation of historical test as prospective evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import zipfile

import numpy as np
from scipy.optimize import least_squares
import scipy
import published_data_audit_010 as audit

SCHEMA="janus.ocean.glow010.real_fast_photoluminescence_decay_fit.v1"
SAMPLES={1:"Eu_only",2:"Eu_plus_B",3:"Eu_plus_Dy"}
N_EXPECTED=441
N_TRAIN=264
BLOCK_LENGTH=12
N_BOOTSTRAP=2000
KINDS=("mono","bi","power")

def model(kind,p,t):
    if kind=="mono":
        b,a,tau=p
        return b+a*np.exp(-t/tau)
    if kind=="bi":
        b,a1,tau1,a2,tau2=p
        return b+a1*np.exp(-t/tau1)+a2*np.exp(-t/tau2)
    if kind=="power":
        b,a,scale,alpha=p
        return b+a*np.power(1+t/scale,-alpha)
    raise ValueError("UNSUPPORTED_MODEL_KIND")

def load_sample(source_zip,sample):
    if sample not in SAMPLES: raise ValueError("NOT_A_REGISTERED_SAMPLE")
    name=f"Decaydata/sample{sample}_biexp_w_bg.txt"
    with zipfile.ZipFile(io.BytesIO(source_zip)) as z:
        raw=z.read(name)
    values=np.loadtxt(io.BytesIO(raw))
    if (values.shape!=(N_EXPECTED,4) or not np.isfinite(values).all()
        or not np.all(np.diff(values[:,0])>0)
        or abs(values[0,0]-105)>1e-6
        or abs(values[-1,0]-6705)>1e-6):
        raise ValueError("ORIGINAL_PHOTOLUMINESCENCE_MEASUREMENT_FORMAT_CHANGED")
    return values[:,0],values[:,1],hashlib.sha256(raw).hexdigest()

def model_initializations(kind,values):
    amp=float(max(values))
    bg=float(max(0,np.percentile(values[-40:],20)))
    if kind=="mono":
        return ([[bg,amp,tau] for tau in (500,1500,3000)]+[[0,amp,1000]],
                ([0,0,1],[amp,amp*10,100_000]))
    if kind=="bi":
        starts=[]
        for tau1,tau2 in [(100,1000),(250,2000),(500,5000),(30,400),(600,5000)]:
            for f in (.3,.6):
                starts.append([bg,amp*f,tau1,amp*(1-f),tau2])
        return starts,([0,0,1,0,1],[amp,amp*10,100_000,amp*10,100_000])
    if kind=="power":
        starts=[[bg,amp,scale,alpha] for scale in (50,150,500,1500,3000)
                for alpha in (.5,1,2,3,4)]
        return starts,([0,0,1,.05],[amp,amp*10,100_000,12])
    raise ValueError("UNSUPPORTED_MODEL_KIND")

def fit_one(x,y,kind):
    if len(x)!=N_EXPECTED or len(y)!=N_EXPECTED:
        raise ValueError("CHRONOLOGICAL_441_ROWS_REQUIRED")
    tr_t=x[:N_TRAIN]-x[0]
    tr_y=y[:N_TRAIN]
    te_t=x[N_TRAIN:]-x[0]
    te_y=y[N_TRAIN:]
    starts,bounds=model_initializations(kind,tr_y)
    w=np.sqrt(np.maximum(tr_y,25))
    best=None
    for init in starts:
        p0=np.clip(np.array(init,dtype=float),
                   np.array(bounds[0])+1e-9,np.array(bounds[1])-1e-9)
        r=least_squares(lambda p:(model(kind,p,tr_t)-tr_y)/w,
                        p0,bounds=bounds,max_nfev=2500,
                        ftol=1e-9,xtol=1e-9,gtol=1e-9)
        val=float(np.sum(r.fun**2))
        if best is None or val<best[0]:
            best=(val,r.x)
    predicted=model(kind,best[1],te_t)
    err=np.abs(predicted-te_y)
    # All raw held-out rows preserved; no use of later outcomes in optimizer.
    return {
      "kind":kind,
      "parameters":[round(float(p),9) for p in best[1]],
      "n_train":N_TRAIN,"n_test":len(te_y),
      "train_weighted_sse":round(best[0],7),
      "holdout_mae_original_units":round(float(np.mean(err)),7),
      "holdout_rmse_original_units":round(float(np.sqrt(np.mean((predicted-te_y)**2))),7),
      "holdout_weighted_rmse":round(float(np.sqrt(np.mean(
            ((predicted-te_y)/np.sqrt(np.maximum(te_y,25)))**2))),7),
      "holdout_error_vector":err,
    }

def paired_block_bootstrap_bi_minus_power(bi_err,power_err,sample):
    diff=np.asarray(bi_err)-np.asarray(power_err)
    n=len(diff)
    if n!=N_EXPECTED-N_TRAIN:raise ValueError("HOLDOUT_LENGTH_CHANGED")
    gen=np.random.default_rng(20261110+sample)
    vals=np.empty(N_BOOTSTRAP)
    for i in range(N_BOOTSTRAP):
        idx=[]
        for _ in range(math.ceil(n/BLOCK_LENGTH)):
            start=int(gen.integers(0,n-BLOCK_LENGTH+1))
            idx.extend(range(start,start+BLOCK_LENGTH))
        vals[i]=float(np.mean(diff[idx[:n]]))
    low,high=np.quantile(vals,[.025,.975])
    return {"difference_positive_favors_power":round(float(np.mean(diff)),6),
            "block_bootstrap_95pct_interval":[round(float(low),6),round(float(high),6)],
            "block_length_rows":BLOCK_LENGTH,"bootstrap_replicates":N_BOOTSTRAP,
            "not_an_independent_experimental_replication":True}

def run(original_zip):
    if hashlib.md5(original_zip).hexdigest()!="423e3e457d3458a0aac0b20365ebfd4b":
        raise ValueError("REAL_SOURCE_ZENODO_ZIP_MD5_MISMATCH")
    rows=[]
    for sample in SAMPLES:
        x,y,file_sha=load_sample(original_zip,sample)
        results={name:fit_one(x,y,name) for name in KINDS}
        bootstrap=paired_block_bootstrap_bi_minus_power(
            results["bi"]["holdout_error_vector"],
            results["power"]["holdout_error_vector"],sample)
        winner=min(KINDS,key=lambda name:results[name]["holdout_mae_original_units"])
        rows.append({
          "sample":sample,"material":SAMPLES[sample],
          "source_file_sha256":file_sha,
          "time_units":"nanoseconds",
          "intensity_units":"source reported photoluminescence counts/relative units",
          "time_first_ns":float(x[0]),"time_last_ns":float(x[-1]),
          "negative_background_corrected_intensities_included":bool(np.any(y<0)),
          "train_rows":N_TRAIN,"test_rows":N_EXPECTED-N_TRAIN,
          "winner_on_this_exploratory_historical_holdout":winner,
          "family_fit_scores":[{
            k:v for k,v in results[name].items() if k!="holdout_error_vector"
          } for name in KINDS],
          "paired_improvement_biexp_to_power":bootstrap,
        })
    return {
      "schema":SCHEMA,"experiment":"JANUS-OCEAN-GLOW-010",
      "status":"ACTUAL_PUBLIC_FAST_NANOSECOND_PHOTOLUMINESCENCE_FITS_COMPLETED",
      "source":{"zenodo_doi":"10.5281/zenodo.6991932","article_doi":"10.1002/adpr.202100179",
                "author":"Delgado et al. 2022","license":"CC BY 4.0",
                "zip_md5":"423e3e457d3458a0aac0b20365ebfd4b",
                "zip_sha256":hashlib.sha256(original_zip).hexdigest()},
      "method":{
        "split":"first 264 real chronological time/intensity rows to fit, remaining 177 for held-out scoring, per material",
        "training_weight":"max(observed intensity,25)^(-1/2), weighted nonlinear least squares",
        "holdout_primary":"unweighted MAE in source intensity units, ALL 177 holdout observations retained",
        "model_families":{
           "mono":"b+A*exp(-(t-t_first)/tau)",
           "bi":"b+A1*exp(-(t-t_first)/tau1)+A2*exp(-(t-t_first)/tau2)",
           "power":"b+A*(1+(t-t_first)/scale)^(-alpha)",
        },
        "multistart_fit":"deterministic bounded nonlinear least_squares; 4, 10, 25 initializations",
        "confidence_interval":"Exploratory paired moving-block bootstrap on late residual differences, not independent confidence of a general scientific effect",
        "numpy_version":np.__version__,"scipy_version":scipy.__version__,
        "all_hyperparameters_selected_for_exploration_not_pre_registered_before_2022_data":True
      },
      "samples":rows,
      "all_three_historical_samples_power_best":all(x["winner_on_this_exploratory_historical_holdout"]=="power" for x in rows),
      "actual_afterglow_in_seconds_fitted":False,
      "millisecond_to_multihour_trap_memory_parameters_identified":False,
      "no_real_SUNLU_PLA_Glow_phosphor_measurements":True,
      "retrocausality_proven":False,
      "scientific_limitations":[
        "These time-resolved curves are nanosecond prompt luminescence after a pulse, not measured hours-long green afterglow.",
        "S1 (Eu), S2 (Eu+B) and S3 (Eu+Dy) differ in compositions. They are not direct replication samples of one material.",
        "Historic source data and split were inspected retrospectively; holdout cannot be promoted to a prospective preregistered confirmatory test.",
        "The power-law advantage on this one time-split does not establish the microscopic recombination mechanism.",
        "The late part may be affected by instrument background/negative corrected counts; compare with independently calibrated photodetection apparatus to generalize.",
        "A model of real glow-PLA energy storage in seconds and hours requires real afterglow measurements, temperature, excitation, optical absorption and material loading calibration.",
      ]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    results=run(audit.fetch() if hasattr(audit,"fetch") else None)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf8") as f:
        f.write(json.dumps(results,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":results["status"],"samples":[
      {"sample":v["sample"],"winner":v["winner_on_this_exploratory_historical_holdout"],
       "mae":{m["kind"]:m["holdout_mae_original_units"] for m in v["family_fit_scores"]}}
       for v in results["samples"]]},sort_keys=True))
if __name__=="__main__":
    main()
