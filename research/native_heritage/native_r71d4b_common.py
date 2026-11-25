"""R71D4B: learned source-position and stop scores, explicit evidence spans."""
from native_r71d4_common import *
import string,datetime

def partition(payload):
    return int(sha(payload.encode("ascii"))[:8],16)%4==0
def payload_for(rng,kind,n,i):
    if kind=="date":
        return str(datetime.date(rng.randint(1900,2099),1,1)+datetime.timedelta(days=rng.randrange(365)))
    alphabet={"digits":string.digits,"letters":string.ascii_letters,"identifier":string.ascii_letters+string.digits+"_-","repeat":string.ascii_letters+string.digits}[kind]
    if kind=="repeat":
        pattern="".join(rng.choice(alphabet) for _ in range(1+i%3))
        return (pattern*((n+len(pattern)-1)//len(pattern)))[:n]
    return "".join(rng.choice(alphabet) for _ in range(n))
def suite(spec,exam=False):
    rng=random.Random(spec["seed"]);rows=[];seen=set()
    kinds=("digits","letters","date","identifier","repeat","missing")
    for i in range(spec["cases"]):
        kind=kinds[i%6];j=i//6
        if kind=="missing":n=0
        elif kind=="date":n=10
        elif exam and j%2:n=25+(j//2)%8
        else:n=1+(j//2)%24 if exam else 1+j%24
        # The frozen hash partition has no single ASCII digit in exam.
        # Substitute length two only for this empty exam stratum; train unchanged.
        if exam and kind=="digits" and n==1 and not any(partition(c) for c in string.digits):n=2
        # Different payload hash partitions, not just different random seeds.
        for attempt in range(2000):
            payload="" if kind=="missing" else payload_for(rng,kind,n,j+attempt)
            if kind=="missing" or partition(payload)==exam:break
        else:raise ValueError("PAYLOAD_PARTITION")
        padding="".join(rng.choice(string.ascii_letters+string.digits) for _ in range(rng.randrange(2,25)))
        suffix="".join(rng.choice(string.ascii_letters) for _ in range(rng.randrange(2,15)))
        style=rng.randrange(3)
        row={"kind":kind,"payload":payload,"padding":padding,"suffix":suffix,"style":style,"swap":bool(rng.randrange(2)),"ood":n>24}
        identity=sha(canonical(row));req(identity not in seen,"DUPLICATE");seen.add(identity);rows.append(row)
    return rows
def render(r,T,shift=False):
    gap=(" ", "", "\t")[r["style"]]
    decoy=r["padding"];other=r["suffix"]
    if shift:decoy="xX09"+decoy;other="Z"+other
    target=r["payload"];prefix="Copy:target\nJSON:{"
    first='"note":'+gap+json.dumps(decoy)+","
    last='"tail":'+gap+json.dumps(other)
    middle='"target":'+gap+'"'+target+'",'
    if r["kind"]=="missing":
        text=prefix+first+last+"}";span=(0,0)
    else:
        lead=prefix+(first if r["swap"] else "")+'"target":'+gap+'"'
        s=len(T.encode(lead,bos=True));span=(s,s+len(target)-1)
        text=lead+target+'",'+("" if r["swap"] else first)+last+"}"
    ids=T.encode(text,bos=True);req(len(ids)<=128,"FRAME_FIT")
    req((T.decode(ids[span[0]:span[1]+1]) if span[0] else "")==target,"RENDER_GOLD")
    return ids,span
def tensorize(frames,teacher=False):
    t=max(len(ids) for ids,sp in frames);x=[];spans=[];labels=[]
    for ids,(s,e) in frames:
        x.append(ids+[0]*(t-len(ids)));spans.append([s,e])
        n=e-s+1 if s else 0
        if teacher:labels.append((list(range(s+1,e+2)) if s else [])+[0]+[-100]*(32-n))
    return torch.tensor(x),torch.tensor(spans),torch.tensor(labels) if teacher else None

class InvariantCopy(nn.Module):
    """Learn position/stop scoring. Relative arm has an explicit alignment
    inductive bias; it does not hard-code a next-position selection."""
    def __init__(self,base,byte_only=False,relative=True):
        super().__init__();self.base=base.requires_grad_(False);self.base.eval()
        self.byte_only=byte_only;self.relative=relative
        self.emb=nn.Embedding(258,16);self.proj=nn.Linear(base.config.d_model,16)
        self.content=nn.Linear(32,16);self.align=nn.Sequential(nn.Linear(5,32),nn.GELU(),nn.Linear(32,1))
        self.stop=nn.Sequential(nn.Linear(4,32),nn.GELU(),nn.Linear(32,1))
        self.query=nn.Linear(2,16);self.scale=nn.Parameter(torch.tensor(.05))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def features(self,idx):
        e=self.emb(idx)
        if self.byte_only:h=torch.zeros_like(e)
        else:
            captured=[];hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(idx)
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN");h=self.proj(captured[0])
        return self.content(torch.cat([e,h],dim=-1))
    def score(self,features,spans,steps):
        b,t,_=features.shape;dev=features.device;S=len(steps)
        pos=torch.arange(t,device=dev).float()[None,None,:].expand(b,S,t)
        step=steps.float()[None,:,None].expand(b,S,t)
        start=spans[:,0,None,None].float();end=spans[:,1,None,None].float()
        n=torch.where(start>0,end-start+1,torch.zeros_like(start))
        rel=pos-start;left=end-pos
        if self.relative:
            delta=rel-step
            f=torch.stack([delta/8,delta.abs()/8,rel/32,left/32,(n-step).expand_as(pos)/32],dim=-1)
            remain=(n-step[:,:,0:1]).squeeze(-1)
            eos=torch.stack([remain/8,remain.abs()/8,steps.float()[None,:].expand(b,-1)/32,n.squeeze(-1).expand(b,S)/32],-1)
        else:
            f=torch.stack([pos/128,step/32,start.expand_as(pos)/128,end.expand_as(pos)/128,n.expand_as(pos)/32],-1)
            eos=torch.stack([steps.float()[None,:].expand(b,-1)/32,n.squeeze(-1).expand(b,S)/32,start.squeeze(-1).expand(b,S)/128,end.squeeze(-1).expand(b,S)/128],-1)
        q=self.query(torch.stack([step[:,:,0]/32,n.squeeze(-1).expand(b,S)/32],-1))
        z=self.align(f).squeeze(-1)+self.scale*torch.einsum("bsd,btd->bst",q,features)/4
        allowed=(start>0)&(pos>=start)&(pos<=end)
        return torch.cat([self.stop(eos),z.masked_fill(~allowed,-1e9)],-1)
    def forward(self,idx,spans,steps):return self.score(self.features(idx),spans,steps)
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,s):
        req(set(s)==set(self.adapter_state()),"KEYS");state=self.state_dict();state.update(s);self.load_state_dict(state,strict=True)
def decode(m,frames,T):
    x,sp,_=tensorize(frames);out=[[] for _ in frames];positions=[[] for _ in frames];done=[False]*len(frames)
    with torch.inference_mode():
        z=m(x,sp,torch.arange(33)).argmax(-1).tolist()
    for i,pred in enumerate(z):
        for k in pred:
            if k==0:done[i]=True;break
            positions[i].append(k-1);out[i].append(int(x[i,k-1]))
    return [(T.decode(v),ok,p) for v,ok,p in zip(out,done,positions)]
