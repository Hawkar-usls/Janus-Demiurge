"""Frozen integration, exact evidence provenance and explicit unsupported scope."""
from native_r71d4b_common import *
import native_r71d4_common as d4
import native_r71d3c_common as ptr

def sealed(folder,expected,name):
    r=read(Path(folder)/"RECEIPT.json");pin=r.pop("receipt_sha256")
    req(pin==expected["receipt"]==sha(canonical(r)),"SEALED_RECEIPT")
    p=Path(folder)/(name+".pt")
    req(sha(p.read_bytes())==expected["sha256"]==r["variants"][name]["sha256"],"SEALED_WEIGHTS")
    return torch.load(p,map_location="cpu",weights_only=True),r

def integration_suite(spec,T):
    rows=ptr.pairs(spec,exam=True)
    req(len(rows)==spec["pairs"] and all(ptr.key_partition(k) for r in rows for k in list(r["doc"])+r["targets"]),"KEY_SPLIT")
    cases=[]
    for i,r in enumerate(rows):
        for target in r["targets"]:
            doc=r["doc"];verb="Locate" if (i//32)%2 else "Read"
            alt=dict(doc)
            if target in alt:alt[target]=(alt[target]+137)%100000
            else:alt[target]=i%100000
            cases.append({"normal":ptr.frame(doc,target,T,verb,(i//64)%2),
                "mixed":ptr.frame(doc,target,T,verb,4),
                "reordered":ptr.frame(dict(reversed(list(doc.items()))),target,T,verb,4),
                "changed":ptr.frame(alt,target,T,verb,4),
                "erased":ptr.frame(doc,target,T,verb,4,True),
                "deleted":ptr.frame({},target,T,verb,4)})
    return rows,cases

def run_batch(pointer,copier,fs,T,normalize=True):
    if normalize:
        nf,maps=zip(*(d4.normalize(f,T) for f in fs))
        p=ptr.predict(pointer,list(nf))
        spans=[(0,0) if s==0 else (mp[s],mp[e]) for (s,e),mp in zip(p,maps)]
    else:spans=ptr.predict(pointer,fs)
    # Inference never sees frame gold. Copy is constrained to predicted span.
    frames=[(f[0],sp) for f,sp in zip(fs,spans)]
    outputs=decode(copier,frames,T)
    result=[]
    for f,sp,(out,stop,positions) in zip(fs,spans,outputs):
        s,e=sp;literal=T.decode(f[0][s:e+1]) if s else ""
        expected_pos=list(range(s,e+1)) if s else []
        accepted=stop and out==literal and positions==expected_pos
        result.append({"span":sp,"output":out,"literal":literal,"accepted":accepted,"terminated":stop})
    return result

def evaluate(pointer,copier,fs,T,normalize=True):
    results=[]
    for i in range(0,len(fs),32):results.extend(run_batch(pointer,copier,fs[i:i+32],T,normalize))
    exact=[];missing=present=absent_correct=wrong_accepted=rejected=pointer_exact=copy_exact=literal_exact=0
    for f,r in zip(fs,results):
        gold=f[4];target=T.decode(f[0][gold[0]:gold[1]+1]) if gold[0] else ""
        good=r["span"]==gold and r["output"]==target and r["accepted"]
        exact.append(good);pointer_exact+=int(r["span"]==gold)
        literal_exact+=int(r["literal"]==target and r["span"]==gold)
        copy_exact+=int(r["accepted"]);wrong_accepted+=int(r["accepted"] and not good)
        rejected+=int(not r["accepted"])
        if gold[0]==0:missing+=1;absent_correct+=int(good)
        else:present+=1
    return {"n":len(fs),"exact":sum(exact),"pairs":len(fs)//2,"exact_pairs":sum(exact[i] and exact[i+1] for i in range(0,len(fs),2)),"present_n":present,"missing_n":missing,"missing_correct":absent_correct,"pointer_exact":pointer_exact,"direct_copy_reference":literal_exact,"copy_guard_accepted":copy_exact,"wrong_accepted":wrong_accepted,"rejected":rejected},results

def stress_suite(T):
    # This is deliberately out of supported scope: target spans exceed
    # the frozen pointer's five-byte limit. No parser at inference.
    out=[]
    for i in range(64):
        target=("2026-11-%02d"%(1+i%28)) if i%2==0 else "JANUS_ID_%04d"%i
        prefix="Find:target\nJSON:"
        body='{"target":"'+target+'","note":7}'
        ids=T.encode(prefix+body,bos=True);s=len(T.encode(prefix+'{"target":"',bos=True))
        qstart=len(T.encode("Find:",bos=True));ds=len(T.encode(prefix,bos=True))
        req(T.decode(ids[s:s+len(target)])==target,"STRESS_GOLD")
        out.append((ids,qstart,6,ds,(s,s+len(target)-1)))
    return out
