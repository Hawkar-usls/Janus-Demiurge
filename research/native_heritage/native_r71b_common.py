"""Shared bounded native training/evaluation helpers."""
import hashlib,json,random,sys
from pathlib import Path
import torch
def req(x,msg):
    if not x:raise ValueError(msg)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def read(path):return json.loads(Path(path).read_bytes())
def load_base(root,spec):
    root=Path(root).resolve();sys.path.insert(0,str(root))
    from janus_model.model import JanusModelConfig,JanusTinyTransformer,ByteTokenizer,parameter_count
    from janus_model.checkpoint_admission import preflight,checked_config
    p=root/"janus_model/checkpoints/promoted.pt"
    req(preflight(p,expected_sha256=spec["parent_sha256"])==spec["parent_sha256"],"PARENT_PIN")
    x=torch.load(p,map_location="cpu",weights_only=True);cfg=JanusModelConfig.from_dict(checked_config(x["config"]))
    req(cfg.context_length==128,"CONTEXT")
    m=JanusTinyTransformer(cfg);m.load_state_dict(x["model_state"],strict=True)
    req(parameter_count(m)==446208 and all(bool(v.isfinite().all()) for v in m.state_dict().values()),"PARAMS")
    m.eval();return m,JanusTinyTransformer,ByteTokenizer
def walk(obj,p=()):
    if isinstance(obj,dict):
        for k,v in sorted(obj.items()):yield from walk(v,p+(k,))
    elif type(obj) is int and 0<=obj<=9999:yield p,obj
def source_numbers(root,sources):
    vals=[]
    for s in sources:
        raw=(Path(root)/s["path"]).read_bytes()
        req(len(raw)<1000000 and hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()==s["blob"],"SOURCE_BLOB")
        for p,v in walk(json.loads(raw)):
            if p:vals.append((s["blob"],"/".join(p),v))
    req(len(vals)>=20,"INSUFFICIENT_NUMBERS");return vals
GROUPS=("lookup","addition","comparison","missing")
def build(spec,root,exam=False):
    rng=random.Random(spec["seed"]);nums=source_numbers(root,spec["sources"]);rows=[];seen=set()
    aliases=[("u","v"),("m","n"),("red","blue"),("left","right")] if exam else [("a","b"),("p","q"),("first","second"),("low","high")]
    for group in GROUPS:
        for i in range(spec["tasks_per_group"]):
            for attempt in range(500):
                k,l=rng.choice(aliases)
                real=i%2==0
                if real:
                    aa,bb=rng.sample(nums,2);a,b=aa[2],bb[2];src=[list(aa),list(bb)]
                else:
                    pool=list(range(50,100)) if exam else list(range(10,50))
                    a,b=rng.sample(pool,2);src=[]
                if a==b:continue
                doc={k:a,l:b}
                if group=="lookup":q="Value of "+k+"?";gold=str(a);alt=str(b);other={k:b,l:a}
                elif group=="addition":q=k+"+"+l+"?";gold=str(a+b);alt=str(a+1+b);other={k:a+1,l:b}
                elif group=="comparison":q=k+">"+l+"? 1=yes,0=no.";gold=str(int(a>b));alt=str(int(b>a));other={k:b,l:a}
                else:q="Value of absent? ?=absent.";gold="?";alt=None;other=None
                opts=[gold]
                if alt is not None:opts.append(alt)
                for v in rng.sample(["?","0","1",str(a),str(b),str(a+b),str(a+1),str(b+1),"99999"],9):
                    if v not in opts:opts.append(v)
                    if len(opts)==4:break
                req(len(opts)==4,"OPTIONS");opts.remove(gold);rng.shuffle(opts);opts.insert((i//2)%4,gold)
                r={"group":group,"doc":doc,"q":q,"gold":gold,"options":opts,"other":other,"alt":alt,"sources":src,"real_projection":real}
                identity=sha(canonical([doc,q]))
                if identity not in seen:seen.add(identity);rows.append(r);break
            else:raise ValueError("UNIQUE_TASKS")
    for r in rows:
        def exact(doc):
            a,b=doc.values()
            if r["group"]=="lookup":return str(a)
            if r["group"]=="addition":return str(a+b)
            if r["group"]=="comparison":return str(int(a>b))
            return str(doc.get("absent","?"))
        req(exact(r["doc"])==r["gold"] and (r["other"] is None or exact(r["other"])==r["alt"]),"EXACT_REFERENCE")
    return rows
def prompt(r,doc,forced):
    t="JSON:"+json.dumps(doc,separators=(",",":"))+"\nQ:"+r["q"]
    return t+("\n"+",".join(k+"="+v for k,v in zip("ABCD",r["options"]))+"\nA:" if forced else "\nAnswer:")
def sequence(r,forced,T):
    prefix=T.encode(prompt(r,r["doc"],forced),bos=True)
    answer="ABCD"[r["options"].index(r["gold"])] if forced else r["gold"]
    seq=prefix+T.encode(answer+"\n")
    req(len(seq)<=129,"CONTEXT_FIT")
    x=seq[:-1];y=[-100]*(len(prefix)-1)+seq[len(prefix):]
    return x,y
def batch(rows,indices,T):
    seq=[sequence(rows[i//2],bool(i%2),T) for i in indices];n=max(len(x) for x,y in seq)
    return torch.tensor([x+[0]*(n-len(x)) for x,y in seq]),torch.tensor([y+[-100]*(n-len(y)) for x,y in seq])
