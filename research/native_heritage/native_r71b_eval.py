"""Separate evaluation runner, no optimizer."""
from native_r71b_common import *
import native_baseline_r71a as a
def evaluate(m,rows,T):
    @torch.inference_mode()
    def forced(r,d):
        ids=T.encode(prompt(r,d,True),bos=True);req(len(ids)<=128,"FIT")
        z,_=m(torch.tensor([ids]));return r["options"][int(z[0,-1,[65,66,67,68]].argmax())]
    @torch.inference_mode()
    def free(r,d):
        ids=T.encode(prompt(r,d,False),bos=True);req(len(ids)+6<=128,"FIT")
        x=torch.tensor([ids]);out=[]
        for _ in range(6):
            z,_=m(x);n=int(z[0,-1].argmax())
            if n in (10,13,257):break
            if n>=256:return "<invalid>"
            out.append(n);x=torch.cat([x,torch.tensor([[n]])],dim=1)
        return T.decode(out).strip()
    groups={g:{"n":0,"forced":0,"free":0,"no_context":0,"paired_both":0,"paired_n":0} for g in GROUPS}
    rr=[]
    for r in rows:
        f=forced(r,r["doc"]);v=free(r,r["doc"]);z=forced(r,{})
        pair=r["other"] is not None and f==r["gold"] and forced(r,r["other"])==r["alt"]
        row={"forced":f==r["gold"],"free":v==r["gold"],"no_context":z==r["gold"],"paired_both":pair}
        rr.append(row);g=groups[r["group"]];g["n"]+=1;g["paired_n"]+=int(r["other"] is not None)
        for k,val in row.items():g[k]+=int(val)
    return {"groups":groups,"rows":rr,**{k:sum(g[k] for g in groups.values()) for k in ("n","forced","free","no_context","paired_both","paired_n")}}
def anchor(m,root):
    raw=(Path(root)/"janus_model/eval/JANUS_ANCHOR_EVAL-v1.txt").read_bytes();vals=[]
    with torch.inference_mode():
        for i in range(0,len(raw)-128,128):
            w=list(raw[i:i+129]);_,loss=m(torch.tensor([w[:-1]]),torch.tensor([w[1:]]));vals.append(float(loss))
    return sum(vals)/len(vals)
def main():
    root,pool,candidates,seal,out=sys.argv[1:6]
    torch.set_num_threads(2);torch.manual_seed(711)
    tr=read("research/native_heritage/R71B_TRAIN.json");ex=read("research/native_heritage/R71B_EXAM.json")
    req(not {s["blob"] for s in tr["sources"]}&{s["blob"] for s in ex["sources"]},"SPLIT")
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    base,Model,T=load_base(root,tr)
    old=a.build(202611242130);fresh=build(ex,pool,exam=True)
    req(len(fresh)==96 and len(old)==64,"COUNTS")
    models={"parent":base}
    for k,v in receipt["variants"].items():
        path=Path(candidates)/(k+".pt");req(sha(path.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(path,map_location="cpu",weights_only=True);req(obj["config"]==base.config.to_dict(),"CONFIG")
        m=Model(base.config);m.load_state_dict(obj["model_state"],strict=True);m.eval();models[k]=m
    results={k:{"fresh":evaluate(m,fresh,T),"regression":evaluate(m,old,T),"anchor_nll":anchor(m,root)} for k,m in models.items()}
    req(results["parent"]["regression"]["forced"]==12 and results["parent"]["regression"]["free"]==0 and results["parent"]["regression"]["paired_both"]==0,"R71A_REPRODUCTION")
    gates={}
    for k in receipt["variants"]:
        oldp=results["parent"]["regression"]["rows"];oldc=results[k]["regression"]["rows"]
        losses=sum(a1[t] and not b1[t] for a1,b1 in zip(oldp,oldc) for t in ("forced","free","paired_both"))
        fm=results[k]["fresh"];pm=results["parent"]["fresh"]
        gates[k]={"old_item_losses":losses,"fresh_forced_gain":fm["forced"]-pm["forced"],"fresh_free_gain":fm["free"]-pm["free"],"anchor_delta":results[k]["anchor_nll"]-results["parent"]["anchor_nll"],"research_gate":losses==0 and fm["forced"]>pm["forced"] and fm["free"]>pm["free"] and fm["paired_both"]>pm["paired_both"] and results[k]["anchor_nll"]<=results["parent"]["anchor_nll"]*1.01}
    for r in results.values():
        for k in ("fresh","regression"):r[k].pop("rows")
    report={"schema":"janus.native.r71b.result.v1","candidate_receipt":pin,"fresh_suite_sha256":sha(canonical(fresh)),"deterministic_reference":96,"results":results,"gates":gates,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71B_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
