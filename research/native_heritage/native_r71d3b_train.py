from native_r71d3b_common import *
def main():
    root,pool,out=sys.argv[1:4];tr=read("research/native_heritage/R71D3B_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);parent.eval();pin=frozen_digest(parent)
    rows=pairs(tr,source_numbers(pool,bt["sources"]));req(len(rows)==2048,"TRAIN_COUNT")
    variants={}
    for name in ("native_grounded","random_grounded","byte_only"):
        torch.manual_seed(tr["seed"]);base=Model(parent.config)
        if name!="random_grounded":base.load_state_dict(parent.state_dict(),strict=True)
        before=frozen_digest(base)
        m=GroundedPointer(base,name=="byte_only");m.train()
        params=[v for v in m.parameters() if v.requires_grad];opt=torch.optim.AdamW(params,lr=tr["lr"]);rng=random.Random(tr["seed"]);samples=[]
        for step in range(tr["steps"]):
            fs=train_frames([rng.choice(rows) for _ in range(tr["pairs_per_step"])],rng,T)
            idx,qs,ql,doc,gold=batch(fs);y=label(gold)
            req(bool(((gold[:,1]-gold[:,0])<5).all()),"SPAN_LENGTH")
            z=m(idx,qs,ql,doc);loss=F.cross_entropy(z,y);req(bool(loss.isfinite()),"FINITE")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,159,319,479,639):samples.append(float(loss.detach()))
        req(frozen_digest(base)==before,"BASE_CHANGED")
        obj={"adapter":m.adapter_state(),"config":base.config.to_dict()}
        if name=="random_grounded":obj["random_base"]=base.state_dict()
        p=Path(out)/(name+".pt");torch.save(obj,p)
        variants[name]={"sha256":sha(p.read_bytes()),"base_initial_tensor_sha256":before,"base_final_tensor_sha256":frozen_digest(base),"trainable_parameters":sum(v.numel() for v in params),"losses":samples}
        print("R71D3B_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d3b.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"train_pairs":len(rows),"train_pairs_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D3B_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
