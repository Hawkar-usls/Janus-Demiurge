from native_r72b3_common import *
import native_r71b_eval as b_eval
import native_r71c_eval as c_eval
def main():
    root,hist,manifest,registry,candidates,baseline_folder,seal,out=sys.argv[1:9]
    tr=read("research/native_heritage/R72B3_TRAIN.json");ex=read("research/native_heritage/R72B3_EXAM.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    r=read(Path(candidates)/"RECEIPT.json");pin=r.pop("receipt_sha256")
    req(pin==seal==sha(canonical(r)) and r["train_spec_sha256"]==sha(canonical(tr)),"SEAL")
    req(not set(s["blob"] for s in tr["sources"])&set(s["blob"] for s in ex["sources"]),"DOCUMENT_SPLIT")
    parent,Model,T=load_base(root,tr);basepin=frozen_digest(parent);req(basepin==r["parent_tensor_sha256"]==tr["parent_tensor_sha256"],"PARENT")
    real,cov=load_rows(ex,registry);syn=synthetic(True);req(set(x["label"] for x in real)==set(LABELS),"CLASS_SUPPORT")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    matrices={}
    for key,rows,mode in (("real_full",real,"full"),("real_key",real,"key"),("real_value",real,"value"),("contrast",syn,"full")):
        matrices[key]=(rows,*features(parent,rows,mode),targets(rows),mode)
    results={};predictions={};outputs={}
    for name,v in r["variants"].items():
        p=Path(candidates)/(name+".pt");req(sha(p.read_bytes())==v["sha256"],"CANDIDATE")
        obj=torch.load(p,map_location="cpu",weights_only=True);req(obj["byte_only"]==(name=="byte_semantics"),"ARM")
        m=SemanticHead(parent.config.d_model,obj["byte_only"]);m.load_state_dict(obj["state"],strict=True);m.eval()
        req(all(bool(t.isfinite().all()) for t in m.state_dict().values()),"FINITE")
        scores={};predictions[name]=[]
        for key,(rows,b,h,y,mode) in matrices.items():
            with torch.inference_mode():prob=m(b,h).softmax(-1);conf,pred=prob.max(-1)
            s=stats(y,pred);keep=conf>=0.8;s["confidence_0_8"]={"n":int(keep.sum()),"correct":int(((pred==y)&keep).sum()),"wrong":int(((pred!=y)&keep).sum())}
            if key=="real_full":
                for row,a,c in zip(rows,pred.tolist(),conf.tolist()):predictions[name].append({"source":row["source"],"path":row["path"],"span":row["span"],"token_sha256":row["token_sha256"],"gold":row["label"],"predicted":LABELS[a],"confidence":c})
            scores[key]=s
            outputs[(name,key)]=(pred,conf)
        results[name]=scores
    old=read(Path(baseline_folder)/"RECEIPT.json");oldpin=old.pop("receipt_sha256")
    req(oldpin==ex["baseline"]["receipt"]==sha(canonical(old)) and old["parent_tensor_sha256"]==basepin,"BASELINE_SEAL")
    for name,hashval in ex["baseline"]["artifacts"].items():
        p=Path(baseline_folder)/(name+".pt");req(sha(p.read_bytes())==hashval==old["variants"][name]["sha256"],"BASELINE_SHA")
        obj=torch.load(p,map_location="cpu",weights_only=True);m=B2Head(parent.config.d_model,obj["byte_only"]);m.load_state_dict(obj["state"],strict=True);m.eval()
        scores={}
        for key,(rows,b,h,y,mode) in matrices.items():
            with torch.inference_mode():p=m(b,h).argmax(-1)
            scores[key]=stats(y,p)
            if key=="contrast":
                ids=collections.defaultdict(list)
                for row,ok in zip(rows,(p==y).tolist()):ids[row["contrast_id"]].append(ok)
                scores[key]["triples_exact"]=sum(all(v) for v in ids.values());scores[key]["triples_n"]=len(ids)
        results["frozen_b2_"+name]=scores
    for name in ("native_semantics","byte_semantics"):
        rows,bb,hh,y,mode=matrices["contrast"];p,_=outputs[(name,"contrast")];ids=collections.defaultdict(list)
        for row,ok in zip(rows,(p==y).tolist()):ids[row["contrast_id"]].append(ok)
        results[name]["contrast"]["triples_exact"]=sum(all(v) for v in ids.values());results[name]["contrast"]["triples_n"]=len(ids)
    results["lexical"]={key:stats(y,torch.tensor([lexical(row,mode) for row in rows])) for key,(rows,b,h,y,mode) in matrices.items()}
    # Fixed agreement guard: never relabel a disagreement as true evidence.
    selective={}
    for key,(rows,b,h,y,mode) in matrices.items():
        p,conf=outputs[("native_semantics",key)];q,qconf=outputs[("byte_semantics",key)]
        rule=torch.tensor([lexical(row,mode) for row in rows])
        keep=(p==q)&(p==rule)&(conf>=.8)&(qconf>=.8)
        critical=torch.tensor([r["label"] in ("epistemic_limit","hypothesis_plan") for r in rows])
        selective[key]={"n":len(y),"accepted":int(keep.sum()),"correct":int((keep&(p==y)).sum()),"wrong":int((keep&(p!=y)).sum()),"critical_as_evidence":int((keep&critical&(p==LABELS.index("evidence_statement"))).sum())}
    after={"anchor":b_eval.anchor(parent,root),"historical":c_eval.holdout(parent,docs)}
    req(frozen_digest(parent)==basepin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    gates={}
    for name in ("native_semantics","byte_semantics"):
        s=results[name]["real_full"];g=ex["gates"]
        checks={"macro_f1":s["macro_f1"]>=g["macro_f1_min"],"critical_recall":all(s["by_role"][k]["recall"]>=g["critical_recall_min"] for k in ("epistemic_limit","hypothesis_plan")),"critical_as_evidence":s["critical_as_evidence"]==0,"contrast":results[name]["contrast"]["accuracy"]>=g["contrast_exact_min"],"language":before==after}
        gates[name]={**checks,"isolated_semantic_gate":all(checks.values())}
    native=results["native_semantics"]["real_full"]["macro_f1"];byte=results["byte_semantics"]["real_full"]["macro_f1"];lex=results["lexical"]["real_full"]["macro_f1"]
    gates["native_gain"]=(native-max(byte,lex))>=ex["gates"]["native_gain_min"]
    report={"schema":"janus.native.r72b3.result.v1","candidate_receipt":pin,"exam_sha256":sha(canonical(real+syn)),"real_rows":len(real),"synthetic_rows":len(syn),"coverage":cov,"results":results,"gates":gates,"language":{"before":before,"after":after},"predictions":predictions,"selective_agreement":selective,"separate_typed_views":True,"auxiliary_epistemic_head":True,"same_exam_frozen_b2":True,"manual_role_labels_not_truth":True,"external_blind":False,"parent_pretraining_overlap_unknown":True,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report));print("R72B3_EXAM "+json.dumps({k:v for k,v in report.items() if k!="predictions"},sort_keys=True))
if __name__=="__main__":main()
