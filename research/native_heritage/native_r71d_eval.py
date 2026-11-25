from native_r71d_common import *
import native_baseline_r71a as a
import native_r71b_eval as b
import native_r71c_eval as c
def evaluate_new(m,rows,T):
    @torch.inference_mode()
    def answer(r,doc,forced):
        p=T.encode(prompt(r,doc,forced),bos=True);req(len(p)+(0 if forced else 6)<=128,"FIT");x=torch.tensor([p])
        if forced:
            z,_=m(x);return r["options"][int(z[0,-1,[65,66,67,68]].argmax())]
        out=[]
        for _ in range(6):
            z,_=m(x);n=int(z[0,-1].argmax())
            if n in (10,13,257):break
            if n>=256:return "<invalid>"
            out.append(n);x=torch.cat([x,torch.tensor([[n]])],dim=1)
        return T.decode(out).strip()
    metrics={g:{} for g in GROUPS}
    for r in rows:
        d=metrics[r["group"]]
        for forced,mode in ((True,"forced"),(False,"free")):
            orig=answer(r,r["doc"],forced);alt=answer(r,r["other"],forced)
            null=answer(r,{},forced);reorder=answer(r,dict(reversed(list(r["doc"].items()))),forced)
            for suffix,v in (("",orig==r["gold"]),("_changed",alt==r["alt"]),("_pair",orig==r["gold"] and alt==r["alt"]),("_no_context",null==r["gold"]),("_reordered",reorder==r["gold"])):
                key=mode+suffix;d[key]=d.get(key,0)+int(v)
    return {"n":len(rows),"groups":metrics,**{k:sum(d[k] for d in metrics.values()) for k in next(iter(metrics.values()))}}
def main():
    root,bpool,hist,manifest,candidates,seal,out=sys.argv[1:8]
    tr=read("research/native_heritage/R71D_TRAIN.json");ex=read("research/native_heritage/R71D_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json");be=read("research/native_heritage/R71B_EXAM.json")
    req(not {s["sha256"] for s in ct["replay"]}&{s["sha256"] for s in ce["historical_holdout"]},"TEXT_SPLIT")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT_TENSOR_PIN")
    models={"parent":parent};language={"parent":parent}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE_PIN")
        x=torch.load(p,map_location="cpu",weights_only=True);req(x["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config)
        if x["kind"]=="full":
            base.load_state_dict(x["model_state"],strict=True);m=base
        else:
            base.load_state_dict(x["random_base"] if name=="random_adapter" else parent.state_dict(),strict=True)
            req(frozen_digest(base)==v["base_initial_tensor_sha256"]==v["base_final_tensor_sha256"],"FROZEN_ADAPTER_BASE")
            m=RoutedAdapter(base,tr["adapter_rank"]);m.load_adapter(x["adapter"])
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE");m.eval()
        models[name]=m;language[name]=base
    olda=a.build(202611242130);oldb=build(be,bpool,exam=True);oldc=new_suite(ce);fresh=fresh_suite(ex)
    req(len(fresh)==128 and len(oldc)==96 and all(exact_new(r,r["doc"])==r["gold"] and exact_new(r,r["other"])==r["alt"] for r in fresh),"FRESH_REFERENCE")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    results={}
    for name,m in models.items():
        lm=language[name]
        results[name]={"fresh":evaluate_new(m,fresh,T),"regression_A":b.evaluate(m,olda,T),"regression_B":b.evaluate(m,oldb,T),"regression_C":c.fresh_eval(m,oldc,T),"language_routed_anchor_nll":b.anchor(lm,root),"language_routed_historical_nll":c.holdout(lm,docs),"task_mode_anchor_nll":b.anchor(m,root)}
        if name=="native_adapter":
            probe=torch.tensor([[256,65,66,67]])
            with torch.inference_mode():
                req(torch.equal(parent(probe)[0],lm(probe)[0]),"BYPASS_LOGITS")
    p=results["parent"];req(p["regression_A"]["forced"]==12 and p["regression_B"]["forced"]==20 and p["regression_C"]["forced"]==24,"BASELINE_REPRO")
    gates={}
    for name in receipt["variants"]:
        r=results[name];lost={}
        for s in ("regression_A","regression_B"):
            lost[s]=sum(u[k] and not v[k] for u,v in zip(p[s]["rows"],r[s]["rows"]) for k in ("forced","free","paired_both"))
        f=r["fresh"];fp=p["fresh"]
        lang=r["language_routed_anchor_nll"]<=p["language_routed_anchor_nll"]*1.01 and r["language_routed_historical_nll"]<=p["language_routed_historical_nll"]*1.01
        gates[name]={"lost_A_B":lost,"language_gate":lang,"fresh_free_gain":f["free"]-fp["free"],"fresh_free_pairs":f["free_pair"],"fresh_forced_pairs":f["forced_pair"],"research_gate":name!="random_adapter" and lang and sum(lost.values())==0 and r["regression_C"]["forced"]>=p["regression_C"]["forced"] and f["free"]>max(fp["free"],f["free_no_context"]) and f["free_pair"]>fp["free_pair"]}
    for r in results.values():
        for s in ("regression_A","regression_B"):r[s].pop("rows")
    report={"schema":"janus.native.r71d.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(fresh)),"deterministic_reference":128,"results":results,"gates":gates,"explicit_task_route":True,"automatic_router_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
