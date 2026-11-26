#!/usr/bin/env python3
"""ESSENCE-triggered adaptive research request ledger, never a production trainer."""
import argparse,hashlib,json,re
from pathlib import Path

SCHEMA="janus.essence.adaptive_repair.pulse.v1"
def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def seal(x):return {**x,"sha256":digest(x)}
def checked(x):
    body={k:v for k,v in x.items() if k!="sha256"}
    if x.get("sha256")!=digest(body):raise ValueError("STATE_HASH")
    return body
def read(p):
    if p.is_symlink() or p.stat().st_size>4*1024*1024:raise ValueError("INPUT_BOUND")
    return json.loads(p.read_text())
def initial():return seal({"schema":SCHEMA,"records":[],"seen":[],"production":False})
def advance(state,record,source_id):
    prev=checked(state)
    if prev["schema"]!=SCHEMA or prev["production"] is not False:raise ValueError("STATE_SCHEMA")
    if not re.fullmatch(r"[0-9a-f]{40}",source_id):raise ValueError("REGISTRY_PIN")
    if record.get("schema")!="janus.r84.h38n3.execution.v1" or record.get("production") is not False or record.get("run_id")!=45847415226:raise ValueError("RECORD")
    train=[r["data"] for r in record["receipts"] if r["tag"]=="R84H38N3_TRAIN"]
    result=[r["data"] for r in record["receipts"] if r["tag"]=="R84H38N3_RESULT"]
    if len(train)!=1 or len(result)!=1:raise ValueError("RECEIPTS")
    t,v=train[0],result[0]
    if v["repair"]!=t or v["quality_gate"]!="HOLD" or t["legacy_feature_conflicts"]!=5:raise ValueError("HOLD_CONTRACT")
    key=digest(record)
    if key in prev["seen"]:return state,"NO_NEW_EVIDENCE_HOLD"
    if len(prev["records"])>=64:raise ValueError("STATE_CAPACITY_HOLD")
    item={"evidence_sha256":key,"source_commit":source_id,"run_id":record["run_id"],"memory_sha":t["memory_sha"],"prior_strategies":t["attempts"],"quality_gate":v["quality_gate"],"status":"WAIT_VERIFIED_NEW_BANK_AND_FROZEN_EXAM","next_strategy":"CONSENSUS_WITH_DIRECTION_AND_ERROR_GATES","training_authorized":False,"production":False}
    return seal({**prev,"records":prev["records"]+[item],"seen":prev["seen"]+[key]}),"REPAIR_REQUEST_RECORDED"
def main():
    p=argparse.ArgumentParser();p.add_argument("--state",type=Path,required=True);p.add_argument("--registry",type=Path,required=True);p.add_argument("--source-commit",required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    state=read(a.state) if a.state.exists() else initial()
    new,status=advance(state,read(a.registry),a.source_commit)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(new,sort_keys=True,indent=2)+"\n")
    print("H38N4_ESSENCE_PULSE",json.dumps({"status":status,"state_sha":new["sha256"],"records":len(new["records"]),"training_executed":False,"production":False},sort_keys=True))
if __name__=="__main__":main()
