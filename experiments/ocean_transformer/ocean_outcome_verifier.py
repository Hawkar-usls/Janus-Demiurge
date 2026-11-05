#!/usr/bin/env python3
"""Independent non-production resolver for JANUS Ocean MetaNext and air-alert models.

Reads sealed forecasts from isolated Git branches. After source outcomes mature,
writes append-only resolution JSON. No model learning, tactical alerting,
retrocausality claims, or production modification is performed.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo
import urllib.request
import time

GIT_SOURCE="https://github.com/Hawkar-usls/janus-meta-registry.git"
CSV_SOURCE="https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/volunteer_data_en.csv"
KIEV=ZoneInfo("Europe/Kyiv")
SKIP_PREFIXES=("JANUS-META-NEXT-","JANUS-AIR-ALERT-")
NOTICE="Research result only. Never use these statistics instead of official air-raid warnings or shelter instructions."


def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise RuntimeError("REFUSE_OVERWRITE_EXISTING_FORECAST_EVALUATION")
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def hashbytes(content):return hashlib.sha256(content).hexdigest()
def parse_time(value):
    return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)


def classify(path):
    parts=path.split("/")
    parent="/".join(parts[:-1]) or "_root"
    filename=parts[-1].removesuffix(".json")
    tokens=re.findall(r"[A-Za-z][A-Za-z0-9]{1,16}",filename)
    ignore={"janus","v1","v2","v3","json","registry","meta","state","report","data"}
    token=next((s.lower() for s in tokens if s.lower() not in ignore),"misc")
    return parent+"/"+token


def git(cwd,*args,timeout=180):
    proc=subprocess.run(["git",*args],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if proc.returncode:raise RuntimeError(f"git_{args[0]}: {proc.stderr[:220]}")
    return proc.stdout


def event_blocks(raw):
    events=[]
    for block in raw.split("\x1e"):
        if not block.strip():continue
        parts=block.strip().splitlines()
        head=parts[0].split("\x1f")
        if len(head)!=2:continue
        names=sorted(set(z.strip() for z in parts[1:] if z.strip().lower().endswith(".json")
                         and not Path(z.strip()).name.upper().startswith(SKIP_PREFIXES)))
        if not names:continue
        events.append({"commit_sha":head[0],"committed_at_utc":parse_time(head[1]).isoformat(),
                       "first_json_path":names[0],"actual_category":classify(names[0]),
                       "json_files_added_in_commit":len(names)})
    return events


def resolve_meta(root, now, temp):
    predictions=sorted(Path(root).glob("run-*-prediction.json"))
    pending=[x for x in predictions if not x.with_name(x.name.replace("-prediction.json","-resolution.json")).exists()]
    if not pending:return {"records":len(predictions),"pending":0,"resolved":0}
    # Local shallow no-blob clone, no checkout, for chronology and no private data.
    git(None,"clone","--quiet","--filter=blob:none","--depth=1200","--no-checkout",
        GIT_SOURCE,str(temp),timeout=180)
    current=git(temp,"rev-parse","HEAD").strip()
    processed=0
    pending_count=0
    for file in pending:
        pred=read(file)
        if pred.get("schema")!="janus.meta_next.prediction.v1":continue
        head=pred["source_head_sha"]
        # Require source HEAD to be a verifiable ancestor. Never guess.
        ok=subprocess.run(["git","merge-base","--is-ancestor",head,"HEAD"],cwd=temp)
        if ok.returncode!=0:
            pending_count+=1;continue
        raw=git(temp,"log","--first-parent","--reverse","--diff-filter=A",
                "--format=%x1e%H%x1f%cI","--name-only",f"{head}..HEAD","--","*.json",timeout=180)
        events=event_blocks(raw)
        if not events:
            pending_count+=1;continue
        first=events[0]
        issued=parse_time(pred["issued_at_utc"])
        occurred=parse_time(first["committed_at_utc"])
        valid_lead=issued<occurred
        predicted=pred["top3"][0]["category"]
        result={
            "schema":"janus.meta_next.first_new_json_outcome.v1",
            "source_head_at_forecast":head,
            "resolved_against_head":current,
            "forecast_issued_utc":issued.isoformat(),
            "first_actual_new_json":first,
            "predicted_category":predicted,
            "predicted_top3":pred["top3"],
            "exact_top1_category_match":predicted==first["actual_category"] if valid_lead else None,
            "top3_category_match":first["actual_category"] in [x["category"] for x in pred["top3"]] if valid_lead else None,
            "valid_prospective_lead":valid_lead,
            "evaluation_status":"SCORED_PROSPECTIVE" if valid_lead else "INVALID_EVENT_WAS_ALREADY_BEFORE_FORECAST",
            "notes":[
                "Categories, not exact file names or file contents, are predicted.",
                "The reference is the first eligible JSON-addition commit after frozen source HEAD.",
                "Commits are ordered by first-parent history, and simultaneous multi-file additions have no true internal order.",
                "No evidence of reverse temporal information or supernatural prediction."
            ]
        }
        dest=file.with_name(file.name.replace("-prediction.json","-resolution.json"))
        save(dest,result);processed+=1
    return {"records":len(predictions),"new_results":processed,"still_pending":pending_count}


def fetch_csv():
    req=urllib.request.Request(CSV_SOURCE,headers={"User-Agent":"JANUS-Independent-Research-Resolver/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=60) as response:blob=response.read(25_000_001)
            if len(blob)>25_000_000:raise RuntimeError("ALERTS_SOURCE_OVERSIZE")
            return blob
        except Exception:
            if attempt==2:raise
            time.sleep(2*(attempt+1))
    raise RuntimeError("SOURCE_UNAVAILABLE")


def resolve_alerts(root,now):
    forecast_files=sorted(Path(root).glob("*/forecast.json"))
    matured=[]
    skipped=0
    for p in forecast_files:
        dest=p.parent/"resolved.json"
        if dest.exists():continue
        record=read(p)
        if record.get("schema")!="janus.ukraine.public_alerts.experimental_daily.v1":continue
        target=date.fromisoformat(record["target_local_date"])
        if now.date()<target+timedelta(days=2):
            skipped+=1;continue
        matured.append((p,record,target))
    if not matured:return {"records":len(forecast_files),"new_resolution":0,"not_yet_mature":skipped}
    raw=fetch_csv()
    src_hash=hashbytes(raw)
    rows=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    events=set()
    last_event=None
    for r in rows:
        try:
            name=(r["region"] or "").strip()
            when=parse_time(r["started_at"]).astimezone(KIEV).date()
            if not name:continue
            events.add((name,when))
            last_event=max(last_event,when) if last_event else when
        except (ValueError,TypeError,OverflowError):continue
    completed=0
    for p,rec,target in matured:
        # Source freshness guard: if no records after target, cannot know if zero means safe.
        if last_event is None or last_event<target+timedelta(days=1):continue
        obs=[]
        for row in rec["region_probabilities"]:
            y=int((row["oblast"],target) in events)
            prob=float(row["probability_next_local_day_alert_start"])
            base=float(row["recent_28day_baseline"])
            if not 0<=prob<=1 or not 0<=base<=1:raise RuntimeError("BAD_PROBABILITY")
            obs.append({"oblast":row["oblast"],"public_alert_start_observed":bool(y),
                        "predicted_probability":prob,"recent_baseline":base})
        n=len(obs)
        model_brier=sum((o["predicted_probability"]-int(o["public_alert_start_observed"]))**2 for o in obs)/n
        base_brier=sum((o["recent_baseline"]-int(o["public_alert_start_observed"]))**2 for o in obs)/n
        out={
            "schema":"janus.ukraine.public_alert_outcome_research.v1",
            "forecast_issued_at_utc":rec["issued_at_utc"],
            "target_local_date":target.isoformat(),
            "resolve_at_utc":now.astimezone(timezone.utc).isoformat(),
            "fresh_source_sha256":src_hash,
            "source_last_event_local_date":last_event.isoformat(),
            "total_regions":n,
            "regions_with_recorded_alert_starts":sum(int(o["public_alert_start_observed"]) for o in obs),
            "mean_brier_forecast":round(model_brier,6),
            "mean_brier_recent_baseline":round(base_brier,6),
            "forecast_beats_baseline":model_brier<base_brier,
            "per_region_outcomes":obs,
            "not_a_strike_prediction":True,
            "official_safety_notice":NOTICE,
            "source_caveat":"Volunteer archive; missing records may reflect reporting gaps; label is any alert start, not an attack."
        }
        save(p.parent/"resolved.json",out);completed+=1
    return {"records":len(forecast_files),"new_resolution":completed,
            "not_yet_mature":skipped,"fresh_source_last_event":last_event.isoformat() if last_event else None}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--meta-ledger",required=True)
    parser.add_argument("--alerts-ledger",required=True)
    parser.add_argument("--temp-clone",default="/tmp/janus_meta_resolver_source")
    args=parser.parse_args()
    now=datetime.now(KIEV)
    m=resolve_meta(args.meta_ledger,now,args.temp_clone)
    a=resolve_alerts(args.alerts_ledger,now)
    print(json.dumps({"meta":m,"air_alerts":a,"research_only":True,
                      "safety_notice":NOTICE},indent=2))


if __name__=="__main__":main()
