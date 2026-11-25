"""R71D7: learned independent key matching plus deterministic structural proof."""
from native_r71d6_common import *
import re

# Strict declared scope, raw original byte offsets; not a general JSON parser.
WS=rb"[ \t\r\n]*"
FIELD=re.compile(WS+rb'"([a-z]{2,7})"'+WS+rb":"+WS+rb"(0|[1-9][0-9]{0,4})"+WS)
def structural(f):
    ids,qs,ql,ds,_=f
    if not (0<qs<qs+ql<=ds<len(ids)<=128):return None
    try:q=bytes(ids[qs:qs+ql]);body=bytes(ids[ds:])
    except ValueError:return None
    if not re.fullmatch(rb"[a-z]{2,7}",q):return None
    if not body.startswith(b"{") or not body.endswith(b"}"):return None
    at=1;fields={}
    if re.fullmatch(WS,body[at:-1]):return q,fields
    while at<len(body)-1:
        m=FIELD.match(body,at)
        if m is None or m.end()>len(body)-1:return None
        k=m.group(1)
        if k in fields:return None
        fields[k]=(ds+m.start(2),ds+m.end(2)-1)
        at=m.end()
        if at==len(body)-1:return q,fields
        if body[at:at+1]!=b",":return None
        at+=1
    return None

def proof(parsed,span):
    if parsed is None:return False
    q,fields=parsed
    return span==fields.get(q,(0,0))

def train_pairs(spec):
    rng=random.Random(spec["seed"]);out=[]
    for i in range(spec["pairs"]):
        q=pointer_module.key(rng,False,2,7)
        if i%2==0:k=q;y=1
        else:
            y=0
            for _ in range(5000):
                mode=i%4
                if mode==1:
                    j=rng.randrange(len(q));k=q[:j]+rng.choice("abcdefghijklmnopqrstuvwxyz")+q[j+1:]
                elif mode==3 and len(q)>2:k=q[:-1]
                else:k=pointer_module.key(rng,False,2,7)
                if k!=q and not pointer_module.key_partition(k):break
                # Prefix can belong to the heldout partition; resample.
                if mode==3:k=pointer_module.key(rng,False,2,7)
                if k!=q and not pointer_module.key_partition(k):break
            else:raise ValueError("NEGATIVE_KEY")
        out.append((q,k,y))
    req(all(not pointer_module.key_partition(q) and not pointer_module.key_partition(k) for q,k,_ in out),"TRAIN_SPLIT")
    return out

def key_batch(rows):
    def enc(s):
        b=list(s.encode("ascii") if isinstance(s,str) else s);req(1<=len(b)<=7,"KEY_LENGTH");return b+[0]*(7-len(b)),len(b)
    a,b,la,lb,y=[],[],[],[],[]
    for q,k,v in rows:
        x,n=enc(q);z,m=enc(k);a.append(x);b.append(z);la.append(n);lb.append(m);y.append(v)
    return torch.tensor(a),torch.tensor(b),torch.tensor(la),torch.tensor(lb),torch.tensor(y,dtype=torch.float32)
class KeyVerifier(nn.Module):
    def __init__(self):
        super().__init__();self.emb=nn.Embedding(258,24)
        self.net=nn.Sequential(nn.Linear(11,32),nn.GELU(),nn.Linear(32,1))
    def forward(self,a,b,la,lb):
        x=F.normalize(self.emb(a),dim=-1);z=F.normalize(self.emb(b),dim=-1)
        sim=(x*z).sum(-1);mask=torch.arange(7,device=a.device)[None,:]<torch.maximum(la,lb)[:,None]
        low=sim.masked_fill(~mask,1).min(-1).values
        avg=(sim*mask).sum(-1)/mask.sum(-1)
        f=torch.cat([sim,low[:,None],avg[:,None],la[:,None].float()/7,lb[:,None].float()/7],-1)
        return self.net(f).squeeze(-1)

def neural_reselect(m,parsed):
    if parsed is None:return None
    q,fields=parsed
    if not fields:return (0,0)
    keys=list(fields);a,b,la,lb,_=key_batch([(q,k,0) for k in keys])
    with torch.inference_mode():z=m(a,b,la,lb)
    i=int(z.argmax());return fields[keys[i]] if float(z[i])>=0 else (0,0)

def raw_spans(pointer,fs,T):
    nf,maps=zip(*(d4.normalize(f,T) for f in fs))
    p=ptr.predict(pointer,list(nf))
    return [(0,0) if s==0 else (mp[s],mp[e]) for (s,e),mp in zip(p,maps)]

def lock_batch(pointer,copier,verifier,fs,T):
    ps=raw_spans(pointer,fs,T);parsed=[structural(f) for f in fs]
    ns=[neural_reselect(verifier,p) for p in parsed]
    # Four routes: baseline, reject-only, learned reselect+proof, explicit
    # deterministic recovery. Rejection is not evidence of missing.
    choices={k:[] for k in ("baseline","strict","neural_recovery","hybrid")}
    for p,s,n in zip(parsed,ps,ns):
        choices["baseline"].append(s)
        choices["strict"].append(s if proof(p,s) else None)
        choices["neural_recovery"].append(s if proof(p,s) else n if n is not None and proof(p,n) else None)
        choices["hybrid"].append(s if proof(p,s) else p[1].get(p[0],(0,0)) if p is not None else None)
    out={}
    for route,spans in choices.items():
        fs2=[(f[0],s if s is not None else (0,0)) for f,s in zip(fs,spans)]
        pred=decode(copier,fs2,T);items=[]
        for f,p,s,original,(value,stop,positions) in zip(fs,parsed,spans,ps,pred):
            if s is None:items.append({"status":"reject","span":None,"value":None,"recovered":False});continue
            a,b=s;literal=T.decode(f[0][a:b+1]) if a else ""
            valid=stop and value==literal and positions==(list(range(a,b+1)) if a else [])
            valid=valid and (not a or (value.isascii() and value.isdigit() and 1<=len(value)<=5))
            if route!="baseline":valid=valid and proof(p,s)
            status=("present" if a else "missing") if valid else "reject"
            items.append({"status":status,"span":s,"value":value if status=="present" else None,"recovered":s!=original})
        out[route]=items
    out["neural_independent"]=[{"span":n,"correct":proof(p,n) if n is not None else False} for p,n in zip(parsed,ns)]
    return out

def fault_exam(T,rows):
    stats={"wrong_span":0,"partial":0,"false_missing":0,"wrong_present":0,"unsupported":0}
    rejected={k:0 for k in stats}
    for r in rows[:128]:
        for q in r["keys"]:
            f=pointer_module.frame(r["doc"],q,T,"Read",4);p=structural(f);req(p is not None,"STRUCTURAL")
            g=f[4];req(proof(p,g),"GOLD_PROOF")
            for k,s in p[1].items():
                if k==p[0]:continue
                kind="wrong_present" if g==(0,0) else "wrong_span"
                stats[kind]+=1;rejected[kind]+=int(not proof(p,s))
            if g!=(0,0):
                stats["false_missing"]+=1;rejected["false_missing"]+=int(not proof(p,(0,0)))
                if g[1]>g[0]:
                    stats["partial"]+=1;rejected["partial"]+=int(not proof(p,(g[0],g[1]-1)))
    bodies=['{"aa":1,"aa":2}','{"aa":{"bb":1}}','{"aa":"123"}','{"aa":-1}','{"aa":123456}','{"aa":01}','{"aa":1,}','{"aa":1}x','{"aa":1.0}','{"aa":true}','{"AA":1}','{"a":1}','{"aa":1,"bb":null}']
    for body in bodies:
        prefix="Find:aa\nJSON:";ids=T.encode(prefix+body,bos=True)
        f=(ids,len(T.encode("Find:",bos=True)),2,len(T.encode(prefix,bos=True)),(0,0))
        stats["unsupported"]+=1;rejected["unsupported"]+=int(structural(f) is None and not proof(structural(f),(0,0)))
    return {k:{"n":stats[k],"rejected":rejected[k]} for k in stats}
