#!/usr/bin/env python3
"""JANUS Ocean v2: real ERA5 weather, chronological tests, sealed future forecasts.

No production checkpoint changes. Use the project's JanusTinyTransformer, train
on separate chronological shards across Github Actions workers, FedAvg weights,
evaluate against weather persistence/24-hour mean, and preregister next-day
predictions. Future outcomes are verified later from ERA5, NEVER invented.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import random
import secrets
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from janus_model.model import JanusTinyTransformer, JanusModelConfig, parameter_count

torch.set_num_threads(1)
LOCATION = {"label": "Kyiv_public_weather_benchmark", "latitude": 50.4501, "longitude": 30.5234}
HORIZON_HOURS = 24
WINDOW = 24
BUCKETS = 81
OFFSET = 30
DIFF_BUCKETS = 41
DIFF_OFFSET = 20
SEED = 20261106
# All Star solar lineage: (level, first difference) is encoded in each hour.
# Weather temperature may be negative; do NOT apply solar log10 transformation.
CFG = JanusModelConfig(vocab_size=BUCKETS + DIFF_BUCKETS, context_length=WINDOW * 2, d_model=32,
                       n_heads=4, n_layers=1, ff_mult=2, dropout=0.0)
LEVELS = torch.arange(BUCKETS).float() - OFFSET


def hash_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def remote_json(base, params):
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "JANUS-Real-Forecast-Research/1.0"})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=35) as f:
                data = f.read(4000000)
            result = json.loads(data)
            if result.get("error"):
                raise RuntimeError(result.get("reason", "upstream error"))
            return result, {"url": url, "response_sha256": hashlib.sha256(data).hexdigest()}
        except Exception as e:
            last_error = str(e)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"DATA_SOURCE_UNAVAILABLE: {last_error}")


def iso_hour(t):
    return datetime.fromisoformat(t).replace(tzinfo=timezone.utc)


def fetch_weather():
    now = datetime.now(timezone.utc)
    end_day = now.date() - timedelta(days=8)  # ERA5 is typically available after ~5 days.
    start_day = end_day - timedelta(days=430)
    params = dict(latitude=LOCATION["latitude"], longitude=LOCATION["longitude"],
                  start_date=start_day.isoformat(), end_date=end_day.isoformat(),
                  hourly="temperature_2m", models="era5", timezone="UTC")
    archive, a_prov = remote_json("https://archive-api.open-meteo.com/v1/archive", params)
    times = archive["hourly"]["time"]
    temps = archive["hourly"]["temperature_2m"]
    if len(times) < 5500 or len(times) != len(temps):
        raise RuntimeError("INSUFFICIENT_ERA5_HISTORY")
    if any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in temps):
        raise RuntimeError("ERA5_NULL_OR_NONFINITE")
    if any((iso_hour(times[i+1]) - iso_hour(times[i])).total_seconds() != 3600
           for i in range(len(times) - 1)):
        raise RuntimeError("ERA5_TIMELINE_GAP")
    if iso_hour(times[-1]) > now - timedelta(days=7):
        raise RuntimeError("SOURCE_FUTURE_LEAKAGE")

    live_params = dict(latitude=LOCATION["latitude"], longitude=LOCATION["longitude"],
                       hourly="temperature_2m", past_days=3, forecast_days=3, timezone="UTC")
    live, l_prov = remote_json("https://api.open-meteo.com/v1/forecast", live_params)
    observed_at = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    valid_at = observed_at + timedelta(hours=HORIZON_HOURS)
    lt = live["hourly"]["time"]
    lv = live["hourly"]["temperature_2m"]
    lookup = {iso_hour(t): x for t, x in zip(lt, lv)}
    input_times = [observed_at - timedelta(hours=WINDOW-1-i) for i in range(WINDOW)]
    input_values = [lookup.get(t) for t in input_times]
    if any(v is None or not math.isfinite(v) for v in input_values):
        raise RuntimeError("MISSING_RECENT_WEATHER_INPUT")
    official_baseline = lookup.get(valid_at)
    if official_baseline is None or not math.isfinite(official_baseline):
        raise RuntimeError("MISSING_FUTURE_OFFICIAL_FORECAST")
    snapshot = {
        "schema": "janus.ocean.weather.snapshot.v1",
        "source_type": "Open-Meteo ERA5 reanalysis; recent input from current forecast-model hourly feed",
        "location": LOCATION,
        "snapshot_created_at_utc": now.isoformat(),
        "hourly_era5": {"time": times, "temperature_2m": temps},
        "archive_fetch_provenance": a_prov,
        "live_forecast_provenance": l_prov,
        "live_input": {
            "observation_anchor_utc": observed_at.isoformat(),
            "valid_target_utc": valid_at.isoformat(),
            "past_24h_model_estimated_temperatures": input_values,
            "official_weather_forecast_temperature_2m": float(official_baseline),
            "disclosure_not_before_utc": (valid_at + timedelta(days=7)).isoformat(),
            "note": "Recent hourly values are feed estimates, not independent station observations. No future temperatures fed into JANUS model."
        },
        "label_delay_days": 7,
        "target_ground_truth": "Delayed Open-Meteo ERA5 reanalysis temperature_2m at fixed valid_target_utc",
    }
    write_json("data/weather_snapshot.json", snapshot)
    print(json.dumps({
        "status": "REAL_WEATHER_SNAPSHOT_FROZEN",
        "source_times": len(times), "end_utc": times[-1],
        "recent_anchor": observed_at.isoformat(), "future_target": valid_at.isoformat(),
        "archive_response_sha256": a_prov["response_sha256"],
        "snapshot_sha256": hash_file("data/weather_snapshot.json"),
    }, indent=2))


def temps_to_tokens(t):
    return (torch.round(t).long() + OFFSET).clamp_(0, BUCKETS-1)


def allstar_weather_features(window_values):
    """Encode 24 causal temperature readings plus first differences.

    The inspiration is All_starsGPT's log-flux / delta-flux solar window,
    adapted for signed air temperatures and without double normalization.
    Every delta depends only on the current and previous hour.
    """
    levels = temps_to_tokens(window_values)
    delta = torch.zeros_like(window_values)
    delta[1:] = window_values[1:] - window_values[:-1]
    delta_tokens = torch.round(delta).long().clamp(-DIFF_OFFSET, DIFF_OFFSET)
    delta_tokens = delta_tokens + BUCKETS + DIFF_OFFSET
    return torch.stack((levels, delta_tokens), dim=1).reshape(-1)


def to_arrays(snapshot):
    values = torch.tensor(snapshot["hourly_era5"]["temperature_2m"], dtype=torch.float32)
    n = len(values)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)
    embargo = 48
    train_anchor = list(range(WINDOW-1, train_end-HORIZON_HOURS))
    val_anchor = list(range(train_end+embargo, val_end-HORIZON_HOURS))
    test_anchor = list(range(val_end+embargo, n-HORIZON_HOURS))
    if min(len(train_anchor),len(val_anchor),len(test_anchor)) < 80:
        raise RuntimeError("CHRONOLOGICAL_SPLIT_TOO_SMALL")
    return values, temps_to_tokens(values), train_anchor, val_anchor, test_anchor


def make_model():
    torch.manual_seed(SEED)
    return JanusTinyTransformer(CFG)


def minibatch(tokens, values, anchors):
    x = torch.stack([allstar_weather_features(values[k-WINDOW+1:k+1]) for k in anchors])
    y_cls = tokens[torch.tensor(anchors, dtype=torch.long) + HORIZON_HOURS]
    y_temp = values[torch.tensor(anchors, dtype=torch.long) + HORIZON_HOURS]
    return x, y_cls, y_temp


@torch.no_grad()
def inferred_logits(model, values, anchors, batch_size=256):
    model.eval()
    pieces = []
    for i in range(0,len(anchors),batch_size):
        x = torch.stack([allstar_weather_features(values[k-WINDOW+1:k+1]) for k in anchors[i:i+batch_size]])
        pieces.append(model(x)[0][:,-1,:BUCKETS].float())
    return torch.cat(pieces)


@torch.no_grad()
def regression_metrics(logits, values, anchors, t=1.0):
    targets = values[torch.tensor(anchors) + HORIZON_HOURS]
    seq = values[torch.tensor(anchors)]
    moving = torch.stack([values[k-WINDOW+1:k+1].mean() for k in anchors])
    probs = torch.softmax(logits / t, dim=-1)
    preds = probs @ LEVELS
    ground_cls = temps_to_tokens(targets)
    return {
        "n": len(anchors),
        "model_mae_c": round(float(torch.abs(preds-targets).mean()),5),
        "model_rmse_c": round(float(((preds-targets)**2).mean().sqrt()),5),
        "model_discrete_nll": round(float(F.cross_entropy(logits/t, ground_cls)),5),
        "persist_24h_mae_c": round(float(torch.abs(seq-targets).mean()),5),
        "persist_24h_rmse_c": round(float(((seq-targets)**2).mean().sqrt()),5),
        "mean_24h_mae_c": round(float(torch.abs(moving-targets).mean()),5),
        "model_frost_brier": round(float((
            (probs[:,:OFFSET+1].sum(dim=-1) - (targets<=0).float())**2
        ).mean()),6),
    }


def worker(args):
    started=time.monotonic()
    snapshot=read_json(args.snapshot)
    values,tokens,train,val,test=to_arrays(snapshot)
    # Non-overlapping anchor shards, globally identical initial weights.
    anchors=train[args.worker::args.workers]
    if len(anchors)<100: raise RuntimeError("RIVER_SHARD_TOO_SMALL")
    rng=random.Random(432198+args.worker*877)
    model=make_model()
    opt=torch.optim.AdamW(model.parameters(),lr=0.003,weight_decay=0.0005)
    completed=0
    for i in range(args.steps):
        if i>=80 and time.monotonic()-started>args.budget_seconds:
            break
        picks=rng.choices(anchors,k=args.batch)
        x,y,_=minibatch(tokens,values,picks)
        model.train()
        opt.zero_grad(set_to_none=True)
        logits,_=model(x)
        loss=F.cross_entropy(logits[:,-1,:BUCKETS],y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        opt.step()
        completed+=1
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/"weights.pt"
    torch.save({
        "config":CFG.to_dict(), "worker_id":args.worker,
        "dataset_sha256":hash_file(Path(args.snapshot)),
        "n_training_anchors":len(anchors),
        "model_state":{k:v.detach().cpu() for k,v in model.state_dict().items()},
    },checkpoint)
    report={
        "schema":"janus.ocean.weather.river.v1","worker_id":args.worker,
        "worker_count":args.workers,"source":"OPEN_METEO_ERA5_REAL_REANALYSIS",
        "dataset_sha256":hash_file(Path(args.snapshot)),
        "train_split":len(train),"validation_split":len(val),"test_split":len(test),
        "training_anchor_count":len(anchors),
        "steps":completed,"batch":args.batch,
        "training_seconds":round(time.monotonic()-started,3),
        "weights_sha256":hash_file(checkpoint),
        "production_weights_modified":False,
    }
    write_json(out/"river.json",report)
    print(json.dumps(report,indent=2))


def aggregate(args):
    snapshot=read_json(args.snapshot)
    values,tokens,train,val,test=to_arrays(snapshot)
    snap_hash=hash_file(Path(args.snapshot))
    files=list(Path(args.input).glob("*/river.json"))
    if len(files)!=args.workers: raise RuntimeError(f"EXPECTED_{args.workers}_RIVERS_GOT_{len(files)}")
    init=make_model()
    state=init.state_dict()
    accumulator={k:torch.zeros_like(v,dtype=torch.float64) for k,v in state.items()}
    total=0
    reports=[]
    ids=set()
    for f in files:
        r=read_json(f)
        if r["worker_id"] in ids or r["worker_count"]!=args.workers or r["dataset_sha256"]!=snap_hash:
            raise RuntimeError("RIVER_MISMATCH_OR_DUPLICATE")
        ids.add(r["worker_id"])
        weight=f.parent/"weights.pt"
        if r["weights_sha256"]!=hash_file(weight):raise RuntimeError("CORRUPTED_RIVER")
        obj=torch.load(weight,map_location="cpu",weights_only=True)
        if obj["config"]!=CFG.to_dict() or obj["dataset_sha256"]!=snap_hash:raise RuntimeError("CONFIG_MISMATCH")
        count=obj["n_training_anchors"]
        for k in state:
            v=obj["model_state"][k]
            if v.shape!=state[k].shape or not bool(torch.isfinite(v).all()): raise RuntimeError("BAD_WEIGHT")
            accumulator[k]+=v.double()*count
        total+=count
        reports.append(r)
    if ids!=set(range(args.workers)):raise RuntimeError("MISSING_RIVER_INDEX")
    merged={k:(v/total).to(dtype=state[k].dtype) for k,v in accumulator.items()}
    model=make_model()
    model.load_state_dict(merged,strict=True)
    # Evaluate validation only to tune one scalar, never optimize on test labels.
    val_logits=inferred_logits(model,values,val)
    val_labels=tokens[torch.tensor(val)+HORIZON_HOURS]
    temperatures=[0.6,0.75,0.9,1.0,1.15,1.35,1.6,2.0,2.5]
    t_star=min(temperatures,key=lambda t:float(F.cross_entropy(val_logits/t,val_labels)))
    test_logits=inferred_logits(model,values,test)
    initial_logits=inferred_logits(init,values,test)
    test_metric=regression_metrics(test_logits,values,test,t_star)
    initial_metric=regression_metrics(initial_logits,values,test,1.0)
    official=snapshot["live_input"]
    live=torch.tensor(official["past_24h_model_estimated_temperatures"],dtype=torch.float32)
    with torch.no_grad():
        pred_logits=model(allstar_weather_features(live).unsqueeze(0))[0][:,-1,:BUCKETS]
        probs=torch.softmax(pred_logits/t_star,dim=-1)[0]
    predicted=float(probs@LEVELS)
    valid=official["valid_target_utc"]
    issuance=datetime.now(timezone.utc)
    if datetime.fromisoformat(valid) <= issuance:
        raise RuntimeError("NONFUTURE_ISSUANCE")
    trial="janus-weather-"+valid.replace(":","").replace("-","").replace("+00:00","Z")
    forecast={
        "schema":"janus.ocean.weather.future.precommit.v1",
        "trial_id":trial,"issued_at_utc":issuance.isoformat(),
        "valid_target_utc":valid,"target_ground_truth":"Open-Meteo ERA5 reanalysis temperature_2m",
        "reveal_not_before_utc":official["disclosure_not_before_utc"],
        "location":LOCATION,"horizon_hours":HORIZON_HOURS,
        "model_mean_temperature_c":round(predicted,4),
        "model_frost_probability":round(float(probs[:OFFSET+1].sum()),6),
        "model_81_class_probabilities":[round(float(x),7) for x in probs],
        "baseline_persistence_24h_c":round(float(live[-1]),4),
        "baseline_mean_24h_c":round(float(live.mean()),4),
        "baseline_operational_weather_model_c":official["official_weather_forecast_temperature_2m"],
        "model_checkpoint_sha256":None,
        "weather_snapshot_sha256":snap_hash,
        "official_forecast_source_sha256":snapshot["live_forecast_provenance"]["response_sha256"],
        "precommit_state":"FROZEN_BEFORE_TARGET_TIME__OUTCOME_UNKNOWN",
        "truth_already_used_in_training":False,
        "physical_retrocausal_channel":False,
    }
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ckpt=out/"ocean_candidate.pt"
    torch.save({
        "config":CFG.to_dict(),"model_state":model.state_dict(),
        "temperature":t_star,"dataset_sha256":snap_hash,
        "production_promotion":False,
    },ckpt)
    forecast["model_checkpoint_sha256"]=hash_file(ckpt)
    write_json(out/"future_precommit.json",forecast)
    result={
        "schema":"janus.ocean.weather.training_result.v1",
        "location":LOCATION,
        "source":"Open-Meteo ERA5 (reanalyzed history), hourly temperature_2m",
        "weather_snapshot_sha256":snap_hash,
        "train":len(train),"validation":len(val),"historical_holdout":len(test),
        "n_workers_verified":len(files),"workers":sorted(reports,key=lambda v:v["worker_id"]),
        "architecture":"JanusTinyTransformer existing class; new small weather-config with All Star temporal-delta features",
        "parameters":parameter_count(model),"aggregation":"FedAvg over distinct train-anchor shards",
        "all_star_solar_lineage":"All_starsGPT(20261105-223030).py: real data, rolling windows, level plus first derivative, best-only memory; signed-weather adaptation uses interleaved tokens and no double normalization; original code/checkpoints not published",
        "temperature_calibrated_on_validation":t_star,
        "untrained_holdout":initial_metric,
        "trained_holdout":test_metric,
        "historical_beats_persistence_mae":test_metric["model_mae_c"]<test_metric["persist_24h_mae_c"],
        "future_trial_id":trial,
        "future_status":"OUTCOME_NOT_YET_AVAILABLE",
        "future_prediction_file":"future_precommit.json",
        "candidate_checkpoint_sha256":hash_file(ckpt),
        "full_real_world_retrocausality_proven":False,
        "production_checkpoint_modified":False,
        "cautions":[
            "ERA5 is retrospective weather reanalysis, not a direct local station sensor",
            "Recent input uses forecast API past-model values, not a weather-station observation",
            "Prospective forecast cannot be scored before delayed external data release",
            "Chronological holdout is historical: no random-split leakage",
            "Winning on reanalysis does not mean information was transferred backward in time",
        ],
    }
    write_json(out/"training_result.json",result)
    with open(os.getenv("GITHUB_STEP_SUMMARY",os.devnull),"a") as h:
        h.write("## JANUS Ocean: REAL weather benchmark\n")
        h.write(f"- Rivers: **{len(files)}**; model parameters: **{parameter_count(model)}**\n")
        h.write(f"- Chronological holdout hours: **{len(test)}**\n")
        h.write(f"- Model MAE: **{test_metric['model_mae_c']} C**\n")
        h.write(f"- Persistence MAE: **{test_metric['persist_24h_mae_c']} C**\n")
        h.write(f"- 24h mean MAE: **{test_metric['mean_24h_mae_c']} C**\n")
        h.write(f"- Trial: **{trial}**\n")
        h.write(f"- Tomorrow forecast: **{predicted:.3f} C**\n")
        h.write("- **No future outcome has been observed or scored. No retrocausality claim.**\n")
    print(json.dumps({"result":result,"future_precommit":forecast},indent=2))


def resolve(args):
    ledger=Path(args.ledger)
    if not ledger.exists():raise RuntimeError("NO_LEDGER_DIRECTORY")
    forecasts=sorted(ledger.glob("*.json"))
    today=datetime.now(timezone.utc)
    resolved=Path(args.resolved)
    resolved.mkdir(parents=True,exist_ok=True)
    examined=0;scored=0;pending=0
    for path in forecasts:
        f=read_json(path)
        target=datetime.fromisoformat(f["valid_target_utc"])
        if target+timedelta(days=7)>today:
            pending+=1
            continue
        destination=resolved/(f["trial_id"]+".json")
        if destination.exists():continue
        examined+=1
        params=dict(latitude=f["location"]["latitude"],longitude=f["location"]["longitude"],
                    start_date=target.date().isoformat(),end_date=target.date().isoformat(),
                    hourly="temperature_2m",models="era5",timezone="UTC")
        payload,provenance=remote_json("https://archive-api.open-meteo.com/v1/archive",params)
        lookup={iso_hour(t):v for t,v in zip(payload["hourly"]["time"],payload["hourly"]["temperature_2m"])}
        truth=lookup.get(target)
        if truth is None or not math.isfinite(truth):raise RuntimeError("TRUTH_MISSING_WAIT")
        metrics={}
        for name,key in [
            ("JANUS","model_mean_temperature_c"),("PERSISTENCE","baseline_persistence_24h_c"),
            ("MOVING_24H","baseline_mean_24h_c"),("OFFICIAL_MODEL","baseline_operational_weather_model_c"),
        ]:
            err=float(f[key])-truth
            metrics[name]={"prediction_c":f[key],"absolute_error_c":round(abs(err),6),"squared_error_c2":round(err**2,6)}
        frost_actual=1 if truth<=0 else 0
        result={
            "schema":"janus.ocean.weather.future.resolved.v1",
            "trial_id":f["trial_id"],"prediction_committed_at_utc":f["issued_at_utc"],
            "valid_target_utc":f["valid_target_utc"],"resolved_at_utc":today.isoformat(),
            "ground_truth_era5_temp_c":truth,"frost_actual":frost_actual,
            "forecast_file_sha256":hash_file(path),
            "source_response_sha256":provenance["response_sha256"],
            "source_url":provenance["url"],
            "frost_brier":round((f["model_frost_probability"]-frost_actual)**2,6),
            "metrics":metrics,
            "retrocausality_proven":False,
            "outcome_maturity_checked":True,
        }
        write_json(destination,result)
        scored+=1
    status={"status":"RESOLUTION_ATTEMPT_COMPLETE","forecast_files":len(forecasts),
            "pending_unmatured":pending,"eligible_examined":examined,"new_outcomes_resolved":scored}
    print(json.dumps(status,indent=2))
    with open(os.getenv("GITHUB_STEP_SUMMARY",os.devnull),"a") as h:
        h.write("## JANUS delayed ERA5 outcome resolution\n")
        h.write(f"- Seen {len(forecasts)} forecasts; {pending} pending; {scored} newly resolved\n")


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("fetch")
    w=sub.add_parser("worker")
    w.add_argument("--snapshot",default="data/weather_snapshot.json")
    w.add_argument("--worker",type=int,required=True)
    w.add_argument("--workers",type=int,default=8)
    w.add_argument("--steps",type=int,default=280)
    w.add_argument("--batch",type=int,default=64)
    w.add_argument("--budget-seconds",type=float,default=50)
    w.add_argument("--output",required=True)
    a=sub.add_parser("aggregate")
    a.add_argument("--snapshot",default="data/weather_snapshot.json")
    a.add_argument("--workers",type=int,default=8)
    a.add_argument("--input",required=True)
    a.add_argument("--output",required=True)
    res=sub.add_parser("resolve")
    res.add_argument("--ledger",required=True)
    res.add_argument("--resolved",required=True)
    args=parser.parse_args()
    if args.command=="fetch": fetch_weather()
    if args.command=="worker": worker(args)
    if args.command=="aggregate": aggregate(args)
    if args.command=="resolve":resolve(args)


if __name__=="__main__":
    main()
