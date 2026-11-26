"""BEACON rhythm synchronisation. All predictions are advisory."""
import argparse,json,hashlib,time,statistics
from pathlib import Path
from tools.mintaka_scheduler_advisor import seal,verified,digest
from tools.mintaka_beacon_predictor import ts,ORGANS
PERIOD={"ESSENCE":900,"BEETLE":1200,"COSMOS":3600,"MEMORY_CORTEX":1200}
PHASE={"ESSENCE":420,"BEETLE":420,"COSMOS":2820,"MEMORY_CORTEX":1020}
SCHEMA="janus.mintaka.beacon.rhythm.v1"
MODES=("last","mean12","nominal","phase","adaptive_gap","phase_skip")
def med(x,default=0):return statistics.median(x) if x else default
def slot(t,p,phase):return ((t-phase)//p)*p+phase
def nextslot(t,p,phase):return slot(t,p,phase)+p
def candidates(rows,k):
    p=PERIOD[k];phase=PHASE[k];last=ts(rows[-1]["started_at"])
    gaps=[ts(b["started_at"])-ts(a["started_at"]) for a,b in zip(rows,rows[1:])]
    # created_at is not scheduled-for; phase residual is only a proxy.
    delays=[ts(z["started_at"])-ts(z["created_at"]) for z in rows[-24:]]
    residual=[ts(z["created_at"])-slot(ts(z["created_at"]),p,phase) for z in rows[-24:]]
    slots=[slot(ts(z["created_at"]),p,phase) for z in rows]
    skips=[max(1,round((b-a)/p)) for a,b in zip(slots,slots[1:])]
    ema=p
    for g in gaps:ema=.7*ema+.3*g
    offset=round(med(residual)+med(delays))
    phase_pred=nextslot(last,p,phase)+offset
    skip_pred=slots[-1]+round(med(skips[-12:],1))*p+offset
    return {"last":last+(gaps[-1] if gaps else p),"mean12":last+round(statistics.mean(gaps[-12:])) if gaps else last+p,"nominal":nextslot(last,p,phase),"phase":max(last+1,phase_pred),"adaptive_gap":last+round(ema),"phase_skip":max(last+1,skip_pred)}
def fit(rows,k):
    sched=sorted((r for r in rows if r["event"]=="schedule"),key=lambda z:(ts(z["started_at"]),str(z["id"])))
    # Keep first run per second for interval models, count all source runs separately.
    sched=list({ts(z["started_at"]):z for z in sched}.values())
    losses={m:[] for m in (*MODES,"selector")}
    choices=[]
    for i in range(5,len(sched)):
        pred=candidates(sched[:i],k);y=ts(sched[i]["started_at"])
        # Select using only previous observed prediction errors.
        chosen=min(MODES,key=lambda m:(sum(losses[m])/len(losses[m]) if losses[m] else 0,MODES.index(m)))
        choices.append(chosen)
        for m,v in pred.items():losses[m].append(abs(y-v))
        losses["selector"].append(abs(y-pred[chosen]))
    n=len(choices)
    def means(a,b):return {m:sum(v[a:b])/len(v[a:b]) if v[a:b] else None for m,v in losses.items()}
    halves=[means(0,n//2),means(n//2,n)]
    admitted=n>=12 and all(h["selector"]<min(h["last"],h["mean12"],h["nominal"]) for h in halves)
    p=PERIOD[k];phase=PHASE[k]
    slots=[slot(ts(z["created_at"]),p,phase) for z in sched]
    gaps=[b-a for a,b in zip(slots,slots[1:])]
    chosen=min(MODES,key=lambda m:(sum(losses[m])/n if n else 0,MODES.index(m)))
    pr=candidates(sched,k) if sched else {}
    return {"scheduled_starts":len(sched),"event_counts":{e:sum(z["event"]==e for z in rows) for e in sorted({z["event"] for z in rows})},"test_n":n,"mae_seconds":means(0,n),"halves":halves,"chosen":chosen,"admitted":admitted,"nominal_period_seconds":p,"median_queue_delay_seconds":med([ts(z["started_at"])-ts(z["created_at"]) for z in sched],None),"median_phase_residual_seconds":med([ts(z["created_at"])-slot(ts(z["created_at"]),p,phase) for z in sched],None),"unobserved_nominal_slots_proxy":sum(max(0,g//p-1) for g in gaps),"last_start":ts(sched[-1]["started_at"]) if sched else None,"predictions":pr}
def initial():
    return seal({"schema":SCHEMA,"history":{k:[] for k in ORGANS},"cache":{},"pending":{},"errors":{k:[] for k in ORGANS},"production":False})
def compute(rows,k,code,prior):
    # Timing includes digest computation, cache comparison and complete fit on miss.
    key=digest({"code":code,"organ":k,"rows":rows})
    if prior and prior["key"]==key:return prior,True
    return {"key":key,"result":fit(rows,k)},False
def advance(old,snap,code,benchmark=False):
    s=verified(old)
    if s["schema"]!=SCHEMA or s["production"] is not False or set(snap["organs"])!=set(ORGANS):raise ValueError("SCHEMA")
    now=ts(snap["observed_at"]);history={};cache={};pending=dict(s["pending"]);errors={k:list(v) for k,v in s["errors"].items()};report={}
    for k in ORGANS:
        block=snap["organs"][k];seen={str(z["id"]):z for z in s["history"][k]}
        for z in block["runs"]:
            if z["event"] not in ("schedule","workflow_run","push","workflow_dispatch") or not ts(z["created_at"])<=ts(z["started_at"])<=now:raise ValueError("TIME_ORDER")
            key=str(z["id"])
            if key in seen and seen[key]!=z:raise ValueError("EVENT_CONFLICT")
            seen[key]=z
        if len(seen)>2048:raise ValueError("CAPACITY_HOLD")
        rows=sorted(seen.values(),key=lambda z:(ts(z["started_at"]),str(z["id"])))
        history[k]=rows
        start=time.process_time_ns();cached,hit=compute(rows,k,code,s["cache"].get(k));fast=time.process_time_ns()-start
        full=None
        if benchmark:
            start=time.process_time_ns();fresh,_=compute(rows,k,code,None);full=time.process_time_ns()-start
            if fresh!=cached:raise ValueError("PARITY")
        cache[k]=cached;r=cached["result"]
        if block["status"]=="OK" and k in pending:
            f=pending[k]
            future=[z for z in rows if z["event"]=="schedule" and ts(z["started_at"])>f["issued"]]
            if future:
                y=ts(future[0]["started_at"])
                errors[k].append({"forecast":f,"actual":y,"run_id":future[0]["id"],"absolute_error_seconds":{m:abs(y-v) for m,v in f["predictions"].items()}})
                pending.pop(k)
        if len(errors[k])>2048:raise ValueError("CAPACITY_HOLD")
        if block["status"]=="OK" and k not in pending and r["predictions"]:
            # Expired predictions become explicit overdue alerts, never silently dropped.
            pending[k]={"issued":now,"predictions":{m:max(now+1,v) for m,v in r["predictions"].items()},"overdue_models":[m for m,v in r["predictions"].items() if v<=now],"selected":r["chosen"],"input_sha256":cached["key"]}
        report[k]={"source_status":block["status"],"model":r,"cache_hit":hit,"full_cpu_ns":full,"cache_cpu_ns":fast,"prospective_n":len(errors[k]),"forecast":pending.get(k)}
    new=seal({"schema":SCHEMA,"history":history,"cache":cache,"pending":pending,"errors":errors,"production":False})
    rec={"schema":"janus.mintaka.beacon.rhythm.report.v1","observed_at":snap["observed_at"],"state_sha256":new["sha256"],"organs":report,"mandatory_reads":4,"full_cpu_ns":sum(z["full_cpu_ns"] for z in report.values()) if benchmark else None,"cache_cpu_ns":sum(z["cache_cpu_ns"] for z in report.values()),"cache_hits":sum(z["cache_hit"] for z in report.values()),"actual_fit_calls":sum(not z["cache_hit"] for z in report.values()),"benchmark_extra_fit_calls":4 if benchmark else 0,"dispatch_authorized":False,"production":False}
    return new,rec
def main():
    p=argparse.ArgumentParser();p.add_argument("--snapshot",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--benchmark",action="store_true");a=p.parse_args()
    old=json.loads(a.state.read_text()) if a.state.exists() else initial()
    s,r=advance(old,json.loads(a.snapshot.read_text()),hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),a.benchmark)
    a.out.mkdir(parents=True,exist_ok=True)
    for k,v in (("state",s),("report",r)):(a.out/(k+".json")).write_text(json.dumps(v,sort_keys=True,indent=2)+"\n")
    print("BEACON_RHYTHM",json.dumps(r,sort_keys=True),flush=True)
if __name__=="__main__":main()
