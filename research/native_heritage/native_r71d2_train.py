from native_r71d2_common import *
def main():
    root,pool,out=sys.argv[1:4];tr=read("research/native_heritage/R71D2_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);parent.eval();pin=frozen_digest(parent)
    old=build(bt,pool);req(len(old)==512 and sha(canonical(old))==tr["old_rows_sha256"],"B_TRAIN_PIN")
    old=[make_pair(r) for r in old];new=make_suite(tr["seed"],tr["synthetic_pairs_per_group"],False)
    rows=old+new;req(len(rows)==1536,"TRAIN_PAIRS")
    buckets={g:([r for r in old if r["group"]==g],[r for r in new if r["group"]==g]) for g in GROUPS}
    variants={}
    for name in ("native_attention","native_output","random_attention"):
        torch.manual_seed(tr["seed"]);base=Model(parent.config)
        if name!="random_attention":base.load_state_dict(parent.state_dict(),strict=True)
        initial=frozen_digest(base)
        model=RoutedAdapter(base,tr["output_rank"]) if name=="native_output" else AttentionAdapter(base,tr["attention_rank"])
        model.eval()
        probe=torch.tensor([[256,65,66,67,10,123,125]])
        with torch.no_grad():
            err=float((model(probe)[0]-base(probe)[0]).abs().max())
        req(err<0.0002,"ZERO_ADAPTER_EQUIVALENCE")
        model.train();params=[p for p in model.parameters() if p.requires_grad];req(sum(p.numel() for p in params)==7680,"PARAMETER_BUDGET")
        opt=torch.optim.AdamW(params,lr=tr["lr"]);rng=random.Random(tr["seed"]);samples=[]
        for step in range(tr["steps"]):
            chosen=[rng.choice(buckets[g][int(rng.random()<.67)]) for g in GROUPS]
            x,y=paired_batch(chosen,rng,T);z,_=model(x)
            loss=F.cross_entropy(z.reshape(-1,258),y.reshape(-1),ignore_index=-100);req(bool(loss.isfinite()),"FINITE")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,119,239,359,479):samples.append(float(loss.detach()))
        req(frozen_digest(base)==initial,"BASE_CHANGED")
        state={"adapter":model.adapter_state(),"config":base.config.to_dict()}
        if name=="random_attention":state["random_base"]=base.state_dict()
        p=Path(out)/(name+".pt");torch.save(state,p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":7680,"base_initial_tensor_sha256":initial,"base_final_tensor_sha256":frozen_digest(base),"zero_adapter_max_error":err,"losses":samples}
        print("R71D2_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d2.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"pairs":len(rows),"pairs_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D2_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
