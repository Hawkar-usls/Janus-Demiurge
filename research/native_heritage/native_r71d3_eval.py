from native_r71d3_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def evaluate(m,rows,T):
    buckets={k:[] for k in ("normal","erased_query","reordered","deleted")}
    present=[]
    for r in rows:
        for target in r["targets"]:
            buckets["normal"].append(render(r["doc"],target,r["verb"],T))
            buckets["erased_query"].append(render(r["doc"],target,r["verb"],T,erase=True))
            buckets["reordered"].append(render(dict(reversed(list(r["doc"].items()))),target,r["verb"],T))
            buckets["deleted"].append(render({},target,r["verb"],T))
            present.append(target in r["doc"])
    preds={}
    for name,frames in buckets.items():
        preds[name]=[]
        for i in range(0,len(frames),32):preds[name].extend(predict(m,frames[i:i+32]))
    scores={name:[x==f[3] for x,f in zip(preds[name],frames)] for name,frames in buckets.items()}
    start_correct=sum(x[0]==f[3][0] for x,f in zip(preds["normal"],buckets["normal"]))
    end_correct=sum(x[1]==f[3][1] for x,f in zip(preds["normal"],buckets["normal"]))
    present_n=sum(present);missing_n=len(present)-present_n
    def pairs(s):return sum(s[i] and s[i+1] for i in range(0,len(s),2))
    def present_hits(name):return sum(ok and p for ok,p in zip(scores[name],present))
    duplicate_indices=[i for i,r in enumerate(rows) if len(set(r["doc"].values()))<len(r["doc"])]
    copy_hits=0
    for i,f in enumerate(buckets["normal"]):
        if present[i]:
            s,e=preds["normal"][i]
            copy_hits+=int(s>0 and T.decode(f[0][s:e+1])==T.decode(f[0][f[3][0]:f[3][1]+1]))
    cohorts={}
    for label,flag in (("in_range",False),("ood",True)):
        ix=[i for i,r in enumerate(rows) if r["ood"]==flag]
        cohorts[label]={"pairs":len(ix),"exact_pairs":sum(scores["normal"][2*i] and scores["normal"][2*i+1] for i in ix)}
    return {"pairs":len(rows),"queries":len(present),"present_n":present_n,"missing_n":missing_n,"exact_spans":sum(scores["normal"]),"start_correct":start_correct,"end_correct":end_correct,"present_exact":present_hits("normal"),"missing_correct":sum(ok and not p for ok,p in zip(scores["normal"],present)),"exact_pairs":pairs(scores["normal"]),"erased_query_present_exact":present_hits("erased_query"),"erased_query_pairs":pairs(scores["erased_query"]),"reordered_pairs":pairs(scores["reordered"]),"deleted_context_abstentions":sum(scores["deleted"]),"copy_diagnostic_present":copy_hits,"duplicate_value_pairs":len(duplicate_indices),"duplicate_value_exact_pairs":sum(scores["normal"][2*i] and scores["normal"][2*i+1] for i in duplicate_indices),"cohorts":cohorts,"present_query_gain":(present_hits("normal")-present_hits("erased_query"))/present_n}
def main():
    root,hist,manifest,candidates,seal,out=sys.argv[1:7]
    tr=read("research/native_heritage/R71D3_TRAIN.json");ex=read("research/native_heritage/R71D3_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT_PIN")
    rows=make_pairs(ex,exam=True);req(len(rows)==256 and all(not r["archive"] for r in rows),"EXAM_COUNT")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    parent_language={"anchor_nll":b.anchor(parent,root),"historical_nll":c.holdout(parent,docs)}
    results={}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE_PIN")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(obj["random_base"] if name=="random_attention_pointer" else parent.state_dict(),strict=True)
        req(frozen_digest(base)==v["base_initial_tensor_sha256"]==v["base_final_tensor_sha256"],"FROZEN_BASE")
        m=SpanPointer(base,obj["rank"],tr["pointer_dim"]);m.load_adapter(obj["adapter"]);m.eval()
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE")
        exact=False
        if name!="random_attention_pointer":
            probes=[torch.tensor([[256,65,66,67]]),torch.tensor([T.encode("JSON: example",bos=True)]),torch.tensor([list(docs[0][:128])])]
            with torch.inference_mode():exact=all(torch.equal(parent(z)[0],base(z)[0]) for z in probes)
            req(exact and frozen_digest(base)==receipt["parent_tensor_sha256"],"LANGUAGE_BYPASS")
        results[name]={"pointer":evaluate(m,rows,T),"language_bypass_exact":exact,"anchor_nll":b.anchor(base,root),"historical_nll":c.holdout(base,docs),"base_frozen":True}
    rand=results["random_attention_pointer"]["pointer"];gates={}
    for name,r in results.items():
        f=r["pointer"];accuracy=f["present_exact"]/f["present_n"];random_accuracy=rand["present_exact"]/rand["present_n"]
        tests={"language":r["language_bypass_exact"] and r["anchor_nll"]==parent_language["anchor_nll"] and r["historical_nll"]==parent_language["historical_nll"],"present":accuracy>=ex["present_span_min"],"pairs":f["exact_pairs"]/f["pairs"]>=ex["pair_min"],"query_gain":f["present_query_gain"]>=ex["query_gain_min"],"vs_random":accuracy-random_accuracy>=ex["native_vs_random_min"],"missing":f["missing_correct"]/f["missing_n"]>=ex["missing_accuracy_min"],"reordered":f["reordered_pairs"]/f["pairs"]>=ex["reordered_pair_min"]}
        gates[name]={**tests,"research_gate":name!="random_attention_pointer" and all(tests.values())}
    report={"schema":"janus.native.r71d3.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(rows)),"exact_reference_queries":512,"parent_language":parent_language,"results":results,"gates":gates,"copy_is_diagnostic_not_generation":True,"explicit_pointer_route":True,"automatic_router_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D3_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
