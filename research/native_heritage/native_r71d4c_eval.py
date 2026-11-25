from native_r71d4c_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def main():
    root,hist,manifest,pfolder,cfolder,out=sys.argv[1:7]
    spec=read("research/native_heritage/R71D4C_PROTOCOL.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(spec["seed"])
    parent,Model,T=load_base(root,spec);parent.requires_grad_(False);parent.eval()
    pin=frozen_digest(parent);req(pin==spec["parent_tensor_sha256"],"PARENT_PIN")
    pobj,pr=sealed(pfolder,spec["pointer"],"native_grounded")
    cobj,cr=sealed(cfolder,spec["copy"],"byte_relative")
    req(pr["parent_tensor_sha256"]==cr["parent_tensor_sha256"]==pin,"LINEAGE")
    req(pobj["config"]==cobj["config"]==parent.config.to_dict() and cobj["byte_only"] and cobj["relative"],"CONFIG")
    pointer=ptr.GroundedPointer(parent,False,True);pointer.load_adapter(pobj["adapter"]);pointer.eval()
    copier=InvariantCopy(parent,True,True);copier.load_adapter(cobj["adapter"]);copier.eval()
    req(all(bool(t.isfinite().all()) for m in (pointer,copier) for t in m.state_dict().values()),"FINITE")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout")
    before={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    probe=torch.tensor([[256,65,66,67]])
    with torch.inference_mode():logits=parent(probe)[0].clone()
    rows,cases=integration_suite(spec,T);req(len(cases)==1024,"EXAM_COUNT")
    scores={};preds={}
    for name in ("normal","mixed","reordered","changed","deleted"):
        scores[name],preds[name]=evaluate(pointer,copier,[r[name] for r in cases],T)
    scores["mixed_raw"],_=evaluate(pointer,copier,[r["mixed"] for r in cases],T,False)
    # Erased query still has original target gold in the frame; evaluate
    # counterfactual dependence separately from absent-key accuracy.
    scores["erased"],_=evaluate(pointer,copier,[r["erased"] for r in cases],T)
    change_n=change_correct=0
    for r,a,z in zip(cases,preds["normal"],preds["changed"]):
        f=r["normal"];g=r["changed"]
        x=T.decode(f[0][f[4][0]:f[4][1]+1]) if f[4][0] else ""
        y=T.decode(g[0][g[4][0]:g[4][1]+1]) if g[4][0] else ""
        if x!=y:
            change_n+=1;change_correct+=int(a["accepted"] and z["accepted"] and a["span"]==f[4] and z["span"]==g[4] and a["output"]==x and z["output"]==y)
    stress,_=evaluate(pointer,copier,stress_suite(T),T)
    after={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    with torch.inference_mode():exact=torch.equal(logits,parent(probe)[0])
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==spec["parent_sha256"],"PARENT_CHANGED")
    g=spec["gates"]
    checks={}
    for k in ("normal","mixed","reordered","changed"):
        s=scores[k];checks[k+"_exact"]=s["exact"]/s["n"]>=g["exact_min"]
        checks[k+"_pair"]=s["exact_pairs"]/s["pairs"]>=g["paired_min"]
        checks[k+"_no_wrong_accepted"]=s["wrong_accepted"]<=g["wrong_accepted_max"]
        if s["missing_n"]:checks[k+"_missing"]=s["missing_correct"]/s["missing_n"]>=g["missing_min"]
    checks["counterfactual"]=change_correct/change_n>=g["exact_min"]
    checks["deleted"]=scores["deleted"]["exact"]==scores["deleted"]["n"]
    checks["language"]=exact and before==after
    report={"schema":"janus.native.r71d4c.result.v1","pointer_receipt":spec["pointer"]["receipt"],"copy_receipt":spec["copy"]["receipt"],"fresh_sha256":sha(canonical(rows)),"scores":scores,"changed_pair":{"n":change_n,"both_correct":change_correct},"out_of_scope_stress":stress,"language":{"before":before,"after":after,"exact":exact},"gates":checks,"supported_scope_gate":all(checks.values()),"extended_types_gate":False,"production_changed":False,"automatic_admission":False,"external_blind":False,"training_performed":False,"copy_guard_not_truth_verifier":True}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R71D4C_EXAM "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
