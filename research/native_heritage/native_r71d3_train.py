from native_r71d3_common import *
def main():
    root,pool,out=sys.argv[1:4];tr=read("research/native_heritage/R71D3_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.eval();parent.requires_grad_(False);pin=frozen_digest(parent)
    nums=source_numbers(pool,bt["sources"]);rows=make_pairs(tr,nums);req(len(rows)==1536,"TRAIN_COUNT")
    variants={}
    for name,rank in (("native_pointer",0),("native_attention_pointer",tr["attention_rank"]),("random_attention_pointer",tr["attention_rank"])):
        torch.manual_seed(tr["seed"])
        base=Model(parent.config)
        if name!="random_attention_pointer":base.load_state_dict(parent.state_dict(),strict=True)
        base.eval();before=frozen_digest(base)
        m=SpanPointer(base,rank,tr["pointer_dim"]);m.eval()
        probe=torch.tensor([[256,65,66,67,10,123,125]])
        with torch.no_grad():err=float((m.base.lm_head(m.hidden(probe))-base(probe)[0]).abs().max())
        req(err<0.0002,"ZERO_ADAPTER_EQUIVALENCE")
        m.train();params=[p for p in m.parameters() if p.requires_grad];count=sum(p.numel() for p in params)
        req(count==16384+int(rank>0)*7680,"PARAMETER_COUNT")
        opt=torch.optim.AdamW(params,lr=tr["lr"]);rng=random.Random(tr["seed"]);samples=[]
        for step in range(tr["steps"]):
            selected=[rng.choice(rows) for _ in range(tr["pairs_per_step"])]
            idx,q,mask,gold=batch_frames(training_frames(selected,rng,T))
            scores=m(idx,q,mask);loss=(F.cross_entropy(scores[:,0],gold[:,0])+F.cross_entropy(scores[:,1],gold[:,1]))/2
            req(bool(loss.isfinite()),"FINITE_LOSS")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,159,319,479,639):samples.append(float(loss.detach()))
        req(frozen_digest(base)==before,"BASE_CHANGED")
        state={"adapter":m.adapter_state(),"config":base.config.to_dict(),"rank":rank}
        if name=="random_attention_pointer":state["random_base"]=base.state_dict()
        p=Path(out)/(name+".pt");torch.save(state,p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":count,"base_initial_tensor_sha256":before,"base_final_tensor_sha256":frozen_digest(base),"zero_adapter_max_error":err,"loss":samples}
        print("R71D3_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d3.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"train_pairs":len(rows),"archive_pairs":sum(r["archive"] for r in rows),"pairs_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D3_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
