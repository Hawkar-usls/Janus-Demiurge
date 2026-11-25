"""R71D3B: learned query-byte alignment and joint span localization."""
from native_r71d3_common import *
import string

def key_partition(k):
    return int(sha(k.encode("ascii"))[:8],16)%4==0
def key(rng,exam,lo,hi):
    for _ in range(5000):
        k="".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(lo,hi)))
        if key_partition(k)==exam:return k
    raise ValueError("KEY_PARTITION")
def pairs(spec,nums=None,exam=False):
    rng=random.Random(spec["seed"]);out=[];seen=set()
    for i in range(spec["pairs"]):
        archive=not exam and i<spec["archive_pairs"]
        ood=exam and i%2==1;missing=(i//2)%4==0
        for _ in range(1000):
            n=3+(i//8)%2
            names=[]
            while len(names)<n:
                k=key(rng,exam,6 if ood else 2,7 if ood else 5)
                if k not in names:names.append(k)
            if archive:
                vals=rng.sample(nums,n);values=[v[2] for v in vals];sources=[list(v) for v in vals]
            else:
                values=[rng.randrange(10000,100000) if ood else rng.randrange(0,10000) for _ in names];sources=[]
            if i%5==0:
                values[1]=values[0]
                if archive:sources[1]=list(sources[0])
            doc=shuffled(dict(zip(names,values)),rng);a,b=rng.sample(names,2)
            if missing:
                for _ in range(500):
                    j=rng.randrange(len(b));candidate=b[:j]+rng.choice(string.ascii_lowercase)+b[j+1:]
                    if candidate not in names and key_partition(candidate)==exam:b=candidate;break
                else:b=key(rng,exam,2,7)
                if b in names:continue
            if (i//16)%2:a,b=b,a
            ident=sha(canonical([doc,sorted([a,b])]))
            if ident not in seen:seen.add(ident);break
        else:raise ValueError("PAIR_UNIQUE")
        out.append({"doc":doc,"targets":[a,b],"archive":archive,"ood":ood,"missing_pair":missing,"sources":sources})
    return out

def frame(doc,target,T,verb="Find",style=0,erase=False):
    # Only a raw byte prompt plus explicit query/document boundaries enters inference.
    q="~"*len(target) if erase else target
    prefix=verb+":"+q+"\nJSON:"
    qstart=1+len((verb+":").encode("ascii"))
    body="{";spans={}
    for k,v in doc.items():
        if len(body)>1:body+=","+(" " if style else "")
        body+=json.dumps(k)+(" : " if style==2 else ": " if style==1 else ":")
        begin=1+len((prefix+body).encode("ascii"))
        value=json.dumps(v);body+=value;spans[k]=(begin,begin+len(value)-1)
    body+="}"
    ids=T.encode(prefix+body,bos=True);ds=1+len(prefix.encode("ascii"))
    req(len(ids)<=128 and json.loads(body)==doc and 1<=len(q)<=7,"FRAME")
    gold=spans.get(target,(0,0))
    if target in doc:req(T.decode(ids[gold[0]:gold[1]+1])==str(doc[target]),"GOLD")
    return ids,qstart,len(q),ds,gold

def batch(frames):
    n=max(len(f[0]) for f in frames)
    return (torch.tensor([f[0]+[0]*(n-len(f[0])) for f in frames]),
            torch.tensor([f[1] for f in frames]),torch.tensor([f[2] for f in frames]),
            torch.tensor([[j>=f[3] and j<len(f[0]) for j in range(n)] for f in frames]),
            torch.tensor([f[4] for f in frames]))

class GroundedPointer(nn.Module):
    """Shared learned byte matching + local convolution + optional frozen features."""
    def __init__(self,base,byte_only=False):
        super().__init__()
        self.base=base.requires_grad_(False);self.base.eval();self.byte_only=byte_only
        self.emb=nn.Embedding(258,24)
        self.local=nn.Conv1d(24,32,7,padding=3)
        self.proj=nn.Linear(base.config.d_model,32)
        self.head=nn.Sequential(nn.Linear(32+32+9,64),nn.GELU(),nn.Linear(64,2))
        self.absent=nn.Sequential(nn.Linear(9,32),nn.GELU(),nn.Linear(32,2))
        self.length_bias=nn.Parameter(torch.zeros(5))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def forward(self,idx,qs,ql,doc):
        b,t=idx.shape;dev=idx.device;pos=torch.arange(t,device=dev)
        e=self.emb(idx);norm=F.normalize(e,dim=-1)
        j=torch.arange(7,device=dev);shift=torch.arange(9,device=dev)
        qidx=(qs[:,None]+j[None,:]).clamp(0,t-1)
        q=norm.gather(1,qidx[:,:,None].expand(-1,-1,norm.shape[-1]))
        sim=torch.einsum("btd,bjd->btj",norm,q)
        # Learn alignment offsets, not a hard-coded JSON grammar: score all
        # possible byte starts and all 1..5 byte lengths.
        offsets=pos[None,:,None,None]-ql[:,None,None,None]-shift[None,None,:,None]+j[None,None,None,:]
        valid=(offsets>=0)&(offsets<t)
        ix=offsets.clamp(0,t-1)
        aligned=sim[:,:,None,:].expand(-1,-1,9,-1).gather(1,ix)
        from_doc=doc[:, :,None,None].expand(-1,-1,9,7).gather(1,ix)
        qmask=j[None,None,None,:]<ql[:,None,None,None]
        aligned=aligned.masked_fill(~(valid&from_doc),-1)
        match=(aligned*qmask).sum(-1)/ql[:,None,None]
        match=match.masked_fill(~doc[:,:,None],-1)
        if self.byte_only:
            features=torch.zeros(b,t,32,device=dev)
        else:
            captured=[]
            hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(idx)
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN")
            features=self.proj(captured[0])
        local=self.local(e.transpose(1,2)).transpose(1,2)
        logits=self.head(torch.cat([local,features,match],dim=-1))
        missing=self.absent(match.max(1).values)
        # Missing sentinel at BOS. All document bytes are eligible; no
        # digit masks, field matching, or parsed candidate values.
        s=logits[:,:,0];end=logits[:,:,1]
        lengths=torch.arange(5,device=dev)
        ep=pos[:,None]+lengths[None,:];safe=ep.clamp(max=t-1)
        joint=s[:,:,None]+end[:,safe]+self.length_bias[None,None,:]
        allowed=doc[:,:,None]&doc[:,safe]&(ep[None,:,:]<t)
        joint=joint.masked_fill(~allowed,-1e9)
        sentinel=missing.sum(-1)
        flat=joint.flatten(1)
        return torch.cat([sentinel[:,None],flat],dim=1)
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,state):
        req(set(state)==set(self.adapter_state()),"ADAPTER_KEYS")
        merged=self.state_dict();merged.update(state);self.load_state_dict(merged,strict=True)

def label(g):
    return torch.where(g[:,0]==0,0,1+g[:,0]*5+g[:,1]-g[:,0])
def predict(m,frames):
    idx,qs,ql,doc,_=batch(frames)
    with torch.inference_mode():p=m(idx,qs,ql,doc).argmax(-1).tolist()
    return [(0,0) if x==0 else ((x-1)//5,(x-1)//5+(x-1)%5) for x in p]
def train_frames(rows,rng,T):
    frames=[]
    for r in rows:
        for target in r["targets"]:
            frames.append(frame(shuffled(r["doc"],rng),target,T,verb=rng.choice(["Find","Get"]),style=rng.randrange(2)))
    return frames
