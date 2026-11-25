from native_r72b6_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,candidates,b2folder,b4folder,b5folder,seal,out=sys.argv[1:11]
    tr=read("research/native_heritage/R72B6_TRAIN.json");ex=read("research/native_heritage/R72B6_EXAM.json");old=read("research/native_heritage/R72B5_EXAM.json")
    ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    r=read(Path(candidates)/"RECEIPT.json");pin=r.pop("receipt_sha256")
    req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    req(not set(s["blob"] for s in tr["sources"])&set(s["blob"] for s in ex["sources"]+old["sources"]),"DOCUMENT_SPLIT")
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==tr["parent_tensor_sha256"],"PARENT")
    b2=frozen_heads(b2folder,ex["baseline"]["receipt"],ex["baseline"]["artifacts"],basepin,parent.config.d_model,B2Head)
    b4=frozen_heads(b4folder,ex["baseline_b4"]["receipt"],ex["baseline_b4"]["artifacts"],basepin,parent.config.d_model,B4Head)
    b5=frozen_heads(b5folder,ex["baseline_b5"]["receipt"],ex["baseline_b5"]["artifacts"],basepin,parent.config.d_model,B5Head)
    models=frozen_heads(candidates,seal,{k:v["sha256"] for k,v in r["variants"].items()},basepin,parent.config.d_model,ScopeHead)
    real,cov=load_rows(ex,registry);replay,rcov=load_rows(old,registry);syn=synthetic(True)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    results={};locks={};gates={}
    for suite,rows in (("fresh_real",real),("disclosed_real",replay),("fresh_scope",syn),("disclosed_contrast",b5_synthetic(True))):
        b,h=old_features(parent,rows);sb=torch.cat([b,cue_features(rows)],-1);gb=torch.cat([sb,scope_cues(rows)],-1);xb=torch.cat([gb,scope_vector(rows)],-1);y=targets(rows);gy=groups(y)
        results[suite]={};locks[suite]={}
        for name in models:
            with torch.inference_mode():
                l2=b2[name](b,h);l4=b4[name](sb,h);l5=b5[name](gb,h);rl,el,ol=models[name](xb,h)
                p=rl.argmax(-1);e=el.argmax(-1);o=ol.argmax(-1);z=compose(e,o);op=l5.argmax(-1)
                locks[suite][name]={"b2":torch.equal(l2,b2[name](b,h)),"b4":torch.equal(l4,b4[name](sb,h)),"b5":torch.equal(l5,b5[name](gb,h))}
            d={"b5":group_stats(gy,op),"role":group_stats(gy,p),"composed":selective_stats(gy,z),"role_old_correct_lost":int(((op==gy)&(p!=gy)).sum()),"role_new_correct":int(((op!=gy)&(p==gy)).sum())}
            if suite=="fresh_scope":
                ge=torch.tensor([r["event"] for r in rows]);go=torch.tensor([r["outcome"] for r in rows]);d["factor_exact"]=int(((e==ge)&(o==go)).sum());d["event_exact"]=int((e==ge).sum());d["outcome_exact"]=int((o==go).sum());d["n"]=len(rows)
                d["cohorts"]={}
                for c in sorted(set(r["cohort"] for r in rows)):
                    ix=[i for i,r in enumerate(rows) if r["cohort"]==c]
                    d["cohorts"][c]={"n":len(ix),"factor_exact":int(((e[ix]==ge[ix])&(o[ix]==go[ix])).sum()),"b5":int((op[ix]==gy[ix]).sum()),"role":int((p[ix]==gy[ix]).sum()),"composed":selective_stats(gy[ix],z[ix])}
            results[suite][name]=d
        rule=torch.tensor([rule_scope(row) for row in rows]);rp=compose(rule[:,0],rule[:,1]);results[suite]["scope_rule"]={"composed":selective_stats(gy,rp)}
        if suite=="fresh_scope":results[suite]["scope_rule"]["factor_exact"]=int(((rule[:,0]==ge)&(rule[:,1]==go)).sum())
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    for name in models:
        a=results["fresh_real"][name]["role"];s=results["fresh_scope"][name];g=ex["scope_gates"]
        checks={"locked":all(all(x[name].values()) for x in locks.values()),"language":before==after,"real_macro_f1":a["macro_f1"]>=g["real_macro_f1_min"],"factor_exact":s["factor_exact"]/s["n"]>=g["factor_exact_min"],"negative_result":s["cohorts"]["negative_result"]["factor_exact"]/s["cohorts"]["negative_result"]["n"]>=g["negative_result_min"],"negated_execution":s["cohorts"]["negated_execution"]["factor_exact"]/s["cohorts"]["negated_execution"]["n"]>=g["negated_execution_min"],"contrast_group":s["composed"]["correct"]/s["n"]>=g["contrast_group_min"],"no_critical_as_evidence":a["critical_as_evidence"]==s["composed"]["critical_as_evidence"]==0}
        gates[name]={**checks,"full_gate":all(checks.values())}
    report={"schema":"janus.native.r72b6.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(real+syn)),"coverage":cov,"replay_coverage":rcov,"results":results,"locks":locks,"gates":gates,"language":{"before":before,"after":after},"factor_labels_on_synthetic_only":True,"explicit_composition":True,"abstention_not_correct":True,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B6_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
