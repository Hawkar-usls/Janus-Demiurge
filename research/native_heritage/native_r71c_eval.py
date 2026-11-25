from native_r71c_common import *
import native_baseline_r71a as a
import native_r71b_eval as b
def fresh_eval(m,rows,T):
    @torch.inference_mode()
    def answer(r,doc,forced):
        p=T.encode(prompt(r,doc,forced),bos=True);req(len(p)+(0 if forced else 6)<=128,"FIT")
        x=torch.tensor([p]);z,_=m(x)
        if forced:return r["options"][int(z[0,-1,[65,66,67,68]].argmax())]
        out=[]
        for _ in range(6):
            z,_=m(x);n=int(z[0,-1].argmax())
            if n in (10,13,257):break
            if n>=256:return "<invalid>"
            out.append(n);x=torch.cat([x,torch.tensor([[n]])],dim=1)
        return T.decode(out).strip()
    keys=("forced","free","forced_pair","free_pair","forced_no_context","free_no_context")
    groups={g:{k:0 for k in keys} for g in GROUPS}
    for r in rows:
        g=groups[r["group"]]
        for forced,label in ((True,"forced"),(False,"free")):
            orig=answer(r,r["doc"],forced);changed=answer(r,r["other"],forced);nc=answer(r,{},forced)
            g[label]+=int(orig==r["gold"]);g[label+"_pair"]+=int(orig==r["gold"] and changed==r["alt"]);g[label+"_no_context"]+=int(nc==r["gold"])
    return {"n":len(rows),"groups":groups,**{k:sum(v[k] for v in groups.values()) for k in keys}}
def holdout(m,docs):
    vals=[]
    with torch.inference_mode():
        for raw in docs:
            for i in range(0,len(raw)-128,128):
                w=list(raw[i:i+129]);_,loss=m(torch.tensor([w[:-1]]),torch.tensor([w[1:]]));vals.append(float(loss))
    req(bool(vals),"HOLDOUT_WINDOWS");return sum(vals)/len(vals)
def main():
    root,bpool,hist,manifest,candidates,seal,out=sys.argv[1:8]
    tr=read("research/native_heritage/R71C_TRAIN.json");ex=read("research/native_heritage/R71C_EXAM.json");be=read("research/native_heritage/R71B_EXAM.json")
    req(not {s["sha256"] for s in tr["replay"]}&{s["sha256"] for s in ex["historical_holdout"]},"TEXT_SPLIT")
    torch.set_num_threads(2);torch.manual_seed(713)
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);models={"parent":parent}
    for k,v in receipt["variants"].items():
        p=Path(candidates)/(k+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE_PIN")
        x=torch.load(p,map_location="cpu",weights_only=True);req(x["config"]==parent.config.to_dict(),"CONFIG")
        model=Model(parent.config);model.load_state_dict(x["model_state"],strict=True);req(all(bool(v.isfinite().all()) for v in model.state_dict().values()),"FINITE");model.eval();models[k]=model
    olda=a.build(202611242130);oldb=build(be,bpool,exam=True);fresh=new_suite(ex)
    req(len(fresh)==96 and len(olda)==64 and len(oldb)==96,"COUNTS")
    req(all(exact(r,r["doc"])==r["gold"] and exact(r,r["other"])==r["alt"] for r in fresh),"REFERENCE")
    docs=historical(hist,manifest,tr,ex["historical_holdout"],"holdout")
    results={}
    for k,m in models.items():
        results[k]={"fresh":fresh_eval(m,fresh,T),"regression_A":b.evaluate(m,olda,T),"regression_B":b.evaluate(m,oldb,T),"anchor_nll":b.anchor(m,root),"historical_holdout_nll":holdout(m,docs)}
    p=results["parent"]
    req(p["regression_A"]["forced"]==12 and p["regression_B"]["forced"]==20 and p["regression_B"]["free"]==0,"BASELINE_REPRODUCTION")
    gates={}
    for k in receipt["variants"]:
        r=results[k];losses={}
        for s in ("regression_A","regression_B"):
            losses[s]=sum(v[t] and not w[t] for v,w in zip(p[s]["rows"],r[s]["rows"]) for t in ("forced","free","paired_both"))
        f=r["fresh"];fp=p["fresh"]
        gates[k]={"lost":losses,"anchor_delta":r["anchor_nll"]-p["anchor_nll"],"historical_delta":r["historical_holdout_nll"]-p["historical_holdout_nll"],"free_gain":f["free"]-fp["free"],"free_pair_gain":f["free_pair"]-fp["free_pair"],"research_gate":sum(losses.values())==0 and r["anchor_nll"]<=p["anchor_nll"]*1.01 and r["historical_holdout_nll"]<=p["historical_holdout_nll"]*1.01 and f["free"]>fp["free"] and f["free_pair"]>fp["free_pair"] and f["forced_pair"]>=fp["forced_pair"]}
    for r in results.values():
        for s in ("regression_A","regression_B"):r[s].pop("rows")
    report={"schema":"janus.native.r71c.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(fresh)),"deterministic_reference":96,"results":results,"gates":gates,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71C_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
