"""Chronological offline replay of MINTAKA polling policies, not a scheduler."""
import argparse,json,math,hashlib
from pathlib import Path
from datetime import datetime,timezone
from statistics import median
from tools.mintaka_scheduler_advisor import seal,verified

DAY=1440
SLA=30
POLICIES=("FIXED15","FIXED30","FIXED60","ADAPTIVE_A","ADAPTIVE_B","ADAPTIVE_C")
def minute(t):
    return int(datetime.fromisoformat(t.replace("Z","+00:00")).timestamp()//60)
def step(policy,now,seen):
    if policy.startswith("FIXED"):return int(policy[5:])
    if len(seen)<3:return 30
    gaps=[b-a for a,b in zip(seen,seen[1:]) if b>a][-12:]
    if len(gaps)<2:return 30
    # Learn a robust interarrival forecast from already observed timestamps.
    target=median(gaps);elapsed=now-seen[-1]
    near={"ADAPTIVE_A":.5,"ADAPTIVE_B":.75,"ADAPTIVE_C":.9}[policy]
    # Long checks are only shadow suggestions, not mandatory health deadlines.
    return 60 if elapsed+60<near*target else 15 if elapsed>=near*target and elapsed<1.5*target else 30
def replay(events,start,end,policy,history=()):
    ev=sorted(set(t for t in events if start<=t<end));seen=sorted(set(t for t in history if t<start));i=0
    now=start;checks=empty=0;delays=[];actions=[]
    while now<end:
        checks+=1;new=[]
        while i<len(ev) and ev[i]<=now:
            new.append(ev[i]);delays.append(now-ev[i]);i+=1
        if not new:empty+=1
        seen.extend(new);gap=step(policy,now,seen)
        assert gap in (15,30,60)
        actions.append([now,gap,len(new)])
        now+=gap
    # Common terminal observation to avoid right-censoring differences.
    checks+=1;new=0
    while i<len(ev):
        delays.append(end-ev[i]);i+=1;new+=1
    if not new:empty+=1
    ds=sorted(delays)
    return {"events":len(ev),"detected":len(ds),"on_time":sum(x<=SLA for x in ds),"late":sum(x>SLA for x in ds),"checks":checks,"empty":empty,"max_delay":max(ds,default=0),"p95":ds[max(0,math.ceil(.95*len(ds))-1)] if ds else None,"mean_delay":sum(ds)/len(ds) if ds else None}
def selection(events,start,split):
    results={p:replay(events,start,split,p) for p in POLICIES}
    # Require no late arrivals in calibration; deterministic lexicographic cost.
    valid=[p for p in POLICIES if results[p]["late"]==0]
    best=min(valid,key=lambda p:(results[p]["checks"],results[p]["empty"],results[p]["p95"] or 0,POLICIES.index(p))) if valid else "FIXED15"
    return best,results
def exam(events,start,end):
    split=start+(end-start)*2//3
    old=[t for t in events if t<split]
    chosen,cal=selection(events,start,split)
    candidates={p:replay(events,split,end,p,old) for p in POLICIES}
    result=candidates[chosen];base=candidates["FIXED15"];strong=candidates["FIXED30"]
    # Strict test: preserve deadline and improve even on the efficient 30m baseline.
    pass_gate=(chosen.startswith("ADAPTIVE") and result["events"]>=8 and result["late"]==0 and result["detected"]==base["detected"] and result["checks"]<strong["checks"] and result["empty"]<strong["empty"])
    return {"split_minute":split,"chosen":chosen,"calibration":cal,"evaluation":candidates,"gate":"SHADOW_REPLAY_PASS" if pass_gate else "HOLD"}
def stress():
    out={}
    # Deliberately adverse bursts, silence and drift. Known scenario generators, not live data.
    cases={"bursts":[i*240+j for i in range(8) for j in (1,2,4,7)],"silence":[1,2,3,1700,1701,1702],"shift":[i*120+1 for i in range(8)]+[960+i*17 for i in range(40)],"uniform":[i*31+1 for i in range(62)]}
    for k,v in cases.items():out[k]=exam(v,0,2160)
    # Hard safety: speculative 60m can violate 30m SLA; never authorize it for mandatory work.
    for p in POLICIES:
        for t in range(0,300,13):
            assert min(SLA,step(p,t,[0,7,19]))<=SLA
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument("--trace",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    src=json.loads(a.trace.read_text());start=minute(src["start"]);end=minute(src["end"])
    assert end-start>=DAY and src["schema"]=="janus.mintaka.live_trace.v1"
    reports={}
    for name,rows in src["streams"].items():
        ids=set()
        for r in rows:
            assert r["id"] not in ids;ids.add(r["id"])
        events=[minute(z["completed_at"]) for z in rows]
        # Simultaneous events count as a single readiness epoch, not a single job.
        reports[name]={"raw_events":len(rows),"unique_minutes":len(set(events)),"result":exam(events,start,end)}
    rec=seal({"schema":"janus.mintaka.homeostasis.replay.v1","trace_sha256":hashlib.sha256(a.trace.read_bytes()).hexdigest(),"window":{"start":src["start"],"end":src["end"]},"sla_minutes":SLA,"streams":reports,"stress":stress(),"scope":"Historical completion timestamp replay; no actual changed schedule, no causal estimate of delivery reliability or CPU savings. Workload proxy is poll count. Mandatory cadence remains <=30 minutes in proposed guard; 60-minute shadow suggestions not admitted.","dispatch_authorized":False,"production":False})
    a.out.mkdir(parents=True,exist_ok=True);(a.out/"report.json").write_text(json.dumps(rec,sort_keys=True,indent=2)+"\n")
    print("MINTAKA_HOMEOSTASIS",json.dumps(rec,sort_keys=True))
if __name__=="__main__":main()
