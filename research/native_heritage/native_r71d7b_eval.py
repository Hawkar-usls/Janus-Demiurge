from native_r71d7b_common import *
from native_r71d7_eval import score_routes
import native_r71b_eval as b
import native_r71c_eval as c
def main():
    root,hist,manifest,vfolder,pfolder,cfolder,afolder,out=sys.argv[1:9]
    ex=read("research/native_heritage/R71D7B_PROTOCOL.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    parent,Model,T=load_base(root,ex);pin=frozen_digest(parent);req(pin==ex["parent_tensor_sha256"],"PARENT")
    pobj,pr=sealed(pfolder,ex["pointer"],"native_grounded");cobj,cr=sealed(cfolder,ex["copy"],"byte_relative");aobj,ar=sealed(afolder,ex["arithmetic"],"native_arithmetic");vobj,vr=sealed(vfolder,ex["verifier"],"verifier")
    req(all(r["parent_tensor_sha256"]==pin for r in (pr,cr,ar,vr)),"LINEAGE")
    req(all(o["config"]==parent.config.to_dict() for o in (pobj,cobj,aobj)),"CONFIG")
    pointer=ptr.GroundedPointer(parent,False,True);pointer.load_adapter(pobj["adapter"]);pointer.eval()
    copier=InvariantCopy(parent,True,True);copier.load_adapter(cobj["adapter"]);copier.eval()
    arith=ArithmeticHead(parent,False);arith.load_adapter(aobj["adapter"]);arith.eval();table,local=learned_table(arith)
    req(local["exact"]==400,"ARITH")
    verifier=KeyVerifier();verifier.load_state_dict(vobj["state"],strict=True);verifier.eval()
    rows=stress_rows(ex);req(len(rows)==512,"ROWS")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    probe=torch.tensor([[256,65,66,67]])
    with torch.inference_mode():logits=parent(probe)[0].clone()
    scores={};faults={};cohorts={}
    for variant in ("normal","changed","reordered"):
        fs=supported_frames(rows,T,variant);combined={}
        for i in range(0,len(fs),32):
            z=lock_batch(pointer,copier,verifier,fs[i:i+32],T)
            for k,v in z.items():combined.setdefault(k,[]).extend(v)
        scores[variant]=score_routes(table,fs,combined,T);faults[variant]=injected_recovery(verifier,fs)
        cohorts[variant]={}
        for mode in ("near","prefix","duplicate","missing"):
            ix=[2*i+j for i,r in enumerate(rows) if r["mode"]==mode for j in (0,1)]
            cohorts[variant][mode]=score_routes(table,[fs[i] for i in ix],{k:[v[i] for i in ix] for k,v in combined.items()},T)
    unsupported_cases=unsupported(T);unsupported_ok=all(x["status"]=="reject" for x in unsupported_cases)
    after={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    with torch.inference_mode():lang=torch.equal(logits,parent(probe)[0]) and before==after
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==ex["parent_sha256"],"PARENT_CHANGED")
    gates={}
    for route in ("baseline","strict","neural_recovery","hybrid"):
        checks={k:v[route]["exact"]==v[route]["n"] and v[route]["wrong_accepted"]==0 for k,v in scores.items()}
        gates[route]={**checks,"unsupported_preflight":unsupported_ok,"language":lang,"full_gate":all(checks.values()) and unsupported_ok and lang}
    report={"schema":"janus.native.r71d7b.result.v1","fresh_sha256":sha(canonical(rows)),"sealed_receipts":{k:ex[k]["receipt"] for k in ("pointer","copy","arithmetic","verifier")},"scores":scores,"cohorts":cohorts,"fault_recovery":faults,"unsupported":unsupported_cases,"gates":gates,"language":{"before":before,"after":after,"exact":lang},"training_performed":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D7B_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
