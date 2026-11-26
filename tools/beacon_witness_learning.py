"""BEACON witness learning: verified importer snapshots and separate external review."""
import argparse, hashlib, json, math, statistics
from datetime import datetime
from pathlib import Path
from collections import Counter,defaultdict
LINES={
 "beetle_producer":("Hawkar-usls/janus-lapis","JANUS Universal Beetle hourly"),
 "beetle_local_receiver":("Hawkar-usls/janus-lapis","JANUS Beetle Memory Receiver"),
 "beetle_genesis_watchdog":("Hawkar-usls/janus-lapis","JANUS Beetle → Genesis durable delivery watchdog"),
 "genesis_home":("Hawkar-usls/Janus_Genesis","JANUS Habitat Cloud HOME v1"),
 "genesis_receiver":("Hawkar-usls/Janus_Genesis","JANUS Beetle Memory Receiver")}
KNOWN={"SCHEDULE_OK":0,"SCHEDULE_SILENCE":1}
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
def stamp(s):
    t=datetime.fromisoformat(s.replace("Z","+00:00"))
    if t.tzinfo is None:raise ValueError("TIMEZONE")
    return int(t.timestamp())
def validate(r):
    if r.get("receipt_sha256")!=digest({k:v for k,v in r.items() if k!="receipt_sha256"}):raise ValueError("RECEIPT_HASH")
    if r["schema"]!="janus.external_witness.import_receipt.v1" or r["collector"]["type"]!="TRUSTED_META_REGISTRY_IMPORTER_NOT_EXTERNAL_WITNESS":raise ValueError("ORIGIN")
    a=r["authority"]
    if a!={"command_authority":False,"runtime_execution":False,"scientific_authority_delta":0,"scientific_proof":False}:raise ValueError("AUTHORITY")
    now=stamp(r["observed_at_utc"]);out={}
    for k,(repo,name) in LINES.items():
        x=r["observations"].get(k,{})
        st=x.get("status","UNKNOWN")
        if st not in KNOWN:out[k]={"status":st};continue
        if x.get("repository")!=repo or x.get("workflow")!=name or x.get("active_schedule_run"):raise ValueError("LINE_BINDING")
        run=x["last_schedule_run"];t=stamp(run["completed_at"]);age=(now-t)/60
        if not 0<=age or abs(age-x["age_minutes"])>.025 or KNOWN[st]!=int(age>=360):raise ValueError("AGE_LABEL")
        if type(run["run_id"]) is not int or run["run_id"]<=0:raise ValueError("RUN_ID")
        out[k]={"status":st,"age":age,"run_id":run["run_id"],"completed":t}
    return {"time":now,"lines":out,"sha":r["receipt_sha256"],"collector_id":str(r["collector"]["run_id"])+":"+str(r["collector"]["run_attempt"])}
def features(a,k):
    x=a["lines"][k];age=x["age"];other=sum(v["status"]=="SCHEDULE_SILENCE" for j,v in a["lines"].items() if j!=k)
    unknown=sum(v["status"] not in KNOWN for j,v in a["lines"].items() if j!=k)
    bucket=min(6,int(age//60))
    return {"line":(k,),"age":(k,bucket),"swarm":(k,bucket,min(2,other),int(unknown>0))}
def examples(rows):
    # A label is the next actual confirmed observation 30–120m later,
    # never a guessed missed trigger. UNKNOWN/active endpoints are excluded.
    out=[]
    for a,b in zip(rows,rows[1:]):
        h=(b["time"]-a["time"])/60
        if not 30<=h<=120:continue
        for k in LINES:
            x=a["lines"][k];y=b["lines"][k]
            if x["status"] not in KNOWN or y["status"] not in KNOWN:continue
            if y["completed"]<x["completed"]:continue
            out.append({"at":a["time"],"label_at":b["time"],"line":k,"y":KNOWN[y["status"]],"features":features(a,k),"persist":KNOWN[x["status"]],"age_rule":int(x["age"]+60>=360)})
    return out
def evaluate(ex,cutoff):
    model={m:defaultdict(lambda:[0,0]) for m in ("line","age","swarm")}
    names=("line","age","swarm","persist","age_rule")
    bytime=defaultdict(list)
    for z in ex:bytime[z["at"]].append(z)
    train=Counter();test=Counter();loss=Counter();cm=defaultdict(Counter);byline=defaultdict(Counter);pending=[]
    # Apply outcomes only once they have become available at the forecast timestamp.
    for at,zs in sorted(bytime.items()):
        ready=[z for z in pending if z["label_at"]<=at];pending=[z for z in pending if z["label_at"]>at]
        for z in ready:
            for m,counts in model.items():
                n=counts[z["features"][m]];n[0]+=z["y"];n[1]+=1
        for z in zs:
            if z["label_at"]<=cutoff:train[z["line"]]+=1
            elif at>=cutoff:
                y=z["y"];test[z["line"]]+=1
                p={"persist":z["persist"],"age_rule":z["age_rule"]}
                for m,counts in model.items():
                    a,n=counts[z["features"][m]]
                    # Back off to line history, then neutral prior; no test lookahead.
                    if n<4 and m!="line":a,n=model["line"][z["features"]["line"]]
                    p[m]=(a+1)/(n+2)
                for m in names:
                    e=(p[m]-y)**2;loss[m]+=e;byline[z["line"]][m]+=e
                    c=cm[m];pred=int(p[m]>=.5);c["tp" if pred and y else "fp" if pred else "fn" if y else "tn"]+=1
            pending.append(z)
    n=sum(test.values());scores={m:loss[m]/n if n else None for m in names}
    # Fixed, preregistered swarm model; comparison includes persistence/age and univariate learned baseline.
    gate=n>=30 and cm["swarm"]["tp"]+cm["swarm"]["fn"]>=5 and all(scores["swarm"]<scores[m] for m in names if m!="swarm") and cm["swarm"]["fn"]<=cm["persist"]["fn"] and cm["swarm"]["fp"]<=cm["persist"]["fp"]
    return {"training_counts":dict(train),"test_counts":dict(test),"test_n":n,"brier":scores,"confusion":{m:dict(cm[m]) for m in names},"per_line_brier":{k:{m:v/test[k] for m,v in byline[k].items()} for k in test},"gate":"SHADOW_PASS" if gate else "HOLD"}
def timing(rows,cutoff):
    # Only distinct observed successful completions; intermediary successes may
    # have been missed by polling. Score next *observed* completion, not next actual run.
    report={}
    for k in LINES:
        known={};history=[];errors={m:[] for m in ("last","mean12","beacon")}
        for a in rows:
            z=a["lines"][k]
            if z["status"] not in KNOWN or z["run_id"] in known:continue
            known[z["run_id"]]=z["completed"]
            if history and z["completed"]<=history[-1][0]:continue
            gaps=[v[0]-u[0] for u,v in zip(history,history[1:])]
            if len(gaps)>=4 and a["time"]>=cutoff and history[-1][1]>=cutoff and z["completed"]>history[-1][1]:
                y=z["completed"]-history[-1][0];ema=gaps[0]
                for g in gaps[1:]:ema=.7*ema+.3*g
                for m,v in (("last",gaps[-1]),("mean12",statistics.mean(gaps[-12:])),("beacon",ema)):
                    errors[m].append(abs(y-v))
            history.append((z["completed"],a["time"]))
        report[k]={"distinct_observed_completions":len(history),"test_n":len(errors["beacon"]),"mae_seconds":{m:statistics.mean(v) if v else None for m,v in errors.items()}}
    return report
def external_crosscheck(rows,ext):
    at=stamp(ext["observed_at_utc"]);prior=[x for x in rows if x["time"]<=at]
    if not prior:raise ValueError("NO_PRIOR_IMPORTER")
    a=prior[-1];result={}
    for k,x in ext["lines"].items():
        y=a["lines"][k]
        if x["status"] not in KNOWN:result[k]="EXTERNAL_UNKNOWN_NO_LABEL"
        elif y["status"] not in KNOWN:result[k]="IMPORTER_UNKNOWN_NO_LABEL"
        else:result[k]="AGREE_RUN_AND_STATUS" if x["status"]==y["status"] and x["run_id"]==y["run_id"] and abs(stamp(x["reported_utc"])-y["completed"])<=2 else "DISAGREEMENT_HOLD"
    return {"importer_sha":a["sha"],"importer_time":a["time"],"external_time":at,"lines":result,"external_training_rows":0}
def main():
    p=argparse.ArgumentParser();p.add_argument("--archive",type=Path,required=True);p.add_argument("--external",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    rows=[];seen=set();counts=Counter();quarantine=[]
    for path in sorted((a.archive/"observations").glob("*/*.json")):
        r=json.loads(path.read_text());z=validate(r)
        if z["collector_id"] in seen:raise ValueError("DUPLICATE_RECEIPT")
        seen.add(z["collector_id"]);rows.append(z)
        for k,v in z["lines"].items():counts[k+":"+v["status"]]+=1
    rows.sort(key=lambda z:z["time"])
    if len(rows)<10 or len(rows)>4096 or any(a["time"]>=b["time"] for a,b in zip(rows,rows[1:])):raise ValueError("ARCHIVE_BOUND_OR_ORDER")
    cut=rows[len(rows)*7//10]["time"]
    ext=json.loads(a.external.read_text())
    report={"schema":"janus.beacon.witness.learning.v1","receipts":len(rows),"first":rows[0]["time"],"last":rows[-1]["time"],"cutoff":cut,"receipt_chain_sha256":digest([z["sha"] for z in rows]),"status_counts":dict(counts),"risk":evaluate(examples(rows),cut),"timing":timing(rows,cut),"external_crosscheck":external_crosscheck(rows,ext),"scope":"Trusted internal archive training, external snapshot audit only; no alert selection bias in archive, no proof of complete run history; no external outage claim.","dispatch_authorized":False,"production":False}
    a.out.mkdir(parents=True,exist_ok=True);(a.out/"report.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("BEACON_WITNESS_LEARNING",json.dumps(report,sort_keys=True),flush=True)
if __name__=="__main__":main()
