"""R71D6: learned local decimal transition and explicit recurrent assembly."""
from native_r71d5_common import *

def local_states():
    return torch.cartesian_prod(torch.arange(2),torch.arange(2),torch.arange(10),torch.arange(10))
def transition_gold(x):
    # Training and reference only; joint class = carry/borrow*10 + digit.
    op,c,a,b=x.unbind(-1)
    add=a+b+c;sub=a-b-c
    return torch.where(op==0,(add>=10).long()*10+add%10,(sub<0).long()*10+sub%10)
class ArithmeticHead(nn.Module):
    def __init__(self,base,byte_only=False):
        super().__init__();self.base=base.requires_grad_(False);self.base.eval();self.byte_only=byte_only
        self.emb=nn.Embedding(258,16);self.native=nn.Linear(base.config.d_model,16)
        self.op=nn.Embedding(2,8);self.carry=nn.Embedding(2,8)
        self.net=nn.Sequential(nn.Linear(80,128),nn.GELU(),nn.Linear(128,128),nn.GELU(),nn.Linear(128,20))
    def train(self,mode=True):
        super().train(mode);self.base.eval();return self
    def table(self):
        digits=torch.arange(48,58,device=self.emb.weight.device);e=self.emb(digits)
        if self.byte_only:h=torch.zeros_like(e)
        else:
            captured=[];hook=self.base.norm.register_forward_hook(lambda mod,inp,out:captured.append(out))
            try:
                with torch.no_grad():self.base(torch.stack([torch.full_like(digits,256),digits],-1))
            finally:hook.remove()
            req(len(captured)==1,"HIDDEN");h=self.native(captured[0][:,-1])
        return torch.cat([e,h],-1)
    def forward(self,x):
        op,c,a,b=x.unbind(-1);t=self.table()
        return self.net(torch.cat([t[a],t[b],self.op(op),self.carry(c)],-1))
    def adapter_state(self):return {k:v for k,v in self.state_dict().items() if not k.startswith("base.")}
    def load_adapter(self,s):
        req(set(s)==set(self.adapter_state()),"KEYS");d=self.state_dict();d.update(s);self.load_state_dict(d,strict=True)

def training_trace(rows):
    result=[]
    for r,variant,op in examples(rows):
        v=values_of(r[variant],r["keys"])
        if any(s is None for s in v):continue
        a,b=v;n=max(len(a),len(b))
        if op and int(a)<int(b):a,b=b,a
        c=0
        for x,y in zip(reversed(a.zfill(n)),reversed(b.zfill(n))):
            state=[int(op),c,int(x),int(y)];result.append(state)
            c=int(transition_gold(torch.tensor([state]))[0])//10
    return torch.tensor(result,dtype=torch.long)
def learned_table(m):
    states=local_states()
    with torch.inference_mode():p=m(states).argmax(-1)
    return p.reshape(2,2,10,10),{"n":400,"exact":int((p==transition_gold(states)).sum()),"add_exact":int((p[:200]==transition_gold(states)[:200]).sum()),"sub_exact":int((p[200:]==transition_gold(states)[200:]).sum()),"local_pairs_seen_in_training":True}
def recurrence(table,a,b,op):
    # Assembly reads learned digit and next carry/borrow classes, not
    # numeric addition or subtraction. ASCII zero padding is explicit.
    n=max(len(a),len(b));c=0;out=[]
    for x,y in zip(reversed(a.zfill(n)),reversed(b.zfill(n))):
        cls=int(table[op,c,ord(x)-48,ord(y)-48]);c,d=divmod(cls,10);out.append(chr(48+d))
    if op==0 and c:out.append(chr(48+c))
    return "".join(reversed(out)).lstrip("0") or "0",c
def arithmetic(table,values,op):
    if any(v is None for v in values):return None
    a,b=values;req(all(1<=len(s)<=8 and s.isascii() and s.isdigit() for s in (a,b)),"OPERAND")
    out,c=recurrence(table,a,b,op)
    if op==1 and c:
        out,borrow=recurrence(table,b,a,op)
        if borrow:return None
        return "-"+out if out!="0" else "0"
    return out
def exact_reference(v,op):
    if any(s is None for s in v):return None
    a,b=map(int,v);return str(a-b if op else a+b)
def chain_suite(seed):
    rng=random.Random(seed);rows=[]
    for i in range(256):
        n=5+i%4;k=rng.randrange(1,10)
        a,b=(str(10**n-1),str(k)) if (i//4)%2==0 else (str(10**(n-1)),str(k))
        if (i//8)%2:a,b=b,a
        # Some cases require long carry or borrow, others are arbitrary.
        if (i//16)%2:a,b=str(rng.randrange(10**(n-1),10**n)),str(rng.randrange(10**(n-1),10**n))
        rows.append([a,b])
    return rows
