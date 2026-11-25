from native_r71d5_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def evidence(rows,pointer,copier,T,variant,reverse=False):
    frames=[]
    for r in rows:
        doc=r[variant]
        if reverse:doc=dict(reversed(list(doc.items())))
        for k in r["keys"]:frames.append(pointer_module.frame(doc,k,T,"Locate",4))
    results=[]
    for i in range(0,len(frames),32):results.extend(run_batch(pointer,copier,frames[i:i+32],T,True))
    out=[]
    for i in range(0,len(frames),2):
        vals=[];exact=[];accepted=[]
        for f,z in zip(frames[i:i+2],results[i:i+2]):
            # Reject invalid operand syntax and failed byte-copy provenance;
            # cannot certify that the pointer selected the requested key.
            s=z["output"];valid=z["accepted"] and (z["span"]==(0,0) or (1<=len(s)<=5 and s.isascii() and s.isdigit()))
            vals.append(s if valid and z["span"]!=(0,0) else None)
            exact.append(valid and z["span"]==f[4])
            accepted.append(valid)
        out.append({"values":vals,"source_exact":all(exact),"valid":all(accepted)})
    return out
def evaluate(model,rows,ev,variant):
    values=[];dirs=[];gold=[];source=[];valid=[];cohort=[]
    for r,e in zip(rows,ev):
        target=values_of(r[variant],r["keys"])
        for d in (False,True):
            values.append(e["values"]);dirs.append(d);gold.append(compose(target,reference(target,d)))
            source.append(e["source_exact"]);valid.append(e["valid"]);cohort.append(r)
    predicted=[]
    for i in range(0,len(values),128):
        predicted.extend(predict_order(model,values[i:i+128],dirs[i:i+128]))
    hits=[];wrong=0;missing=0;missing_ok=0;ood=0;ood_ok=0;order_correct=0;oracle_ref=0;false_abstain=0
    for v,d,g,p,s,ok,r in zip(values,dirs,gold,predicted,source,valid,cohort):
        answer=compose(v,p) if ok else None
        right=ok and s and answer==g
        hits.append(right);wrong+=int(answer is not None and not right)
        order_correct+=int(p==reference(v,d))
        oracle_ref+=int(ok and s and compose(v,reference(v,d))==g)
        if g is None:missing+=1;missing_ok+=int(right)
        else:false_abstain+=int(answer is None)
        if r["ood"]:ood+=1;ood_ok+=int(right)
    return {"n":len(hits),"exact":sum(hits),"source_exact":sum(source),"neural_order_correct":order_correct,"deterministic_on_same_evidence":oracle_ref,"wrong_accepted":wrong,"false_abstain":false_abstain,"missing_n":missing,"missing_correct":missing_ok,"ood_n":ood,"ood_exact":ood_ok,"both_directions":sum(hits[i] and hits[i+1] for i in range(0,len(hits),2))},hits
def main():
    root,hist,manifest,candidates,pfolder,cfolder,seal,out=sys.argv[1:9]
    tr=read("research/native_heritage/R71D5_TRAIN.json");ex=read("research/native_heritage/R71D5_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"]==ex["parent_tensor_sha256"],"PARENT")
    pobj,pr=sealed(pfolder,ex["pointer"],"native_grounded");cobj,cr=sealed(cfolder,ex["copy"],"byte_relative")
    req(pr["parent_tensor_sha256"]==cr["parent_tensor_sha256"]==receipt["parent_tensor_sha256"],"LINEAGE")
    req(pobj["config"]==cobj["config"]==parent.config.to_dict() and cobj["byte_only"] and cobj["relative"],"CONFIG")
    pointer=pointer_module.GroundedPointer(parent,False,True);pointer.load_adapter(pobj["adapter"]);pointer.eval()
    copier=copy_module.InvariantCopy(parent,True,True);copier.load_adapter(cobj["adapter"]);copier.eval()
    rows=make_cases(ex,True);req(len(rows)==512,"EXAM_COUNT")
    evidence_sets={}
    for variant in ("doc","changed"):
        evidence_sets["oracle_"+variant]=[{"values":values_of(r[variant],r["keys"]),"source_exact":True,"valid":True} for r in rows]
        evidence_sets["predicted_"+variant]=evidence(rows,pointer,copier,T,variant)
        evidence_sets["reordered_"+variant]=evidence(rows,pointer,copier,T,variant,True)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");baseline={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    results={};gates={}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(parent.state_dict(),strict=True);req(frozen_digest(base)==v["base_tensor_sha256"]==receipt["parent_tensor_sha256"],"BASE")
        m=ComposeHead(base,name=="byte_compose");m.load_adapter(obj["adapter"]);m.eval()
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE")
        with torch.inference_mode():
            probe=torch.tensor([[256,65,66,67]]);exact=torch.equal(parent(probe)[0],base(probe)[0])
        lang={"anchor":b.anchor(base,root),"historical":c.holdout(base,docs)}
        scores={};hits={}
        for k,e in evidence_sets.items():
            scores[k],hits[k]=evaluate(m,rows,e,k.rsplit("_",1)[1])
        both={route:sum(a and b for a,b in zip(hits[route+"_doc"],hits[route+"_changed"])) for route in ("oracle","predicted","reordered")}
        checks={"language":exact and lang==baseline}
        for k,s in scores.items():
            oracle=k.startswith("oracle")
            checks[k+"_exact"]=s["exact"]/s["n"]>=(ex["oracle_min"] if oracle else ex["full_min"])
            checks[k+"_ood"]=s["ood_exact"]/s["ood_n"]>=ex["ood_min"]
            checks[k+"_missing"]=s["missing_n"]==0 or s["missing_correct"]/s["missing_n"]>=ex["missing_min"]
            checks[k+"_no_wrong"]=s["wrong_accepted"]<=ex["wrong_accepted_max"]
        for route,n in both.items():checks[route+"_counterfactual"]=n/1024>=ex["pair_min"]
        results[name]={"scores":scores,"both_original_changed":both,"language":lang,"language_exact":exact}
        gates[name]={**checks,"isolated_gate":all(v for k,v in checks.items() if k=="language" or k.startswith("oracle")),"end_to_end_gate":all(checks.values())}
    req(frozen_digest(parent)==ex["parent_tensor_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d5.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(rows)),"pointer_receipt":ex["pointer"]["receipt"],"copy_receipt":ex["copy"]["receipt"],"results":results,"gates":gates,"explicit_operand_slots":True,"arithmetic_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D5_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
