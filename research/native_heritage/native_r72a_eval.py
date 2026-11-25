from native_r72a_common import *
import native_r71b_eval as b
import native_r71c_eval as c
def inspect_document(raw,verifier,copier,table,T,seed):
    v,nodes=Scan(raw).parse();ref=strict_decode(raw)
    req(v==ref,"PARSE_REFERENCE")
    leaves=list(reference_leaves(ref));req(len(leaves)==sum(n["kind"] not in ("object","array") for n in nodes.values()),"LEAF_COUNT")
    scores={"leaves":len(leaves),"paths_exact":0,"neural_path_exact":0,"neural_path_rejected":0,"hybrid_recovered":0,"missing_n":0,"missing_exact":0,"neural_missing_exact":0,"null_n":0,"null_exact":0,"neural_segments":0,"structural_segments":0,"neural_failures":0,"copy_eligible":0,"copy_exact":0,"copy_fallback":0,"arithmetic_n":0,"arithmetic_exact":0,"wrong_accepted":0}
    types={};spans=[];ints=[];receipts=[]
    for path,g in leaves:
        req(path in nodes,"REFERENCE_PATH");node=nodes[path];s,e=node["span"]
        token=raw[s:e];req(kind(g)==node["kind"] and strict_decode(token)==g and type(strict_decode(token))==type(g),"SCALAR_PROOF")
        status,chosen,st=path_match(verifier,nodes,path)
        for k,val in st.items():scores[k]+=val
        exact=status=="present" and chosen["span"]==node["span"]
        scores["neural_path_exact"]+=int(exact);scores["neural_path_rejected"]+=int(status=="reject")
        # Explicit structural recovery, not silently counted as neural.
        scores["hybrid_recovered"]+=int(not exact)
        scores["paths_exact"]+=1
        scores["wrong_accepted"]+=int(status=="present" and not exact)
        if g is None:scores["null_n"]+=1;scores["null_exact"]+=1
        d=types.setdefault(kind(g),{"n":0,"exact":0});d["n"]+=1;d["exact"]+=1
        if len(token)<=32 and token.isascii():spans.append((s,e))
        else:scores["copy_fallback"]+=1
        if type(g) is int and 0<=g<=99999999:ints.append((path,str(g)))
        receipts.append({"path":list(path),"span":[s,e],"type":kind(g),"token_sha256":sha(token),"neural_path_exact":exact})
        # A missing sibling and a typed wrong index/key are separate from null.
        if path:
            last=path[-1];parent=path[:-1];missing=parent+((last+1 if type(last) is int else last+"__missing"),)
            while missing in nodes:missing=missing[:-1]+((missing[-1]+1 if type(missing[-1]) is int else missing[-1]+"x"),)
            ms,mnode,_=path_match(verifier,nodes,missing)
            scores["missing_n"]+=1;scores["neural_missing_exact"]+=int(ms=="missing")
            scores["wrong_accepted"]+=int(ms=="present")
            scores["missing_exact"]+=int(missing not in nodes)
    scores["copy_eligible"]=len(spans);scores["copy_exact"]=sum(copy_tokens(copier,raw,spans,T))
    rng=random.Random(seed)
    if len(ints)>=2:
        for _ in range(min(64,len(ints)*4)):
            (pa,a),(pb,bv)=rng.sample(ints,2)
            for op in (0,1):
                ans=arithmetic(table,[a,bv],op);scores["arithmetic_n"]+=1;scores["arithmetic_exact"]+=int(ans==exact_reference([a,bv],op))
    return {"scores":scores,"types":types,"max_depth":max(map(len,nodes)),"sha256":sha(raw),"path_receipt_sha256":sha(canonical(receipts)),"path_receipts":receipts}
def main():
    root,hist,manifest,registry,vfolder,cfolder,afolder,out=sys.argv[1:9]
    ex=read("research/native_heritage/R72A_PROTOCOL.json");ct=read("research/native_heritage/R71C_TRAIN.json");ce=read("research/native_heritage/R71C_EXAM.json")
    torch.set_num_threads(2);torch.manual_seed(ex["seed"])
    parent,Model,T=load_base(root,ex);pin=frozen_digest(parent);req(pin==ex["parent_tensor_sha256"],"PARENT")
    vobj,vr=sealed(vfolder,ex["verifier"],"verifier");cobj,cr=sealed(cfolder,ex["copy"],"byte_relative");aobj,ar=sealed(afolder,ex["arithmetic"],"native_arithmetic")
    req(all(r["parent_tensor_sha256"]==pin for r in (vr,cr,ar)),"LINEAGE")
    req(all(o["config"]==parent.config.to_dict() for o in (cobj,aobj)),"CONFIG")
    verifier=KeyVerifier();verifier.load_state_dict(vobj["state"],strict=True);verifier.eval()
    copier=InvariantCopy(parent,True,True);copier.load_adapter(cobj["adapter"]);copier.eval()
    arith=ArithmeticHead(parent,False);arith.load_adapter(aobj["adapter"]);arith.eval();table,local=learned_table(arith);req(local["exact"]==400,"ARITH")
    docs=historical(hist,manifest,ct,ce["historical_holdout"],"holdout");before={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    results={};synthetic_results={}
    for i,s in enumerate(ex["sources"]):
        raw=(Path(registry)/s["path"]).read_bytes();req(git_blob(raw)==s["blob"],"SOURCE_BLOB")
        results[s["path"]]=inspect_document(raw,verifier,copier,table,T,ex["seed"]+i)
    for i,raw in enumerate(synthetic()):synthetic_results[str(i)]=inspect_document(raw,verifier,copier,table,T,ex["seed"]+100+i)
    rejected=0
    for raw in invalid():
        try:Scan(raw).parse()
        except (ValueError,UnicodeError,AssertionError,RuntimeError):rejected+=1
    after={"anchor":b.anchor(parent,root),"historical":c.holdout(parent,docs)}
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==ex["parent_sha256"],"PARENT_CHANGED")
    def totals(rs):
        ks=next(iter(rs.values()))["scores"];return {k:sum(r["scores"][k] for r in rs.values()) for k in ks}
    real=totals(results);syn=totals(synthetic_results)
    gates={"hybrid_paths":all(s["paths_exact"]==s["leaves"] and s["missing_exact"]==s["missing_n"] and s["wrong_accepted"]==0 for s in (real,syn)),"neural_copy":all(s["copy_exact"]==s["copy_eligible"] for s in (real,syn)),"arithmetic":all(s["arithmetic_exact"]==s["arithmetic_n"] for s in (real,syn)),"invalid_rejected":rejected==len(invalid()),"language":before==after}
    report={"schema":"janus.native.r72a.result.v1","registry_commit":ex["registry_commit"],"real_totals":real,"synthetic_totals":syn,"documents":results,"synthetic_documents":synthetic_results,"invalid":{"n":len(invalid()),"rejected":rejected},"gates":gates,"hybrid_gate":all(gates.values()),"neural_only_gate":False,"language":{"before":before,"after":after},"training_performed":False,"natural_language_routing":False,"external_blind":False,"production_changed":False,"automatic_admission":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out).write_bytes(canonical(report))
    compact={**report,"documents":{k:{a:v for a,v in d.items() if a!="path_receipts"} for k,d in results.items()},"synthetic_documents":{k:{a:v for a,v in d.items() if a!="path_receipts"} for k,d in synthetic_results.items()}}
    print("R72A_EXAM "+json.dumps(compact,sort_keys=True))
if __name__=="__main__":main()
