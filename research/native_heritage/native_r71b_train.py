"""R71B balanced vs skewed task sampling, fixed CPU budgets."""
from native_r71b_common import *
import torch.nn.functional as F
def main():
    root,pool,out=sys.argv[1:4];tr=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    base,Model,T=load_base(root,tr);rows=build(tr,pool)
    req(len(rows)==512,"TRAIN_COUNT")
    require_unique={sha(canonical([r["doc"],r["q"]])) for r in rows};req(len(require_unique)==512,"DEDUP")
    buckets={g:[i for i,r in enumerate(rows) if r["group"]==g] for g in GROUPS}
    variants={}
    for name in ("balanced","skewed","scratch_balanced"):
        torch.manual_seed(tr["seed"]);m=Model(base.config)
        if name!="scratch_balanced":m.load_state_dict(base.state_dict(),strict=True)
        m.train();opt=torch.optim.AdamW(m.parameters(),lr=tr["learning_rate"]);rng=random.Random(tr["seed"])
        draws={g:0 for g in GROUPS};losses=[]
        for step in range(tr["steps"]):
            groups=rng.choices(GROUPS,weights=[7,1,1,1] if name=="skewed" else [1]*4,k=tr["batch_size"])
            idx=[]
            for g in groups:
                draws[g]+=1;idx.append(2*rng.choice(buckets[g])+rng.randrange(2))
            x,y=batch(rows,idx,T);logits,_=m(x)
            loss=F.cross_entropy(logits.reshape(-1,258),y.reshape(-1),ignore_index=-100)
            req(bool(loss.isfinite()),"NONFINITE_LOSS")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.0);opt.step()
            if step in (0,59,119,179,239):losses.append(float(loss))
        path=Path(out)/(name+".pt");torch.save({"config":m.config.to_dict(),"model_state":m.state_dict()},path)
        variants[name]={"sha256":sha(path.read_bytes()),"loss":losses,"draws":draws}
    req(sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71b.candidates.v1","parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"rows_sha256":sha(canonical(rows)),"rows":len(rows),"real_projection_rows":sum(r["real_projection"] for r in rows),"formats":2,"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report))
    print("R71B_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
