from native_r71d7_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def suite(rows,variant,T):
    fs=[]
    for r in rows:
        doc=r["changed"] if variant=="changed" else r["doc"]
        if variant=="reordered":doc=dict(reversed(list(doc.items())))
        if variant=="deleted":doc={}
        for k in r["keys"]:fs.append(pointer_module.frame(doc,k,T,"Locate",4))
    return fs
def score_routes(table,fs,out,T):
    stats={}
    for route,items in out.items():
        if route=="neural_independent":
            stats[route]={"n":len(items),"exact":sum(x["correct"] for x in items)};continue
        s={"operands":len(items),"operand_exact":0,"recovered_operands":0,"rejected_operands":0,"wrong_accepted_operands":0,"n":len(items),"exact":0,"wrong_accepted":0,"rejected":0,"missing_correct":0,"missing_n":0,"deterministic_reference":0}
        for f,x in zip(fs,items):
            right=x["status"]!="reject" and x["span"]==f[4]
            s["operand_exact"]+=int(right);s["wrong_accepted_operands"]+=int(x["status"]!="reject" and not right)
            s["recovered_operands"]+=int(x["recovered"]);s["rejected_operands"]+=int(x["status"]=="reject")
        for i in range(0,len(fs),2):
            ff=fs[i:i+2];xx=items[i:i+2];v=[x["value"] for x in xx]
            gold=[T.decode(f[0][f[4][0]:f[4][1]+1]) if f[4][0] else None for f in ff]
            # Independent standard JSON parser reference, not used in inference.
            ref=[json.loads(T.decode(f[0][f[3]:])).get(T.decode(f[0][f[1]:f[1]+f[2]])) for f in ff]
            ref=[str(a) if a is not None else None for a in ref];req(ref==gold,"GOLD_REFERENCE")
            valid=all(x["status"]!="reject" for x in xx);provenance=valid and all(x["span"]==f[4] for f,x in zip(ff,xx))
            for op in (0,1):
                g=exact_reference(gold,op);p=arithmetic(table,v,op) if valid else None
                right=provenance and p==g
                s["exact"]+=int(right);s["wrong_accepted"]+=int(valid and not right);s["rejected"]+=int(not valid)
                s["deterministic_reference"]+=int(exact_reference(ref,op)==g)
                if g is None:s["missing_n"]+=1;s["missing_correct"]+=int(right)
        stats[route]=s
    return stats
def main():
    root,hist,manifest,candidates,pfolder,cfolder,afolder,seal,out=sys.argv[1:10]
    tr=read("research/native_heritage/R71D7_TRAIN.json");ex=read("research/native_heritage/R71D7_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"])
    receipt=read(Path(candidates)/"RECEIPT.json");pin=receipt.pop("receipt_sha256")
    req(pin==seal==sha(canonical(receipt)) and receipt["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==receipt["parent_tensor_sha256"]==ex["parent_tensor_sha256"],"PARENT")
    pobj,pr=sealed(pfolder,ex["pointer"],"native_grounded");cobj,cr=sealed(cfolder,ex["copy"],"byte_relative");aobj,ar=sealed(afolder,ex["arithmetic"],"native_arithmetic")
    req(all(r["parent_tensor_sha256"]==basepin for r in (pr,cr,ar)),"LINEAGE")
    req(all(o["config"]==parent.config.to_dict() for o in (pobj,cobj,aobj)),"CONFIG")
    pointer=ptr.GroundedPointer(parent,False,True);pointer.load_adapter(pobj["adapter"]);pointer.eval()
    copier=InvariantCopy(parent,True,True);copier.load_adapter(cobj["adapter"]);copier.eval()
    arith=ArithmeticHead(parent,False);arith.load_adapter(aobj["adapter"]);arith.eval()
    table,local=learned_table(arith);req(local["exact"]==400,"ARITH_REGRESSION")
    p=Path(candidates)/"verifier.pt";req(sha(p.read_bytes())==receipt["variants"]["verifier"]["sha256"],"VERIFIER_SHA")
    verifier=KeyVerifier();verifier.load_state_dict(torch.load(p,map_location="cpu",weights_only=True)["state"],strict=True);verifier.eval()
    req(all(bool(t.isfinite().all()) for m in (pointer,copier,arith,verifier) for t in m.state_dict().values()),"FINITE")
    rows=make_cases(ex,True);req(len(rows)==512,"EXAM_COUNT")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    probe=torch.tensor([[256,65,66,67]])
    with torch.inference_mode():logits=parent(probe)[0].clone()
    scores={}
    for variant in ("normal","changed","reordered","deleted"):
        fs=suite(rows,variant,T);combined={}
        for i in range(0,len(fs),32):
            z=lock_batch(pointer,copier,verifier,fs[i:i+32],T)
            for k,v in z.items():combined.setdefault(k,[]).extend(v)
        scores[variant]=score_routes(table,fs,combined,T)
    fault=fault_exam(T,rows);faultpass=all(v["n"]>0 and v["n"]==v["rejected"] for v in fault.values())
    after={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    with torch.inference_mode():language=torch.equal(logits,parent(probe)[0]) and before==after
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    gates={}
    for route in ("baseline","strict","neural_recovery","hybrid"):
        checks={k: v[route]["exact"]==v[route]["n"] and v[route]["wrong_accepted"]==0 for k,v in scores.items()}
        gates[route]={**checks,"language":language,"fault_guard":faultpass,"full_gate":all(checks.values()) and language and faultpass}
    report={"schema":"janus.native.r71d7.result.v1","candidate_receipt":pin,"fresh_sha256":sha(canonical(rows)),"scores":scores,"fault_injection":fault,"gates":gates,"language":{"before":before,"after":after,"exact":language},"sealed_arithmetic":local,"structural_scope":"flat unique lowercase ASCII keys length 2..7, unsigned integer 0..99999, <=128 bytes","hybrid_recovery_is_deterministic":True,"neural_recovery_uses_structural_candidates":True,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D7_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
