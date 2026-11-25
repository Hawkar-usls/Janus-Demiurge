from native_r72b6b_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,folder,out=sys.argv[1:7]
    tr=read("research/native_heritage/R72B6_TRAIN.json");ex=read("research/native_heritage/R72B6_EXAM.json");spec=read("research/native_heritage/R72B6B_PROTOCOL.json")
    ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==tr["parent_tensor_sha256"],"PARENT")
    models=frozen_heads(folder,spec["baseline"]["receipt"],spec["baseline"]["artifacts"],basepin,parent.config.d_model,ScopeHead)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    fresh=fresh_cases();replay=synthetic(True);real,cov=load_rows(ex,registry)
    results={};receipts={};locks={}
    for suite,rows in (("fresh",fresh),("disclosed_b6",replay),("real_role_only",real)):
        b,h=scope_features(parent,rows);y=groups(targets(rows));results[suite]={};receipts[suite]={};locks[suite]={}
        for name,m in models.items():
            with torch.inference_mode():
                l,a,z=m(b,h);e=a.argmax(-1);o=z.argmax(-1);p=compose(e,o);role=l.argmax(-1)
                after_l,after_a,after_z=m(b,h)
            locks[suite][name]=torch.equal(l,after_l) and torch.equal(a,after_a) and torch.equal(z,after_z)
            if suite=="real_role_only":
                results[suite][name]={"role":group_stats(y,role),"scope_not_applied":True};continue
            ge=torch.tensor([r["event"] for r in rows]);go=torch.tensor([r["outcome"] for r in rows])
            rr=[locked_scope(row,int(ee),int(oo)) for row,ee,oo in zip(rows,e,o)]
            ee=torch.tensor([q[0] for q in rr]);oo=torch.tensor([q[1] for q in rr]);pp=compose(ee,oo)
            # Independent rule-only baseline receives no neural fallback.
            rules=[locked_scope(row,-1,-1) for row in rows];re_=torch.tensor([q[0] for q in rules]);ro=torch.tensor([q[1] for q in rules]);rp=compose(re_,ro)
            d={"n":len(rows),"neural":selective_stats(y,p),"guard":selective_stats(y,pp),"rule_only":selective_stats(y,rp),"neural_factor_exact":int(((e==ge)&(o==go)).sum()),"guard_factor_exact":int(((ee==ge)&(oo==go)).sum()),"rule_factor_exact":int(((re_==ge)&(ro==go)).sum()),"routes":dict(collections.Counter(q[2] for q in rr)),"cohorts":{}}
            for c in sorted(set(r["cohort"] for r in rows)):
                ix=[i for i,r in enumerate(rows) if r["cohort"]==c]
                d["cohorts"][c]={"n":len(ix),"neural_factor":int(((e[ix]==ge[ix])&(o[ix]==go[ix])).sum()),"guard_factor":int(((ee[ix]==ge[ix])&(oo[ix]==go[ix])).sum()),"guard_group":selective_stats(y[ix],pp[ix]),"lost_neural_correct":int(((p[ix]==y[ix])&(pp[ix]!=y[ix])).sum())}
            results[suite][name]=d
            receipts[suite][name]=[{"id":row["contrast_id"],"text_sha256":sha(row["value"].encode()),"event":int(a),"outcome":int(z),"route":q[2],"witnesses":q[3],"gold_event":row["event"],"gold_outcome":row["outcome"]} for row,a,z,q in zip(rows,ee,oo,rr)]
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    gates={};g=spec["gates"]
    for name in models:
        f=results["fresh"][name];r=results["disclosed_b6"][name];c=f["cohorts"]
        checks={"locked":all(x[name] for x in locks.values()),"language":before==after,"fresh_factor":f["guard_factor_exact"]/f["n"]>=g["fresh_factor_min"],"fresh_group":f["guard"]["correct"]/f["n"]>=g["fresh_group_min"],"negative":c["negative_result"]["guard_factor"]/c["negative_result"]["n"]>=g["negative_recall_min"],"negated":c["negated_execution"]["guard_factor"]/c["negated_execution"]["n"]>=g["negated_recall_min"],"critical":f["guard"]["critical_as_evidence"]==r["guard"]["critical_as_evidence"]==0,"negative_retained":r["cohorts"]["negative_result"]["lost_neural_correct"]<=g["disclosed_negative_losses_max"]}
        gates[name]={**checks,"narrow_guard_gate":all(checks.values())}
    report={"schema":"janus.native.r72b6b.result.v1","fresh_sha256":sha(canonical(fresh)),"results":results,"gates":gates,"locks":locks,"real_coverage":cov,"language":{"before":before,"after":after},"receipts":receipts,"trained":False,"external_blind":False,"real_scope_validation":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B6B_EXAM "+json.dumps({k:v for k,v in report.items() if k!="receipts"},sort_keys=True))
if __name__=="__main__":main()
