"""MINTAKA: bounded, learnable scheduler health advisor; no dispatch authority."""
import argparse, hashlib, json, math
from pathlib import Path

STAGES=("wake","persist","learn")
MODES=("RED","AMBER","GREEN")
SCHEMA="janus.mintaka.scheduler.shadow.v1"
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def seal(x):return {**x,"sha256":digest(x)}
def verified(x):
    v={k:z for k,z in x.items() if k!="sha256"}
    if x.get("sha256")!=digest(v):raise ValueError("STATE_HASH")
    return v
def initial():return seal({"schema":SCHEMA,"observations":[],"production":False})
def extract(runs):
    out=[]
    for workflow,items in runs.items():
        for run in items:
            if run["event"] not in ("schedule","push","workflow_run","workflow_dispatch") or run["status"]!="completed":continue
            stage_jobs={"pulse":"wake"} if workflow=="essence" else {"persist":"persist","execute-research":"learn"}
            for job in run["jobs"]:
                stage=stage_jobs.get(job["name"])
                if not stage or job["conclusion"] not in ("success","failure","timed_out"):continue
                # A green job with a skipped learner step is not a learning success.
                if stage=="learn" and job["conclusion"]=="success" and not job.get("training_executed",False):continue
                out.append({"id":str(job["id"]),"run_id":str(run["id"]),"stage":stage,"event":run["event"],"created":run["created_at"],"revision":run["head_sha"],"y":int(job["conclusion"]=="success")})
    return out
def append(state,observations):
    s=verified(state)
    if s["schema"]!=SCHEMA or s["production"] is not False:raise ValueError("STATE")
    byid={z["id"]:z for z in s["observations"]}
    for z in observations:
        if z["stage"] not in STAGES or z["y"] not in (0,1):raise ValueError("OBSERVATION")
        if z["id"] in byid and byid[z["id"]]!=z:raise ValueError("CONFLICT")
        byid[z["id"]]=z
    if len(byid)>2048:raise ValueError("CAPACITY_HOLD")
    return seal({**s,"observations":sorted(byid.values(),key=lambda z:(z["created"],int(z["id"])))})
def posterior(rows,stage,event=None):
    x=[z["y"] for z in rows if z["stage"]==stage and (event is None or z["event"]==event)]
    return (1+sum(x))/(2+len(x)),len(x)
def assess(state,queue_ready,active_memory,remaining,paused,round_no):
    rows=verified(state)["observations"];metrics={};advice={}
    for stage in STAGES:
        xs=[z for z in rows if z["stage"]==stage]
        # Strict chronological prediction: use only prior observations, compare fixed 0.5 and last outcome.
        model=base=last=0.0
        for k,z in enumerate(xs):
            p,_=posterior(xs[:k],stage,z["event"])
            y=z["y"];model+=(p-y)**2;base+=(.5-y)**2
            last+=((xs[k-1]["y"] if k else .5)-y)**2
        n=len(xs);p,_=posterior(xs,stage)
        # Do not use a stale failure as a hard gate; only bounded advisory interval.
        current=[z for z in xs if z["revision"]==xs[-1]["revision"]] if xs else []
        cp,cn=posterior(current,stage)
        learned=n>=8 and model<base and model<=last and cn>=3
        delay=15 if learned and cp>=.8 else 30 if learned and cp>=.5 else 60
        metrics[stage]={"observations":n,"current_revision_n":cn,"posterior":p,"current_posterior":cp,"brier":model/n if n else None,"fixed_brier":base/n if n else None,"persistence_brier":last/n if n else None,"learned":learned}
        advice[stage]={"review_after_minutes":delay,"mode":"SHADOW_ADVISORY_ONLY","no_dispatch":True}
    # Source traffic-light Latin square rotates audit priority only, never grants authority.
    rotation={stage:MODES[(i+round_no)%3] for i,stage in enumerate(STAGES)}
    gates={"wake":"RED" if paused else "GREEN","persist":"RED" if paused else "GREEN" if queue_ready else "AMBER","learn":"RED" if paused or remaining<=0 else "GREEN" if queue_ready and active_memory else "AMBER"}
    return {"schema":SCHEMA,"metrics":metrics,"advice":advice,"audit_rotation":rotation,"hard_gate":gates,"state_sha256":state["sha256"],"dispatch_authorized":False,"production":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--runs",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--queue-ready",action="store_true");p.add_argument("--active-memory",action="store_true");p.add_argument("--remaining",type=int,required=True);p.add_argument("--paused",action="store_true");p.add_argument("--round",type=int,required=True);a=p.parse_args()
    s=json.loads(a.state.read_text()) if a.state.exists() else initial()
    s=append(s,extract(json.loads(a.runs.read_text())))
    r=assess(s,a.queue_ready,a.active_memory,a.remaining,a.paused,sum(z["stage"]=="wake" for z in verified(s)["observations"]))
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"state.json").write_text(json.dumps(s,sort_keys=True,indent=2)+"\n")
    (a.out/"advice.json").write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print("MINTAKA_SHADOW",json.dumps(r,sort_keys=True))
if __name__=="__main__":main()
