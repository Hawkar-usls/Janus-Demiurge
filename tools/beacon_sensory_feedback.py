"""Learn only from distinct, independently corroborated completions. Shadow only."""
import argparse, json, hashlib, math, statistics
from pathlib import Path
from datetime import datetime,timezone
from tools.beacon_external_receiver import check,seal,epoch,validate,LINES
SEED="6f26fdfe-b154-8333-b451-e7225e398801"
BASE="d12a1e30ade83063c1eb7e0f52d89cc297926aec50cda1ed2c5e872ded72154d"
SCHEMA="janus.beacon.sensory.feedback.v1"
def initial(base):
    if base["receipt_chain_sha256"]!=BASE or base["production"] is not False or base["dispatch_authorized"] is not False:raise ValueError("BASE")
    lines={}
    for k in LINES:
        v=base["timing"][k]["learned_state"]
        lines[k]={"last":v["last_completion_epoch"],"ema":v["ewma_gap_seconds"],"recent":v["recent_gaps_seconds"],"updates":[],"pending":None,"prospective":[]}
    return seal({"schema":SCHEMA,"base_chain":BASE,"base_checkpoint":base["checkpoint_sha256"],"archive_cutoff":base["last"],"lines":lines,"seen":{},"production":False})
def predictions(v):
    return {"beacon":v["last"]+round(v["ema"]),"last":v["last"]+v["recent"][-1],"mean12":v["last"]+round(statistics.mean(v["recent"]))}
def advance(old,receiver,now):
    s=check(old);r=check(receiver)
    if s["schema"]!=SCHEMA or s["base_chain"]!=BASE or s["production"] is not False or r["schema"]!="janus.beacon.external.receiver.state.v1" or r["production"] is not False:raise ValueError("SCHEMA")
    rows=r["records"]
    if len(rows)>2048 or set(s["seen"])-set(rows):raise ValueError("RECEIVER_HISTORY")
    for k,h in s["seen"].items():
        if rows[k]["mailbox_sha256"]!=h:raise ValueError("IMMUTABLE_CONFLICT")
    # Deep copy verified state, never modify parent.
    s=json.loads(json.dumps(s));fresh=0;learned=0;scored=0;skips=0
    for key,rec in sorted(rows.items(),key=lambda kv:(epoch(kv[1]["observation"]["observed_at_utc"]),kv[0])):
        if key in s["seen"]:continue
        if rec["authority"] is not False:raise ValueError("AUTHORITY")
        x=validate(rec["observation"],key+".json");at=epoch(x["observed_at_utc"])
        if at>now:raise ValueError("FUTURE_OBSERVATION")
        s["seen"][key]=rec["mailbox_sha256"];fresh+=1
        for k,q in rec["crosscheck"].items():
            if k not in LINES:raise ValueError("LINE")
            if q["status"] not in ("CORROBORATED_COMPLETION_ONLY","CORROBORATED_STATUS_SHADOW"):continue
            if x["lines"][k].get("run_id")!=q["run_id"]:raise ValueError("RUN_BINDING")
            t=epoch(q["completed_at"]);v=s["lines"][k]
            if t>at:raise ValueError("FUTURE_COMPLETION")
            # Existing archive already knows every completion at or before its cutoff;
            # do not count old run IDs/late backfill or the manual seed as new knowledge.
            if key==SEED or t<=s["archive_cutoff"] or t<=v["last"] or any(a["run_id"]==q["run_id"] for a in v["updates"]):
                skips+=1;continue
            pred=predictions(v);f=v["pending"]
            if f and t>f["issued"]:
                v["prospective"].append({"forecast":f,"actual":t,"run_id":q["run_id"],"absolute_error_seconds":{m:abs(t-y) for m,y in f["predictions"].items()}})
                scored+=1
            v["pending"]=None
            gap=t-v["last"];before=v["ema"];v["ema"]=.7*before+.3*gap
            v["updates"].append({"external_run_id":key,"run_id":q["run_id"],"completion":t,"observed":at,"importer_receipt_sha256":q["importer_receipt_sha256"],"prior_ema":before,"new_ema":v["ema"],"gap":gap,"retrospective_error_seconds":{m:abs(t-y) for m,y in pred.items()}})
            v["last"]=t;v["recent"]=(v["recent"]+[gap])[-12:];learned+=1
    # Only issue real future forecasts; no backdated score.
    for k,v in s["lines"].items():
        if v["pending"] is None:
            p=predictions(v)
            if all(t>now for t in p.values()):v["pending"]={"issued":now,"predictions":p}
        if len(v["updates"])>2048:raise ValueError("CAPACITY")
    # Candidate hourly sequence, not proof of unattended transport: inbox lacks
    # cryptographic provenance and relay runtime attestation.
    hours=sorted({epoch(q["observation"]["scheduled_for"]) for k,q in rows.items() if k!=SEED})
    streak=best=0;last=None
    for t in hours:
        streak=streak+1 if last is not None and t-last==3600 else 1
        best=max(best,streak);last=t
    out=seal(s)
    stats={}
    for k,v in s["lines"].items():
        n=len(v["prospective"]);mae={m:statistics.mean([z["absolute_error_seconds"][m] for z in v["prospective"]]) if n else None for m in ("beacon","last","mean12")}
        stats[k]={"updates":len(v["updates"]),"prospective_n":n,"mae_seconds":mae,"ema_gap_seconds":v["ema"],"admitted":False}
    report={"schema":"janus.beacon.sensory.feedback.report.v1","state_sha256":out["sha256"],"receiver_state_sha256":receiver["sha256"],"received_total":len(rows),"new_packets":fresh,"new_distinct_completions_learned":learned,"new_prospective_scores":scored,"old_or_duplicate_completions_skipped":skips,"manual_seed_excluded":SEED,"candidate_hourly_streak":best,"automatic_transfer_proof":"REQUIRES_SEPARATE_RELAY_RUN_EVIDENCE","lines":stats,"dispatch_authorized":False,"production":False,"quality_gate":"HOLD"}
    return out,report
def main():
    p=argparse.ArgumentParser();p.add_argument("--receiver",type=Path,required=True);p.add_argument("--base",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--out",type=Path,required=True);a=p.parse_args()
    base=json.loads(a.base.read_text());s=json.loads(a.state.read_text()) if a.state.exists() else initial(base)
    if s["base_checkpoint"]!=base["checkpoint_sha256"]:raise ValueError("BASE_PIN")
    now=datetime.now(timezone.utc).timestamp()
    s,r=advance(s,json.loads(a.receiver.read_text()),now)
    a.out.mkdir(parents=True,exist_ok=True)
    for k,v in (("state",s),("report",r)):(a.out/(k+".json")).write_text(json.dumps(v,sort_keys=True,indent=2)+"\n")
    print("BEACON_SENSORY_FEEDBACK",json.dumps(r,sort_keys=True),flush=True)
if __name__=="__main__":main()
