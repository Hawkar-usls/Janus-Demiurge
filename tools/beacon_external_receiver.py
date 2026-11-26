"""Untrusted external mailbox -> validated shadow evidence, never execution."""
import argparse, hashlib, json, re
from datetime import datetime
from pathlib import Path
from collections import Counter
LINES=("beetle_producer","beetle_local_receiver","beetle_genesis_watchdog","genesis_home","genesis_receiver")
STATUSES={"UNKNOWN","SCHEDULE_OK","SCHEDULE_SILENCE","SCHEDULE_ACTIVE","SCHEDULE_LONG_RUNNING"}
UUID=re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
def sha(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def seal(v):return {**v,"sha256":sha(v)}
def check(v):
    b={k:x for k,x in v.items() if k!="sha256"}
    if v.get("sha256")!=sha(b):raise ValueError("STATE_HASH")
    return b
def epoch(v):
    if not isinstance(v,str) or not v.endswith("Z"):raise ValueError("UTC")
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    return d.timestamp()
def exact(x,keys):
    if type(x) is not dict or set(x)!=set(keys):raise ValueError("FIELDS")
def validate(x,filename):
    exact(x,("schema","source","origin_class","run_id","observed_at_utc","scheduled_for","source_completed_at","coverage","lines","authority","production"))
    if x["schema"]!="janus.beacon.external_observation.v1" or x["source"]!="EXTERNAL_SILENCE_WITNESS" or x["origin_class"]!="RELAY_NORMALIZED_TASK_RESULT":raise ValueError("ORIGIN")
    if not isinstance(x["run_id"],str) or not UUID.fullmatch(x["run_id"]) or filename!=x["run_id"]+".json":raise ValueError("IDENTITY")
    now=epoch(x["observed_at_utc"]);done=epoch(x["source_completed_at"]);scheduled=epoch(x["scheduled_for"])
    if not scheduled<=now<=done or done-now>900:raise ValueError("TIME_ORDER")
    exact(x["coverage"],("pages","records","api_status"))
    c=x["coverage"]
    if type(c["pages"]) is not int or not 0<=c["pages"]<=40 or type(c["records"]) is not int or not 0<=c["records"]<=200 or c["api_status"] not in ("OK","PARTIAL","UNAVAILABLE"):raise ValueError("COVERAGE")
    exact(x["authority"],("command","runtime","science"))
    if any(v is not False for v in x["authority"].values()) or x["production"] is not False:raise ValueError("AUTHORITY")
    exact(x["lines"],LINES)
    for k,z in x["lines"].items():
        if type(z) is not dict or z.get("status") not in STATUSES:raise ValueError("STATUS")
        if z["status"]=="UNKNOWN":
            exact(z,("status",));continue
        if c["api_status"]!="OK" or c["pages"]<20 or c["records"]<200:raise ValueError("INCOMPLETE_COVERAGE")
        if z["status"] in ("SCHEDULE_ACTIVE","SCHEDULE_LONG_RUNNING"):
            exact(z,("status",));continue
        exact(z,("status","run_id","completion_basis","reported_at"))
        if type(z["run_id"]) is not int or z["run_id"]<=0 or z["completion_basis"] not in ("UPDATED_AT","JOB_COMPLETED_AT"):raise ValueError("COMPLETION")
        t=epoch(z["reported_at"])
        if t>now or int(now-t>=21600)!=int(z["status"]=="SCHEDULE_SILENCE"):raise ValueError("AGE_LABEL")
    return x
def importer(path):
    r=json.loads(path.read_text());b={k:v for k,v in r.items() if k!="receipt_sha256"}
    if r.get("receipt_sha256")!=sha(b) or r.get("schema")!="janus.external_witness.import_receipt.v1" or r["collector"]["type"]!="TRUSTED_META_REGISTRY_IMPORTER_NOT_EXTERNAL_WITNESS":raise ValueError("IMPORTER_HASH_OR_ORIGIN")
    return r
def crosscheck(x,rows):
    now=epoch(x["observed_at_utc"]);prior=[r for r in rows if epoch(r["observed_at_utc"])<=now]
    latest=max(prior,key=lambda r:epoch(r["observed_at_utc"])) if prior else None
    out={}
    for k,z in x["lines"].items():
        if z["status"]=="UNKNOWN":out[k]={"status":"UNKNOWN_NO_LABEL"};continue
        if z["status"] not in ("SCHEDULE_OK","SCHEDULE_SILENCE"):out[k]={"status":"ACTIVE_REPORTED_NO_LABEL"};continue
        # Match a distinct completed run in a prior, sealed importer receipt.
        matches=[]
        for r in prior:
            line=r["observations"].get(k,{})
            run=line.get("last_schedule_run") or {}
            if line.get("status") not in ("SCHEDULE_OK","SCHEDULE_SILENCE") or run.get("run_id")!=z["run_id"] or not run.get("completed_at"):continue
            completed=epoch(run["completed_at"]);observed=epoch(r["observed_at_utc"])
            if completed>observed or abs(completed-epoch(z["reported_at"]))>2:continue
            matches.append((observed,r,run))
        if not matches:out[k]={"status":"UNCORROBORATED_NO_LABEL"};continue
        _,r,run=max(matches,key=lambda a:a[0]);out[k]={"status":"CORROBORATED_COMPLETION_ONLY","run_id":z["run_id"],"completed_at":run["completed_at"],"importer_receipt_sha256":r["receipt_sha256"]}
        # Do not score external status if updated_at, even when completion matches.
        if latest and now-epoch(latest["observed_at_utc"])<=900 and z["completion_basis"]=="JOB_COMPLETED_AT":
            q=latest["observations"].get(k,{})
            if q.get("status")==z["status"] and (q.get("last_schedule_run") or {}).get("run_id")==z["run_id"] and not q.get("active_schedule_run"):
                out[k]["status"]="CORROBORATED_STATUS_SHADOW"
    return out
def process(paths,rows,old):
    s=check(old);prior=s["records"];out=dict(prior);errors=[]
    if len(paths)>2048:raise ValueError("MAILBOX_CAPACITY")
    seen=set()
    for p in sorted(paths):
        try:
            if p.is_symlink() or p.stat().st_size>16384:raise ValueError("FILE")
            raw=p.read_bytes();x=validate(json.loads(raw),p.name);key=x["run_id"];h=hashlib.sha256(raw).hexdigest()
            if key in seen:raise ValueError("DUPLICATE")
            seen.add(key)
            if key in out:
                if out[key]["mailbox_sha256"]!=h:raise ValueError("IMMUTABLE_CONFLICT")
                continue
            out[key]={"mailbox_sha256":h,"observation":x,"crosscheck":crosscheck(x,rows),"authority":False}
        except (ValueError,KeyError,TypeError,OSError) as e:errors.append({"file":p.name,"reason":str(e)[:80]})
    # Never erase historical receipts even if mailbox files disappear.
    missing=sorted(set(prior)-seen)
    if len(out)>2048:raise ValueError("STATE_CAPACITY")
    state=seal({"schema":"janus.beacon.external.receiver.state.v1","records":out,"production":False})
    stats=Counter(z["status"] for q in out.values() for z in q["crosscheck"].values())
    distinct={(k,z["run_id"],z["completed_at"]) for q in out.values() for k,z in q["crosscheck"].items() if z["status"] in ("CORROBORATED_COMPLETION_ONLY","CORROBORATED_STATUS_SHADOW")}
    report={"schema":"janus.beacon.external.receiver.report.v1","state_sha256":state["sha256"],"accepted":len(out),"new":len(out)-len(prior),"status_counts":dict(stats),"distinct_corroborated_completions":len(distinct),"rejected":errors,"missing_prior":missing,"dispatch_authorized":False,"production":False,"training_authorized":False,"origin":"RELAY_NORMALIZED_UNATTESTED_TASK_OUTPUT"}
    return state,report
def main():
    p=argparse.ArgumentParser();p.add_argument("--mailbox",type=Path,required=True);p.add_argument("--archive",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    old=json.loads(a.state.read_text()) if a.state.exists() else seal({"schema":"janus.beacon.external.receiver.state.v1","records":{},"production":False})
    rows=[importer(p) for p in (a.archive/"observations").glob("*/*.json")]
    if not rows or len(rows)>4096:raise ValueError("IMPORTER_CAPACITY")
    s,r=process(list(a.mailbox.glob("*.json")),rows,old)
    a.out.mkdir(parents=True,exist_ok=True)
    for n,v in (("state",s),("report",r)):(a.out/(n+".json")).write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print("BEACON_EXTERNAL_RECEIVER",json.dumps(r,sort_keys=True),flush=True)
    if r["rejected"] or r["missing_prior"]:raise SystemExit(2)
if __name__=="__main__":main()
