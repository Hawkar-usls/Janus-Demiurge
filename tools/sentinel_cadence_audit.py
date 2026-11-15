#!/usr/bin/env python3
"""24-hour real GitHub Actions Sentinel schedule delivery audit.

Scheduled triggers are best-effort. This independently reads GitHub's genuine
completed main-branch schedule runs; one passing push/manual drill is NEVER
treated as 24-hour cron proof. No dispatch, state writes or model authority.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import urllib.request

REPO="Hawkar-usls/Janus-Demiurge"
FILES={"A":"sentinel-node-a.yml","B":"sentinel-node-b.yml",
       "C":"sentinel-node-c.yml"}
WINDOW_MINUTES=24*60
INTERVAL_MINUTES=15
EXPECTED_PER_24H=WINDOW_MINUTES//INTERVAL_MINUTES
MIN_DELIVERED=int(math.ceil(EXPECTED_PER_24H*0.80))
MAX_GAP_MINUTES=45
SCHEMA="janus.sentinel.real_cron_delivery_audit/1.0"
BASE="https://api.github.com/repos/"+REPO


def stamp(x):
    if not isinstance(x,str) or len(x)>55:
        raise ValueError("INVALID_ACTIONS_TIMESTAMP")
    t=datetime.fromisoformat(x.replace("Z","+00:00"))
    if t.tzinfo is None:
        raise ValueError("UNZONED_ACTIONS_TIMESTAMP")
    return t.astimezone(timezone.utc)


def canonical(o):
    return json.dumps(o,ensure_ascii=False,sort_keys=True,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def read_workflow_runs(role,token):
    if role not in FILES or not isinstance(token,str) or len(token)<17:
        raise ValueError("UNAUTHORIZED_AUDIT_REQUEST")
    items=[]
    for page in range(1,4):
        route=(f"/actions/workflows/{FILES[role]}/runs?"
               f"per_page=100&page={page}")
        request=urllib.request.Request(BASE+route,headers={
            "Authorization":"Bearer "+token,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"JANUS-Sentinel-audit/1.0",
        })
        with urllib.request.urlopen(request,timeout=15) as answer:
            if answer.status!=200:
                raise ValueError("ACTION_INVENTORY_HTTP_NOT_200")
            raw=answer.read(6_000_001)
            if len(raw)>6_000_000:
                raise ValueError("ACTION_INVENTORY_TOO_LARGE")
            chunk=json.loads(raw).get("workflow_runs")
        if not isinstance(chunk,list) or len(chunk)>100:
            raise ValueError("INVALID_ACTIONS_INVENTORY")
        items.extend(chunk)
        if len(chunk)<100:
            break
    return items


def evaluate(history, now, activated):
    now=stamp(now) if isinstance(now,str) else now
    activated=stamp(activated) if isinstance(activated,str) else activated
    if now.tzinfo is None or activated.tzinfo is None:
        raise ValueError("NAIVE_AUDIT_WINDOW")
    since=now-timedelta(minutes=WINDOW_MINUTES)
    statuses={}
    for role in FILES:
        rows=history[role]
        if not isinstance(rows,list) or len(rows)>300:
            raise ValueError("BAD_AUDIT_HISTORY")
        observations=[]
        seen=set()
        for x in rows:
            if not isinstance(x,dict):
                raise ValueError("UNTRUSTED_ACTIONS_ROW")
            if x.get("event")!="schedule":
                continue
            if x.get("head_branch")!="main":
                continue
            rid=x.get("id")
            if type(rid) is not int or rid<1 or rid in seen:
                raise ValueError("DUPLICATE_OR_BAD_SCHEDULE_RUN_ID")
            seen.add(rid)
            created=stamp(x.get("created_at"))
            if since<=created<=now+timedelta(seconds=60):
                observations.append((created,x.get("status"),x.get("conclusion")))
        observations.sort()
        delivered=len(observations)
        successes=[t for t,state,conclusion in observations
                   if state=="completed" and conclusion=="success"]
        points=[since]+successes+[now]
        largest_gap=max((b-a).total_seconds()/60
                        for a,b in zip(points,points[1:]))
        statuses[role]={
            "expected_delivery_count":EXPECTED_PER_24H,
            "observed_schedule_count":delivered,
            "successful_schedule_count":len(successes),
            "largest_success_gap_minutes":round(largest_gap,2),
            "latest_schedule_utc":observations[-1][0].isoformat()
                                    if observations else None,
            "latest_success_utc":successes[-1].isoformat()
                                    if successes else None,
        }
    enough_time=activated<=since
    deliver=all(v["successful_schedule_count"]>=MIN_DELIVERED and
                v["largest_success_gap_minutes"]<=MAX_GAP_MINUTES
                for v in statuses.values())
    verdict=("HOLD_WAIT_FOR_24H_AFTER_DEPLOY" if not enough_time else
             "PASS_REAL_GITHUB_24H_CRON_DELIVERY" if deliver else
             "FAIL_REAL_GITHUB_24H_CRON_DELIVERY")
    result={
        "schema":SCHEMA,"status":verdict,
        "verified_window_start_utc":since.isoformat(),
        "verified_window_end_utc":now.isoformat(),
        "policy_activated_utc":activated.isoformat(),
        "min_successful_runs_per_node":MIN_DELIVERED,
        "max_success_gap_minutes":MAX_GAP_MINUTES,
        "nodes":statuses,"only_schedule_events":True,
        "only_actual_github_runs":True,
        "self_verified_not_independent":True,
        "common_github_failure_domain":True,
        "production_authority":False,
    }
    result["receipt_sha256"]=hashlib.sha256(canonical(result)).hexdigest()
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--activated",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    current=datetime.now(timezone.utc)
    activated=stamp(args.activated)
    evidence=evaluate({r:read_workflow_runs(r,os.environ.get("GH_TOKEN",""))
                       for r in FILES},current,activated)
    path=Path(args.out)
    if path.exists() or path.is_symlink():
        raise ValueError("AUDIT_RECEIPT_MUST_BE_IMMUTABLE")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":evidence["status"],
                      "node_successes":{r:x["successful_schedule_count"]
                                        for r,x in evidence["nodes"].items()},
                      "receipt_sha256":evidence["receipt_sha256"]},sort_keys=True))
    if evidence["status"].startswith("FAIL_"):
        raise SystemExit(1)


if __name__=="__main__":
    main()
