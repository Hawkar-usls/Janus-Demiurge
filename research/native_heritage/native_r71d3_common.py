"""R71D3: learned byte-span pointer, no JSON parsing in model inference."""
from native_r71d2_common import *
import math

class SpanPointer(nn.Module):
    def __init__(self,base,rank=0,width=32):
        super().__init__()
        self.base=base.requires_grad_(False);self.base.eval();self.config=base.config
        d=self.config.d_model
        self.attention=nn.ModuleList(nn.ModuleList(LowRank(d,rank) for _ in range(3)) for _ in range(self.config.n_layers)) if rank else nn.ModuleList()
        self.q=nn.ModuleList(nn.Linear(d,width,bias=False) for _ in range(2))
        self.k=nn.ModuleList(nn.Linear(d,width,bias=False) for _ in range(2))
        self.scale=width**-0.5
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def hidden(self,idx):
        b,t=idx.shape;h=self.config.n_heads;d=self.config.d_model;w=d//h
        req(t<=self.config.context_length,"CONTEXT")
        x=self.base.token(idx)+self.base.pos(torch.arange(t,device=idx.device))[None,:,:]
        for i,layer in enumerate(self.base.blocks.layers):
            n=layer.norm1(x);a=layer.self_attn
            p=F.linear(n,a.in_proj_weight,a.in_proj_bias).chunk(3,dim=-1)
            if len(self.attention):p=[v+delta(n) for v,delta in zip(p,self.attention[i])]
            q,k,v=[z.reshape(b,t,h,w).transpose(1,2) for z in p]
            y=F.scaled_dot_product_attention(q,k,v,dropout_p=0.0,is_causal=True)
            x=x+a.out_proj(y.transpose(1,2).contiguous().reshape(b,t,d))
            x=x+layer.linear2(layer.activation(layer.linear1(layer.norm2(x))))
        return self.base.norm(x)
    def forward(self,idx,query_index,allowed):
        h=self.hidden(idx);q=h[torch.arange(h.shape[0],device=h.device),query_index]
        scores=[]
        for qp,kp in zip(self.q,self.k):
            logits=(kp(h)*qp(q)[:,None,:]).sum(-1)*self.scale
            scores.append(logits.masked_fill(~allowed,-1e9))
        return torch.stack(scores,dim=1)
    def adapter_state(self):
        return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,state):
        req(set(state)==set(self.adapter_state()),"ADAPTER_KEYS")
        merged=self.state_dict();merged.update(state);self.load_state_dict(merged,strict=True)

def make_pairs(spec,nums=None,exam=False):
    rng=random.Random(spec["seed"]);out=[];seen=set()
    keys_train=["a","b","p","q","low","high","red","blue","sun","moon","first","second","item","count","mass","rate","val","temp"]
    keys_exam=["iris","fern","lake","hill","fox","owl","ink","wax","mint","ruby","sand","coal","nova","lyra","pine","rose"]
    keys=keys_exam if exam else keys_train
    for i in range(spec["pairs"]):
        archive=not exam and i<spec["archive_pairs"]
        absent=(i//2)%4==0;ood=exam and i%2==1
        for _ in range(2000):
            n=3+(i%2)
            names=rng.sample(keys,n+1)
            if archive:
                chosen=rng.sample(nums,n);values=[x[2] for x in chosen];sources=[list(x) for x in chosen]
            else:
                values=[rng.randrange(1000,10000) if ood else rng.randrange(0,1000) for _ in range(n)];sources=[]
            if i%5==0:
                values[1]=values[0] # duplicate-valued decoy
                if archive:sources[1]=list(sources[0])
            doc=dict(zip(names[:n],values));doc=shuffled(doc,rng)
            a,b=rng.sample(names[:n],2)
            if absent:b=names[-1]
            if (i//16)%2:a,b=b,a
            verb=("Locate" if (i//8)%2 else "Find") if not exam else ("Read" if (i//8)%2 else "Find")
            ident=sha(canonical([doc,sorted([a,b]),verb]))
            if ident not in seen:seen.add(ident);break
        else:raise ValueError("PAIR_UNIQUE")
        out.append({"doc":doc,"targets":[a,b],"verb":verb,"ood":ood,"missing_pair":absent,"archive":archive,"sources":sources})
    return out

def render(doc,target,verb,T,erase=False):
    # Rendering/gold construction is outside inference. The neural model sees
    # raw bytes, end-of-query index, and document boundary mask ONLY.
    key="~"*len(target.encode("ascii")) if erase else target
    prefix=verb+":"+key+"\nJSON:"
    qindex=len(T.encode(verb+":"+key,bos=True))-1
    body="{";spans={}
    for k,v in doc.items():
        if len(body)>1:body+=","
        body+=json.dumps(k,ensure_ascii=True)+":"
        start=1+len((prefix+body).encode("ascii"))
        val=json.dumps(v,ensure_ascii=True,separators=(",",":"))
        body+=val;spans[k]=(start,start+len(val.encode("ascii"))-1)
    body+="}"
    ids=T.encode(prefix+body,bos=True)
    req(len(ids)<=128 and json.loads(body)==doc,"RENDER")
    start_doc=1+len(prefix.encode("ascii"))
    mask=[i==0 or start_doc<=i<len(ids) for i in range(len(ids))]
    gold=spans.get(target,(0,0))
    if target in doc:
        req(T.decode(ids[gold[0]:gold[1]+1])==str(doc[target]),"GOLD_BYTES")
        req(T.decode(ids[start_doc:gold[0]]).endswith(json.dumps(target)+":"),"GOLD_KEY")
    return ids,qindex,mask,gold

def batch_frames(frames):
    n=max(len(x[0]) for x in frames)
    return (torch.tensor([x+[0]*(n-len(x)) for x,_,_,_ in frames],dtype=torch.long),
            torch.tensor([q for _,q,_,_ in frames],dtype=torch.long),
            torch.tensor([m+[False]*(n-len(m)) for _,_,m,_ in frames],dtype=torch.bool),
            torch.tensor([g for _,_,_,g in frames],dtype=torch.long))
def predict(model,frames):
    # Gold is discarded before the model is called; no key/value matching,
    # parsing or value candidate mask at prediction time.
    idx,q,mask,_=batch_frames(frames)
    with torch.inference_mode():s=model(idx,q,mask)
    n=idx.shape[1];p=torch.arange(n);a=p[:,None];b=p[None,:]
    valid=((a==0)&(b==0))|((a>0)&(b>=a)&(b-a<8))
    v=s[:,0,:,None]+s[:,1,None,:]
    v=v.masked_fill(~(valid[None,:,:]&mask[:,:,None]&mask[:,None,:]),-1e9)
    ix=v.flatten(1).argmax(1).tolist()
    return [(i//n,i%n) for i in ix]

def training_frames(pairs,rng,T):
    out=[]
    for r in pairs:
        # Both queries, independently randomized field order; same source.
        for target in r["targets"]:
            out.append(render(shuffled(r["doc"],rng),target,r["verb"],T))
    return out
