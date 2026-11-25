"""Fresh frozen stress test; no training and no modification of D7."""
from native_r71d7_common import *
import string

def stress_rows(spec):
    rng=random.Random(spec["seed"]);rows=[];seen=set()
    def neighbor(k,mode,forbidden):
        for _ in range(5000):
            if mode=="prefix":
                c=k+rng.choice(string.ascii_lowercase) if len(k)<7 else k[:-1]
                if len(k)==7 and c in forbidden:c=k[:-1]+rng.choice(string.ascii_lowercase)
            else:
                j=rng.randrange(len(k));c=k[:j]+rng.choice(string.ascii_lowercase)+k[j+1:]
            if 2<=len(c)<=7 and c not in forbidden and pointer_module.key_partition(c):return c
            if mode=="prefix" and len(k)==7:break
        return None
    for i in range(spec["pairs"]):
        mode=("near","prefix","duplicate","missing")[i%4]
        for _ in range(5000):
            a=pointer_module.key(rng,True,2,5 if mode=="prefix" else 7)
            b=neighbor(a,"prefix" if mode=="prefix" else "near",{a})
            if b is None:continue
            n=2+(i//4)%5
            names=[a,b]
            while len(names)<n:
                k=pointer_module.key(rng,True,2,7)
                if k not in names:names.append(k)
            v=rng.choice([0,9,10,99,100,999,1000,9999,10000,99999,rng.randrange(100000)])
            w=v if mode=="duplicate" else max(0,min(99999,v+rng.choice([-1,1,10,100])))
            vals=[v,w]+[rng.randrange(10**rng.randrange(1,6)) for _ in names[2:]]
            doc=shuffled(dict(zip(names,vals)),rng)
            q=[a,b]
            if mode=="missing":
                absent=neighbor(b,"near",set(names))
                if absent is None:continue
                q[(i//4)%2]=absent
            changed=dict(doc)
            for j,k in enumerate(q):
                if k in changed:changed[k]=(changed[k]+(1 if j==0 else 10001))%100000
                else:changed[k]=rng.randrange(100000)
            # Mixed formatting fits original context; reduce fields only
            # when source itself would exceed 128 bytes.
            signature=sha(canonical([doc,q,changed]))
            if signature in seen:continue
            seen.add(signature);rows.append({"doc":doc,"changed":changed,"keys":q,"mode":mode});break
        else:raise ValueError("STRESS_ROW")
    return rows

def render_stress(doc,q,T,style=4):
    # Use the frozen renderer; cap context via a deterministic subset of
    # decoys, never remove queried keys.
    return pointer_module.frame(doc,q,T,"Locate",style)

def supported_frames(rows,T,variant):
    fs=[]
    for r in rows:
        doc=dict(r["changed"] if variant=="changed" else r["doc"])
        if variant=="reordered":doc=dict(reversed(list(doc.items())))
        # With six fields, mixed whitespace can exceed the 128-byte
        # native context. Drop only distractors before any inference.
        while True:
            try:
                frames=[render_stress(doc,k,T,4) for k in r["keys"]]
                break
            except (ValueError,AssertionError,RuntimeError):
                candidates=[k for k in doc if k not in r["keys"]]
                if not candidates:raise
                doc.pop(candidates[-1])
        fs.extend(frames)
    req(all(structural(f) is not None for f in fs),"SUPPORTED")
    return fs

def injected_recovery(verifier,fs):
    counts={"n":0,"neural_exact":0,"proof_rejected":0}
    for f in fs:
        p=structural(f);g=f[4];q,fields=p
        bad=[s for k,s in fields.items() if k!=q]
        if g!=(0,0):bad.append((0,0))
        if g[1]>g[0]:bad.append((g[0],g[1]-1))
        n=neural_reselect(verifier,p)
        for s in bad:
            counts["n"]+=1;counts["proof_rejected"]+=int(not proof(p,s));counts["neural_exact"]+=int(n==g and proof(p,n))
    return counts

def unsupported(T):
    bodies=['{"aa":1,"aa":2}','{"aa":{"bb":1}}','{"aa":[1]}','{"aa":"123"}','{"aa":-1}','{"aa":123456}','{"aa":01}','{"aa":1,}','{"aa":1}x','{"aa":1.0}','{"aa":true}','{"AA":1}','{"a":1}','{"aa":1,"bb":null}','{"a\\u0061":1}','{"aa":1,, "bb":2}','{"aa":1,"bb":2','{"aa":1} {"bb":2}','{"aa":1e2}','{"aa":+1}','{"aa":1,"bbbbbbbb":2}','{"aa":'+("1"*105)+'}']
    res=[]
    for body in bodies:
        prefix="Find:aa\nJSON:";ids=T.encode(prefix+body,bos=True)
        f=(ids,len(T.encode("Find:",bos=True)),2,len(T.encode(prefix,bos=True)),(0,0))
        # Fail closed before inference; unsupported must not mean missing.
        status="reject" if structural(f) is None else "admitted"
        res.append({"body":body,"status":status})
    return res
