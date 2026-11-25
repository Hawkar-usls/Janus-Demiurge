from native_r71d4b_common import *
def main():
    root,out=sys.argv[1:3];tr=read("research/native_heritage/R71D4B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);pin=frozen_digest(parent)
    rows=suite(tr);req(len(rows)==4096 and all(not partition(r["payload"]) for r in rows if r["payload"]),"TRAIN_SPLIT")
    variants={}
    for name,byte,relative in (("native_relative",False,True),("byte_relative",True,True),("native_absolute",False,False)):
        torch.manual_seed(tr["seed"]);base=Model(parent.config);base.load_state_dict(parent.state_dict(),strict=True)
        m=InvariantCopy(base,byte,relative);m.train();params=[p for p in m.parameters() if p.requires_grad]
        opt=torch.optim.AdamW(params,lr=tr["lr"]);rng=random.Random(tr["seed"]);losses=[]
        for step in range(tr["steps"]):
            fs=[render(rng.choice(rows),T) for _ in range(tr["batch_size"])]
            x,sp,y=tensorize(fs,True);z=m(x,sp,torch.arange(33));loss=F.cross_entropy(z.flatten(0,1),y.flatten(),ignore_index=-100)
            req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,119,239,359,479):losses.append(float(loss.detach()))
        req(frozen_digest(base)==pin,"BASE_CHANGED")
        p=Path(out)/(name+".pt");torch.save({"adapter":m.adapter_state(),"config":base.config.to_dict(),"relative":relative,"byte_only":byte},p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(p.numel() for p in params),"losses":losses,"base_tensor_sha256":frozen_digest(base)}
        print("R71D4B_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(len({v["trainable_parameters"] for v in variants.values()})==1,"PARAM_MATCH")
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d4b.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"train_cases":len(rows),"train_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D4B_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
