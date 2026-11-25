"""R71D4: neural copying from explicit evidence; never invent bytes."""
from native_r71d3c_common import *
class CopyHead(nn.Module):
    def __init__(self,base,byte_only=False):
        super().__init__();self.base=base.requires_grad_(False);self.base.eval();self.byte_only=byte_only
        self.emb=nn.Embedding(258,24);self.pos=nn.Embedding(128,16);self.step=nn.Embedding(8,16)
        self.proj=nn.Linear(base.config.d_model,24);self.key=nn.Linear(64,32)
        self.query=nn.Sequential(nn.Linear(16+24,32),nn.GELU(),nn.Linear(32,32))
        self.eos=nn.Linear(32,1)
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def features(self,idx):
        b,t=idx.shape;e=self.emb(idx)
        if self.byte_only:h=torch.zeros_like(e)
        else:
            captured=[];hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(idx)
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN");h=self.proj(captured[0])
        return e,self.key(torch.cat([e,h,self.pos(torch.arange(t,device=idx.device))[None,:,:].expand(b,-1,-1)],-1))
    def forward(self,idx,spans,previous):
        # Input consists of bytes, selected evidence boundaries, and prior
        # emitted byte. No parsed key/value or target answer in inference.
        b,t=idx.shape;dev=idx.device
        e,h=self.features(idx)
        q=self.query(torch.cat([self.step(torch.arange(previous.shape[1],device=dev))[None,:,:].expand(b,-1,-1),self.emb(previous)],-1))
        z=torch.einsum("bsd,btd->bst",q,h)/32**.5
        # relative-position features learned via shared position embeddings;
        # allow only positions in cited span. Missing evidence allows EOS only.
        # Recompute position contribution relative to span start, not document origin.
        absolute=self.pos(torch.arange(t,device=dev))
        relative=self.pos((torch.arange(t,device=dev)[None,:]-spans[:,0,None]).clamp(0,127))
        delta=self.key.weight[:,48:] 
        z=z+torch.einsum("bsd,btd->bst",q,F.linear(relative-absolute[None,:,:],delta))/32**.5
        p=torch.arange(t,device=dev)[None,:]
        allowed=(spans[:,0,None]>0)&(p>=spans[:,0,None])&(p<=spans[:,1,None])
        return torch.cat([self.eos(q),z.masked_fill(~allowed[:,None,:],-1e9)],-1)
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,s):
        req(set(s)==set(self.adapter_state()),"KEYS");d=self.state_dict();d.update(s);self.load_state_dict(d,strict=True)

def copy_batch(frames,spans):
    t=max(len(f[0]) for f in frames);xs=[];prev=[];labels=[]
    for f,(s,e) in zip(frames,spans):
        ids=f[0];v=ids[s:e+1] if s>0 else []
        req(len(v)<=5,"MAX_COPY")
        xs.append(ids+[0]*(t-len(ids)))
        prev.append([256]+v+[0]*(5-len(v)))
        labels.append((list(range(s+1,e+2)) if s>0 else [])+[0]+[-100]*(5-len(v)))
    return torch.tensor(xs),torch.tensor(spans),torch.tensor(prev),torch.tensor(labels)
def copy_decode(m,frames,spans,T):
    # No oracle labels are supplied. Autoregressive decoder chooses byte
    # positions or EOS; raw evidence is used only to realize chosen bytes.
    t=max(len(f[0]) for f in frames);idx=torch.tensor([f[0]+[0]*(t-len(f[0])) for f in frames]);sp=torch.tensor(spans)
    prev=torch.full((len(frames),1),256,dtype=torch.long);done=[False]*len(frames);out=[[] for _ in frames];terminated=[False]*len(frames)
    with torch.inference_mode():
        for _ in range(6):
            z=m(idx,sp,prev)[:,-1].argmax(-1).tolist();next_ids=[]
            for i,k in enumerate(z):
                if done[i] or k==0:
                    if not done[i]:terminated[i]=True
                    done[i]=True;next_ids.append(256)
                else:
                    byte=int(idx[i,k-1]);out[i].append(byte);next_ids.append(byte)
            prev=torch.cat([prev,torch.tensor(next_ids)[:,None]],1)
            if all(done):break
    return [(T.decode(v),ok) for v,ok in zip(out,terminated)]
def literal(f,span,T):
    s,e=span
    return T.decode(f[0][s:e+1]) if s>0 else ""
def normalize(f,T):
    # Reversible lexical whitespace removal outside JSON strings. No JSON
    # parser or key search. Preserve byte offset map and query prefix.
    ids,qs,ql,ds,gold=f;new=ids[:ds];mapping=list(range(ds));quoted=False;escape=False
    for i in range(ds,len(ids)):
        c=ids[i]
        if not quoted and c in (9,10,13,32):continue
        new.append(c);mapping.append(i)
        if quoted:
            if escape:escape=False
            elif c==92:escape=True
            elif c==34:quoted=False
        elif c==34:quoted=True
    req(not quoted,"STRING_BOUNDARY")
    return (new,qs,ql,ds,(0,0)),mapping
