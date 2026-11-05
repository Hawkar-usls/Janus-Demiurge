#!/usr/bin/env python3
"""JANUS Ocean v3: bounded 40-river retraining on real ERA5 observations.

Uses JANUS's actual JanusTinyTransformer; improves v2 with conditional 24-hour
temperature-change prediction, an All Star level/delta temporal input, FedAvg
on different historical shards, calibration on validation only, and preserved
prospective forecasts. No claims of backward-time data transmission.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import torch
import torch.nn.functional as F
import real_weather_forecast as old
from janus_model.model import JanusModelConfig, JanusTinyTransformer, parameter_count

torch.set_num_threads(1)

WORKERS = 40
H = 24
D = 30
CLASSES = 2 * D + 1
LEVELS = torch.arange(-D, D + 1, dtype=torch.float32)
CFG = JanusModelConfig(
    vocab_size=old.BUCKETS + old.DIFF_BUCKETS,
    context_length=old.WINDOW * 2,
    d_model=48, n_heads=4, n_layers=2, ff_mult=2, dropout=0.0
)
SEED = 2026110603
SOURCE_DAYS = 900
TRANSFER = {"label": "Lviv_external_validation_only", "latitude": 49.8397, "longitude": 24.0297}


def new_model():
    torch.manual_seed(SEED)
    return JanusTinyTransformer(CFG)


def json_write(p, v):
    old.write_json(p, v)


def fetch(args):
    start = time.monotonic()
    now = datetime.now(timezone.utc)
    end_day = now.date() - timedelta(days=8)
    start_day = end_day - timedelta(days=SOURCE_DAYS)
    params = {
        "latitude": old.LOCATION["latitude"], "longitude": old.LOCATION["longitude"],
        "start_date": start_day.isoformat(), "end_date": end_day.isoformat(),
        "hourly": "temperature_2m", "models": "era5", "timezone": "UTC"
    }
    kyiv, kyiv_prov = old.remote_json("https://archive-api.open-meteo.com/v1/archive", params)
    transfer_params = dict(params, latitude=TRANSFER["latitude"], longitude=TRANSFER["longitude"])
    lviv, lviv_prov = old.remote_json(
        "https://archive-api.open-meteo.com/v1/archive", transfer_params
    )
    times = kyiv["hourly"]["time"]
    temps = kyiv["hourly"]["temperature_2m"]
    transfer_times = lviv["hourly"]["time"]
    transfer_temps = lviv["hourly"]["temperature_2m"]
    if times != transfer_times or len(times) < 15000:
        raise RuntimeError("DATA_SOURCE_TIME_ALIGNMENT_FAIL")
    if (len(temps) != len(times) or len(transfer_temps) != len(times)
        or any(v is None or not isinstance(v, (float, int)) or not math.isfinite(v)
               for v in (temps + transfer_temps))):
        raise RuntimeError("NONFINITE_OR_MISSING_SOURCE")
    if any((old.iso_hour(times[i+1]) - old.iso_hour(times[i])).total_seconds() != 3600
           for i in range(len(times) - 1)):
        raise RuntimeError("HOURLY_GAP")
    if old.iso_hour(times[-1]) > now - timedelta(days=7):
        raise RuntimeError("FUTURE_SOURCE_LEAKAGE")
    live_params = {
        "latitude": old.LOCATION["latitude"], "longitude": old.LOCATION["longitude"],
        "hourly": "temperature_2m", "past_days": 3, "forecast_days": 3, "timezone": "UTC"
    }
    live, live_prov = old.remote_json("https://api.open-meteo.com/v1/forecast", live_params)
    anchor = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    valid = anchor + timedelta(hours=H)
    lookup = {old.iso_hour(t): v for t, v in zip(live["hourly"]["time"], live["hourly"]["temperature_2m"])}
    input_times = [anchor - timedelta(hours=23-i) for i in range(24)]
    inputs = [lookup.get(t) for t in input_times]
    official = lookup.get(valid)
    if (any(v is None or not math.isfinite(float(v)) for v in inputs)
        or official is None or not math.isfinite(float(official))):
        raise RuntimeError("LIVE_INPUT_MISSING")
    snapshot = {
        "schema": "janus.ocean.v3.real.weather.snapshot",
        "captured_at_utc": now.isoformat(),
        "snapshot_is_immutable_per_workflow_run": True,
        "training_source": "Open-Meteo ERA5 hourly temperature_2m delayed reanalysis",
        "trained_location": old.LOCATION,
        "transfer_location": TRANSFER,
        "kyiv": {"time": times, "temp": temps, "provenance": kyiv_prov},
        "lviv_transfer_only": {"time": transfer_times, "temp": transfer_temps, "provenance": lviv_prov},
        "live": {
            "anchor_utc": anchor.isoformat(),
            "valid_target_utc": valid.isoformat(),
            "past_model_estimated_temperatures": inputs,
            "official_forecast_temp_c": float(official),
            "source_provenance": live_prov,
            "reveal_not_before_utc": (valid + timedelta(days=7)).isoformat(),
            "note": "Recent input is Open-Meteo model estimate; not independent station measurement."
        },
        "blind_holdout_policy": "Workers use only training anchors; temperature scaling and blend are chosen using Kyiv validation; final Kyiv test and Lviv transfer test are read only in aggregator.",
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    json_write(args.output, snapshot)
    print(json.dumps({
        "phase": "FROZEN_V3_REAL_SNAPSHOT", "hours_per_city": len(times),
        "trained_city": old.LOCATION["label"], "transfer_city": TRANSFER["label"],
        "latest_era5_utc": times[-1], "future_target_utc": valid.isoformat(),
        "snapshot_sha256": old.hash_file(args.output),
        "fetch_wall_seconds": round(time.monotonic()-start, 2),
    }, indent=2))


def split(snapshot):
    values = torch.tensor(snapshot["kyiv"]["temp"], dtype=torch.float32)
    n = len(values)
    # 48h embargoes: no training outcome can touch a validation outcome.
    tr_end = int(n*0.70)
    va_end = int(n*0.85)
    tr = list(range(23, tr_end - H))
    va = list(range(tr_end+48, va_end-H))
    te = list(range(va_end+48, n-H))
    if len(tr) < 4000 or len(va) < 500 or len(te) < 500:
        raise RuntimeError("CHRONOLOGICAL_SPLIT_INSUFFICIENT")
    return values, tr, va, te


def batch(values, indices):
    x = torch.stack([
        old.allstar_weather_features(values[i-23:i+1]) for i in indices
    ])
    anchors = torch.tensor(indices, dtype=torch.long)
    diff = values[anchors + H] - values[anchors]
    labels = (diff.round().long()+D).clamp(0,CLASSES-1)
    return x, labels


@torch.no_grad()
def logits_eval(model, values, indices):
    model.eval()
    out=[]
    for k in range(0, len(indices), 256):
        v=indices[k:k+256]
        x=torch.stack([old.allstar_weather_features(values[i-23:i+1]) for i in v])
        out.append(model(x)[0][:, -1, :CLASSES].float())
    return torch.cat(out, 0)


def objective_fit(logits, values, indices, temperature=1., correction_strength=1.):
    last = values[torch.tensor(indices, dtype=torch.long)]
    truth = values[torch.tensor(indices, dtype=torch.long) + H]
    probs = torch.softmax(logits / temperature, dim=-1)
    correction = probs @ LEVELS
    predicted = last + correction_strength * correction
    persistence = last
    moving = torch.stack([values[i-23:i+1].mean() for i in indices])
    targets = ((truth - last).round().long()+D).clamp(0, CLASSES-1)
    frost = (probs * (
        last.unsqueeze(1) + correction_strength * LEVELS.unsqueeze(0) <= 0
    ).float()).sum(-1)
    return {
        "n": int(len(indices)),
        "mae_c": round(float((predicted-truth).abs().mean()), 6),
        "rmse_c": round(float(((predicted-truth)**2).mean().sqrt()), 6),
        "nll_delta": round(float(F.cross_entropy(logits / temperature, targets)), 6),
        "frost_brier": round(float(((frost-(truth<=0).float())**2).mean()), 6),
        "persistence_mae_c": round(float((persistence-truth).abs().mean()), 6),
        "mean24h_mae_c": round(float((moving-truth).abs().mean()), 6),
        "clipped_targets": int(((truth-last).abs() > D).sum()),
    }


def worker(args):
    begin = time.monotonic()
    snapshot=old.read_json(args.snapshot)
    values,tr,va,te=split(snapshot)
    anchors=tr[args.worker::args.workers]
    if len(anchors)<150: raise RuntimeError("RIVER_SHARD_TOO_SMALL")
    model=new_model()
    optimizer=torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.001)
    rng=random.Random(80000 + args.worker*779)
    steps=0
    for step in range(args.steps):
        if steps>=100 and time.monotonic()-begin >= args.seconds:
            break
        ids=rng.choices(anchors,k=args.batch_size)
        x,y=batch(values,ids)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        z,_=model(x)
        loss=F.cross_entropy(z[:,-1,:CLASSES],y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
        optimizer.step()
        steps+=1
    out=Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    weight=out/"weights.pt"
    torch.save({
        "model_state": {k: v.detach().cpu() for k,v in model.state_dict().items()},
        "config": CFG.to_dict(), "worker_id": args.worker,
        "workers": args.workers, "samples_anchors": len(anchors),
        "source_sha256":old.hash_file(args.snapshot)
    }, weight)
    record={
        "schema":"janus.ocean.v3.river",
        "worker_id":args.worker, "workers":args.workers,
        "train_anchor_count":len(anchors), "steps":steps,
        "generated_training_batches":steps*args.batch_size,
        "snapshot_sha256":old.hash_file(args.snapshot),
        "weights_sha256":old.hash_file(weight),
        "time_seconds":round(time.monotonic()-begin,3),
        "model_parameters":parameter_count(model),
        "production_checkpoint_write":False,
    }
    json_write(out/"river.json",record)
    print(json.dumps(record,indent=2))


def aggregate(args):
    begin=time.monotonic()
    snapshot=old.read_json(args.snapshot)
    values,tr,va,te=split(snapshot)
    transfer=torch.tensor(snapshot["lviv_transfer_only"]["temp"],dtype=torch.float32)
    source_hash=old.hash_file(args.snapshot)
    files=list(Path(args.input).glob("*/river.json"))
    if len(files)!=args.workers:raise RuntimeError(f"INCOMPLETE_RIVERS_{len(files)}")
    state=new_model().state_dict()
    acc={k:torch.zeros_like(v,dtype=torch.float64) for k,v in state.items()}
    seen=set()
    count=0
    logs=[]
    for file in files:
        j=old.read_json(file)
        wid=j["worker_id"]
        if wid in seen or wid<0 or wid>=args.workers or j["snapshot_sha256"]!=source_hash or j["workers"]!=args.workers:
            raise RuntimeError("RIVER_SCHEMA_OR_SHA_MISMATCH")
        seen.add(wid)
        weight=file.parent/"weights.pt"
        if j["weights_sha256"]!=old.hash_file(weight):
            raise RuntimeError("RIVER_WEIGHT_DIGEST_FAIL")
        obj=torch.load(weight,map_location="cpu",weights_only=True)
        if obj["config"]!=CFG.to_dict() or obj["source_sha256"]!=source_hash or obj["worker_id"]!=wid:
            raise RuntimeError("RIVER_WEIGHTS_PROVENANCE_FAIL")
        st=obj["model_state"]
        n=obj["samples_anchors"]
        if set(st)!=set(state) or n<150:
            raise RuntimeError("RIVER_PARAMETER_OR_SOURCE_SHAPE_FAIL")
        for k in state:
            v=st[k]
            if v.shape!=state[k].shape or not torch.isfinite(v).all():
                raise RuntimeError("NONFINITE_OR_BAD_WEIGHTS")
            acc[k]+=v.double()*n
        logs.append(j)
        count+=n
    if seen!=set(range(args.workers)):raise RuntimeError("MISSING_RIVER_ID")
    weights={k:(v/count).to(dtype=state[k].dtype) for k,v in acc.items()}
    model=new_model()
    model.load_state_dict(weights,strict=True)
    init=new_model()
    # All hyperparameter choices below use *validation only*, never Kyiv test
    # or the held-out Lviv city.
    val_logits=logits_eval(model,values,va)
    val_truth=values[torch.tensor(va)+H]-values[torch.tensor(va)]
    val_labels=(val_truth.round().long()+D).clamp(0,CLASSES-1)
    temps=[0.65,0.8,1.0,1.2,1.5,2.0]
    t_star=min(temps,key=lambda t:float(F.cross_entropy(val_logits/t,val_labels)))
    lambdas=[0.0,0.25,0.5,0.75,1.0]
    lam_star=min(lambdas,key=lambda lam:objective_fit(val_logits,values,va,t_star,lam)["mae_c"])
    test_logits=logits_eval(model,values,te)
    initial_logits=logits_eval(init,values,te)
    raw_test=objective_fit(test_logits,values,te,t_star,1.)
    gated_test=objective_fit(test_logits,values,te,t_star,lam_star)
    init_test=objective_fit(initial_logits,values,te,1.,1.)
    # Lviv geographic transfer holdout: NEVER used for fitting or selection
    lviv_logits=logits_eval(model,transfer,te)
    lviv_metrics=objective_fit(lviv_logits,transfer,te,t_star,lam_star)

    recent=snapshot["live"]
    recent_t=torch.tensor(recent["past_model_estimated_temperatures"],dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        z=model(old.allstar_weather_features(recent_t).unsqueeze(0))[0][:,-1,:CLASSES]
        probabilities=torch.softmax(z/t_star,dim=-1)[0]
        raw_temp=float(recent_t[-1]+probabilities@LEVELS)
        selected_temp=float(recent_t[-1]+lam_star*(probabilities@LEVELS))
        future_values=recent_t[-1]+lam_star*LEVELS
        frost_prob=float(probabilities[future_values<=0].sum())
    now=datetime.now(timezone.utc)
    target=datetime.fromisoformat(recent["valid_target_utc"])
    if not now<target:
        raise RuntimeError("NOT_PRE_OUTCOME_FORECAST")
    trial="janus-ocean-v3-"+os.getenv("GITHUB_RUN_ID","local")+"-"+target.strftime("%Y%m%dT%H%MZ")
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    weight_path=out/"ocean_candidate.pt"
    torch.save({
        "config": CFG.to_dict(),"model_state": model.state_dict(),
        "source_sha256":source_hash, "validation_temperature":t_star,
        "validation_correction_strength":lam_star,"promotion":False
    },weight_path)

    forecast={
        "schema":"janus.ocean.weather.future.precommit.v3",
        "trial_id":trial,
        "issued_at_utc":now.isoformat(),
        "valid_target_utc":recent["valid_target_utc"],
        "target_ground_truth":"Open-Meteo ERA5 temperature_2m with delayed release",
        "reveal_not_before_utc":recent["reveal_not_before_utc"],
        "location":snapshot["trained_location"],
        "horizon_hours":H,
        "model_mean_temperature_c":round(selected_temp,5),
        "model_ungated_temperature_c":round(raw_temp,5),
        "model_frost_probability":round(frost_prob,6),
        "model_residual_class_probs":[round(float(x),8) for x in probabilities],
        "baseline_persistence_24h_c":round(float(recent_t[-1]),5),
        "baseline_mean_24h_c":round(float(recent_t.mean()),5),
        "baseline_operational_weather_model_c":float(recent["official_forecast_temp_c"]),
        "validation_temperature":t_star,
        "validation_correction_strength":lam_star,
        "weather_snapshot_sha256":source_hash,
        "model_checkpoint_sha256":old.hash_file(weight_path),
        "issuance_precedes_target":True,
        "truth_already_used_in_training":False,
        "prospective_repetition_group":"The same weather target may also have a v2 forecast. Count outcomes, not number of model precommits, as independent events.",
        "no_physical_retrocausal_channel":True,
        "production_promotion":False,
    }
    json_write(out/"future_precommit.json",forecast)
    result={
        "schema":"janus.ocean.v3.distributed.weather.training",
        "workers_requested":args.workers,
        "workers_verified":len(seen),
        "runner_claim":"GitHub-hosted Ubuntu jobs; concurrent allocation decided by GitHub/account plan",
        "train_anchors":len(tr),"validation_anchors":len(va),
        "kyiv_test_anchors":len(te),"lviv_transfer_test_anchors":len(te),
        "source_data_hours":len(values),"source_end_utc":snapshot["kyiv"]["time"][-1],
        "source_snapshot_sha256":source_hash,
        "config":CFG.to_dict(),"parameters":parameter_count(model),
        "method":"FedAvg on disjoint anchor shards and shared initial weights; All Star level/delta inputs; residual 24h forecast",
        "model_parameters_promotion":False,
        "validation_selected_temperature":t_star,
        "validation_selected_blend_strength":lam_star,
        "kyiv_untrained":init_test,
        "kyiv_raw_trained":raw_test,
        "kyiv_validation_gated":gated_test,
        "lviv_geographic_transfer":lviv_metrics,
        "kyiv_model_beats_persistence_on_holdout":gated_test["mae_c"]<gated_test["persistence_mae_c"],
        "workers":sorted(logs,key=lambda x:x["worker_id"]),
        "future_forecast":forecast,
        "ocean_checkpoint_sha256":old.hash_file(weight_path),
        "total_worker_training_seconds":round(sum(x["time_seconds"] for x in logs),2),
        "ocean_aggregation_seconds":round(time.monotonic()-begin,2),
        "status":"RESEARCH_ONLY__NO_RETROCAUSAL_PROOF__NO_AUTOMATIC_PROMOTION",
        "methodology_notes":[
            "The test data follow train and validation chronologically, with embargo.",
            "Kyiv test period overlaps earlier v2 historical studies; not an untouched first-ever benchmark.",
            "Lviv time series were never used for worker training or hyperparameter selection.",
            "Validation chooses both temperature and residual correction strength, including abstention lambda=0.",
            "No use of future weather ground truth for the prospective prediction.",
            "All Star's solar concept inspires features, not a claim of solar-flare prediction skill.",
            "GitHub-hardware count is matrix job count, not independently measured peak concurrency."
        ],
    }
    json_write(out/"ocean_result.json",result)
    with open(os.getenv("GITHUB_STEP_SUMMARY",os.devnull),"a") as f:
        f.write("## JANUS Ocean v3 — 40 river real ERA5 retraining\n\n")
        f.write(f"- Workers verified: **{len(seen)}/{args.workers}**\n")
        f.write(f"- Training observations: **{len(values)} hours**\n")
        f.write(f"- Model parameters: **{parameter_count(model)}**\n")
        f.write(f"- Kyiv 24h MAE: **{gated_test['mae_c']} °C**, raw **{raw_test['mae_c']} °C**, persistence **{gated_test['persistence_mae_c']} °C**\n")
        f.write(f"- Lviv transfer MAE: **{lviv_metrics['mae_c']} °C**, persistence **{lviv_metrics['persistence_mae_c']} °C**\n")
        f.write(f"- Validation temperature/blend: **{t_star} / {lam_star}**\n")
        f.write(f"- Future target: **{target.isoformat()}**; locked value **{selected_temp:.4f} °C**\n")
        f.write("- Experimental only. No production change. No physical retrocausal interface.\n")
    print(json.dumps({k:v for k,v in result.items() if k!="workers"},indent=2))


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    fetcher=sub.add_parser("fetch")
    fetcher.add_argument("--output",default="data/ocean_v3_snapshot.json")
    w=sub.add_parser("worker")
    w.add_argument("--snapshot",required=True)
    w.add_argument("--workers",type=int,default=40)
    w.add_argument("--worker",type=int,required=True)
    w.add_argument("--steps",type=int,default=650)
    w.add_argument("--seconds",type=float,default=40.0)
    w.add_argument("--lr",type=float,default=0.003)
    w.add_argument("--batch-size",type=int,default=64)
    w.add_argument("--output",required=True)
    a=sub.add_parser("aggregate")
    a.add_argument("--snapshot",required=True)
    a.add_argument("--workers",type=int,default=40)
    a.add_argument("--input",required=True)
    a.add_argument("--output",required=True)
    args=p.parse_args()
    if args.cmd=="fetch":fetch(args)
    elif args.cmd=="worker":worker(args)
    else:aggregate(args)


if __name__=="__main__":
    main()
