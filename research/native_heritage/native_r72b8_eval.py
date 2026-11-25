from native_r72b8_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,folder,oldfolder,seal,out=sys.argv[1:9]
    tr=read("research/native_heritage/R72B8_TRAIN.json");ex=read("research/native_heritage/R72B8_EXAM.json");old=read("research/native_heritage/R72B7B_PROTOCOL.json")
    ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    r=read(Path(folder)/"RECEIPT.json");pin=r.pop("receipt_sha256");req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    req(not set(s["blob"] for s in tr["sources"])&set(s["blob"] for s in ex["sources"]+old["sources"]),"DOC_SPLIT")
    parent,_,_=load_base(root,tr);parent.eval();basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==tr["parent_tensor_sha256"],"PARENT")
    models=frozen_heads(folder,seal,{k:v["sha256"] for k,v in r["variants"].items()},basepin,parent.config.d_model,Student)
    prior=frozen_heads(oldfolder,tr["baseline"]["receipt"],tr["baseline"]["artifacts"],basepin,parent.config.d_model,Student)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    results={};locks={};predictions={}
    for suite,rows in (("fresh_real",registry_rows(ex,registry)),("disclosed_real",registry_rows(old,registry)),("disclosed_b7",new_exam()),("disclosed_b6",b6_cases(True)),("disclosed_b6b",b6b_cases())):
        req(not set(r["train_text_sha256"])&{sha(row["value"].encode()) for row in rows},"TRAIN_OVERLAP")
        x,mask,n=raw_features(parent,rows);ge,go=labels(rows);y=compose(ge,go);known=ge>=0
        results[suite]={};locks[suite]={};predictions[suite]={}
        for base,m in prior.items():
            pe,po=predict_student(m,x,mask,n);pp=compose(pe,po);results[suite][base+"_baseline"]=score(rows,pe,po)
            for mode in ("grounded","replay_only"):
                name=base+"_"+mode;e,o=predict_student(models[name],x,mask,n);p=compose(e,o);d=score(rows,e,o)
                d["old_group_correct_lost"]=int(((pp==y)&(p!=y)&known).sum());d["new_group_correct"]=int(((pp!=y)&(p==y)&known).sum())
                d["old_factor_correct_lost"]=int(((pe==ge)&(po==go)&~((e==ge)&(o==go))&known).sum());results[suite][name]=d
                predictions[suite][name]=[{"source":row["source"],"path":row["path"],"sha256":sha(row["value"].encode()),"event":int(a),"outcome":int(b),"gold_event":row["event"],"gold_outcome":row["outcome"]} for row,a,b in zip(rows,e,o)]
            ee,oo=predict_student(m,x,mask,n);locks[suite][base]=torch.equal(pe,ee) and torch.equal(po,oo)
        t=[locked_scope(row,-1,-1) for row in rows];results[suite]["teacher"]=score(rows,torch.tensor([q[0] for q in t]),torch.tensor([q[1] for q in t]))
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    gates={};g=ex["gates"]
    for base in prior:
        name=base+"_grounded";d=results["fresh_real"][name];c=d["cohorts"];replay=results["fresh_real"][base+"_replay_only"]
        checks={"locked":all(x[base] for x in locks.values()),"language":before==after,"factor":d["factor_exact"]/d["n"]>=g["factor_min"],"group":d["group"]["correct"]/d["n"]>=g["group_min"],"negative":c["negative_result"]["factor_exact"]/c["negative_result"]["n"]>=g["negative_min"],"negated":c["negated_execution"]["factor_exact"]/c["negated_execution"]["n"]>=g["negated_min"],"critical":all(x[name]["group"]["critical_as_evidence"]<=g["critical_max"] for x in results.values()),"retention":all(x[name]["old_group_correct_lost"]<=g["old_correct_losses_max"] for k,x in results.items() if k.startswith("disclosed")),"grounding_gain_vs_replay":d["factor_exact"]>replay["factor_exact"] and d["group"]["correct"]>replay["group"]["correct"]}
        gates[name]={**checks,"pilot_gate":all(checks.values())}
    report={"schema":"janus.native.r72b8.result.v1","candidate_receipt":pin,"results":results,"gates":gates,"locks":locks,"language":{"before":before,"after":after},"predictions":predictions,"manual_selected_pilot":True,"external_blind":False,"native_pretraining_overlap_unknown":True,"teacher_at_student_inference":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B8_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
