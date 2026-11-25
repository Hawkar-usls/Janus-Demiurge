from native_r71d4_common import *
def main():
    root,pool,out=sys.argv[1:4];tr=read("research/native_heritage/R71D4_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);pin=frozen_digest(parent)
    rows=pairs(tr,source_numbers(pool,bt["sources"]));req(len(rows)==tr["pairs"],"TRAIN_COUNT")
    variants={}
    for name in ("native_copy","byte_copy"):
        torch.manual_seed(tr["seed"]);base=Model(parent.config);base.load_state_dict(parent.state_dict(),strict=True)
        m=CopyHead(base,name=="byte_copy");m.train();params=[p for p in m.parameters() if p.requires_grad]
        opt=torch.optim.AdamW(params,lr=tr["lr"]);rng=random.Random(tr["seed"]);losses=[]
        for step in range(tr["steps"]):
            fs=train_frames([rng.choice(rows) for _ in range(tr["batch_pairs"])],rng,T)
            x,sp,prev,y=copy_batch(fs,[f[4] for f in fs]);z=m(x,sp,prev);loss=F.cross_entropy(z.flatten(0,1),y.flatten(),ignore_index=-100)
            req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,99,199,299,399):losses.append(float(loss.detach()))
        req(frozen_digest(base)==pin,"BASE_CHANGED")
        p=Path(out)/(name+".pt");torch.save({"adapter":m.adapter_state(),"config":base.config.to_dict()},p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(v.numel() for v in params),"losses":losses,"base_tensor_sha256":frozen_digest(base)}
        print("R71D4_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d4.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"train_pairs":len(rows),"train_pairs_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D4_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
