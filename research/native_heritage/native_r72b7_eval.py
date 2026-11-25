from native_r72b7_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,folder,oldfolder,seal,out=sys.argv[1:8]
    spec=read("research/native_heritage/R72B7_PROTOCOL.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(spec["seed"])
    r=read(Path(folder)/"RECEIPT.json");pin=r.pop("receipt_sha256");req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(spec)),"SEAL")
    parent,_,_=load_base(root,spec);parent.eval();basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==spec["parent_tensor_sha256"],"PARENT")
    models=frozen_heads(folder,seal,{k:v["sha256"] for k,v in r["variants"].items()},basepin,parent.config.d_model,Student)
    prior=frozen_heads(oldfolder,spec["baseline"]["receipt"],spec["baseline"]["artifacts"],basepin,parent.config.d_model,ScopeHead)
    fresh=new_exam();replay=b6_cases(True);replay2=b6b_cases()
    train_hash=set(r["train_text_sha256"]);req(not train_hash&{sha(row["value"].encode()) for row in fresh+replay+replay2},"TEXT_OVERLAP")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    results={};predictions={};locks={}
    def score(rows,ge,go,e,o):
        y=compose(ge,go);p=compose(e,o)
        d={"n":len(rows),"event_exact":int((e==ge).sum()),"outcome_exact":int((o==go).sum()),"factor_exact":int(((e==ge)&(o==go)).sum()),"group":selective_stats(y,p),"cohorts":{}}
        for c in sorted(set(row["cohort"] for row in rows)):
            ix=[i for i,row in enumerate(rows) if row["cohort"]==c]
            d["cohorts"][c]={"n":len(ix),"factor_exact":int(((e[ix]==ge[ix])&(o[ix]==go[ix])).sum()),"group":selective_stats(y[ix],p[ix])}
        return d
    for suite,rows in (("fresh",fresh),("disclosed_b6",replay),("disclosed_b6b",replay2)):
        ge=torch.tensor([row["event"] for row in rows]);go=torch.tensor([row["outcome"] for row in rows]);y=compose(ge,go)
        x,mask,n=raw_features(parent,rows);b,h=scope_features(parent,rows)
        results[suite]={};locks[suite]={};predictions[suite]={}
        for name,m in models.items():
            e,o=predict_student(m,x,mask,n)
            with torch.inference_mode():
                l,a,z=prior[name](b,h);l2,a2,z2=prior[name](b,h)
            pe=a.argmax(-1);po=z.argmax(-1);p=compose(e,o);oldp=compose(pe,po)
            locks[suite][name]=torch.equal(l,l2) and torch.equal(a,a2) and torch.equal(z,z2)
            results[suite][name]={"student":score(rows,ge,go,e,o),"b6":score(rows,ge,go,pe,po),"old_group_correct_lost":int(((oldp==y)&(p!=y)).sum()),"new_group_correct":int(((oldp!=y)&(p==y)).sum())}
            predictions[suite][name]=[{"id":row["contrast_id"],"text_sha256":sha(row["value"].encode()),"event":int(a),"outcome":int(b),"gold_event":row["event"],"gold_outcome":row["outcome"]} for row,a,b in zip(rows,e,o)]
        # Teacher runs only after student predictions have been collected.
        t=[locked_scope(row,-1,-1) for row in rows];te=torch.tensor([q[0] for q in t]);to=torch.tensor([q[1] for q in t]);results[suite]["teacher"]=score(rows,ge,go,te,to)
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==spec["parent_sha256"],"PARENT_CHANGED")
    gates={};g=spec["gates"]
    for name in models:
        f=results["fresh"][name]["student"];c=f["cohorts"]
        checks={"locked":all(s[name] for s in locks.values()),"language":before==after,"factor":f["factor_exact"]/f["n"]>=g["fresh_factor_min"],"group":f["group"]["correct"]/f["n"]>=g["fresh_group_min"],"negative":c["negative_result"]["factor_exact"]/c["negative_result"]["n"]>=g["negative_min"],"negated":c["negated_execution"]["factor_exact"]/c["negated_execution"]["n"]>=g["negated_min"],"critical":all(results[k][name]["student"]["group"]["critical_as_evidence"]<=g["critical_max"] for k in results),"old_retention":all(results[k][name]["old_group_correct_lost"]<=g["old_correct_losses_max"] for k in ("disclosed_b6","disclosed_b6b"))}
        gates[name]={**checks,"student_gate":all(checks.values())}
    f=results["fresh"];gates["native_advantage"]=((f["native_semantics"]["student"]["factor_exact"]-f["byte_semantics"]["student"]["factor_exact"])/len(fresh)>=g["native_advantage_min"])
    report={"schema":"janus.native.r72b7.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(fresh)),"results":results,"gates":gates,"locks":locks,"language":{"before":before,"after":after},"predictions":predictions,"teacher_at_inference":False,"explicit_rule_features_in_student":False,"external_blind":False,"real_scope_validation":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B7_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
