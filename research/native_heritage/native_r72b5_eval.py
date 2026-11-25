from native_r72b5_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,candidates,b2folder,b4folder,seal,out=sys.argv[1:10]
    tr=read("research/native_heritage/R72B5_TRAIN.json");ex=read("research/native_heritage/R72B5_EXAM.json");old=read("research/native_heritage/R72B4_EXAM.json")
    ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    r=read(Path(candidates)/"RECEIPT.json");pin=r.pop("receipt_sha256")
    req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    req(not set(s["blob"] for s in tr["sources"])&set(s["blob"] for s in ex["sources"]+old["sources"]),"DOCUMENT_SPLIT")
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==tr["parent_tensor_sha256"],"PARENT")
    b2=frozen_heads(b2folder,ex["baseline"]["receipt"],ex["baseline"]["artifacts"],basepin,parent.config.d_model,B2Head)
    b4=frozen_heads(b4folder,ex["baseline_b4"]["receipt"],ex["baseline_b4"]["artifacts"],basepin,parent.config.d_model,B4Head)
    guard=frozen_heads(candidates,seal,{k:v["sha256"] for k,v in r["variants"].items()},basepin,parent.config.d_model,Specialist)
    real,cov=load_rows(ex,registry);replay,rcov=load_rows(old,registry);syn=synthetic(True)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    results={};locks={};gates={};predictions={}
    for suite,rows in (("fresh_real",real),("disclosed_real",replay),("fresh_contrast",syn),("disclosed_contrast",b4_synthetic(True))):
        b,h=old_features(parent,rows);sb=torch.cat([b,cue_features(rows)],-1);gb=torch.cat([sb,scope_cues(rows)],-1);y=targets(rows);gy=groups(y)
        results[suite]={};locks[suite]={}
        for name in b2:
            with torch.inference_mode():
                role0=b2[name](b,h);old0=b4[name](sb,h);p=guard[name](gb,h).argmax(-1)
                role1=b2[name](b,h);old1=b4[name](sb,h)
            rp=role0.argmax(-1);op=old0.argmax(-1);sel=guard_decision(op,p)
            locks[suite][name]={"role_logits_exact":torch.equal(role0,role1),"specialist_logits_exact":torch.equal(old0,old1),"lost_role_correct":int(((rp==y)&(role1.argmax(-1)!=y)).sum()),"lost_specialist_correct":int(((op==gy)&(old1.argmax(-1)!=gy)).sum())}
            d={"b4":group_stats(gy,op),"guard":group_stats(gy,p),"selective":selective_stats(gy,sel),"raw_guard_old_correct_lost":int(((op==gy)&(p!=gy)).sum()),"raw_guard_new_correct":int(((op!=gy)&(p==gy)).sum())}
            if suite=="fresh_contrast":
                d["cohorts"]={}
                for cohort in sorted(set(row["cohort"] for row in rows)):
                    ix=[i for i,row in enumerate(rows) if row["cohort"]==cohort]
                    d["cohorts"][cohort]={"b4":group_stats(gy[ix],op[ix]),"guard":group_stats(gy[ix],p[ix]),"selective":selective_stats(gy[ix],sel[ix])}
                families=collections.defaultdict(list)
                for row,ok in zip(rows,(p==gy).tolist()):families[row["family"]].append(ok)
                d["families_all_correct"]=sum(all(v) for v in families.values());d["families_n"]=len(families)
            results[suite][name]=d
            if suite=="fresh_real":
                predictions[name]=[{"source":row["source"],"path":row["path"],"span":row["span"],"token_sha256":row["token_sha256"],"gold_group":GROUP_NAMES[g],"b4":GROUP_NAMES[o],"guard":GROUP_NAMES[z],"selective":GROUP_NAMES[w] if w>=0 else "abstain"} for row,g,o,z,w in zip(rows,gy.tolist(),op.tolist(),p.tolist(),sel.tolist())]
        rule=torch.tensor([lexical(row) for row in rows]);results[suite]["lexical"]={"group":group_stats(gy,groups(rule))}
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    for name in guard:
        a=results["fresh_real"][name]["guard"];s=results["fresh_contrast"][name]["guard"];g=ex["guard_gates"]
        checks={"locked":all(all(v==0 if k.startswith("lost") else v for k,v in x[name].items()) for x in locks.values()),"language":before==after,"real_macro_f1":a["macro_f1"]>=g["real_macro_f1_min"],"critical_recall":all(a["by_group"][k]["recall"]>=g["critical_recall_min"] for k in ("epistemic_limit","hypothesis_plan")),"real_evidence_recall":a["by_group"]["evidence_statement"]["recall"]>=g["evidence_recall_min"],"contrast_accuracy":s["accuracy"]>=g["contrast_accuracy_min"],"no_critical_as_evidence":a["critical_as_evidence"]==s["critical_as_evidence"]==0}
        gates[name]={**checks,"full_gate":all(checks.values())}
    report={"schema":"janus.native.r72b5.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(real+syn)),"coverage":cov,"replay_coverage":rcov,"results":results,"locks":locks,"gates":gates,"language":{"before":before,"after":after},"predictions":predictions,"separate_output_contracts":True,"abstention_not_correct":True,"explicit_scope_cues":True,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B5_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
