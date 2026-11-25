from native_r71d4b_common import *
import native_r71d4_common as prior
import native_r71b_eval as b
import native_r71c_eval as c
def assess(m,rows,T,shift=False):
    counts={};total={"n":0,"exact":0,"literal":0,"position_exact":0,"terminated":0,"rejected":0,"missing_correct":0,"short":0,"long":0,"wrong_equal_length":0}
    for i in range(0,len(rows),32):
        rr=rows[i:i+32];fs=[render(r,T,shift) for r in rr];pred=decode(m,fs,T)
        for r,(ids,(s,e)),(out,stop,positions) in zip(rr,fs,pred):
            gold=r["payload"];literal=T.decode(ids[s:e+1]) if s else "";req(literal==gold,"REFERENCE")
            pos=list(range(s,e+1)) if s else [];correct=stop and out==gold
            vals={"n":1,"exact":int(correct),"literal":1,"position_exact":int(stop and positions==pos),"terminated":int(stop),"rejected":int(not correct),"missing_correct":int(not s and correct),"short":int(len(out)<len(gold)),"long":int(len(out)>len(gold)),"wrong_equal_length":int(len(out)==len(gold) and out!=gold)}
            for k,v in vals.items():total[k]+=v
            for key in ("type:"+r["kind"],"length:"+str(len(gold)),"cohort:"+("ood" if r["ood"] else "in_range")):
                d=counts.setdefault(key,{k:0 for k in vals})
                for k,v in vals.items():d[k]+=v
    return {**total,"breakdown":counts}
def prior_diagnostic(parent,folder,ex,T):
    receipt=read(Path(folder)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==ex["prior_receipt"]==sha(canonical(receipt)),"PRIOR_SEAL")
    p=Path(folder)/"native_copy.pt";req(sha(p.read_bytes())==ex["prior_native_sha256"]==receipt["variants"]["native_copy"]["sha256"],"PRIOR_WEIGHT")
    obj=torch.load(p,map_location="cpu",weights_only=True);m=prior.CopyHead(parent,False);m.load_adapter(obj["adapter"]);m.eval()
    old=read("research/native_heritage/R71D4_EXAM.json");rows=prior.pairs(old,exam=True);frames=[]
    for i,r in enumerate(rows):
        for target in r["targets"]:frames.append(prior.frame(r["doc"],target,T,"Read" if i%2 else "Locate",(i//32)%2))
    by={}
    for i in range(0,len(frames),32):
        fs=frames[i:i+32];sp=[f[4] for f in fs];pred=prior.copy_decode(m,fs,sp,T)
        for f,s,(out,stop) in zip(fs,sp,pred):
            gold=prior.literal(f,s,T);d=by.setdefault(str(len(gold)),{"n":0,"exact":0,"terminated":0,"short":0,"long":0});d["n"]+=1;d["exact"]+=int(stop and out==gold);d["terminated"]+=int(stop);d["short"]+=int(len(out)<len(gold));d["long"]+=int(len(out)>len(gold))
    req(sum(d["exact"] for d in by.values())==320 and sum(d["n"] for d in by.values())==512,"PRIOR_REPRO")
    return by
def main():
    root,hist,manifest,candidates,old,seal,out=sys.argv[1:8]
    tr=read("research/native_heritage/R71D4B_TRAIN.json");ex=read("research/native_heritage/R71D4B_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)) and receipt["parent_sha256"]==tr["parent_sha256"],"SEAL")
    parent,Model,T=load_base(root,tr);req(frozen_digest(parent)==receipt["parent_tensor_sha256"],"PARENT")
    rows=suite(ex,True);req(len(rows)==768 and all(partition(r["payload"]) for r in rows if r["payload"]),"EXAM_SPLIT")
    diag=prior_diagnostic(parent,old,ex,T)
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");baseline={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    results={};gates={}
    for name,v in receipt["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["config"]==parent.config.to_dict(),"CONFIG")
        base=Model(parent.config);base.load_state_dict(parent.state_dict(),strict=True)
        req(frozen_digest(base)==v["base_tensor_sha256"]==receipt["parent_tensor_sha256"],"BASE")
        m=InvariantCopy(base,obj["byte_only"],obj["relative"]);m.load_adapter(obj["adapter"]);m.eval()
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE")
        with torch.inference_mode():
            probe=torch.tensor([[256,65,66,67]]);exact=torch.equal(parent(probe)[0],base(probe)[0])
        lang={"anchor":b.anchor(base,root),"historical":c.holdout(base,docs)}
        normal=assess(m,rows,T);shift=assess(m,rows,T,True)
        results[name]={"normal":normal,"shifted":shift,"language":lang,"language_exact":exact}
        tests={"exact":normal["exact"]==normal["n"],"shifted":shift["exact"]==shift["n"],"positions":normal["position_exact"]==normal["n"] and shift["position_exact"]==shift["n"],"language":exact and lang==baseline}
        gates[name]={**tests,"isolated_copy_gate":all(tests.values()),"end_to_end_gate":False}
    report={"schema":"janus.native.r71d4b.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(rows)),"prior_D4_by_length":diag,"results":results,"gates":gates,"oracle_evidence_only":True,"pointer_extended_types_tested":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D4B_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
