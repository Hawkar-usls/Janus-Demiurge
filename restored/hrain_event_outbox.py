from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Iterable

SCHEMA="janus.hrain.event.v1"
LEDGER_SCHEMA="janus.hrain.outbox.ledger.v1"
ZERO="0"*64
CRITICAL_TYPES={"record","collapse"}

def _canon(x:Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def _read(path:Path)->list[dict[str,Any]]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def normalize_event(event:dict[str,Any], *, source:str="demiurge") -> dict[str,Any]:
    event_type=str(event.get("type","unknown")).strip().casefold()
    payload={k:v for k,v in event.items() if k!="event_id"}
    identity={"source":source,"event_type":event_type,"payload":payload}
    event_id=hashlib.sha256(_canon(identity)).hexdigest()
    return {"schema":SCHEMA,"event_id":event_id,"source":source,"event_type":event_type,
            "critical":event_type in CRITICAL_TYPES,"payload":payload}

def append(path:str|Path, event:dict[str,Any], *, source:str="demiurge") -> dict[str,Any]:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    rows=_read(p); env=normalize_event(event,source=source)
    for row in rows:
        if row.get("event_id")==env["event_id"]:
            return {"appended":False,"record":row}
    prev=rows[-1]["record_sha256"] if rows else ZERO
    body={"schema":LEDGER_SCHEMA,"seq":len(rows)+1,"previous_hash":prev,**env,
          "transport_authority":False}
    body["record_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    with p.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n")
    return {"appended":True,"record":body}

def verify(path:str|Path)->dict[str,Any]:
    rows=_read(Path(path)); prev=ZERO
    for i,row in enumerate(rows,1):
        if row.get("seq")!=i or row.get("previous_hash")!=prev:
            return {"valid":False,"failed_at":i,"records":len(rows)}
        copy=dict(row); claimed=copy.pop("record_sha256",None)
        if hashlib.sha256(_canon(copy)).hexdigest()!=claimed:
            return {"valid":False,"failed_at":i,"records":len(rows)}
        prev=claimed
    return {"valid":True,"records":len(rows),"head":prev}

def active_window(path:str|Path, *, max_cycle_events:int=64) -> list[dict[str,Any]]:
    rows=_read(Path(path))
    critical=[r for r in rows if r.get("critical")]
    noncritical=[r for r in rows if not r.get("critical")]
    recent=noncritical[-max(0,int(max_cycle_events)):]
    chosen={r["event_id"]:r for r in critical+recent}
    return sorted(chosen.values(),key=lambda r:r["seq"])

def transport_batch(path:str|Path, acknowledged_event_ids:Iterable[str]=(), *, max_cycle_events:int=64)->dict[str,Any]:
    ack=set(acknowledged_event_ids)
    selected=[r for r in active_window(path,max_cycle_events=max_cycle_events) if r["event_id"] not in ack]
    return {"schema":"janus.hrain.transport_batch.v1","events":selected,"event_count":len(selected),
            "authority":{"network_io":False,"acknowledges_events":False,"deletes_ledger":False},
            "law":"OUTBOX_DECOUPLES_EVENT_PRODUCTION_FROM_NETWORK_TRANSPORT"}
