from native_r71d3b_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def eval_suite(m,rows,T):
    frames={k:[] for k in ("normal","erased","reordered","spacing","deleted")}
    present=[]
    for i,r in enumerate(rows):
        for target in r["targets"]:
            verb="Locate" if i%2 else "Read";style=i%2
            frames["normal"].append(frame(r["doc"],target,T,verb,style))
            frames["erased"].append(frame(r["doc"],target,T,verb,style,True))
            frames["reordered"].append(frame(dict(reversed(list(r["doc"].items()))),target,T,verb,style))
            frames["spacing"].append(frame(r["doc"],target,T,verb,2))
            frames["deleted"].append(frame({},target,T,verb,style))
            present.append(target in r["doc"])
    pred={}
    for k,fs in frames.items():
        pred[k]=[]
        for i in range(0,len(fs),32):pred[k].extend(predict(m,fs[i:i+32]))
    ok={k:[v==f[4] for v,f in zip(pred[k],fs)] for k,fs in frames.items()}
    def paircount(xs):return sum(xs[i] and xs[i+1] for i in range(0,len(xs),2))
    def hit(k):return sum(v and p for v,p in zip(ok[k],present))
    n=sum(present);copy=0;dup=[]
    for i,r in enumerate(rows):
        if len(set(r["doc"].values()))<len(r["doc"]):dup.append(i)
    for i,f in enumerate(frames["normal"]):
        if present[i]:
            s,e=pred["normal"][i];g,h=f[4]
            copy+=int(s>0 and T.decode(f[0][s:e+1])==T.decode(f[0][g:h+1]))
    return {"pairs":len(rows),"queries":len(present),"present_n":n,"missing_n":len(present)-n,"present_exact":hit("normal"),"exact_pairs":paircount(ok["normal"]),"missing_correct":sum(v and not p for v,p in zip(ok["normal"],present)),"erased_present_exact":hit("erased"),"query_gain":(hit("normal")-hit("erased"))/n,"reordered_pairs":paircount(ok["reordered"]),"spacing_pairs":paircount(ok["spacing"]),"deleted_abstentions":sum(ok["deleted"]),"copy_diagnostic":copy,"duplicate_pairs":len(dup),"duplicate_exact_pairs":sum(ok["normal"][2*i] and ok["normal"][2*i+1] for i in dup),"ood_exact_pairs":sum(ok["normal"][2*i] and ok["normal"][2*i+1] for i,r in enumerate(rows) if r["ood"])}
def main():
    root,hist,manifest,candidates,seal,out=sys.argv[1:7]
    tr=read("research/native_heritage/R71D3B_TRAIN.json");ex=read("research/native_heritage/R71D3B_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT_TENSOR")
    rows=pairs(ex,exam=True);req(len(rows)==256 and all(key_partition(k) for r in rows for k in list(r["doc"])+r["targets"]),"FRESH_KEYS")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    baseline={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    results={}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(obj["random_base"] if name=="random_grounded" else parent.state_dict(),strict=True)
        req(frozen_digest(base)==v["base_initial_tensor_sha256"]==v["base_final_tensor_sha256"],"FROZEN")
        m=GroundedPointer(base,name=="byte_only");m.load_adapter(obj["adapter"]);m.eval()
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE")
        exact=False
        if name!="random_grounded":
            with torch.inference_mode():
                probes=[torch.tensor([[256,65,66,67]]),torch.tensor([list(docs[0][:128])])]
                exact=all(torch.equal(parent(z)[0],base(z)[0]) for z in probes)
            req(exact and frozen_digest(base)==receipt["parent_tensor_sha256"],"LANGUAGE_BYPASS")
        results[name]={"pointer":eval_suite(m,rows,T),"language_bypass_exact":exact,"anchor":b.anchor(base,root),"historical":c.holdout(base,docs)}
    controls=[results[k]["pointer"] for k in ("random_grounded","byte_only")]
    gates={}
    for name,r in results.items():
        f=r["pointer"];acc=f["present_exact"]/f["present_n"]
        checks={"language":r["language_bypass_exact"] and r["anchor"]==baseline["anchor"] and r["historical"]==baseline["historical"],"span":acc>=ex["span_min"],"pair":f["exact_pairs"]/f["pairs"]>=ex["pair_min"],"missing":f["missing_correct"]/f["missing_n"]>=ex["missing_min"],"query_gain":f["query_gain"]>=ex["query_gain_min"],"reorder":f["reordered_pairs"]/f["pairs"]>=ex["reorder_min"],"native_advantage":acc-max(c["present_exact"]/c["present_n"] for c in controls)>=ex["native_advantage_min"]}
        gates[name]={**checks,"research_gate":name=="native_grounded" and all(checks.values())}
    report={"schema":"janus.native.r71d3b.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(rows)),"exact_reference_queries":512,"results":results,"gates":gates,"copy_diagnostic_not_generation":True,"automatic_router_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D3B_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
