#!/usr/bin/env python3
"""JANUS: retrospectively test next-day oblast-level *alert starts*.

NOT a prediction of missile strikes, impact locations, or actionable safety
warnings. NEVER replace official alerts. Uses public volunteer oblast records
from 2022 onward; delayed prospective verification and baseline comparisons.
No exact-hour predictions; daily oblast-level probability only.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
from datetime import date,datetime,timedelta,timezone
from io import StringIO
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
import urllib.request
from zoneinfo import ZoneInfo

import torch
import torch.nn.functional as F
from janus_model.model import JanusTinyTransformer, JanusModelConfig, parameter_count

torch.set_num_threads(1)
KIEV=ZoneInfo("Europe/Kyiv")
SOURCE="https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/volunteer_data_en.csv"
REPO="https://github.com/Vadimkin/ukrainian-air-raid-sirens-dataset"
WIN=28
LEAD=2 # from last completed historical day to tomorrow
CONTEXT=1+WIN+2
CFG=JanusModelConfig(vocab_size=64,context_length=CONTEXT,d_model=32,
                     n_heads=4,n_layers=1,ff_mult=2,dropout=0.)
SEED=20261106
MIN_REGIONS=19
SAFETY_WARNING=(
    "RESEARCH_ONLY. This is a probabilistic regional forecast of PUBLIC AIR-ALERT "
    "STARTS, NOT missile strikes or their times/places. It is NOT reliable "
    "for personal safety decisions. Always follow official alerts and shelter instructions."
)


def filehash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p,j):
    path=Path(p);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(j,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")


def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))


def fetch_raw():
    req=urllib.request.Request(SOURCE,headers={"User-Agent":"JANUS-Civilian-Safety-Historical-Research/1.0"})
    error=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=60) as f:
                blob=f.read(25_000_001)
            if len(blob)>25_000_000:raise RuntimeError("DATASET_EXCEEDS_25MB_LIMIT")
            if not (500_000<len(blob)<25_000_000):raise RuntimeError("DATASET_ABNORMAL_SIZE")
            return blob
        except Exception as exc:
            error=str(exc);time.sleep(2*(attempt+1))
    raise RuntimeError("SOURCE_FETCH_FAILED: "+str(error))


def parse_utc(value):
    dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc)


def fetch(args):
    now=datetime.now(KIEV)
    cutoff=now.date()-timedelta(days=1)  # completed local calendar days only
    raw=fetch_raw()
    checksum=hashlib.sha256(raw).hexdigest()
    rows=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    required={"region","started_at"}
    if not required.issubset(set(rows.fieldnames or [])):
        raise RuntimeError("CSV_SCHEMA_MISMATCH "+str(rows.fieldnames))
    events=set()
    valid=0
    ignored=0
    years=Counter()
    for r in rows:
        try:
            name=(r["region"] or "").strip()
            time_start=parse_utc(r["started_at"])
            local_day=time_start.astimezone(KIEV).date()
            if not name or local_day>cutoff or local_day<date(2022,2,24):
                ignored+=1;continue
            events.add((name,local_day))
            valid+=1
            years[local_day.year]+=1
        except (ValueError,TypeError,OverflowError):
            ignored+=1
    if valid<40000 or len(years)<5:
        raise RuntimeError(f"INSUFFICIENT_FOUR_YEAR_DATA rows={valid} years={years}")
    recent=max(d for _,d in events)
    if recent < cutoff-timedelta(days=3):
        raise RuntimeError("STALE_ALERT_ARCHIVE: last event "+recent.isoformat())
    population=Counter(name for name,_ in events)
    # Only regions with sustained real coverage, exclude permanent siren gaps
    regions=sorted(name for name,n in population.items() if n>=150)
    if len(regions)<MIN_REGIONS or len(regions)>30:
        raise RuntimeError("REGION_COUNT_OUTSIDE_EXPECTED_RANGE "+str(len(regions)))
    first=min(d for _,d in events)
    days=(cutoff-first).days+1
    vectors=[[0]*days for _ in regions]
    reg_index={name:i for i,name in enumerate(regions)}
    for name,day in events:
        if name in reg_index:
            vectors[reg_index[name]][(day-first).days]=1
    if len(vectors)>30 or len(vectors)+21>CFG.vocab_size:
        raise RuntimeError("TOKEN_VOCAB_SIZE_EXCEEDED")
    snapshot={
        "schema":"janus.public_ukraine_alerts.daily_2022plus.v1",
        "downloaded_at_utc":now.astimezone(timezone.utc).isoformat(),
        "source_url":SOURCE,"source_repo":REPO,"source_license_claim":"MIT (upstream repository)",
        "source_sha256":checksum,"source_bytes":len(raw),
        "raw_valid_rows":valid,"raw_ignored_rows":ignored,
        "counts_by_year":dict(sorted(years.items())),
        "first_day_kyiv":first.isoformat(),"last_complete_day_kyiv":cutoff.isoformat(),
        "last_event_day_kyiv":recent.isoformat(),
        "regions":regions,"region_series":vectors,
        "label":"any recorded public air-alert start during local Kyiv civil calendar day",
        "target_horizon":"two days after last complete source day, i.e. tomorrow in Europe/Kyiv",
        "caveats":[
            "Volunteer eTryvoga messages, not independent authoritative verification of each impact.",
            "Some permanent sirens not represented and no end time necessary for this starts-only dataset.",
            "Missing event rows treated as zero start counts: gaps and Telegram parsing changes are possible.",
            "Region naming and administrative subdivisions may change.",
            "The data describe alarms, not missiles, attacks, or strikes.",
            "No coordinates, local routes, tactical predictions, or exact launch/impact times are generated.",
        ],
        "public_safety_notice":SAFETY_WARNING
    }
    save(args.output,snapshot)
    print(json.dumps({"status":"FOUR_YEAR_OBLAST_ALERTS_FROZEN",
                      "valid_event_rows":valid,"years":dict(years),"regions":len(regions),
                      "first_date":first.isoformat(),"last_day":cutoff.isoformat(),
                      "last_event":recent.isoformat(),"snapshot_sha256":filehash(args.output)},indent=2))


def daydate(s,dayidx):return date.fromisoformat(s["first_day_kyiv"])+timedelta(days=dayidx)


def model_init():
    torch.manual_seed(SEED);return JanusTinyTransformer(CFG)


def splits(s):
    n=len(s["region_series"][0])
    for region in s["region_series"]:
        if len(region)!=n:raise RuntimeError("REGIONAL_LENGTH_MISMATCH")
    tr_end=int(n*.70);val_end=int(n*.85)
    # Predictions at anchor t predict t+2. Enforce a 3-day embargo.
    train_days=range(WIN-1,tr_end-LEAD)
    valid_days=range(tr_end+4,val_end-LEAD)
    test_days=range(val_end+4,n-LEAD)
    if min(len(train_days),len(valid_days),len(test_days))<100:
        raise RuntimeError("CHRONOLOGICAL_SPLIT_TOO_SMALL")
    nregs=len(s["regions"])
    flatten=lambda rr:[(d,r) for d in rr for r in range(nregs)]
    return flatten(train_days),flatten(valid_days),flatten(test_days)


def batch(s,ids):
    series=s["region_series"];nregs=len(s["regions"]);first=date.fromisoformat(s["first_day_kyiv"])
    rows=[];targets=[]
    for d,reg in ids:
        known=series[reg][d-WIN+1:d+1]
        if len(known)!=WIN:raise RuntimeError("INPUT_WINDOW_LENGTH")
        day=first+timedelta(days=d+LEAD)
        # Token ranges: 0/1 alert flags, 2+ region IDs, 2+R day-of-week, 9+R month
        tokens=[2+reg]+known+[2+nregs+day.weekday(),2+nregs+7+day.month-1]
        if len(tokens)!=CONTEXT:raise RuntimeError("CONTEXT_LENGTH")
        rows.append(tokens)
        # Future inference does not have a label yet. A dummy value is returned
        # only for API shape; probs_for() explicitly discards it. Historical
        # evaluation labels MUST exist, and those checks stay in score().
        targets.append(series[reg][d+LEAD] if d+LEAD<len(series[reg]) else 0)
    return torch.tensor(rows,dtype=torch.long),torch.tensor(targets,dtype=torch.long)


@torch.no_grad()
def probs_for(model,s,indices,temperature=1):
    model.eval();chunks=[]
    for k in range(0,len(indices),512):
        x,_=batch(s,indices[k:k+512])
        logits,_=model(x)
        chunks.append(torch.softmax(logits[:,-1,:2]/temperature,-1)[:,1])
    return torch.cat(chunks)


def baseline_probabilities(s,train,test):
    nregs=len(s["regions"]);counts=[0]*nregs
    denom=[0]*nregs
    for d,r in train:
        counts[r]+=s["region_series"][r][d+LEAD]
        denom[r]+=1
    regional=[(counts[r]+1)/(denom[r]+2) for r in range(nregs)]
    recent=[];longterm=[]
    for d,r in test:
        v=s["region_series"][r][d-WIN+1:d+1]
        # modest 2-event Laplace smoothing to avoid confident zero/one outputs
        recent.append((sum(v)+1)/(len(v)+2))
        longterm.append(regional[r])
    return torch.tensor(recent),torch.tensor(longterm)


def score(probs,targets):
    probs=probs.clamp(.00001,.99999)
    return {"n":len(targets),
            "base_rate":round(float(targets.float().mean()),6),
            "accuracy_threshold_0_5":round(float(((probs>=.5)==targets.bool()).float().mean()),6),
            "brier":round(float(((probs-targets.float())**2).mean()),6),
            "log_loss":round(float(F.binary_cross_entropy(probs,targets.float())),6)}


def worker(args):
    start=time.monotonic()
    s=read(args.snapshot);train,_,_=splits(s)
    anchors=train[args.worker::args.workers]
    if len(anchors)<400:raise RuntimeError("SHARD_TOO_SMALL")
    model=model_init()
    opt=torch.optim.AdamW(model.parameters(),lr=.003,weight_decay=.001)
    rnd=random.Random(9000+args.worker*977)
    steps=0
    for k in range(args.steps):
        if steps>=80 and time.monotonic()-start>=args.budget:break
        indices=rnd.choices(anchors,k=args.batch)
        x,y=batch(s,indices)
        model.train();opt.zero_grad(set_to_none=True)
        z,_=model(x)
        loss=F.cross_entropy(z[:,-1,:2],y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1)
        opt.step();steps+=1
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    checkpoint=out/"weights.pt"
    torch.save({"state":{k:v.cpu() for k,v in model.state_dict().items()},
                "config":CFG.to_dict(),"worker":args.worker,
                "snapshot_sha256":filehash(args.snapshot),"anchors":len(anchors)},checkpoint)
    info={"schema":"janus.public_alerts.river.v1","worker":args.worker,"workers":args.workers,
          "anchors":len(anchors),"steps":steps,"snapshot_sha256":filehash(args.snapshot),
          "weight_sha256":filehash(checkpoint),"seconds":round(time.monotonic()-start,3)}
    save(out/"river.json",info)
    print(json.dumps(info,indent=2))


def aggregate(args):
    s=read(args.snapshot);tr,va,te=splits(s)
    files=list(Path(args.input).glob("*/river.json"))
    if len(files)!=args.workers:raise RuntimeError("MISSING_ALERT_RIVERS")
    state=model_init().state_dict()
    summation={k:torch.zeros_like(v,dtype=torch.float64) for k,v in state.items()}
    seen=set();count=0;logs=[]
    for file in files:
        r=read(file);wid=r["worker"]
        if wid in seen or not 0<=wid<args.workers or r["workers"]!=args.workers or r["snapshot_sha256"]!=filehash(args.snapshot):
            raise RuntimeError("RIVER_INTEGRITY_FAIL")
        seen.add(wid)
        path=file.parent/"weights.pt"
        if filehash(path)!=r["weight_sha256"]:raise RuntimeError("WEIGHTS_SHA_FAIL")
        obj=torch.load(path,map_location="cpu",weights_only=True)
        if obj["config"]!=CFG.to_dict() or obj["worker"]!=wid or obj["snapshot_sha256"]!=filehash(args.snapshot):
            raise RuntimeError("WEIGHTS_PROVENANCE_FAIL")
        if obj["anchors"]<400:raise RuntimeError("NOT_ENOUGH_ANCHORS")
        for k in state:
            w=obj["state"][k]
            if w.shape!=state[k].shape or not bool(torch.isfinite(w).all()):
                raise RuntimeError("BAD_MODEL_WEIGHTS")
            summation[k]+=w.double()*obj["anchors"]
        count+=obj["anchors"];logs.append(r)
    if seen!=set(range(args.workers)):raise RuntimeError("MISSING_RIVER")
    merged={k:(v/count).to(dtype=state[k].dtype) for k,v in summation.items()}
    model=model_init();model.load_state_dict(merged,strict=True)
    # Validate temperature and mixture using strictly past validation, not test.
    _,validation_labels=batch(s,va)
    recent_v,long_v=baseline_probabilities(s,tr,va)
    temperatures=[.65,.8,1.,1.2,1.5,2.]
    ratios=[0.,.25,.5,.75,1.]
    best=None
    for t in temperatures:
        pred=probs_for(model,s,va,t)
        for a in ratios:
            blended=a*pred+(1-a)*recent_v
            loss=float(((blended-validation_labels.float())**2).mean())
            if best is None or loss<best[0]:best=(loss,t,a)
    _,t_star,a_star=best
    test_predictions=probs_for(model,s,te,t_star)
    recent,longrate=baseline_probabilities(s,tr,te)
    _,y=batch(s,te)
    blended=a_star*test_predictions+(1-a_star)*recent
    # Forecast tomorrow from yesterday's completed archive, not incomplete today.
    latest=len(s["region_series"][0])-1
    now=datetime.now(KIEV)
    target=daydate(s,latest+LEAD)
    if target!=now.date()+timedelta(days=1):
        raise RuntimeError("NOT_TOMORROW_TARGET__DATA_SNAPSHOT_TOO_OLD")
    nregs=len(s["regions"])
    ids=[(latest,r) for r in range(nregs)]
    nn=probs_for(model,s,ids,t_star)
    forecast=[]
    for r,name in enumerate(s["regions"]):
        xs=s["region_series"][r][latest-WIN+1:latest+1]
        simple=(sum(xs)+1)/(WIN+2)
        prob=float(a_star*nn[r]+(1-a_star)*simple)
        forecast.append({"oblast":name,
                         "probability_next_local_day_alert_start":round(prob,6),
                         "recent_28day_baseline":round(simple,6)})
    forecast.sort(key=lambda x:x["oblast"])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    ck=out/"alerts_candidate.pt"
    torch.save({"state":model.state_dict(),"cfg":CFG.to_dict(),
                "temperature":t_star,"blend":a_star,"promotion":False},ck)
    pre={
        "schema":"janus.ukraine.public_alerts.experimental_daily.v1",
        "issued_at_utc":datetime.now(timezone.utc).isoformat(),
        "target_local_date":target.isoformat(),
        "time_window":"24-hour Kyiv calendar day; NO exact hour prediction",
        "level":"OBLAST_ONLY",
        "target_definition":"at least one recorded PUBLIC air-alert START (not a strike)",
        "region_probabilities":forecast,
        "source_sha256":s["source_sha256"],
        "source_last_complete_day":s["last_complete_day_kyiv"],
        "model_sha256":filehash(ck),
        "evidence_status":"FROZEN_BEFORE_FULL_TARGET_DAY",
        "not_strike_prediction":True,
        "official_warning":SAFETY_WARNING,
        "use_for_civilian_alerting":False,
        "potentially_biasing_data_gaps":s["caveats"],
    }
    save(out/"alerts_precommit.json",pre)
    result={
        "schema":"janus.ukraine.alerts.four_year_model_v1",
        "dataset_start":s["first_day_kyiv"],
        "dataset_end":s["last_complete_day_kyiv"],
        "input_source":"Public volunteer air-alert starts, not strikes",
        "yearly_rows":s["counts_by_year"],
        "raw_rows":s["raw_valid_rows"],
        "oblasts":len(s["regions"]),
        "train_region_days":len(tr),"validation_region_days":len(va),"test_region_days":len(te),
        "workers_verified":len(seen),
        "model_architecture":"JANUS JanusTinyTransformer, last-28-day binary alert-history + region + target calendar",
        "model_parameters":parameter_count(model),
        "forecast_horizon_from_completed_archive_days":LEAD,
        "calibration_temperature":t_star,
        "validation_selected_model_weight":a_star,
        "test_neural":score(test_predictions,y),
        "test_calibrated_blend":score(blended,y),
        "test_recent_28d_baseline":score(recent,y),
        "test_region_long_run_rate_baseline":score(longrate,y),
        "weights_sha256":filehash(ck),
        "source_snapshot_sha256":filehash(args.snapshot),
        "workers":sorted(logs,key=lambda x:x["worker"]),
        "prospective_forecast":pre,
        "safety":"RESEARCH ONLY. Never present as official warning or forecast of missile impacts.",
        "automation":"daily GitHub Actions with recorded source snapshots; manual validation before any user-facing safety claims",
        "production_promotion":False,
        "current_gate":"EXPERIMENTAL_NOT_VALIDATED_FOR_SAFETY",
        "warnings":[
            "Regional public siren starts do not identify strikes or locations/timing of missiles.",
            "Time-correlated observations are not independent; naive N counts overstate significance.",
            "Missing siren data can mean missing collection, not that it was safe.",
            "No precise location/timestamp of an attack is inferred.",
            "Model should not trigger alert notifications or advise anyone to ignore shelter orders."
        ]
    }
    save(out/"alerts_result.json",result)
    with open(os.environ.get("GITHUB_STEP_SUMMARY","/dev/null"),"a") as fh:
        fh.write("## JANUS Ukraine historical public air-alert research\n\n")
        fh.write(f"- Years: {s['first_day_kyiv']} through {s['last_complete_day_kyiv']}; {s['raw_valid_rows']:,} rows / {len(s['regions'])} regions\n")
        fh.write(f"- Holdout samples region-days: {len(te):,}; workers: {len(seen)}\n")
        fh.write(f"- Brier: model {result['test_neural']['brier']}, validation blend {result['test_calibrated_blend']['brier']}, last28 baseline {result['test_recent_28d_baseline']['brier']}\n")
        fh.write(f"- Target local day: **{target.isoformat()}**; daily oblast probabilities sealed in artifact.\n")
        fh.write("- **Not a prediction of actual strikes. Do NOT use for life safety. Follow official Ukraine air alarms.**\n")
    print(json.dumps({k:v for k,v in result.items() if k!="workers"},indent=2))


def cli():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("snapshot");a.add_argument("--output",required=True)
    w=sub.add_parser("worker");w.add_argument("--snapshot",required=True)
    w.add_argument("--workers",type=int,default=8);w.add_argument("--worker",type=int,required=True)
    w.add_argument("--steps",type=int,default=280);w.add_argument("--budget",type=float,default=38)
    w.add_argument("--batch",type=int,default=64);w.add_argument("--output",required=True)
    q=sub.add_parser("aggregate");q.add_argument("--snapshot",required=True)
    q.add_argument("--workers",type=int,default=8);q.add_argument("--input",required=True)
    q.add_argument("--output",required=True)
    args=p.parse_args()
    if args.cmd=="snapshot":fetch(args)
    elif args.cmd=="worker":worker(args)
    else:aggregate(args)


if __name__=="__main__":
    cli()
