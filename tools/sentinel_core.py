#!/usr/bin/env python3
"""JANUS SENTINEL: A/B interchangeable GitHub Action watchdogs, C rescuer.

DUTY: A/B observe each other and C; C observes and can revive either A or B.
All roles share the same source and repo, but separate cron/workflow entrypoints.
A/B optionally consume one fixed, research-only historical Actions Transformer
checkpoint; the model can rank alerts, NEVER authorize dispatch.

DANGEROUS FAILURE MODES: GitHub-wide outage knocks out A,B,C; GitHub cron
is best-effort; the same GitHub token and state branch is a common dependency.
No 24/7 process or independent failure-domain claim is made.

A recovery is a workflow_dispatch to an EXACT same-repo allowlist. It first
wins a Git ref compare-and-swap by a non-force git push of one state JSON claim.
A stale claim is NOT retried until cooldown. Only 1 dispatch/role/job.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

OWNER_REPO="Hawkar-usls/Janus-Demiurge"
BASE="https://api.github.com/repos/"+OWNER_REPO
SCHEMA="janus.sentinel.guardian_cycle/1.0"
STATE="janus.sentinel.recovery_state/1.0"
PLAN="janus.sentinel.guardian_plan/1.0"
ROLES={"A":"sentinel-node-a.yml","B":"sentinel-node-b.yml",
       "C":"sentinel-node-c.yml"}
TARGETS={
    "A":("B","C","WORKER"),
    "B":("A","C","WORKER"),
    "C":("A","B"),
}
WORKER="essence-v44-github-async.yml"
TARGET_FILE={**ROLES,"WORKER":WORKER}
MAX_API_SIZE=320000
COOLDOWN_SECONDS=30*60
LIVENESS_SECONDS=40*60
WORKER_LIVENESS_SECONDS=65*60  # ESSENCE worker keeps its own cadence
MIN_FAILURE_AGE_SECONDS=6*60
OBSERVE_MAX_RUNS=8
HEX40=re.compile(r"^[0-9a-f]{40}$")
INT_ID=re.compile(r"^[1-9][0-9]{0,19}$")


def require(condition,why):
    if not condition:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stamp(value):
    require(type(value) is str and len(value)<50,"INVALID_ACTIONS_TIMESTAMP")
    dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    require(dt.tzinfo is not None,"NAIVE_ACTIONS_TIMESTAMP")
    return dt.astimezone(timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


def to_iso(value):
    return value.isoformat().replace("+00:00","Z")


def read_json(path,maxbytes=16000):
    p=Path(path)
    require(p.is_file() and not p.is_symlink() and
            2<=p.stat().st_size<=maxbytes,
            "INVALID_STATE_FILE")
    return json.loads(p.read_text("utf-8"),
                      parse_constant=lambda _:
                      (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def immutable(path,value):
    p=Path(path)
    require(not p.exists() and not p.is_symlink(),"NO_OVERWRITE_RECEIPT")
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf-8") as f:
        json.dump(value,f,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")


def api(path,token,*,post=None,opener=urllib.request.urlopen):
    require(type(token) is str and 16<len(token)<4096,
            "MISSING_RESTRICTED_ACTIONS_TOKEN")
    allow=(
        path.startswith("/actions/workflows/") and
        (path.endswith("/runs?per_page=8") or
         path.endswith("/dispatches"))
    ) or path.startswith("/contents/essence-runtime/")
    require(allow and ".." not in path,"GITHUB_API_ROUTE_NOT_ALLOWED")
    headers={
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"JANUS-Sentinel/1.0",
        "Authorization":"Bearer "+token,
    }
    if post is not None:
        require(path.endswith("/dispatches") and
                type(post) is dict and post.get("ref")=="main" and
                set(post)<= {"ref","inputs"},
                "DISPATCH_PAYLOAD_NOT_ALLOWED")
        data=canonical(post)
        headers["Content-Type"]="application/json"
    else:
        data=None
    req=urllib.request.Request(BASE+path,headers=headers,
                               data=data,method="POST" if data else "GET")
    with opener(req,timeout=15) as response:
        payload=response.read(MAX_API_SIZE+1)
        require(len(payload)<=MAX_API_SIZE,"OVERSIZED_ACTIONS_RESPONSE")
        if data is not None:
            require(response.status==204,"DISPATCH_HTTP_NOT_204")
            return {"accepted":True,"status":response.status}
        require(response.status==200,"GITHUB_READ_NOT_200")
        return json.loads(payload)


def runs(target,token,*,fetch=api):
    require(target in TARGET_FILE,"UNKNOWN_WORKFLOW")
    name=TARGET_FILE[target]
    response=fetch("/actions/workflows/"+name+
                   "/runs?per_page=8",token)
    require(isinstance(response,dict) and
            type(response.get("workflow_runs")) is list,
            "UNAVAILABLE_ACTIONS_RUN_INVENTORY")
    items=response["workflow_runs"]
    require(len(items)<=OBSERVE_MAX_RUNS,"TOO_MANY_OBSERVED_RUNS")
    out=[]
    seen=set()
    for v in items:
        # GitHub returns PR check runs on the contributor's source branch
        # alongside trusted main runs. They are not heartbeat evidence.
        if isinstance(v,dict) and v.get("event")=="pull_request":
            continue
        require(isinstance(v,dict) and
                type(v.get("id")) is int and v["id"]>0 and
                v["id"] not in seen and
                type(v.get("created_at")) is str and
                v.get("event") in ("push","schedule","workflow_dispatch","pull_request") and
                v.get("status") in ("queued","in_progress","completed","waiting","requested","pending") and
                v.get("head_branch") in ("main",None) and
                type(v.get("run_attempt",1)) is int,
                "UNTRUSTWORTHY_WORKFLOW_RUN_ROW")
        seen.add(v["id"])
        if v["event"]=="pull_request":
            continue # PR tests cannot establish production cron healthy
        out.append({
            "id":v["id"],"created":to_iso(stamp(v["created_at"])),
            "status":v["status"],"conclusion":v.get("conclusion"),
            "event":v["event"],"run_attempt":v.get("run_attempt",1),
            "workflow_id":v.get("workflow_id"),
        })
    return sorted(out,key=lambda row:(row["created"],row["id"]),reverse=True)


def health(rows,now,*,omit_run_id=None,liveness_seconds=LIVENESS_SECONDS):
    rows=[r for r in rows if r["id"]!=omit_run_id]
    if not rows:
        return {"status":"UNKNOWN_NO_OBSERVATIONS","last_run_id":None,
                "age_seconds":None}
    last=rows[0]
    age=(now-stamp(last["created"])).total_seconds()
    require(age>=-60 and age<=31*86400,"RUN_CLOCK_OR_HISTORY_INCONSISTENT")
    seen_success=any(r["conclusion"]=="success" and
                     r["status"]=="completed" and
                     (now-stamp(r["created"])).total_seconds()<48*3600
                     for r in rows)
    status="HEALTHY"
    if last["status"]!="completed":
        status="BUSY_OR_PENDING"
    elif not seen_success:
        status="UNKNOWN_NO_RECENT_SUCCESS" # never self-heal unknown service
    elif last["conclusion"]=="failure" and age>=MIN_FAILURE_AGE_SECONDS:
        status="STALE_FAILED"
    elif age>=liveness_seconds:
        status="STALE_MISSED_WAKE"
    return {
        "status":status,"last_run_id":last["id"],
        "last_event":last["event"],"age_seconds":round(age),
        "known_prior_success":seen_success,
    }


def state_check(obj):
    require(isinstance(obj,dict) and obj.get("schema")==STATE and
            type(obj.get("epoch")) is int and 0<=obj["epoch"]<10**8 and
            type(obj.get("last_dispatch")) is dict and
            len(obj["last_dispatch"])<=4 and
            obj.get("production_model_updates") is False and
            obj.get("authority")=="BOUNDED_GITHUB_ACTIONS_ONLY",
            "SENTINEL_RECOVERY_STATE_INVALID")
    for target,x in obj["last_dispatch"].items():
        require(target in TARGET_FILE and isinstance(x,dict) and
                x.get("target")==target and x.get("issuer") in ROLES and
                type(x.get("run_id")) is str and
                INT_ID.fullmatch(x["run_id"]) and
                type(x.get("issued_at")) is str and
                type(x.get("observed_target_run_id")) is int,
                "UNTRUSTED_SENTINEL_RECOVERY_CLAIM")
        stamp(x["issued_at"])
    return obj


def pending_queue(token,*,fetch=api):
    # Fail-closed if state branch isn't available. No content is loaded.
    inbox=fetch("/contents/essence-runtime/inbox?ref=essence-actions-state",token)
    try:
        results=fetch("/contents/essence-runtime/results?ref=essence-actions-state",token)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        results=[]
    require(isinstance(inbox,list) and isinstance(results,list) and
            len(inbox)<=1000 and len(results)<=2000,
            "QUEUE_INVENTORY_UNAVAILABLE_OR_UNBOUNDED")
    result_names={x["name"] for x in results if
                  isinstance(x,dict) and x.get("type")=="file"}
    return sum(x.get("type")=="file" and
               re.fullmatch(r"[a-z][a-z0-9-]{2,40}\.json",x.get("name",""))
               is not None and x["name"] not in result_names for x in inbox
               if isinstance(x,dict))


def decide(role,run_id,now,observed,stored,*,pending=0,model=None):
    require(role in ROLES and type(run_id) is str and INT_ID.fullmatch(run_id),
            "UNKNOWN_SENTINEL_ROLE")
    state_check(stored)
    require(set(observed)==set(TARGET_FILE),"INCOMPLETE_WORKFLOW_OBSERVATION")
    condition={key:health(observed[key],now,omit_run_id=int(run_id),
                liveness_seconds=(WORKER_LIVENESS_SECONDS if key=="WORKER"
                                  else LIVENESS_SECONDS))
               for key in TARGET_FILE}
    candidates=[]
    for target in TARGETS[role]:
        if target=="WORKER":
            # Preserve the ESSENCE async worker's own schedule. Sentinel only
            # wakes backlog if worker has been absent and there is real work.
            if pending<=0:
                continue
        status=condition[target]["status"]
        if status not in ("STALE_FAILED","STALE_MISSED_WAKE"):
            continue
        last=stored["last_dispatch"].get(target)
        if last and (now-stamp(last["issued_at"])).total_seconds()<COOLDOWN_SECONDS:
            continue
        # Deterministic hard policy; the learned risk score is NOT consulted
        # for dispatch eligibility and cannot expand the target catalog.
        candidates.append(target)
    priority={"A":1,"B":1,"C":0,"WORKER":2}
    target=sorted(candidates,key=lambda x:(priority[x],x))[0] if candidates else None
    return {
       "schema":PLAN,"role":role,"run_id":run_id,
       "observed_at":to_iso(now),"target":target,
       "target_last_run_id":condition[target]["last_run_id"] if target else None,
       "statuses":condition,"pending_worker_requests":pending,
       "model_prediction":model if role in ("A","B") else None,
       "model_has_dispatch_authority":False,
       "recovery_actions_at_most_one":True,
       "recovery_requires_state_cas":True,
       "production_model_updates":False,
       "state_epoch_observed":stored["epoch"],
       "decision":"PROPOSE_CAS_CLAIM" if target else "OBSERVE_ONLY",
    }


def claim(current,plan):
    state_check(current)
    require(plan.get("schema")==PLAN and plan.get("role") in ROLES and
            plan.get("target") in TARGETS[plan["role"]] and
            plan.get("state_epoch_observed")==current["epoch"] and
            plan.get("model_has_dispatch_authority") is False,
            "UNAUTHORIZED_RECOVERY_CLAIM")
    target=plan["target"]
    previous=current["last_dispatch"].get(target)
    when=stamp(plan["observed_at"])
    if previous:
        require((when-stamp(previous["issued_at"])).total_seconds()>=COOLDOWN_SECONDS,
                "RECOVERY_COOLDOWN_FENCE")
    require(type(plan["target_last_run_id"]) is int and
            plan["target_last_run_id"]>0,
            "RECOVERY_CANNOT_DISPATCH_UNKNOWN_WORKFLOW")
    new=json.loads(json.dumps(current))
    new["epoch"]+=1
    new["last_dispatch"][target]={
        "target":target,"issuer":plan["role"],"run_id":plan["run_id"],
        "issued_at":plan["observed_at"],
        "observed_target_run_id":plan["target_last_run_id"],
        "claim_epoch":new["epoch"],
        "outcome":"ATTEMPTED_NOT_CONFIRMED",
    }
    return state_check(new)


def claimed(target,role,run_id,expected_epoch,current):
    state_check(current)
    row=current["last_dispatch"].get(target)
    return bool(row and row["issuer"]==role and
                row["run_id"]==run_id and
                row["claim_epoch"]==expected_epoch and
                row["target"]==target)


def dispatch(plan,current,token,*,fetch=api):
    target=plan.get("target")
    role=plan.get("role")
    require(role in ROLES and target in TARGETS[role] and
            claimed(target,role,plan["run_id"],
                    plan["state_epoch_observed"]+1,current),
            "RECOVERY_CLAIM_NOT_OWNED")
    observed=runs(target,token,fetch=fetch)
    require(observed and observed[0]["id"]==
            plan["target_last_run_id"],
            "RECOVERING_WORKFLOW_HAS_NEWER_RUN_ABORT")
    if target=="WORKER":
        payload={"ref":"main","inputs":{"mode":"pulse","input_hex":""}}
    else:
        # Embed the exact signed-by-Git-CAS recovery identity in the
        # resulting GitHub workflow run-name. Otherwise an unrelated human
        # workflow_dispatch could be mistaken for our successful recovery.
        nonce=("sentinel-recovery-"+role+"-"+plan["run_id"]+"-"+
               str(current["last_dispatch"][target]["claim_epoch"]))
        payload={"ref":"main","inputs":{"recovery_only":"true",
                                         "drill_nonce":nonce}}
    return fetch("/actions/workflows/"+TARGET_FILE[target]+"/dispatches",
                 token,post=payload)


def observe(role,run_id,token,now=None,*,fetch=api,model=None):
    require(role in ROLES,"INVALID_SENTINEL_ROLE")
    now=now or utcnow()
    seen={target:runs(target,token,fetch=fetch) for target in TARGET_FILE}
    if role in ("A","B"):
        try:
            pending=pending_queue(token,fetch=fetch)
        except (ValueError,urllib.error.HTTPError,KeyError,TypeError):
            # Losing the queue inventory is not evidence that an extra
            # workflow should be launched.
            pending=0
    else:
        pending=0
    return now,seen,pending


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="command",required=True)
    q=sub.add_parser("observe")
    q.add_argument("--role",choices=ROLES,required=True)
    q.add_argument("--run-id",required=True)
    q.add_argument("--state",required=True)
    q.add_argument("--out",required=True)
    q=sub.add_parser("claim")
    q.add_argument("--state",required=True)
    q.add_argument("--plan",required=True)
    q.add_argument("--out",required=True)
    q=sub.add_parser("dispatch")
    q.add_argument("--plan",required=True)
    q.add_argument("--state",required=True)
    q.add_argument("--out",required=True)
    a=p.parse_args()
    if a.command=="observe":
        state=read_json(a.state)
        role=a.role
        token=os.environ.get("GH_TOKEN","")
        now,seen,pending=observe(role,a.run_id,token)
        model=None
        if role in ("A","B"):
            path=Path(a.state).parent/"model"/"checkpoint.json"
            try:
                from tools.sentinel_transformer import (read_research_score,
                    predict_recent_risk)
                model=read_research_score(path)
                # Every actual A/B guardian consumes the SAME sealed neural
                # weights. Forecasts cannot authorize/cancel recovery.
                model["risk_by_workflow"]=predict_recent_risk(
                    path,seen,token)
            except FileNotFoundError:
                model={"status":"UNTRAINED_PENDING_REAL_GITHUB_HISTORY",
                       "calibrated":False}
            except (ValueError,KeyError,RuntimeError,OSError,
                    urllib.error.URLError,ImportError) as error:
                # C always works without Torch; A/B retain their
                # deterministic recovery rules after neural failure.
                model={"status":"NEURAL_INFERENCE_FAILED_DETERMINISTIC_GUARD",
                       "error_type":type(error).__name__,
                       "calibrated":False}
        result=decide(role,a.run_id,now,seen,state,pending=pending,model=model)
    elif a.command=="claim":
        result=claim(read_json(a.state),read_json(a.plan,60000))
    else:
        result=dispatch(read_json(a.plan,60000),read_json(a.state),
                        os.environ.get("GH_TOKEN",""))
    immutable(a.out,result)
    print(json.dumps({"command":a.command,"role":result.get("role"),
                      "target":result.get("target"),"status":result.get("decision"),
                      "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
