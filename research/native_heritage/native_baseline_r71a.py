"""R7.1A: read-only native byte-transformer baseline, not a promotion gate."""
import hashlib
import json
import random
import sys
from pathlib import Path
from collections import defaultdict
import torch

def require(ok, tag):
    if not ok:
        raise ValueError(tag)

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def build(seed):
    rng = random.Random(seed)
    rows = []
    for group in ("lookup", "addition", "comparison", "missing"):
        for i in range(16):
            a,b = rng.sample(range(1,10),2)
            doc = {"x":a,"y":b}
            if group == "lookup":
                q = "Value of x?"
                gold, alt = str(a), str(b)
                other = {"x":b,"y":a}
            elif group == "addition":
                q = "x+y?"
                gold = str(a+b)
                n = a+1 if a<9 else a-1
                other = {"x":n,"y":b}
                alt = str(n+b)
            elif group == "comparison":
                q = "x>y? 1=yes,0=no."
                gold,alt = str(int(a>b)),str(int(b>a))
                other = {"x":b,"y":a}
            else:
                q = "Value of z? ?=absent."
                gold,alt,other = "?",None,None
            options = [gold]
            if alt is not None: options.append(alt)
            pool = ["?","0"]+[str(j) for j in range(1,19)]
            rng.shuffle(pool)
            for v in pool:
                if v not in options: options.append(v)
                if len(options)==4: break
            require(len(options)==4,"OPTIONS")
            options.remove(gold);rng.shuffle(options);options.insert(i%4,gold)
            rows.append({"id":group+"-"+str(i),"group":group,"doc":doc,"q":q,"gold":gold,"options":options,"other":other,"alt":alt})
    return rows

def oracle(r, doc):
    if r["group"]=="lookup": return str(doc["x"]) if "x" in doc else "?"
    if r["group"]=="addition": return str(doc["x"]+doc["y"]) if set(("x","y"))<=doc.keys() else "?"
    if r["group"]=="comparison": return str(int(doc["x"]>doc["y"])) if set(("x","y"))<=doc.keys() else "?"
    return str(doc.get("z","?"))

def historical(state):
    rng=random.Random(741)
    rows=[]
    for i,key in enumerate(("attempt_count","promotion_count","rejection_count","source_attempt_budget","source_attempt_count","attempt_count","promotion_count","rejection_count")):
        value=state[key]
        require(type(value) is int and value>=0,"STATE_FIELD")
        doc={key:value,"other":value+1}
        options=[str(value+j) for j in (0,1,2,3)]
        rng.shuffle(options)
        rows.append({"id":"historical-"+str(i),"group":"historical","doc":doc,"q":"Value of "+key+"?","gold":str(value),"options":options,"other":None,"alt":None})
    return rows

def prompt(r,doc,forced):
    txt="JSON:"+json.dumps(doc,separators=(",",":"))+"\nQ:"+r["q"]
    if forced:
        txt+="\n"+",".join(k+"="+v for k,v in zip("ABCD",r["options"]))+"\nA:"
    else:
        txt+="\nAnswer:"
    return txt

def main():
    root=Path(sys.argv[1]).resolve()
    spec=json.loads(Path("research/native_heritage/R71A_PROTOCOL.json").read_bytes())
    parent=spec["parent"]
    checkpoint=root/parent["path"]
    raw=checkpoint.read_bytes()
    require(len(raw)==parent["bytes"] and sha(raw)==parent["sha256"],"CHECKPOINT_SHA")
    require(hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()==parent["git_blob"],"CHECKPOINT_GIT_BLOB")
    state=json.loads((root/"janus_model/state/JANUS_MODEL_STATE.json").read_bytes())
    require(state["checkpoint_sha256"]==parent["sha256"],"STATE_PIN")
    sys.path.insert(0,str(root))
    from janus_model.model import JanusModelConfig, JanusTinyTransformer, ByteTokenizer, parameter_count
    from janus_model.checkpoint_admission import preflight,checked_config
    require(preflight(checkpoint,expected_sha256=parent["sha256"])==parent["sha256"],"PREFLIGHT")
    obj=torch.load(checkpoint,map_location="cpu",weights_only=True)
    require(type(obj) is dict and checked_config(obj["config"])==parent["config"],"CONFIG")
    torch.set_num_threads(1);torch.manual_seed(741)
    cfg=JanusModelConfig.from_dict(parent["config"])
    model=JanusTinyTransformer(cfg)
    model.load_state_dict(obj["model_state"],strict=True);model.eval()
    random_model=JanusTinyTransformer(cfg);random_model.eval()
    require(parameter_count(model)==parent["parameters"] and all(bool(torch.isfinite(v).all()) for v in model.state_dict().values()),"PARAMETERS")
    require(model.token.weight.data_ptr()==model.lm_head.weight.data_ptr(),"TIED_WEIGHTS")
    def ids(txt,max_new=0):
        x=ByteTokenizer.encode(txt,bos=True)
        require(len(x)+max_new<=cfg.context_length,"CONTEXT_OVERFLOW")
        return torch.tensor([x],dtype=torch.long)
    @torch.inference_mode()
    def forced(m,r,doc):
        logits,_=m(ids(prompt(r,doc,True)))
        values=logits[0,-1,[ord(k) for k in "ABCD"]]
        return r["options"][int(values.argmax())]
    @torch.inference_mode()
    def free(m,r,doc):
        x=ids(prompt(r,doc,False),6);out=[]
        for _ in range(6):
            z,_=m(x);n=int(z[0,-1].argmax())
            if n in (10,13,ByteTokenizer.EOS):break
            if n>=256:return "<invalid>"
            out.append(n);x=torch.cat([x,torch.tensor([[n]])],dim=1)
        return ByteTokenizer.decode(out).strip()
    rows=build(spec["exam"]["seed"])
    require(len(rows)==64 and len({r["id"] for r in rows})==64,"SUITE")
    require(all(oracle(r,r["doc"])==r["gold"] and (r["other"] is None or oracle(r,r["other"])==r["alt"]) for r in rows),"ORACLE")
    metrics=defaultdict(lambda:defaultdict(int))
    pairs=defaultdict(int)
    results=[]
    for r in rows+historical(state):
        ans={"native_forced":forced(model,r,r["doc"]),"native_free":free(model,r,r["doc"]),"no_context":forced(model,r,{}),"random_init":forced(random_model,r,r["doc"])}
        if r["group"]=="historical":
            key=r["q"][len("Value of "):-1];ans["deterministic"]=str(r["doc"][key])
        else: ans["deterministic"]=oracle(r,r["doc"])
        g=metrics[r["group"]];g["count"]+=1
        row={"id":r["id"],"group":r["group"],"correct":{}}
        for k,v in ans.items():
            correct=v==r["gold"];g[k]+=int(correct);row["correct"][k]=correct
        if r["other"] is not None:
            pairs["eligible"]+=1
            for k,m in (("native",model),("random_init",random_model)):
                other=forced(m,r,r["other"])
                orig=ans["native_forced" if k=="native" else "random_init"]
                pairs[k+"_both_correct"]+=int(orig==r["gold"] and other==r["alt"])
                pairs[k+"_changed_answer"]+=int(orig!=other)
        results.append(row)
    require(all(v["deterministic"]==v["count"] for v in metrics.values()),"REFERENCE")
    # Fixed language anchor: evaluate all non-overlapping 128-token windows.
    anchor=(root/"janus_model/eval/JANUS_ANCHOR_EVAL-v1.txt").read_bytes()
    losses={}
    with torch.inference_mode():
        for label,m in (("native",model),("random_init",random_model)):
            vals=[]
            for i in range(0,len(anchor)-128,128):
                w=list(anchor[i:i+129]);_,loss=m(torch.tensor([w[:-1]]),torch.tensor([w[1:]]))
                vals.append(float(loss))
            require(bool(vals),"ANCHOR_WINDOWS")
            losses[label]=sum(vals)/len(vals)
    require(sha(checkpoint.read_bytes())==parent["sha256"],"PARENT_MUTATED")
    report={"schema":"janus.native.heritage.r71a.result.v1","status":"BASELINE_MEASURED_NOT_ADMISSION","checkpoint_sha256":parent["sha256"],"parameters":parameter_count(model),"checkpoint_bytes":len(raw),"tensor_entries":len(obj["model_state"]),"finite":True,"suite_sha256":sha(canon(rows)),"metrics":dict(metrics),"counterfactual":dict(pairs),"anchor_sha256":sha(anchor),"anchor_nll":losses,"rows":results,"training_executed":False,"production_changed":False,"external_blind":False,"action_authority":False}
    report["receipt_sha256"]=sha(canon(report))
    Path(sys.argv[2]).write_bytes(canon(report)+b"\n")
    print("R71A_NATIVE_BASELINE "+json.dumps({k:v for k,v in report.items() if k!="rows"},sort_keys=True))
if __name__=="__main__":main()
