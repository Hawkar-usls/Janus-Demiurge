"""R71D2 attention-only low-rank adapters on frozen native backbone."""
from native_r71d_common import *
import math

class LowRank(nn.Module):
    def __init__(self,d,r):
        super().__init__()
        self.down=nn.Linear(d,r,bias=False);self.up=nn.Linear(r,d,bias=False)
        nn.init.zeros_(self.up.weight)
    def forward(self,x):return self.up(self.down(x))

class AttentionAdapter(nn.Module):
    def __init__(self,base,rank):
        super().__init__()
        self.base=base.requires_grad_(False);self.base.eval();self.config=base.config
        self.adapters=nn.ModuleList(nn.ModuleList(LowRank(self.config.d_model,rank) for _ in range(3)) for _ in range(self.config.n_layers))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def forward(self,idx,targets=None):
        req(idx.ndim==2 and idx.shape[1]<=self.config.context_length,"CONTEXT")
        b,t=idx.shape;h=self.config.n_heads;d=self.config.d_model;w=d//h
        x=self.base.token(idx)+self.base.pos(torch.arange(t,device=idx.device))[None,:,:]
        for layer,ad in zip(self.base.blocks.layers,self.adapters):
            n=layer.norm1(x);a=layer.self_attn
            qkv=F.linear(n,a.in_proj_weight,a.in_proj_bias).chunk(3,dim=-1)
            q,k,v=[(p+delta(n)).reshape(b,t,h,w).transpose(1,2) for p,delta in zip(qkv,ad)]
            y=F.scaled_dot_product_attention(q,k,v,dropout_p=0.0,is_causal=True)
            x=x+a.out_proj(y.transpose(1,2).contiguous().reshape(b,t,d))
            x=x+layer.linear2(layer.activation(layer.linear1(layer.norm2(x))))
        z=self.base.lm_head(self.base.norm(x))
        loss=None if targets is None else F.cross_entropy(z.reshape(-1,z.size(-1)),targets.reshape(-1))
        return z,loss
    def adapter_state(self):return self.adapters.state_dict()
    def load_adapter(self,s):self.adapters.load_state_dict(s,strict=True)

def shuffled(doc,rng):
    items=list(doc.items());rng.shuffle(items);return dict(items)
def make_suite(seed,n,exam):
    rng=random.Random(seed);rows=[];seen=set()
    aliases=[("iris","fern"),("lake","hill"),("fox","owl"),("ink","wax")] if exam else [("a","b"),("p","q"),("first","second"),("low","high"),("sun","moon"),("red","blue")]
    for group in GROUPS:
        for i in range(n):
            for _ in range(2000):
                k,l=rng.choice(aliases)
                pool=range(301,400) if exam and i%2 else (range(10,100) if exam or i%2==0 else range(100,300))
                a,b=rng.sample(pool,2);doc={k:a,l:b}
                if group=="lookup":
                    q=("Return "+k+"." if exam else rng.choice(["Value of "+k+"?","Get "+k+".","Read "+k+"."]))
                    gold,alt=str(a),str(b);other={k:b,l:a}
                elif group=="addition":
                    q=("Total of "+k+" and "+l+"?" if exam else rng.choice([k+"+"+l+"?","Add "+k+" and "+l+".","Sum "+k+" and "+l+"."]))
                    gold,alt=str(a+b),str(a+b+1);other={k:a+1,l:b}
                elif group=="comparison":
                    q=(k+" greater than "+l+"? 1=yes,0=no." if exam else rng.choice([k+">"+l+"? 1=yes,0=no.","Is "+k+" larger than "+l+"? 1=yes,0=no."]))
                    gold,alt=str(int(a>b)),str(int(b>a));other={k:b,l:a}
                else:
                    target="spare" if exam else rng.choice(["extra","absent","third"])
                    q=("Return "+target+". ? if missing." if exam else "Get "+target+". ? if missing.")
                    gold,alt="?",str(a);other={**doc,target:a}
                key=sha(canonical([doc,q]))
                if key not in seen:seen.add(key);break
            else:raise ValueError("UNIQUE")
            opts=[gold,alt]
            for v in rng.sample(["?","0","1",str(a),str(b),str(a+b),"99999","7","8"],9):
                if v not in opts:opts.append(v)
                if len(opts)==4:break
            req(len(set(opts))==4,"OPTIONS");rng.shuffle(opts)
            r={"group":group,"doc":shuffled(doc,rng),"other":shuffled(other,rng),"q":q,"gold":gold,"alt":alt,"options":opts,"keys":[k,l],"ood":bool(exam and i%2)}
            if group=="missing":r["target"]=target
            req(oracle(r,r["doc"])==gold and oracle(r,r["other"])==alt,"ORACLE")
            rows.append(r)
    return rows
def oracle(r,doc):
    k,l=r["keys"]
    if r["group"]=="lookup":return str(doc[k])
    if r["group"]=="addition":return str(doc[k]+doc[l])
    if r["group"]=="comparison":return str(int(doc[k]>doc[l]))
    return str(doc.get(r["target"],"?"))
def paired_batch(rows,rng,T):
    seq=[]
    for r in rows:
        forced=bool(rng.randrange(2));opts=list(r["options"]);rng.shuffle(opts)
        for side in (0,1):
            v=task_pair(r,side);v={**v,"doc":shuffled(v["doc"],rng),"options":opts}
            seq.append(sequence(v,forced,T))
    n=max(len(x) for x,y in seq)
    return torch.tensor([x+[0]*(n-len(x)) for x,y in seq]),torch.tensor([y+[-100]*(n-len(y)) for x,y in seq])
