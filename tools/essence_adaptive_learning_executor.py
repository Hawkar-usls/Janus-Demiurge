#!/usr/bin/env python3
"""Bounded learned semantic veto research; never a production model promoter."""
import argparse,hashlib,json,math,re
from pathlib import Path
from tools.essence_adaptive_repair_pulse import checked as queue_checked

SCHEMA="janus.essence.adaptive_role_learner.v1"
B=128
LABELS=tuple(range(8,17)) # REQUIRES, PREVENTS, polarity, role direction, HOLD
def seal(x):
    return {**x,"sha256":digest(x)}
def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def check(x):
    body={k:v for k,v in x.items() if k!="sha256"}
    if digest(body)!=x.get("sha256"):raise ValueError("STATE_HASH")
    return body
def read(p):
    if p.is_symlink() or p.stat().st_size>2*1024*1024:raise ValueError("FILE_BOUND")
    return json.loads(p.read_text())
def initial():
    return seal({"schema":SCHEMA,"records":[],"training_rows":[],"attempted_texts":[],"replay_exams":[],"weights":[[0.0]*B for _ in LABELS],"production":False})
def rows(x):
    if not isinstance(x,list) or not 1<=len(x)<=96:raise ValueError("ROW_COUNT")
    seen=set()
    for z in x:
        if set(z)!={"text","y"} or z["y"] not in LABELS or type(z["y"]) is not int:raise ValueError("LABEL")
        t=z["text"]
        if not isinstance(t,str) or not re.fullmatch(r"[a-z0-9 ]{8,180}",t) or t!= " ".join(t.split()) or t.split().count("evone")!=1 or t.split().count("evtwo")!=1 or t in seen:raise ValueError("ROW")
        seen.add(t)
    return x
def features(t):
    w=t.split();keys=["bias"]+[f"{i}:{a}" for i,a in enumerate(w)]+w+[" ".join(w[i:i+2]) for i in range(len(w)-1)]+[" ".join(w[i:i+3]) for i in range(len(w)-2)]
    ix=sorted({int.from_bytes(hashlib.sha256(k.encode()).digest()[:4],"little")%B for k in keys})
    return ix
def probabilities(weights,t):
    ix=features(t);scores=[sum(w[k] for k in ix)/math.sqrt(len(ix)) for w in weights]
    m=max(scores);p=[math.exp(x-m) for x in scores];s=sum(p);return [v/s for v in p]
def predict(weights,t):
    p=probabilities(weights,t);j=max(range(len(p)),key=lambda k:p[k])
    # Fixed prior rule, not selected on held-out exams.
    return LABELS[j] if p[j]>=.65 and j!=len(LABELS)-1 else None
def fit(parent,train):
    # This function receives no exam rows or exam labels.
    w=[r[:] for r in parent]
    for _ in range(120):
        for z in train:
            ix=features(z["text"]);p=probabilities(w,z["text"]);k=LABELS.index(z["y"]);a=.12/math.sqrt(len(ix))
            for j in range(len(LABELS)):
                delta=a*((j==k)-p[j])
                for v in ix:w[j][v]+=delta
    return w
def score(w,exam):
    out=[]
    for z in exam:
        y=predict(w,z["text"])
        out.append({"text":z["text"],"gold":z["y"],"prediction":y,
                    "correct":z["y"]!=16 and y==z["y"],"wrong":z["y"]!=16 and y is not None and y!=z["y"],
                    "unknown_false":z["y"]==16 and y is not None})
    return out
def cycle(state,queue,manifest,bank,exam,pulse_id,run_id):
    s=check(state);q=queue_checked(queue)
    if s["schema"]!=SCHEMA or s["production"] is not False or q.get("schema")!="janus.essence.adaptive_repair.pulse.v1" or q.get("production") is not False:raise ValueError("STATE")
    if manifest.get("schema")!="janus.essence.approved_role_bank.v1" or manifest.get("production") is not False or manifest.get("authorization")!="BOUNDED_RESEARCH_ONLY" or manifest.get("preflight",{}).get("overlap")!=[]:raise ValueError("APPROVAL")
    if not any(r["evidence_sha256"]==manifest["queue_evidence_sha256"] and r["production"] is False for r in q["records"]):raise ValueError("QUEUE_BINDING")
    if manifest["bank_sha256"]!=digest(bank) or manifest["exam_sha256"]!=digest(exam):raise ValueError("DATA_PIN")
    if len(s["records"])>=3:return state,{"status":"THREE_ATTEMPT_BUDGET_HOLD","training_executed":False}
    if any(r["bank_sha256"]==manifest["bank_sha256"] or r["pulse_id"]==pulse_id or r["run_id"]==run_id for r in s["records"]):return state,{"status":"ALREADY_CONSUMED_HOLD","training_executed":False}
    bank=rows(bank);exam=rows(exam)
    b={z["text"] for z in bank};x={z["text"] for z in exam}
    oldb=set(s["attempted_texts"]);oldx={z["text"] for z in s["replay_exams"]}
    forbidden=set(manifest["preflight"]["forbidden_normalized_sha256"])
    if b&x or b&(oldb|oldx) or x&(oldb|oldx) or any(hashlib.sha256(t.encode()).hexdigest() in forbidden for t in b|x):raise ValueError("OVERLAP")
    replay=s["training_rows"]+bank
    if len(replay)>288 or len(s["replay_exams"])+len(exam)>288:raise ValueError("TOTAL_BOUND")
    child=fit(s["weights"],replay)
    # Compare frozen parent and child on the new held-out set and historical exams.
    tests=s["replay_exams"]+exam;before=score(s["weights"],tests);after=score(child,tests)
    lost=sum(a["correct"] and not b["correct"] for a,b in zip(before,after))
    wrong=sum(a["wrong"] for a in after);unknown=sum(a["unknown_false"] for a in after)
    bg=sum(a["correct"] for a in before[-len(exam):]);ag=sum(a["correct"] for a in after[-len(exam):])
    accept=lost==0 and wrong==0 and unknown==0 and ag>bg
    rec={"pulse_id":pulse_id,"run_id":run_id,"parent_state_sha256":state["sha256"],"parent_weights_sha256":digest(s["weights"]),"candidate_weights_sha256":digest(child),"bank_sha256":manifest["bank_sha256"],"exam_sha256":manifest["exam_sha256"],"fresh_parent_correct":bg,"fresh_child_correct":ag,"wrong":wrong,"unknown_false":unknown,"lost":lost,"decision":"SHADOW_ACCEPT" if accept else "ROLLBACK_KEEP_FROZEN","training_executed":True,"production":False}
    # Never adopt candidate weights outside this isolated research verifier.
    nextstate=seal({**s,"records":s["records"]+[rec],"training_rows":replay if accept else s["training_rows"],"attempted_texts":sorted(oldb|b),"replay_exams":tests,"weights":child if accept else s["weights"]})
    return nextstate,rec
FIRST_STEP_STATE="3d73c23772755948bed0b3db30d485ff1c93e8fb4948b172b79a8d7aca7349c0"
FIRST_STEP_WEIGHTS="9bd2a248eaadc7ecf3b6c0565845b773b23cb4f988daafa89640b23d79be07fa"
FIRST_STEP_TEXT="evone is not prevented from proceeding by evtwo"
def verify_first_step(anchor):
    s=check(anchor)
    if anchor["sha256"]!=FIRST_STEP_STATE or digest(s["weights"])!=FIRST_STEP_WEIGHTS or len(s["records"])!=1 or s["records"][0]["decision"]!="SHADOW_ACCEPT" or s["records"][0]["wake_origin"]!="RECOVERY_REPLAY" or s["production"] is not False:
        raise ValueError("FIRST_STEP_ANCHOR")
    if predict(s["weights"],FIRST_STEP_TEXT)!=15 or sum(z["correct"] for z in score(s["weights"],s["replay_exams"]))!=1:raise ValueError("FIRST_STEP_SKILL")
    return s
def verify_transition(parent,child,plan,root):
    a=check(parent);b=check(child);n=len(b["records"])
    if a["schema"]!=SCHEMA or b["schema"]!=SCHEMA or a["production"] is not False or b["production"] is not False or n!=len(a["records"])+1 or not 2<=n<=3 or b["records"][:-1]!=a["records"]:raise ValueError("LINEAGE_PREFIX")
    r=b["records"][-1];m=plan["batches"][n-1]
    if r["parent_state_sha256"]!=parent["sha256"] or r["parent_weights_sha256"]!=digest(a["weights"]) or r["bank_sha256"]!=m["bank_sha256"] or r["exam_sha256"]!=m["exam_sha256"] or r["training_executed"] is not True or r["production"] is not False:raise ValueError("LINEAGE_BINDING")
    if r.get("wake_origin")!="LIVE_PARENT" or r.get("parent_event")!="schedule" or r.get("parent_run_attempt")!=1 or not re.fullmatch(r"[1-9][0-9]{0,19}",str(r.get("parent_job_id",""))) or any(x["pulse_id"]==r["pulse_id"] or x["run_id"]==r["run_id"] for x in a["records"]):raise ValueError("LINEAGE_WAKE")
    bank=rows(read(root/m["id"]/"TRAIN.json"));exam=rows(read(root/m["id"]/"EXAM.json"))
    if digest(bank)!=m["bank_sha256"] or digest(exam)!=m["exam_sha256"]:raise ValueError("LINEAGE_DATA")
    if b["replay_exams"]!=a["replay_exams"]+exam or b["attempted_texts"]!=sorted(set(a["attempted_texts"])|{z["text"] for z in bank}):raise ValueError("LINEAGE_MEMORY")
    accepted=r["decision"]=="SHADOW_ACCEPT"
    if r["decision"] not in ("SHADOW_ACCEPT","ROLLBACK_KEEP_FROZEN"):raise ValueError("LINEAGE_DECISION")
    if b["training_rows"]!=a["training_rows"]+(bank if accepted else []):raise ValueError("LINEAGE_TRAINING")
    if digest(b["weights"])!=(r["candidate_weights_sha256"] if accepted else r["parent_weights_sha256"]):raise ValueError("LINEAGE_WEIGHTS")
    before=score(a["weights"],b["replay_exams"]);after=score(b["weights"],b["replay_exams"])
    old_n=len(a["replay_exams"]);old_before=before[:old_n];old_after=after[:old_n]
    observed={"prior_exam_total":old_n,"prior_parent_correct":sum(z["correct"] for z in old_before),"prior_retained_correct":sum(z["correct"] and q["correct"] for z,q in zip(old_before,old_after)),"prior_lost":sum(z["correct"] and not q["correct"] for z,q in zip(old_before,old_after)),"first_step_prediction":predict(b["weights"],FIRST_STEP_TEXT),"durable_weights_sha256":digest(b["weights"])}
    if r.get("inheritance")!=observed or observed["prior_lost"]!=0 or observed["first_step_prediction"]!=15:raise ValueError("LINEAGE_RETENTION")
    if accepted:
        if r["lost"] or r["wrong"] or r["unknown_false"] or r["fresh_child_correct"]<=r["fresh_parent_correct"] or sum(z["wrong"] for z in after)!=0 or sum(z["unknown_false"] for z in after)!=0 or r["fresh_child_correct"]!=sum(z["correct"] for z in after[old_n:]) or r["fresh_parent_correct"]!=sum(z["correct"] for z in before[old_n:]):raise ValueError("LINEAGE_ADMISSION")
    elif b["weights"]!=a["weights"]:raise ValueError("LINEAGE_ROLLBACK")
    return observed
def verify_lineage(anchor,current,history,plan,root):
    verify_first_step(anchor);s=check(current);n=len(s["records"])
    if not 1<=n<=3:raise ValueError("LINEAGE_COUNT")
    parent=anchor
    for i in range(2,n+1):
        child=read(history/f"attempt-{i:03d}.json")
        verify_transition(parent,child,plan,root);parent=child
    if parent!=current:raise ValueError("LINEAGE_HEAD")
    return {"attempts":n,"accepted_generations":sum(r["decision"]=="SHADOW_ACCEPT" for r in s["records"]),"autonomous_attempts":sum(r.get("parent_event")=="schedule" and r.get("wake_origin")=="LIVE_PARENT" for r in s["records"]),"active_state_sha256":current["sha256"],"active_weights_sha256":digest(s["weights"]),"first_step_prediction":predict(s["weights"],FIRST_STEP_TEXT),"prior_correct":sum(z["correct"] for z in score(s["weights"],s["replay_exams"])),"production":False}

def main():
    p=argparse.ArgumentParser();p.add_argument("--queue",type=Path,required=True);p.add_argument("--state",type=Path,required=True);p.add_argument("--approved",type=Path,required=True);p.add_argument("--pulse-id",required=True);p.add_argument("--run-id",required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--cortex",type=Path,required=True);p.add_argument("--validate-only",action="store_true");p.add_argument("--wake-origin",choices=("LIVE_PARENT","RECOVERY_REPLAY"),default="LIVE_PARENT");p.add_argument("--anchor",type=Path);p.add_argument("--lineage-dir",type=Path);p.add_argument("--parent-job-id");a=p.parse_args()
    if not a.approved.is_file() or not a.queue.is_file():
        print("H38N5_EXECUTOR",json.dumps({"status":"WAIT_APPROVED_BANK_OR_QUEUE","training_executed":False,"production":False}));return
    if not re.fullmatch(r"[1-9][0-9]{0,19}",a.pulse_id) or not re.fullmatch(r"[1-9][0-9]{0,19}",a.run_id):raise ValueError("RUN_ID")
    plan=read(a.approved);old=read(a.state) if a.state.exists() else initial()
    s=check(old)
    if plan.get("schema")!="janus.essence.approved_role_plan.v1" or plan.get("production") is not False or not 1<=len(plan.get("batches",[]))<=3:raise ValueError("PLAN")
    if a.anchor is not None:
        if not a.state.is_file() or a.lineage_dir is None:raise ValueError("DURABLE_LINEAGE_REQUIRED")
        lineage=verify_lineage(read(a.anchor),old,a.lineage_dir,plan,a.approved.parent)
        print("H38N7_PARENT_LINEAGE",json.dumps(lineage,sort_keys=True),flush=True)
        if not a.validate_only and (a.wake_origin!="LIVE_PARENT" or not re.fullmatch(r"[1-9][0-9]{0,19}",a.parent_job_id or "")):raise ValueError("SCHEDULED_PARENT_REQUIRED")
    seen={r["bank_sha256"] for r in s["records"]}
    if len({z["bank_sha256"] for z in plan["batches"]})!=len(plan["batches"]):raise ValueError("DUPLICATE_BANK")
    items=[z for z in plan["batches"] if z["bank_sha256"] not in seen]
    if not items:
        print("H38N5_EXECUTOR",json.dumps({"status":"NO_NEW_APPROVED_BANK_HOLD","training_executed":False,"production":False}));return
    m=dict(items[0]);bid=m["id"]
    queue=read(a.queue);q=queue_checked(queue)
    if queue["sha256"]!=plan["queue_state_sha256"] or len(q["records"])!=1:raise ValueError("QUEUE_STATE_PIN")
    item=q["records"][0]
    if item["run_id"]!=45847415226 or item["memory_sha"]!="8d1e0625ca228dcc6f2370226c167bbaf87382d4f3a5aaddc6db3c2839f6ab1e":raise ValueError("QUEUE_ORIGIN")
    m["queue_evidence_sha256"]=item["evidence_sha256"]
    # Read the actual active Memory Cortex generation, not a registry-only copy.
    root=a.cortex
    ptr=read(root/"CURRENT.json");manifest=read(root/ptr["manifest_path"])
    def cortex_seal(z):
        return hashlib.sha256(json.dumps({k:v for k,v in z.items() if k!="receipt_sha256"},sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    key=plan["active_memory_source_sha256"]
    if ptr["generation"]<7 or ptr["manifest_path"]!=f"generations/{ptr['generation']:06d}.json" or cortex_seal(ptr)!=ptr["receipt_sha256"] or cortex_seal(manifest)!=manifest["receipt_sha256"] or manifest["receipt_sha256"]!=ptr["manifest_sha256"] or manifest["generation"]!=ptr["generation"] or key not in manifest["documents"]:raise ValueError("ACTIVE_MEMORY")
    raw=(root/"objects"/key[:2]/(key[2:]+".txt")).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=key:raise ValueError("MEMORY_BYTES")
    if not re.fullmatch(r"batch-00[1-3]",bid):raise ValueError("BATCH_ID")
    folder=a.approved.parent/bid
    bank=read(folder/"TRAIN.json");exam=read(folder/"EXAM.json")
    if a.validate_only:
        rows(bank);rows(exam)
        if digest(bank)!=m["bank_sha256"] or digest(exam)!=m["exam_sha256"]:raise ValueError("DATA_PIN")
        print("H38N6_RUNTIME_PREFLIGHT",json.dumps({"generation":ptr["generation"],"manifest":ptr["manifest_sha256"],"memory_source_sha256":key,"queue_state_sha256":queue["sha256"],"batch":bid,"training_executed":False,"production":False},sort_keys=True));return
    new,r=cycle(old,queue,m,bank,exam,a.pulse_id,a.run_id)
    if r.get("training_executed"):
        body=check(new);r.update(wake_origin=a.wake_origin,cortex_generation=ptr["generation"],cortex_manifest_sha256=ptr["manifest_sha256"],memory_source_sha256=key,queue_state_sha256=queue["sha256"]);body["records"][-1]=r
        if a.anchor is not None:
            prior=score(s["weights"],s["replay_exams"]);after=score(body["weights"],s["replay_exams"])
            r.update(parent_event="schedule",parent_run_attempt=1,parent_job_id=a.parent_job_id,inheritance={"prior_exam_total":len(prior),"prior_parent_correct":sum(z["correct"] for z in prior),"prior_retained_correct":sum(z["correct"] and q["correct"] for z,q in zip(prior,after)),"prior_lost":sum(z["correct"] and not q["correct"] for z,q in zip(prior,after)),"first_step_prediction":predict(body["weights"],FIRST_STEP_TEXT),"durable_weights_sha256":digest(body["weights"])})
            new=seal(body);verify_transition(old,new,plan,a.approved.parent)
        else:new=seal(body)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(new,sort_keys=True,indent=2)+"\n")
    print("H38N5_EXECUTOR",json.dumps({**r,"state_sha256":new["sha256"],"cycles":len(new["records"]),"production":False},sort_keys=True))
if __name__=="__main__":main()
