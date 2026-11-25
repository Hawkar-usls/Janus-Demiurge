"""Bounded native MEMORY LOCK task and adapter utilities."""
from native_r71c_common import *
from torch import nn
import torch.nn.functional as F
def frozen_digest(m):
    h=hashlib.sha256()
    for name,t in sorted(m.state_dict().items()):
        h.update(name.encode());h.update(str(t.dtype).encode());h.update(str(tuple(t.shape)).encode());h.update(t.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
class RoutedAdapter(nn.Module):
    """Explicit task-mode residual at final hidden state; never alters native weights."""
    def __init__(self,base,rank):
        super().__init__();self.base=base
        self.base.requires_grad_(False);self.base.eval()
        self.down=nn.Linear(base.config.d_model,rank,bias=False)
        self.up=nn.Linear(rank,base.config.d_model,bias=False)
        nn.init.zeros_(self.up.weight)
        self.config=base.config
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def forward(self,idx,targets=None):
        # No persistent hooks or changes to base model. Capture exact final
        # hidden state for this call only; the parent remains eval/frozen.
        captured=[]
        handle=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
        try:
            with torch.no_grad():self.base(idx)
        finally:handle.remove()
        req(len(captured)==1,"HIDDEN_CAPTURE")
        h=captured[0];z=self.base.lm_head(h+self.up(F.gelu(self.down(h))))
        loss=None if targets is None else F.cross_entropy(z.reshape(-1,z.size(-1)),targets.reshape(-1))
        return z,loss
    def adapter_state(self):return {"down":self.down.state_dict(),"up":self.up.state_dict()}
    def load_adapter(self,state):
        self.down.load_state_dict(state["down"],strict=True);self.up.load_state_dict(state["up"],strict=True)
def make_pair(r):
    if r["other"] is not None:return r
    doc=dict(r["doc"]);v=next(iter(doc.values()));other={**doc,"absent":v}
    opts=list(r["options"]);alt=str(v)
    if alt not in opts:
        j=next(i for i,o in enumerate(opts) if o!=r["gold"]);opts[j]=alt
    return {**r,"options":opts,"other":other,"alt":alt}
def pair_rows(old):
    out=[]
    for r in old:
        p=make_pair(r)
        out.extend([p,{**p,"doc":p["other"],"gold":p["alt"],"other":p["doc"],"alt":p["gold"]}])
    return out
def fresh_suite(ex):
    rng=random.Random(ex["seed"]);rows=[];seen=set()
    for group in GROUPS:
        for i in range(ex["cases_per_group"]):
            for _ in range(1000):
                k,l=rng.choice([("mars","venus"),("east","west"),("alpha","beta"),("cat","dog")])
                a,b=rng.sample(range(201,300),2);doc={k:a,l:b}
                if group=="lookup":q="Read "+k+".";g=str(a);v=str(b);other={k:b,l:a}
                elif group=="addition":q="Sum "+k+" and "+l+".";g=str(a+b);v=str(a+b+1);other={k:a+1,l:b}
                elif group=="comparison":q="Is "+k+">"+l+"? 1=yes,0=no.";g=str(int(a>b));v=str(int(b>a));other={k:b,l:a}
                else:q="Read extra. ? if missing.";g="?";v=str(a);other={**doc,"extra":a}
                key=sha(canonical([doc,q]))
                if key not in seen:seen.add(key);break
            else:raise ValueError("FRESH_UNIQUE")
            opts=options(g,v,rng,i)
            rows.append({"group":group,"doc":doc,"q":q,"gold":g,"options":opts,"other":other,"alt":v,"keys":[k,l]})
    return rows
def exact_new(r,doc):
    k,l=r["keys"]
    if r["group"]=="lookup":return str(doc[k])
    if r["group"]=="addition":return str(doc[k]+doc[l])
    if r["group"]=="comparison":return str(int(doc[k]>doc[l]))
    return str(doc.get("extra","?"))
def varied_train(rows):
    out=[]
    for i,r in enumerate(rows):
        d=r["doc"];k,l=list(d)[:2];q=r["q"]
        if i%2:
            if r["group"]=="lookup":q="Get "+k+"."
            elif r["group"]=="addition":q="Add "+k+" and "+l+"."
            elif r["group"]=="comparison":q="Is "+k+" larger than "+l+"? 1=yes,0=no."
            else:q="Get absent. ? if unavailable."
        out.append({**r,"q":q})
    return out
def task_pair(r,swap):
    if not swap:return r
    return {**r,"doc":r["other"],"gold":r["alt"],"other":r["doc"],"alt":r["gold"]}
