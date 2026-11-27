"""JANUS R1.17: NumPy array math, explicit reverse pass; no ML framework.

Implements the pinned JanusTinyTransformer evaluation-mode architecture.
No archive import, pickle, network access, dropout, or production integration.
The legacy MicroGPT scalar graph is provenance/inspiration, not a compatible
checkpoint format. This module deliberately differentiates normalization
and softmax in full, and shares the embedding and output parameter.
"""
import hashlib
import math
import numpy as np

VOCAB, WIDTH, CONTEXT, HEADS, LAYERS, FF = 258, 128, 128, 4, 2, 512
EPS = 1e-5

def require(ok, msg):
    if not ok:
        raise RuntimeError(msg)

def shapes():
    out = {"token.weight": (VOCAB, WIDTH), "pos.weight": (CONTEXT, WIDTH),
           "norm.weight": (WIDTH,), "norm.bias": (WIDTH,)}
    for i in range(LAYERS):
        p = f"blocks.layers.{i}."
        out.update({p+"self_attn.in_proj_weight": (3*WIDTH, WIDTH),
                    p+"self_attn.in_proj_bias": (3*WIDTH,),
                    p+"self_attn.out_proj.weight": (WIDTH, WIDTH),
                    p+"self_attn.out_proj.bias": (WIDTH,),
                    p+"linear1.weight": (FF, WIDTH), p+"linear1.bias": (FF,),
                    p+"linear2.weight": (WIDTH, FF), p+"linear2.bias": (WIDTH,),
                    p+"norm1.weight": (WIDTH,), p+"norm1.bias": (WIDTH,),
                    p+"norm2.weight": (WIDTH,), p+"norm2.bias": (WIDTH,)})
    return out

def seal(state):
    h = hashlib.sha256()
    for k, a in sorted(state.items()):
        a = np.ascontiguousarray(a)
        h.update(repr((k, a.dtype.str, a.shape)).encode()+b"\0")
        h.update(a.tobytes())
    return h.hexdigest()

def validate(weights):
    require(set(weights)==set(shapes()), "PARAMETER_NAMES")
    for k,s in shapes().items():
        a=weights[k]
        require(a.shape==s and a.dtype==np.float64 and np.isfinite(a).all(), "PARAMETER:"+k)

def softmax(x):
    a=np.exp(x-np.max(x,axis=-1,keepdims=True))
    return a/a.sum(axis=-1,keepdims=True)

def layer_norm(x,g,b):
    centered=x-x.mean(axis=-1,keepdims=True)
    inv=1/np.sqrt((centered**2).mean(axis=-1,keepdims=True)+EPS)
    z=centered*inv
    return z*g+b,(z,inv,g)

def ln_backward(dy,c):
    z,inv,g=c
    dg=(dy*z).sum(axis=(0,1)); db=dy.sum(axis=(0,1))
    dz=dy*g
    dx=inv*(dz-dz.mean(axis=-1,keepdims=True)-z*(dz*z).mean(axis=-1,keepdims=True))
    return dx,dg,db

def linear(x,w,b):
    return x@w.T+b

def lin_backward(dy,x,w):
    a=dy.reshape(-1,dy.shape[-1]); b=x.reshape(-1,x.shape[-1])
    return dy@w,a.T@b,a.sum(axis=0)

def gelu(x):
    e=np.fromiter((math.erf(float(t)/math.sqrt(2)) for t in x.flat),dtype=np.float64,count=x.size).reshape(x.shape)
    cdf=.5*(1+e)
    return x*cdf,cdf+x*np.exp(-.5*x*x)/math.sqrt(2*math.pi)

class NativeCore:
    def __init__(self,weights):
        validate(weights)
        self.w={k:v.copy() for k,v in weights.items()}

    def forward(self,tokens):
        w=self.w
        require(tokens.ndim==2 and tokens.dtype==np.int64 and 0<tokens.shape[1]<=CONTEXT and tokens.min()>=0 and tokens.max()<VOCAB,"TOKEN_INPUT")
        B,T=tokens.shape
        x=w["token.weight"][tokens]+w["pos.weight"][:T]
        caches=[]
        mask=np.triu(np.ones((T,T),dtype=bool),1)
        hd=WIDTH//HEADS; scale=hd**-.5
        def split(a): return a.reshape(B,T,HEADS,hd).transpose(0,2,1,3)
        for i in range(LAYERS):
            p=f"blocks.layers.{i}."
            u,n1=layer_norm(x,w[p+"norm1.weight"],w[p+"norm1.bias"])
            q,k,v=map(split,np.split(linear(u,w[p+"self_attn.in_proj_weight"],w[p+"self_attn.in_proj_bias"]),3,axis=-1))
            scores=(q@k.swapaxes(-1,-2))*scale
            a=softmax(np.where(mask,-np.inf,scores))
            attended=(a@v).transpose(0,2,1,3).reshape(B,T,WIDTH)
            h=x+linear(attended,w[p+"self_attn.out_proj.weight"],w[p+"self_attn.out_proj.bias"])
            r,n2=layer_norm(h,w[p+"norm2.weight"],w[p+"norm2.bias"])
            pre=linear(r,w[p+"linear1.weight"],w[p+"linear1.bias"])
            act,gd=gelu(pre)
            x=h+linear(act,w[p+"linear2.weight"],w[p+"linear2.bias"])
            caches.append((u,n1,q,k,v,a,attended,r,n2,act,gd))
        final,nf=layer_norm(x,w["norm.weight"],w["norm.bias"])
        logits=final@w["token.weight"].T
        require(np.isfinite(logits).all(),"FORWARD_NONFINITE")
        return logits,(tokens,caches,final,nf)

    def loss_grad(self,tokens,targets):
        logits,cache=self.forward(tokens)
        require(targets.shape==tokens.shape and targets.dtype==np.int64 and targets.min()>=0 and targets.max()<VOCAB,"TARGET_INPUT")
        B,T=tokens.shape
        prob=softmax(logits)
        row,col=np.indices((B,T))
        m=logits.max(axis=-1)
        loss=float(np.mean(m+np.log(np.exp(logits-m[...,None]).sum(axis=-1))-logits[row,col,targets]))
        delta=prob.copy()
        delta[row,col,targets]-=1
        delta/=B*T
        grads=self.backward(delta,cache)
        return loss,logits,grads

    def backward(self,d,cache):
        w=self.w; tokens,caches,final,nf=cache
        B,T=tokens.shape; hd=WIDTH//HEADS; scale=hd**-.5
        g={}
        # Shared parameter: both output and input embedding paths contribute.
        g["token.weight"]=d.reshape(-1,VOCAB).T@final.reshape(-1,WIDTH)
        dx=d@w["token.weight"]
        dx,g["norm.weight"],g["norm.bias"]=ln_backward(dx,nf)
        def join(z): return z.transpose(0,2,1,3).reshape(B,T,WIDTH)
        for i in reversed(range(LAYERS)):
            p=f"blocks.layers.{i}."
            u,n1,q,k,v,a,attended,r,n2,act,gd=caches[i]
            da,g[p+"linear2.weight"],g[p+"linear2.bias"]=lin_backward(dx,act,w[p+"linear2.weight"])
            dr,g[p+"linear1.weight"],g[p+"linear1.bias"]=lin_backward(da*gd,r,w[p+"linear1.weight"])
            dh,g[p+"norm2.weight"],g[p+"norm2.bias"]=ln_backward(dr,n2)
            dh+=dx
            datt,g[p+"self_attn.out_proj.weight"],g[p+"self_attn.out_proj.bias"]=lin_backward(dh,attended,w[p+"self_attn.out_proj.weight"])
            dz=datt.reshape(B,T,HEADS,hd).transpose(0,2,1,3)
            dv=a.swapaxes(-1,-2)@dz
            dp=dz@v.swapaxes(-1,-2)
            ds=a*(dp-(dp*a).sum(axis=-1,keepdims=True))
            dq=(ds@k)*scale
            dk=(ds.swapaxes(-1,-2)@q)*scale
            dproj=np.concatenate((join(dq),join(dk),join(dv)),axis=-1)
            du,g[p+"self_attn.in_proj_weight"],g[p+"self_attn.in_proj_bias"]=lin_backward(dproj,u,w[p+"self_attn.in_proj_weight"])
            dx,g[p+"norm1.weight"],g[p+"norm1.bias"]=ln_backward(du,n1)
            dx+=dh
        np.add.at(g["token.weight"],tokens,dx)
        g["pos.weight"]=np.zeros_like(w["pos.weight"])
        g["pos.weight"][:T]=dx.sum(axis=0)
        validate(g)
        return g

class AdamW:
    def __init__(self,w,lr=1e-4):
        self.lr=lr
        self.t=0
        self.m={k:np.zeros_like(a) for k,a in w.items()}
        self.v={k:np.zeros_like(a) for k,a in w.items()}
    def step(self,w,g):
        validate(w); validate(g)
        self.t+=1
        for k in w:
            self.m[k]=.9*self.m[k]+.1*g[k]
            self.v[k]=.999*self.v[k]+.001*g[k]**2
            mh=self.m[k]/(1-.9**self.t); vh=self.v[k]/(1-.999**self.t)
            w[k]*=1-self.lr*.01
            w[k]-=self.lr*mh/(np.sqrt(vh)+1e-8)
        validate(w)
    def snapshot(self,w):
        return self.t, {k:v.copy() for k,v in w.items()}, {k:v.copy() for k,v in self.m.items()}, {k:v.copy() for k,v in self.v.items()}
    def restore(self,w,s):
        self.t,ww,mm,vv=s
        for k in w: w[k][...]=ww[k]
        self.m={k:v.copy() for k,v in mm.items()}
        self.v={k:v.copy() for k,v in vv.items()}
    def digest(self,w):
        return (self.t,seal(w),seal(self.m),seal(self.v))

def generate(model,ids,count=5):
    require(len(ids)+count<=CONTEXT,"GEN_BOUNDS")
    out=list(ids)
    for _ in range(count):
        z,_=model.forward(np.array([out],dtype=np.int64))
        out.append(int(z[0,-1].argmax()))
    return out[len(ids):]
