"""BEACON: separate forward-only timing models and exact-input diagnostic cache."""
import argparse, hashlib, json, math, time
from datetime import datetime, timezone
from pathlib import Path
from tools.mintaka_scheduler_advisor import seal, verified, digest
ORGANS=("ESSENCE","BEETLE","COSMOS","MEMORY_CORTEX")
SCHEMA="janus.mintaka.beacon.v1"
MIN_GAP=60
MAX_GAP=7*86400
def ts(x):
    return int(datetime.fromisoformat(x.replace("Z","+00:00")).timestamp())
def initial():
    return seal({"schema":SCHEMA,"events":{k:[] for k in ORGANS},"cache":{},"live_forecasts":{},"live_errors":{k:[] for k in ORGANS},"production":False})
def fit(rows):
    # All intervals are observed past starts. Concurrent starts coalesce at same second.
    times=sorted({ts(z["started_at"]) for z in rows})
    gaps=[b-a for a,b in zip(times,times[1:]) if MIN_GAP<=b-a<=MAX_GAP]
    alphas=(.1,.3,.6)
    models={str(a):None for a in alphas};loss={str(a):0.0 for a in alphas}
    errors={"adaptive":[],"last":[],"mean":[]}
    for i,y in enumerate(gaps):
        if i>=4:
            chosen=min(loss,key=lambda k:(loss[k],float(k)))
            values={"adaptive":models[chosen],"last":gaps[i-1],"mean":sum(gaps[max(0,i-12):i])/min(12,i)}
            for k,p in values.items():errors[k].append(abs(y-p))
        for a in alphas:
            k=str(a);old=models[k]
            if old is not None:loss[k]+=abs(y-old)
            models[k]=y if old is None else old+a*(y-old)
    def mae(x):return sum(x)/len(x) if x else None
    n=len(errors["adaptive"]);m={k:mae(v) for k,v in errors.items()}
    halves=[{k:mae(v[i:j]) for k,v in errors.items()} for i,j in ((0,n//2),(n//2,n))]
    admitted=n>=12 and all(h["adaptive"]<min(h["last"],h["mean"]) for h in halves)
    chosen=min(loss,key=lambda k:(loss[k],float(k)))
    p=models[chosen] if gaps else None
    return {"n":len(times),"gap_n":len(gaps),"excluded_short_or_long_gaps":len(times)-1-len(gaps) if times else 0,"test_n":n,"mae_seconds":m,"halves":halves,"alpha":float(chosen),"admitted":admitted,"predicted_gap_seconds":round(p) if p is not None else None,"last_start_epoch":times[-1] if times else None}
def advance(old, snapshot, code_sha):
    s=verified(old)
    if s["schema"]!=SCHEMA or s["production"] is not False:raise ValueError("STATE")
    if set(snapshot["organs"])!=set(ORGANS):raise ValueError("ORGANS")
    cutoff=ts(snapshot["observed_at"])
    results={};hist={};cache={};live=dict(s["live_forecasts"]);errs={k:list(s["live_errors"][k]) for k in ORGANS}
    for k in ORGANS:
        block=snapshot["organs"][k]
        prior=s["events"][k];seen={str(x["id"]):x for x in prior}
        for z in block["runs"]:
            if z["event"]!="schedule" or ts(z["started_at"])>cutoff:raise ValueError("EVENT")
            key=str(z["id"])
            if key in seen and seen[key]!=z:raise ValueError("CONFLICT")
            seen[key]=z
        if len(seen)>2048:raise ValueError("CAPACITY_HOLD")
        rows=sorted(seen.values(),key=lambda z:(ts(z["started_at"]),str(z["id"])))
        hist[k]=rows
        # Input hash includes code version and exact history; no stale predictions on changed data.
        key=digest({"code":code_sha,"organ":k,"rows":rows})
        start=time.process_time_ns();base=fit(rows);baseline_ns=time.process_time_ns()-start
        prev=s["cache"].get(k);start=time.process_time_ns()
        hit=bool(prev and prev["key"]==key)
        actual=prev["result"] if hit else fit(rows)
        cached_ns=time.process_time_ns()-start
        if actual!=base:raise ValueError("CACHE_PARITY")
        # Paired actual runner timings; both arms execute, no claim of net savings.
        cache[k]={"key":key,"result":actual}
        # A forecast is recorded before the next observed start. Only reconcile
        # when the collection succeeded; historical backfill cannot score as future.
        prior_forecast=live.get(k)
        if block["status"]=="OK" and prior_forecast:
            future=[z for z in rows if ts(z["started_at"])>prior_forecast["issued_epoch"]]
            if future:
                y=ts(future[0]["started_at"])
                errs[k].append({"forecast":prior_forecast,"actual_epoch":y,"run_id":str(future[0]["id"]),"absolute_error_seconds":abs(y-prior_forecast["predicted_epoch"]),"baseline_last_error_seconds":abs(y-prior_forecast["last_epoch"])})
                if len(errs[k])>2048:raise ValueError("ERROR_CAPACITY")
                live.pop(k,None)
        if block["status"]=="OK" and k not in live and actual["predicted_gap_seconds"] is not None:
            # Issue only forecasts still in the future; stale arrival forecasts are not reissued.
            p=actual["last_start_epoch"]+actual["predicted_gap_seconds"]
            gaps=[b-a for a,b in zip(sorted({ts(z["started_at"]) for z in rows}),sorted({ts(z["started_at"]) for z in rows})[1:]) if MIN_GAP<=b-a<=MAX_GAP]
            if p>cutoff and gaps:
                live[k]={"issued_epoch":cutoff,"predicted_epoch":p,"last_epoch":actual["last_start_epoch"]+gaps[-1],"input_sha256":key}
        results[k]={"source_status":block["status"],"model":actual,"cache_hit":hit,"baseline_cpu_ns":baseline_ns,"cache_arm_cpu_ns":cached_ns,"live_error_n":len(errs[k]),"forecast":live.get(k),"mandatory_poll_unchanged":True}
    new=seal({"schema":SCHEMA,"events":hist,"cache":cache,"live_forecasts":live,"live_errors":errs,"production":False})
    report={"schema":"janus.mintaka.beacon.report.v1","observed_at":snapshot["observed_at"],"state_sha256":new["sha256"],"results":results,"baseline_total_cpu_ns":sum(z["baseline_cpu_ns"] for z in results.values()),"cache_arm_total_cpu_ns":sum(z["cache_arm_cpu_ns"] for z in results.values()),"cache_hits":sum(z["cache_hit"] for z in results.values()),"mandatory_source_reads":len(ORGANS),"scope":"Scheduled workflow start timestamps, not all organ execution; chronological replay plus future receipts; paired CPU of optional predictor only, not system-wide savings.","dispatch_authorized":False,"production":False}
    return new,report
def main():
    p=argparse.ArgumentParser();p.add_argument("--snapshot",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    old=json.loads(a.state.read_text()) if a.state.exists() else initial()
    code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    state,report=advance(old,json.loads(a.snapshot.read_text()),code)
    a.out.mkdir(parents=True,exist_ok=True)
    for n,v in (("state",state),("report",report)):
        (a.out/(n+".json")).write_text(json.dumps(v,sort_keys=True,indent=2)+"\n")
    print("MINTAKA_BEACON",json.dumps(report,sort_keys=True),flush=True)
if __name__=="__main__":main()
