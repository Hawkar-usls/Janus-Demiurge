"""R71D5B: learned local digit relation + explicit lexicographic reduction."""
from native_r71d5_common import *

class ComposeHead(nn.Module):
    def __init__(self,base,byte_only=False):
        super().__init__();self.base=base.requires_grad_(False);self.base.eval();self.byte_only=byte_only
        self.emb=nn.Embedding(258,16);self.native=nn.Linear(base.config.d_model,16)
        self.rel=nn.Sequential(nn.Linear(64,64),nn.GELU(),nn.Linear(64,3))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def digit_table(self):
        # Each digit receives the same two-token context; no positional
        # leakage or direct numeric value supplied to the neural head.
        dev=self.emb.weight.device;digits=torch.arange(48,58,device=dev)
        e=self.emb(digits)
        if self.byte_only:h=torch.zeros_like(e)
        else:
            captured=[];hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(torch.stack([torch.full_like(digits,256),digits],-1))
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN");h=self.native(captured[0][:,-1])
        return torch.cat([e,h],-1)
    def local(self,ids):
        # ASCII zero padding is a declared representation choice; no
        # comparison of numeric values is performed by inference code.
        idx=torch.where(ids==0,torch.full_like(ids,48),ids)-48
        table=self.digit_table()
        a,b=table[idx[:,0]],table[idx[:,1]]
        return self.rel(torch.cat([a,b],-1))
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,s):
        req(set(s)==set(self.adapter_state()),"KEYS");d=self.state_dict();d.update(s);self.load_state_dict(d,strict=True)

def local_gold(ids):
    # Training/reference only. 0=less, 1=equal, 2=greater.
    x=torch.where(ids==0,torch.full_like(ids,48),ids)
    a,b=x[:,0],x[:,1]
    return (a>=b).long()+(a>b).long()

def all_local():
    x=torch.arange(48,58)
    return torch.cartesian_prod(x,x).reshape(100,2,1)

def predict_order(model,values,dirs):
    ids,length=operand_batch(values)
    with torch.inference_mode():relations=model.local(ids).argmax(-1)
    out=[]
    for rel,l,d in zip(relations.tolist(),length.tolist(),dirs):
        if min(l)==0:out.append(2);continue
        # Explicit deterministic aggregation of learned local classes.
        # Ascending/descending stable tie preserves original source order.
        first=next((r for r in rel if r!=1),1)
        out.append(int(first==0 if d else first==2))
    return out

def local_report(m):
    x=all_local();gold=local_gold(x).flatten()
    with torch.inference_mode():p=m.local(x).argmax(-1).flatten()
    mat=torch.zeros(3,3,dtype=torch.long)
    for a,b in zip(gold.tolist(),p.tolist()):mat[a,b]+=1
    return {"n":100,"exact":int((p==gold).sum()),"confusion":mat.tolist(),"training_pairs_seen":True}
