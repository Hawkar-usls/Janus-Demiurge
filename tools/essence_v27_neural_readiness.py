#!/usr/bin/env python3
"""ESSENCE v2.7 cheap GitHub-only readiness gate for prospective neural trials.

No PyTorch, no gradients, no untrusted code execution, no model promotion.
This gate can inspect finished labels to establish minimum cohort diversity,
but never exposes labels or model scores to research workers. The actual
neural verifier independently rechecks the full GitHub source and timestamps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

SCHEMA="janus.essence.future_readiness/2.7"
NEURAL_SCHEMA="janus.essence.github_future_weights/2.6"
REPO="Hawkar-usls/Janus-Demiurge"
MAX_PAGES=8
MIN_FUTURE=48
MIN_NEW_RETRAIN=24
MIN_HISTORY=180


def time(value):
    if not isinstance(value,str):
        raise ValueError("INVALID_TIMESTAMP")
    try:
        date=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if date.tzinfo is None:
        raise ValueError("UNZONED_TIMESTAMP")
    return date.astimezone(timezone.utc)


def sealed(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,
        ensure_ascii=False,separators=(",",":"),allow_nan=False
        ).encode("utf-8")).hexdigest()


def verified_state(state):
    if state is None:
        return None
    if (not isinstance(state,dict) or state.get("schema")!=NEURAL_SCHEMA
        or state.get("research_only") is not True
        or state.get("production_authority") is not False
        or type(state.get("generation")) is not int
        or not 0<=state["generation"]<=4
        or state.get("state_sha256")!=sealed({k:v for k,v in state.items()
                                               if k!="state_sha256"})):
        raise ValueError("INVALID_SEALED_NEURAL_STATE")
    if not isinstance(state.get("history"),list):
        raise ValueError("INVALID_RESEARCH_HISTORY")
    return state


def usable(raw,now):
    if not isinstance(raw,list) or len(raw)>MAX_PAGES*100:
        raise ValueError("INVALID_GITHUB_HISTORY")
    seen=set()
    rows=[]
    for run in raw:
        if not isinstance(run,dict):
            continue
        rid,wid=run.get("id"),run.get("workflow_id")
        if (type(rid) is not int or type(wid) is not int
            or rid<=0 or wid<=0 or rid in seen
            or run.get("head_branch")!="main"
            or run.get("status")!="completed"
            or run.get("conclusion") not in ("success","failure")
            or run.get("run_attempt")!=1):
            continue
        seen.add(rid)
        try:
            created=time(run["created_at"])
            started=time(run["run_started_at"])
            updated=time(run["updated_at"])
        except (ValueError,TypeError,KeyError):
            continue
        seconds=(updated-started).total_seconds()
        if (created>now or updated>now or started<created
            or seconds<3 or seconds>7200):
            continue
        rows.append((created,rid,0 if seconds<30 else 1 if seconds<120 else 2))
    return sorted(rows)


def readiness(state,raw,published,now):
    verified_state(state)
    if published>now:
        raise ValueError("STATE_PUBLISHED_IN_FUTURE")
    rows=usable(raw,now)
    info={"schema":SCHEMA,"eligible":False,"completed_usable":len(rows),
          "generation":state.get("generation",0) if state else 0,
          "production_authority":False}
    if len(rows)<MIN_HISTORY:
        return dict(info,status="HOLD_TOO_FEW_REAL_GITHUB_RUNS")
    pending=state.get("pending") if state else None
    if pending is not None:
        if not isinstance(pending,dict):
            raise ValueError("INVALID_PENDING_CHECKPOINT")
        freeze=time(pending.get("sealed_before"))
        if (published<freeze
            or pending.get("status")!="FROZEN_AWAITING_GITHUB_FUTURE"
            or pending.get("parent_sha256") is None
            or pending.get("challenger_sha256") is None):
            raise ValueError("UNPUBLISHED_NEURAL_WEIGHTS")
        if len(raw)==MAX_PAGES*100 and rows[0][0]>published:
            return dict(info,status="HOLD_GITHUB_HISTORY_TRUNCATED")
        future=[r for r in rows if r[0]>published]
        info["completed_after_frozen_git_commit"]=len(future)
        if len(future)<MIN_FUTURE:
            return dict(info,status="HOLD_NEED_MORE_POSTFREEZE_RUNS")
        counts=[sum(r[2]==label for r in future) for label in range(3)]
        if sum(c>=5 for c in counts)<2 or max(counts)/len(future)>0.85:
            return dict(info,status="HOLD_LOW_INFORMATION_FUTURE_COHORT")
        return dict(info,eligible=True,status="READY_PROSPECTIVE_NEURAL_EXAM")
    if state and state["generation"]>=4:
        return dict(info,status="HOLD_MAX_RESEARCH_GENERATIONS")
    if state and state.get("parent") is not None:
        history=state.get("history") or []
        if history:
            last=history[-1]
            if not isinstance(last,dict) or not isinstance(
                 last.get("independent_future_verification"),dict):
                raise ValueError("INVALID_EVALUATION_HISTORY")
            consumed=last["independent_future_verification"].get("last_new_created_at")
            if not consumed:
                raise ValueError("MISSING_LAST_EVALUATED_CUTOFF")
            cutoff=time(consumed)
            fresh=sum(t>cutoff for t,_,_ in rows)
            info["new_runs_since_previous_trial"]=fresh
            if fresh<MIN_NEW_RETRAIN:
                return dict(info,status="HOLD_RETRAIN_REQUIRES_NEW_HISTORY")
    return dict(info,eligible=True,status="READY_TO_TRAIN_RESEARCH_CHALLENGER")


def fetch(token):
    if not token or len(token)>4096:
        raise ValueError("MISSING_GITHUB_READ_TOKEN")
    headers={"Accept":"application/vnd.github+json",
             "X-GitHub-Api-Version":"2022-11-28",
             "Authorization":"Bearer "+token,
             "User-Agent":"JANUS-ESSENCE-v27-Readiness"}
    observations=[]
    for page in range(1,MAX_PAGES+1):
        url=(f"https://api.github.com/repos/{REPO}/actions/runs?"
             f"branch=main&per_page=100&page={page}")
        with urlopen(Request(url,headers=headers),timeout=30) as resp:
            value=json.load(resp)
        batch=value.get("workflow_runs") if isinstance(value,dict) else None
        if not isinstance(batch,list) or len(batch)>100:
            raise ValueError("UNTRUSTED_ACTION_HISTORY")
        observations.extend(batch)
        if len(batch)<100:
            break
    return observations


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--state",required=True)
    ap.add_argument("--published-at",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    path=Path(args.state)
    state=json.loads(path.read_text()) if path.is_file() else None
    now=datetime.now(timezone.utc)
    report=readiness(state,fetch(os.environ.get("GH_TOKEN","")),
                     time(args.published_at),now)
    report["evaluated_at"]=now.isoformat()
    report["receipt_sha256"]=sealed(report)
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as f:
            f.write("ready="+str(report["eligible"]).lower()+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in
                      ("receipt_sha256","evaluated_at")},sort_keys=True))


if __name__=="__main__":
    main()
