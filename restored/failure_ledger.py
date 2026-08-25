from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

SCHEMA="janus.failure_ledger.record.v1"
ZERO="0"*64

def canon(x:Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def _records(path:Path)->list[dict[str,Any]]:
    if not path.exists(): return []
    out=[]
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip(): out.append(json.loads(line))
    return out

def append(path:str|Path, *, kind:str, subject_sha256:str, status:str, detail:dict[str,Any]|None=None)->dict[str,Any]:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    existing=_records(p)
    evidence={"kind":kind,"subject_sha256":subject_sha256,"status":status,"detail":detail or {}}
    evidence_id=hashlib.sha256(canon(evidence)).hexdigest()
    for rec in existing:
        if rec.get("evidence_id")==evidence_id:
            return {"appended":False,"record":rec}
    prev=existing[-1]["record_hash"] if existing else ZERO
    body={"schema":SCHEMA,"seq":len(existing)+1,"previous_hash":prev,"evidence_id":evidence_id,**evidence}
    body["record_hash"]=hashlib.sha256(canon(body)).hexdigest()
    with p.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
    return {"appended":True,"record":body}

def verify(path:str|Path)->dict[str,Any]:
    recs=_records(Path(path)); prev=ZERO
    for i,rec in enumerate(recs,1):
        if rec.get("seq")!=i or rec.get("previous_hash")!=prev:
            return {"valid":False,"records":len(recs),"failed_at":i}
        copy=dict(rec); claimed=copy.pop("record_hash",None)
        if hashlib.sha256(canon(copy)).hexdigest()!=claimed:
            return {"valid":False,"records":len(recs),"failed_at":i}
        prev=claimed
    return {"valid":True,"records":len(recs),"head":prev}
