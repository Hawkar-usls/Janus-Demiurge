from native_r71d4_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def evaluate(m,pointer,rows,T):
    suites={k:[] for k in ("normal","mixed","deleted")}
    for i,r in enumerate(rows):
        for target in r["targets"]:
            verb="Read" if i%2 else "Locate"
            suites["normal"].append(frame(r["doc"],target,T,verb,(i//32)%2))
            suites["mixed"].append(frame(r["doc"],target,T,verb,4))
            suites["deleted"].append(frame({},target,T,verb,4))
    report={}
    for name,fs in suites.items():
        for route in ("oracle","raw","normalized"):
            spans=[]
            for i in range(0,len(fs),32):
                f=fs[i:i+32]
                if route=="oracle":spans.extend(v[4] for v in f)
                elif route=="raw":spans.extend(predict(pointer,f))
                else:
                    n,maps=zip(*(normalize(v,T) for v in f));ps=predict(pointer,list(n))
                    spans.extend((0,0) if s==0 else (mp[s],mp[e]) for (s,e),mp in zip(ps,maps))
            outputs=[]
            for i in range(0,len(fs),32):outputs.extend(copy_decode(m,fs[i:i+32],spans[i:i+32],T))
            correct=guarded=guard_rejected=literal_correct=missing_correct=present_n=missing_n=source_match=0
            for f,sp,(out,terminated) in zip(fs,spans,outputs):
                gold=literal(f,f[4],T);evidence=literal(f,sp,T)
                match=terminated and out==evidence
                source_match+=int(match);literal_correct+=int(sp==f[4])
                correct+=int(terminated and out==gold and sp==f[4])
                guard_rejected+=int(not match)
                guarded+=int(match and out==gold and sp==f[4])
                if f[4][0]==0:missing_n+=1;missing_correct+=int(sp==(0,0) and terminated and out=="")
                else:present_n+=1
            report[name+"_"+route]={"n":len(fs),"present_n":present_n,"missing_n":missing_n,"exact_evidence":literal_correct,"neural_exact":correct,"source_match":source_match,"guarded_exact":guarded,"guard_rejected":guard_rejected,"missing_correct":missing_correct}
    return report
def main():
    root,hist,manifest,candidates,prior,seal,out=sys.argv[1:8]
    tr=read("research/native_heritage/R71D4_TRAIN.json");ex=read("research/native_heritage/R71D4_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT")
    pr=read(Path(prior)/"RECEIPT.json");pp=pr.pop("receipt_sha256")
    req(pp==ex["pointer_receipt"]==sha(canonical(pr)) and pr["parent_tensor_sha256"]==receipt["parent_tensor_sha256"],"PRIOR_SEAL")
    p=Path(prior)/"native_grounded.pt";req(sha(p.read_bytes())==ex["pointer_sha256"]==pr["variants"]["native_grounded"]["sha256"],"PRIOR_WEIGHT")
    obj=torch.load(p,map_location="cpu",weights_only=True);pointer=GroundedPointer(parent,False,True);pointer.load_adapter(obj["adapter"]);pointer.eval()
    rows=pairs(ex,exam=True);req(len(rows)==256,"EXAM_COUNT")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    baseline={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    results={};gates={}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(parent.state_dict(),strict=True)
        req(frozen_digest(base)==v["base_tensor_sha256"]==receipt["parent_tensor_sha256"],"FROZEN")
        m=CopyHead(base,name=="byte_copy");m.load_adapter(obj["adapter"]);m.eval()
        with torch.inference_mode():
            probe=torch.tensor([[256,65,66,67]]);exact=torch.equal(parent(probe)[0],base(probe)[0])
        req(exact,"LANGUAGE")
        r=evaluate(m,pointer,rows,T);lang={"anchor":b.anchor(base,root),"historical":c.holdout(base,docs)}
        results[name]={"copy":r,"language":lang,"language_exact":exact}
        checks={"oracle":r["normal_oracle"]["neural_exact"]/512>=ex["oracle_exact_min"],"raw":r["normal_raw"]["guarded_exact"]/512>=ex["raw_exact_min"],"mixed_raw":r["mixed_raw"]["guarded_exact"]/512>=ex["mixed_exact_min"],"mixed_normalized":r["mixed_normalized"]["guarded_exact"]/512>=ex["mixed_exact_min"],"missing":r["normal_raw"]["missing_correct"]/r["normal_raw"]["missing_n"]>=ex["missing_min"],"deleted":r["deleted_raw"]["missing_correct"]==512,"language":exact and lang==baseline}
        gates[name]={**checks,"raw_research_gate":all(checks.values()),"normalized_research_gate":all(v for k,v in checks.items() if k!="mixed_raw")}
    report={"schema":"janus.native.r71d4.result.v1","candidate_receipt":pin,"prior_pointer_receipt":pp,"fresh_sha256":sha(canonical(rows)),"results":results,"gates":gates,"copy_guard_checks_evidence_not_truth":True,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D4_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
