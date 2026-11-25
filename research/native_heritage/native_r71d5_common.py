"""R71D5: two-fact neural composition; frozen retrieval and explicit slots."""
from native_r71d4c_common import *
import native_r71d3c_common as pointer_module
import native_r71d4b_common as copy_module

def make_cases(spec,exam=False):
    rng=random.Random(spec["seed"]);rows=[];seen=set()
    for i in range(spec["pairs"]):
        ood=exam and i%2==1;missing=(i//2)%8==0;equal=(i//2)%8==1;near=(i//2)%8 in (2,3)
        lo,hi=(10000,100000) if ood else (0,10000)
        for _ in range(2000):
            a=rng.randrange(lo,hi);b=a if equal else (max(lo,min(hi-1,a+rng.choice([-1,1]))) if near else rng.randrange(lo,hi))
            if not equal and a==b:continue
            # Partition both orderings together, not individual operands.
            signature=sha(canonical(sorted([a,b])))
            if (int(signature[:8],16)%4==0)!=exam or signature in seen:continue
            seen.add(signature);break
        else:raise ValueError("PAIR_PARTITION")
        # Split aliases independently from values; decoy keys share no target.
        keys=[]
        while len(keys)<4:
            k=pointer_module.key(rng,exam,2,7 if ood else 5)
            if k not in keys:keys.append(k)
        ka,kb,dc,dd=keys
        doc={ka:a,kb:b,dc:rng.randrange(lo,hi),dd:rng.randrange(lo,hi)}
        if missing:doc.pop(ka if (i//16)%2 else kb)
        # Change one operand to reverse order, or introduce missing fact.
        changed=dict(doc)
        if missing:changed[ka]=a;changed[kb]=b
        elif equal:changed[ka]=a+1 if a<hi-1 else a-1
        else:changed[ka],changed[kb]=b,a
        rows.append({"keys":[ka,kb],"doc":shuffled(doc,rng),"changed":shuffled(changed,rng),"ood":ood,"missing":missing,"equal":equal,"near":near})
    return rows

def reference(values,descending):
    if any(v is None for v in values):return 2
    a,b=map(int,values)
    return int(a<b if descending else a>b)

def values_of(doc,keys):
    return [str(doc[k]) if k in doc else None for k in keys]

def operand_batch(values):
    # Neural input is ASCII byte sequence, right-aligned by byte length.
    # No conversion to int, no value sort or comparison.
    ids=[];length=[]
    for pair in values:
        v=[];n=[]
        for s in pair:
            bs=[] if s is None else list(s.encode("ascii"))
            req(len(bs)<=5 and all(48<=x<=57 for x in bs),"OPERAND_BYTES")
            v.append([0]*(5-len(bs))+bs);n.append(len(bs))
        ids.append(v);length.append(n)
    return torch.tensor(ids),torch.tensor(length)

class ComposeHead(nn.Module):
    """Learn per-position comparison and choose a two-source order.
    Native features and byte-only controls have identical dimensions.
    Numeric positional weighting is an explicit inductive bias, not a solver."""
    def __init__(self,base,byte_only=False):
        super().__init__();self.base=base.requires_grad_(False);self.base.eval();self.byte_only=byte_only
        self.emb=nn.Embedding(258,16);self.native=nn.Linear(base.config.d_model,16)
        self.digit=nn.Sequential(nn.Linear(32,32),nn.GELU(),nn.Linear(32,1))
        self.weights=nn.Parameter(torch.zeros(5));self.bias=nn.Parameter(torch.zeros(()))
        self.missing=nn.Sequential(nn.Linear(2,16),nn.GELU(),nn.Linear(16,1))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def forward(self,ids,length,descending):
        b=ids.shape[0];flat=ids.reshape(-1,5);e=self.emb(flat)
        if self.byte_only:h=torch.zeros_like(e)
        else:
            captured=[];hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(torch.cat([torch.full((flat.shape[0],1),256,dtype=torch.long,device=ids.device),flat],dim=1))
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN");h=self.native(captured[0][:,1:])
        digits=self.digit(torch.cat([e,h],-1)).squeeze(-1).reshape(b,2,5)
        # Missing leading positions share a learned zero symbol score.
        w=torch.exp(self.weights.clamp(-4,4))*torch.tensor([1.,.1,.01,.001,.0001],device=ids.device)
        value=(digits*w[None,None,:]).sum(-1)
        diff=value[:,0]-value[:,1]
        # Learned zero digit/padding consistency, direction and tied stable order.
        signed=torch.where(descending,-diff,diff)
        order=torch.stack([-signed+self.bias,signed-self.bias],-1)
        abstain=self.missing(length.float()/5).squeeze(-1)
        return torch.cat([order,abstain[:,None]],-1)
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,s):
        req(set(s)==set(self.adapter_state()),"KEYS");d=self.state_dict();d.update(s);self.load_state_dict(d,strict=True)

def examples(rows):
    for r in rows:
        for variant in ("doc","changed"):
            for descending in (False,True):
                yield r,variant,descending

def train_batch(rows):
    vals=[];dirs=[];labels=[]
    for r,variant,d in examples(rows):
        v=values_of(r[variant],r["keys"]);vals.append(v);dirs.append(d);labels.append(reference(v,d))
    ids,l=operand_batch(vals);return ids,l,torch.tensor(dirs,dtype=torch.bool),torch.tensor(labels)
def predict_order(model,values,dirs):
    ids,l=operand_batch(values)
    with torch.inference_mode():return model(ids,l,torch.tensor(dirs,dtype=torch.bool)).argmax(-1).tolist()
def compose(values,choice):
    if choice==2 or any(x is None for x in values):return None
    return values if choice==0 else list(reversed(values))
