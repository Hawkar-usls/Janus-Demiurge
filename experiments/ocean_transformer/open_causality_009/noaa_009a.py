#!/usr/bin/env python3
"""OPEN-LIGHT-009A: honest prospective daily NOAA SURFRAD radiation forecast.

Only NOAA observations available at PREPARE are used. No target day is fetched
during PREPARE. Prediction artifact must be GitHub timestamped before target.
This is a classical forward prediction test, NOT retrocausality evidence.
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
import urllib.request

SCHEMA="janus.ocean.open_light_009a.v1"
STATION="bon"
STATION_NAME="Bondville_IL"
BASE="https://gml.noaa.gov/aftp/data/radiation/surfrad"
N_HISTORY=4
HISTORY_GAP_DAYS=4  # latest training day is prepare day minus four days
HOURS=24


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def now_utc():
    return dt.datetime.now(dt.timezone.utc)

def as_date(x):
    return dt.date.fromisoformat(x)

def parse_utc(x):
    t=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
    if t.tzinfo is None or t.utcoffset()!=dt.timedelta(0):
        raise ValueError("UTC_TIMESTAMP_REQUIRED")
    return t

def store(path,obj):
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf-8") as f:
        f.write(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n")

def url_for(date):
    return (f"{BASE}/{STATION}/{date.year}/"
            f"{STATION}{date.year%100:02d}{date.timetuple().tm_yday:03d}.dat")

def fetch(date):
    url=url_for(date)
    req=urllib.request.Request(url,headers={"User-Agent":"JANUS-Ocean-009A/1.0 scientific audit"})
    with urllib.request.urlopen(req,timeout=35) as handle:
        raw=handle.read(1200000)
    if len(raw)<30000 or len(raw)>1100000:
        raise ValueError("NOAA_DAILY_DATA_MISSING_OR_UNEXPECTED_SIZE")
    return parse_day(raw,date,url)

def parse_day(raw,date,url):
    """Official SURFRAD: 2 header lines + whitespace data, GHI column 8, QC 9."""
    lines=raw.decode("ascii").splitlines()
    if len(lines)<1002:
        raise ValueError("NOAA_DAILY_NOT_COMPLETE")
    info=lines[1].split()
    if len(info)<3:
        raise ValueError("NOAA_STATION_HEADER_INVALID")
    lat,lon=float(info[0]),float(info[1])
    if not (35.0<lat<45.0 and -95<lon< -80):
        raise ValueError("UNEXPECTED_NOAA_STATION_LOCATION")
    rows={}
    for line in lines[2:]:
        f=line.split()
        if len(f)<10: raise ValueError("NOAA_ROW_NOT_COMPLETE")
        year,jday,hour,minute=[int(f[i]) for i in (0,1,4,5)]
        if (year!=date.year or jday!=date.timetuple().tm_yday or
                not 0<=hour<24 or not 0<=minute<60):
            raise ValueError("NOAA_DATE_ROW_MISMATCH")
        key=hour*60+minute
        if key in rows: raise ValueError("NOAA_DUPLICATE_MINUTE")
        ghi=float(f[8])
        qc=int(f[9])
        if not math.isfinite(ghi):
            raise ValueError("NOAA_NONFINITE_RADIATION")
        rows[key]=(ghi,qc)
    if len(rows)!=1440 or any(i not in rows for i in range(1440)):
        raise ValueError("NOAA_MISSING_MINUTE_ROWS")
    mean=[]
    valid_counts=[]
    for hour in range(HOURS):
        vs=[max(0.0,rows[hour*60+m][0]) for m in range(60)
            if rows[hour*60+m][1]==0 and rows[hour*60+m][0]>-9000]
        mean.append(sum(vs)/len(vs) if len(vs)>=45 else None)
        valid_counts.append(len(vs))
    return {"date":date.isoformat(),"url":url,
            "raw_sha256":hashlib.sha256(raw).hexdigest(),
            "latitude":lat,"longitude":lon,
            "hourly_ghi":mean,"minute_valid_count":valid_counts,
            "qc_zero_only":True}

def solar_cos_zen(date,hour,lat,lon):
    """Approximate NOAA-style solar geometry at UTC hour midpoint."""
    n=date.timetuple().tm_yday
    minutes=hour*60+30
    gamma=2*math.pi/365*(n-1+(hour+0.5-12)/24)
    decl=(.006918-.399912*math.cos(gamma)+.070257*math.sin(gamma)
          -.006758*math.cos(2*gamma)+.000907*math.sin(2*gamma)
          -.002697*math.cos(3*gamma)+.00148*math.sin(3*gamma))
    eqtime=229.18*(.000075+.001868*math.cos(gamma)-.032077*math.sin(gamma)
                   -.014615*math.cos(2*gamma)-.040849*math.sin(2*gamma))
    true_minutes=(minutes+eqtime+4*lon)%1440
    ha=math.radians(true_minutes/4-180)
    la=math.radians(lat)
    return max(0.,min(1.,math.sin(la)*math.sin(decl)+math.cos(la)*math.cos(decl)*math.cos(ha)))

def haurwitz(date,hour,lat,lon):
    c=solar_cos_zen(date,hour,lat,lon)
    return 1098*c*math.exp(-.059/c) if c>0 else 0.0

def forecast(history,target):
    if len(history)!=N_HISTORY or len({x["date"] for x in history})!=N_HISTORY:
        raise ValueError("FOUR_DISTINCT_TRAINING_DAYS_REQUIRED")
    lat,lon=history[0]["latitude"],history[0]["longitude"]
    if any(abs(x["latitude"]-lat)>.1 or abs(x["longitude"]-lon)>.1 for x in history):
        raise ValueError("NOAA_STATION_COORDINATES_CHANGED")
    if any(any(v is None for v in x["hourly_ghi"]) for x in history):
        raise ValueError("NOAA_TRAINING_QC_HOURLY_INCOMPLETE")
    model=[]; base={"persistence":[],"diurnal":[],"clear_sky":[]}
    for h in range(HOURS):
        past=[x["hourly_ghi"][h] for x in history]
        persistence=past[-1]
        diurnal=sum(past)/len(past)
        sky=haurwitz(target,h,lat,lon)
        # Ratio trained only from past measured GHI / geometry for same hour.
        ratios=[min(1.5,x["hourly_ghi"][h]/haurwitz(as_date(x["date"]),h,lat,lon))
                for x in history if haurwitz(as_date(x["date"]),h,lat,lon)>30]
        transparency=statistics.median(ratios) if ratios else 0.0
        predicted=max(0.0,0.5*diurnal+0.5*sky*transparency)
        model.append(round(predicted,5))
        for key,val in (("persistence",persistence),("diurnal",diurnal),("clear_sky",sky)):
            base[key].append(round(max(0.0,val),5))
    return model,base

def prepare(target_date, now, source_days=None):
    if target_date<(now.date()+dt.timedelta(days=2)):
        raise ValueError("TARGET_MUST_BE_TWO_DAYS_AHEAD")
    train_dates=[now.date()-dt.timedelta(days=i) for i in range(HISTORY_GAP_DAYS+N_HISTORY-1,HISTORY_GAP_DAYS-1,-1)]
    rows=source_days if source_days is not None else [fetch(day) for day in train_dates]
    if [r["date"] for r in rows]!=[x.isoformat() for x in train_dates]:
        raise ValueError("NOAA_TRAINING_DATES_DRIFT")
    model,baselines=forecast(rows,target_date)
    payload={"schema":SCHEMA,"lane":"OPEN-LIGHT-009A","phase":"EARLY_PRECOMMIT",
             "created_utc":now.isoformat(),"target_date_utc":target_date.isoformat(),
             "target_first_unix":int(dt.datetime.combine(target_date,dt.time.min,tzinfo=dt.timezone.utc).timestamp()),
             "model":"FIXED_PHYSICS_INFORMED_SOLAR_RATIO_V1_NOT_NEURAL_TRANSFORMER",
             "expected_station":STATION,"training_dates":[r["date"] for r in rows],
             "training_source_sha256":[r["raw_sha256"] for r in rows],
             "training_source_url":[r["url"] for r in rows],
             "predictions_w_m2":model,"baselines_w_m2":baselines,
             "hours_utc":list(range(HOURS)),"target_data_seen":False,
             "original_QPU005_modified":False,"retrocausality_proven":False,
             "workflow_run_id":os.environ.get("GITHUB_RUN_ID","UNIT_TEST_NO_WITNESS")}
    return {"payload":payload,"sha256":sha(payload)}

def assess(early, target, artifact_created_at, now):
    p=early.get("payload")
    if not isinstance(p,dict) or early.get("sha256")!=sha(p) or p.get("lane")!="OPEN-LIGHT-009A":
        raise ValueError("FORECAST_COMMIT_HASH_WRONG")
    t=as_date(p["target_date_utc"])
    if target["date"]!=p["target_date_utc"] or target.get("latitude") is None:
        raise ValueError("NOAA_TARGET_DATE_OR_STATION_MISMATCH")
    attested=parse_utc(artifact_created_at)
    if attested >= dt.datetime.fromtimestamp(p["target_first_unix"],dt.timezone.utc):
        raise ValueError("NO_EARLY_GITHUB_WITNESS_BEFORE_TARGET")
    if now < dt.datetime.combine(t+dt.timedelta(days=3),dt.time.min,tzinfo=dt.timezone.utc):
        raise ValueError("TARGET_NOAA_RELEASE_EMBARGO")
    readings=target["hourly_ghi"]
    if len(readings)!=24 or any(v is None for v in readings):
        raise ValueError("NOAA_TARGET_INCOMPLETE_KEEP_UNKNOWN_NOT_ZERO")
    scores={}
    for name,vals in [("JANUS_PHYSICS_HEURISTIC",p["predictions_w_m2"]),*p["baselines_w_m2"].items()]:
        if len(vals)!=24 or any(not isinstance(v,(float,int)) or not math.isfinite(v) for v in vals):
            raise ValueError("BAD_PRECOMMITTED_FORECAST")
        scores[name]=round(sum(abs(a-b) for a,b in zip(vals,readings))/24,6)
    return {"schema":SCHEMA,"lane":"OPEN-LIGHT-009A","status":"PUBLIC_REAL_NOAA_OBSERVATION_SCORED",
            "early_forecast_sha256":early["sha256"],"github_witness_created_at":artifact_created_at,
            "target_date":p["target_date_utc"],"target_source_url":target["url"],
            "target_original_sha256":target["raw_sha256"],
            "target_all_24_hours":True,"n_hours":24,"mae_w_m2":scores,
            "model_beats_all_baselines":all(scores["JANUS_PHYSICS_HEURISTIC"]<v for n,v in scores.items() if n!="JANUS_PHYSICS_HEURISTIC"),
            "source_measurements_are_physical":True,"independent_retrocausal_late_choice":False,
            "retrocausality_proven":False}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=("prepare","assess"))
    ap.add_argument("--target",required=True)
    ap.add_argument("--early")
    ap.add_argument("--artifact-created-at")
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    if a.phase=="prepare":
        out=prepare(as_date(a.target),now_utc())
    else:
        if not a.early or not a.artifact_created_at: ap.error("assessment needs --early and --artifact-created-at")
        out=assess(json.loads(Path(a.early).read_text()),fetch(as_date(a.target)),a.artifact_created_at,now_utc())
    store(a.output,out)
    print(json.dumps({"status":out.get("status","PRECOMMITTED"),
                      "target":a.target,"sha256":sha(out),"retrocausality_proven":False}))
if __name__=="__main__":main()
