from native_r71d2_common import *
import native_baseline_r71a as a
import native_r71b_eval as b
import native_r71c_eval as c
import native_r71d_eval as d
def evaluate(m,rows,T):
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
    groups={g:{"n":0} for g in GROUPS};cohorts={k:{"n":0} for k in ("in_range","ood")};items=[]
    for r in rows:
        item={}
        for forced,mode in ((True,"forced"),(False,"free")):
            x=answer(r,r["doc"],forced);y=answer(r,r["other"],forced);null=answer(r,{},forced)
            re=answer(r,dict(reversed(list(r["doc"].items()))),forced);re2=answer(r,dict(reversed(list(r["other"].items()))),forced)
            item.update({mode+"_side_correct":int(x==r["gold"])+int(y==r["alt"]),mode+"_pair":int(x==r["gold"] and y==r["alt"]),mode+"_null_side_correct":int(null==r["gold"])+int(null==r["alt"]),mode+"_reordered_pair":int(re==r["gold"] and re2==r["alt"]),mode+"_changed":int(x!=y)})
        items.append(item)
        for g in (groups[r["group"]],cohorts["ood" if r["ood"] else "in_range"]):
            g["n"]+=1
            for k,v in item.items():g[k]=g.get(k,0)+v
    keys=items[0].keys()
    total={k:sum(i[k] for i in items) for k in keys}
    nonmissing={k:sum(groups[g][k] for g in GROUPS if g!="missing") for k in keys}
    n=sum(groups[g]["n"] for g in GROUPS if g!="missing")
    return {"n":len(rows),"groups":groups,"cohorts":cohorts,**total,"nonmissing_n":n,"nonmissing_free_context_gain":(nonmissing["free_side_correct"]-nonmissing["free_null_side_correct"])/(2*n),"nonmissing_forced_context_gain":(nonmissing["forced_side_correct"]-nonmissing["forced_null_side_correct"])/(2*n)}
def main():
    root,bpool,hist,manifest,candidates,seal,out=sys.argv[1:8]
    tr=read("research/native_heritage/R71D2_TRAIN.json");ex=read("research/native_heritage/R71D2_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json");be=read("research/native_heritage/R71B_EXAM.json");de=read("research/native_heritage/R71D_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT_TENSOR")
    models={"parent":parent};language={"parent":parent}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE_PIN")
        x=torch.load(p,map_location="cpu",weights_only=True);req(x["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(x["random_base"] if name=="random_attention" else parent.state_dict(),strict=True)
        req(frozen_digest(base)==v["base_initial_tensor_sha256"]==v["base_final_tensor_sha256"],"BASE_FROZEN")
        model=RoutedAdapter(base,tr["output_rank"]) if name=="native_output" else AttentionAdapter(base,tr["attention_rank"])
        model.load_adapter(x["adapter"]);model.eval()
        req(all(bool(v.isfinite().all()) for v in model.state_dict().values()),"FINITE")
        models[name]=model;language[name]=base
    fresh=make_suite(ex["seed"],ex["pairs_per_group"],True);req(len(fresh)==192,"FRESH_COUNT")
    olda=a.build(202611242130);oldb=build(be,bpool,exam=True);oldc=new_suite(ce);oldd=fresh_suite(de)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    results={}
    for name,m in models.items():
        lm=language[name];f=evaluate(m,fresh,T)
        exact=False
        if name!="random_attention":
            with torch.inference_mode():
                probes=[torch.tensor([[256,65,66,67]]),torch.tensor([T.encode("JSON: example",bos=True)]),torch.tensor([list(docs[0][:128])])]
                exact=all(torch.equal(parent(p)[0],lm(p)[0]) for p in probes)
            req(exact and frozen_digest(lm)==receipt["parent_tensor_sha256"],"LANGUAGE_BYPASS")
        results[name]={"fresh":f,"regression_A":b.evaluate(m,olda,T),"regression_B":b.evaluate(m,oldb,T),"regression_C":c.fresh_eval(m,oldc,T),"regression_D":d.evaluate_new(m,oldd,T),"language_bypass_exact":exact,"anchor_nll":b.anchor(lm,root),"historical_nll":c.holdout(lm,docs)}
    p=results["parent"];req(p["regression_A"]["forced"]==12 and p["regression_B"]["forced"]==20 and p["regression_C"]["forced"]==24 and p["regression_D"]["forced"]==30,"BASELINE_REPRO")
    gates={}
    for name in receipt["variants"]:
        r=results[name];f=r["fresh"];lost={}
        for s in ("regression_A","regression_B"):
            lost[s]=sum(u[k] and not v[k] for u,v in zip(p[s]["rows"],r[s]["rows"]) for k in ("forced","free","paired_both"))
        gates[name]={"lost_A_B":lost,"language_exact":r["language_bypass_exact"],"context_gain_pass":f["nonmissing_free_context_gain"]>=ex["context_gain_min"],"paired_pass":f["free_pair"]>=ex["free_pair_min"],"research_gate":name!="random_attention" and r["language_bypass_exact"] and f["nonmissing_free_context_gain"]>=ex["context_gain_min"] and f["free_pair"]>=ex["free_pair_min"] and sum(lost.values())==0 and r["regression_C"]["forced"]>=p["regression_C"]["forced"] and r["regression_D"]["forced"]>=p["regression_D"]["forced"]}
    for r in results.values():
        for s in ("regression_A","regression_B"):r[s].pop("rows")
    report={"schema":"janus.native.r71d2.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(fresh)),"results":results,"gates":gates,"explicit_task_route":True,"automatic_router_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D2_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
