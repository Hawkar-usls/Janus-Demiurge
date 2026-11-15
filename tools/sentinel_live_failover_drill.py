#!/usr/bin/env python3
"""One-shot real GitHub SENTINEL failover drill; ONLY its three guardian workflows.

Injects controlled FAULT into genuine A/B workflow_dispatch runs, waits until
fail-closed 10-minute observation period, asks C to do its NORMAL recovery
decision (not forge GH API history), then requires an actual CAS claim on the
data-only state branch and a genuine successful recovery workflow run.

When A is recovered by C, an explicit normal A wake may then rescue B.
All failed runs are ephemeral Sentinel-specific GitHub jobs and do not touch
other workflows, production models, NAS, user secrets or repos.

No unlimited retry, no claimed 24/7 uptime and no false PASS without GH run
IDs, actual state claim and observed recovery runs.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

REPO="Hawkar-usls/Janus-Demiurge"
BASE="https://api.github.com/repos/"+REPO
SCHEMA="janus.sentinel.real_github_failover_drill/1.0"
TARGETS={"A":"sentinel-node-a.yml","B":"sentinel-node-b.yml",
         "C":"sentinel-node-c.yml"}
PAGESIZE=30
API_MAX=800000
POLL=12
WAIT_SECONDS=26*60


def require(ok,code):
    if not ok:
        raise RuntimeError(code)


def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode()


def stamp(x):
    if not isinstance(x,str) or len(x)>60:raise ValueError("BAD_TIMESTAMP")
    v=datetime.fromisoformat(x.replace("Z","+00:00"))
    if v.tzinfo is None:raise ValueError("UNZONED_TIMESTAMP")
    return v.astimezone(timezone.utc)


def utcnow():
    return datetime.now(timezone.utc)


def fetch(endpoint,token,*,post=None,opener=urllib.request.urlopen):
    require(isinstance(endpoint,str) and
            ".." not in endpoint and
            (endpoint.startswith("/actions/workflows/sentinel-node-")
             or endpoint=="/contents/sentinel/recovery.json?ref=sentinel-state"),
            "DRILL_GITHUB_API_DENY")
    if post is not None:
        require(endpoint.endswith("/dispatches") and
                endpoint in {f"/actions/workflows/{w}/dispatches"
                             for w in TARGETS.values()} and
                isinstance(post,dict) and post.get("ref")=="main" and
                set(post)=={"ref","inputs"},
                "DRILL_DISPATCH_ALLOWLIST_DENIED")
        body=post["inputs"]
        require(isinstance(body,dict) and
                set(body)<={"fault_inject","recovery_only","drill_nonce"} and
                isinstance(body.get("drill_nonce"),str) and
                body["drill_nonce"].startswith("sentinel-drill-v1-") and
                len(body["drill_nonce"])<=64 and
                set(body.values())!=set(),
                "UNSAFE_SENTINEL_TEST_INPUTS")
        data=canonical(post)
    else:
        require(endpoint=="/contents/sentinel/recovery.json?ref=sentinel-state"
                or endpoint.endswith(f"/runs?per_page={PAGESIZE}"),
                "DRILL_READ_NOT_ALLOWLISTED")
        data=None
    require(isinstance(token,str) and 16<len(token)<4096,
            "NO_GITHUB_ACTIONS_WRITE_TOKEN")
    req=urllib.request.Request(
        BASE+endpoint,data=data,
        method="POST" if data else "GET",
        headers={
          "Authorization":"Bearer "+token,
          "Accept":"application/vnd.github+json",
          "X-GitHub-Api-Version":"2022-11-28",
          "User-Agent":"JANUS-Sentinel-controlled-drill/1.0",
          **({"Content-Type":"application/json"} if data else {}),
        })
    with opener(req,timeout=18) as result:
        b=result.read(API_MAX+1)
        require(len(b)<=API_MAX,"OVERSIZED_DRILL_API_RESPONSE")
        if post is not None:
            require(result.status==204,"GH_WORKFLOW_DISPATCH_NOT_ACCEPTED")
            return {"status":204,"accepted":True}
        require(result.status==200,"GH_READ_BAD_HTTP_CODE")
        return json.loads(b)


def dispatch(node,token,nonce,*,fault=False,recovery=False,call=fetch):
    require(node in TARGETS and isinstance(nonce,str) and
            re.fullmatch(r"sentinel-drill-v1-[0-9]{4,20}(-[a-z0-9-]{1,16})?",nonce)
            and not(fault and recovery),
            "UNAUTHORIZED_DRILL_NODE_DISPATCH")
    return call(
        f"/actions/workflows/{TARGETS[node]}/dispatches",
        token,post={"ref":"main",
                     "inputs":{"fault_inject":"true" if fault else "false",
                               "recovery_only":"true" if recovery else "false",
                               "drill_nonce":nonce}})


def recent(node,token,*,call=fetch):
    require(node in TARGETS,"UNKNOWN_NODE")
    out=call(
        f"/actions/workflows/{TARGETS[node]}/runs?per_page={PAGESIZE}",
        token)
    require(isinstance(out,dict) and
            isinstance(out.get("workflow_runs"),list) and
            len(out["workflow_runs"])<=PAGESIZE,
            "DRILL_ACTIONS_OBSERVATIONS_UNAVAILABLE")
    return out["workflow_runs"]


def find_tagged(rows,node,nonce,*,conclusion):
    expected=f"JANUS SENTINEL {node} · {nonce}"
    matched=[v for v in rows if isinstance(v,dict) and
             v.get("event")=="workflow_dispatch" and
             v.get("display_title")==expected and
             v.get("head_branch")=="main" and
             v.get("status")=="completed" and
             v.get("conclusion")==conclusion]
    require(len(matched)<=1,"DUPLICATE_DRILL_NONCE_IN_GITHUB")
    return matched[0] if matched else None


def state(token,*,call=fetch):
    raw=call("/contents/sentinel/recovery.json?ref=sentinel-state",token)
    require(isinstance(raw,dict) and raw.get("encoding")=="base64"
            and isinstance(raw.get("content"),str),
            "UNAVAILABLE_GIT_RECOVERY_CAS")
    obj=json.loads(base64.b64decode(raw["content"]))
    from tools.sentinel_core import state_check
    return state_check(obj)


def wait_until(predicate,deadline,*,description,interval=POLL):
    while utcnow()<deadline:
        result=predicate()
        if result is not None:
            return result
        time.sleep(interval)
    raise RuntimeError("DRILL_TIMEOUT_"+description)


def check_no_unknown_prior_claim(st,roles):
    for role in roles:
        recent=st["last_dispatch"].get(role)
        if recent:
            when=stamp(recent["issued_at"])
            require((utcnow()-when).total_seconds()>90*60,
                    "DRILL_CANNOT_BYPASS_EXISTING_COOLDOWN_"+role)


def validate_claim(st,target,fault,expected_issuer):
    row=st["last_dispatch"].get(target)
    if not row or row.get("observed_target_run_id")!=fault["id"]:
        return None
    require(row["target"]==target and row["issuer"]==expected_issuer and
            row["outcome"]=="ATTEMPTED_NOT_CONFIRMED" and
            int(row["run_id"])>0 and
            1<=row["claim_epoch"]<=st["epoch"] and
            stamp(row["issued_at"])>=stamp(fault["created_at"]),
            "BAD_RECOVERY_CLAIM")
    return row


def prove_healthy_after_claim(node,fault,claim,token,*,call=fetch):
    # Pre-existing successful runs don't count. Recovery is a NEW main-branch
    # workflow_dispatch with a later GH timestamp than the failure and claim.
    cutoff=max(stamp(fault["created_at"]),stamp(claim["issued_at"]))
    rows=recent(node,token,call=call)
    restored=[v for v in rows if v.get("event")=="workflow_dispatch"
        and v.get("status")=="completed"
        and v.get("conclusion")=="success"
        and v.get("head_branch")=="main"
        and stamp(v["created_at"])>=cutoff
        and v["id"]!=fault["id"]]
    return max(restored,key=lambda x:x["id"]) if restored else None


def run(*,token,run_id,mode="AB"):
    require(mode in ("A","AB","C"),"UNAUTHORIZED_DRILL_FAULT_COHORT")
    require(type(run_id) is str and re.fullmatch(r"[1-9][0-9]{4,19}",run_id),
            "DRILL_RUN_ID_INVALID")
    nonce=f"sentinel-drill-v1-{run_id}"
    injected=["A","B"] if mode=="AB" else [mode]
    initial=state(token)
    check_no_unknown_prior_claim(initial,injected)
    records={
        "schema":SCHEMA,
        "status":"STARTED_NOT_YET_PROVEN",
        "drill_source_run_id":run_id,
        "drill_mode":mode,
        "nonce":nonce,
        "data_branch":"sentinel-state",
        "initial_epoch":initial["epoch"],
        "injected_nodes":injected,
        "faults":{},"claims":{},"recovery_runs":{},
        "actual_dispatch_actions":[],
        "training_or_checkpoint_changes":False,
        "production_authority":False,
        "touches_live_production":False,
        "external_independent_replication":False,
    }
    deadline=utcnow()+timedelta(seconds=WAIT_SECONDS)
    for role in injected:
        dispatch(role,token,nonce,fault=True)
        records["actual_dispatch_actions"].append({
            "target":role,"type":"CONTROLLED_REAL_WORKFLOW_FAILURE"})
    for role in injected:
        failure=wait_until(
            lambda role=role:find_tagged(
                recent(role,token),role,nonce,conclusion="failure"),
            deadline,description=f"FAILURE_{role}")
        records["faults"][role]={
            "run_id":failure["id"],
            "created_at":failure["created_at"],
            "conclusion":failure["conclusion"],
            "url":failure["html_url"],
        }

    # The real SENTINEL recovery policy requires >=10m age for failed run.
    earliest=max(stamp(v["created_at"]) for v in records["faults"].values()) + timedelta(minutes=10,seconds=12)
    while utcnow()<earliest:
        require(utcnow()<deadline,"DRILL_TIMEOUT_WAIT_FOR_REAL_POLICY_AGE")
        time.sleep(min(POLL,max(1,(earliest-utcnow()).total_seconds())))

    for role in injected:
        # Reject if a normal scheduled wake already replaced the fault
        # before the recovery actor. Never manufacture a PASS.
        rows=recent(role,token)
        latest=max(rows,key=lambda v:v["id"])
        if latest["id"]!=records["faults"][role]["run_id"]:
            before=state(token)["last_dispatch"].get(role)
            require(before and before.get("observed_target_run_id")==
                    records["faults"][role]["run_id"],
                    "SCHEDULE_PREEMPTED_TEST_NOT_RECOVERY_PROOF")
    actor="C" if mode in ("A","AB") else "A"
    dispatch(actor,token,nonce+"-probe")
    records["actual_dispatch_actions"].append({
        "target":actor,"type":"WAKE_REAL_DETERMINISTIC_GUARDIAN"})
    first="A" if mode in ("A","AB") else "C"
    failed_first=next((x for x in recent(first,token)
       if x["id"]==records["faults"][first]["run_id"]),None)
    require(failed_first is not None,"ORIGINAL_FAILURE_NO_LONGER_AVAILABLE")

    claim=wait_until(
        lambda:validate_claim(state(token),first,failed_first,actor),
        deadline,description="CAS_CLAIM_"+first)
    records["claims"][first]=claim
    recovered=wait_until(
        lambda:prove_healthy_after_claim(first,failed_first,claim,token),
        deadline,description="CONFIRMED_SUCCESS_"+first)
    records["recovery_runs"][first]={
        "run_id":recovered["id"],"url":recovered["html_url"],
        "conclusion":recovered["conclusion"],
    }

    if mode=="AB":
        # C must rescue one of A/B. A then performs next distinct, bounded
        # peer recovery; this extra normal wake is explicit, not recursive.
        dispatch("A",token,nonce+"-peer")
        records["actual_dispatch_actions"].append({
            "target":"A","type":"WAKE_RECOVERED_PEER_TO_CHECK_B"})
        failed_b=next((x for x in recent("B",token)
            if x["id"]==records["faults"]["B"]["run_id"]),None)
        require(failed_b is not None,"B_FAILURE_PROVENANCE_MISSING")
        claim_b=wait_until(
            lambda:validate_claim(state(token),"B",failed_b,"A"),
            deadline,description="CAS_CLAIM_B")
        records["claims"]["B"]=claim_b
        recovered_b=wait_until(
            lambda:prove_healthy_after_claim("B",failed_b,claim_b,token),
            deadline,description="CONFIRMED_SUCCESS_B")
        records["recovery_runs"]["B"]={
            "run_id":recovered_b["id"],"url":recovered_b["html_url"],
            "conclusion":recovered_b["conclusion"],
        }
    records["status"]=(
        "PASS_REAL_GH_AB_FALL_C_RESCUES_A_THEN_A_RESCUES_B"
        if mode=="AB" else
        "PASS_REAL_GH_C_RESCUES_A"
        if mode=="A" else
        "PASS_REAL_GH_A_RESCUES_C")
    records["actual_git_cas_claims_observed"]=len(records["claims"])
    records["recovery_runs_verified"]=len(records["recovery_runs"])
    records["claims_only_after_failure_age_10m"]=True
    records["no_recursive_workflow_dispatch"]=True
    records["shared_github_failure_domain"]=True
    return records


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("A","AB","C"),default="AB")
    p.add_argument("--run-id",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=run(token=os.getenv("GH_TOKEN",""),run_id=args.run_id,
               mode=args.mode)
    path=Path(args.out)
    require(not path.exists(),"IMMUTABLE_DRILL_RESULT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True,exist_ok=True)
    result["receipt_sha256"]=hashlib.sha256(canonical(result)).hexdigest()
    path.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
        "status":result["status"],
        "claims":result["actual_git_cas_claims_observed"],
        "recovered":result["recovery_runs_verified"],
        "receipt_sha256":result["receipt_sha256"],
        "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
