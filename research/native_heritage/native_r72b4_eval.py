from native_r72b4_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,candidates,b2folder,b3folder,seal,out=sys.argv[1:10]
    tr=read("research/native_heritage/R72B4_TRAIN.json");ex=read("research/native_heritage/R72B4_EXAM.json");old=read("research/native_heritage/R72B3_EXAM.json")
    ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    r=read(Path(candidates)/"RECEIPT.json");pin=r.pop("receipt_sha256")
    req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    req(not set(s["blob"] for s in tr["sources"])&set(s["blob"] for s in ex["sources"]+old["sources"]),"DOCUMENT_SPLIT")
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==tr["parent_tensor_sha256"],"PARENT")
    b2=frozen_heads(b2folder,ex["baseline"]["receipt"],ex["baseline"]["artifacts"],basepin,parent.config.d_model,B2Head)
    b3=frozen_heads(b3folder,ex["baseline_b3"]["receipt"],ex["baseline_b3"]["artifacts"],basepin,parent.config.d_model,B3Head)
    specialist=frozen_heads(candidates,seal,{k:v["sha256"] for k,v in r["variants"].items()},basepin,parent.config.d_model,Specialist)
    real,cov=load_rows(ex,registry);replay,rcov=load_rows(old,registry);syn=synthetic(True)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    results={};locks={};gates={};predictions={}
    for suite,rows in (("fresh_real",real),("disclosed_regression",replay),("fresh_contrast",syn),("disclosed_contrast",b3_synthetic(True))):
        b,h=old_features(parent,rows);sb=torch.cat([b,cue_features(rows)],-1);y=targets(rows);gy=groups(y)
        results[suite]={};locks[suite]={}
        for name in b2:
            with torch.inference_mode():
                old_logits=b2[name](b,h);rp=old_logits.argmax(-1);p3=b3[name](b,h).argmax(-1);sp=specialist[name](sb,h).argmax(-1)
                # Public field-role endpoint uses frozen B2, independently of specialist.
                new_logits=b2[name](b,h);new_role=new_logits.argmax(-1)
            good=rp==y;lost=good&(new_role!=y)
            locks[suite][name]={"old_exact":int(good.sum()),"locked_exact":int((new_role==y).sum()),"lost_correct":int(lost.sum()),"logits_identical":torch.equal(old_logits,new_logits),"role_override":False}
            s=group_stats(gy,sp)
            if "contrast" in suite:
                ids=collections.defaultdict(list)
                for row,ok in zip(rows,(sp==gy).tolist()):
                    if not row["contrast_id"].startswith("other:"):ids[row["contrast_id"]].append(ok)
                s["triples_exact"]=sum(all(v) for v in ids.values());s["triples_n"]=len(ids)
            results[suite][name]={"locked_role":stats(y,new_role),"b2_group":group_stats(gy,groups(rp)),"b3_group":group_stats(gy,groups(p3)),"specialist":s}
            if suite=="fresh_real":
                predictions[name]=[{"source":row["source"],"path":row["path"],"span":row["span"],"token_sha256":row["token_sha256"],"role":LABELS[a],"group":GROUP_NAMES[z],"gold_role":row["label"]} for row,a,z in zip(rows,new_role.tolist(),sp.tolist())]
        rule=torch.tensor([lexical(row) for row in rows]);results[suite]["lexical"]={"group":group_stats(gy,groups(rule))}
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    for name in specialist:
        real_s=results["fresh_real"][name]["specialist"];syn_s=results["fresh_contrast"][name]["specialist"]
        g=ex["gates"]
        checks={"role_lock":all(x[name]["logits_identical"] and x[name]["lost_correct"]==0 for x in locks.values()),"language":before==after,"real_macro_f1":real_s["macro_f1"]>=g["macro_f1_min"],"critical_recall":all(real_s["by_group"][k]["recall"]>=g["critical_recall_min"] for k in ("epistemic_limit","hypothesis_plan")),"real_no_critical_as_evidence":real_s["critical_as_evidence"]==0,"contrast_no_critical_as_evidence":syn_s["critical_as_evidence"]==0,"contrast_accuracy":syn_s["accuracy"]>=g["contrast_exact_min"]}
        gates[name]={**checks,"full_gate":all(checks.values())}
    report={"schema":"janus.native.r72b4.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(real+syn)),"coverage":cov,"replay_coverage":rcov,"results":results,"role_lock":locks,"gates":gates,"language":{"before":before,"after":after},"predictions":predictions,"separate_output_contracts":True,"explicit_lexical_cues":True,"role_lock_by_construction":True,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B4_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
