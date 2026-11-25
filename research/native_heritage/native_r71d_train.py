from native_r71d_common import *
def main():
    root,pool,hist,manifest,out=sys.argv[1:6]
    tr=read("research/native_heritage/R71D_TRAIN.json");ct=read("research/native_heritage/R71C_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);parent.eval();pin=frozen_digest(parent)
    old=build(bt,pool);req(len(old)==512 and sha(canonical(old))==tr["old_rows_sha256"],"B_ROWS")
    rows=varied_train([make_pair(r) for r in old]);req(len(rows)==512,"PAIR_ROWS")
    docs=historical(hist,manifest,ct,ct["replay"],"train");req(sha(canonical([sha(d) for d in docs]))==tr["replay_sha256"],"REPLAY_PIN")
    buckets={g:[r for r in rows if r["group"]==g] for g in GROUPS};variants={}
    for name in ("combined_control","memory_lock","native_adapter","random_adapter"):
        torch.manual_seed(tr["seed"])
        base=Model(parent.config)
        if name!="random_adapter":base.load_state_dict(parent.state_dict(),strict=True)
        is_adapter=name.endswith("adapter")
        base_pin=frozen_digest(base)
        model=RoutedAdapter(base,tr["adapter_rank"]) if is_adapter else base
        model.train();params=[p for p in model.parameters() if p.requires_grad]
        opt=torch.optim.AdamW(params,lr=tr["lr_adapter"] if is_adapter else tr["lr_full"])
        anchors=[p.detach().clone() for p in params]
        rng=random.Random(tr["seed"]);lrng=random.Random(tr["seed"]+1);samples=[]
        for step in range(tr["steps"]):
            # Each step has one pair per group; the answer must change with the input.
            sampled=[]
            for g in GROUPS:
                r=rng.choice(buckets[g]);forced=rng.randrange(2)
                sampled.extend([(task_pair(r,False),forced),(task_pair(r,True),forced)])
            seqs=[sequence(r,bool(f),T) for r,f in sampled];n=max(len(x) for x,y in seqs)
            x=torch.tensor([x+[0]*(n-len(x)) for x,y in seqs]);y=torch.tensor([y+[-100]*(n-len(y)) for x,y in seqs])
            z,_=model(x);task=F.cross_entropy(z.reshape(-1,258),y.reshape(-1),ignore_index=-100)
            hx,hy=sample_text(docs,lrng,tr["replay_batch"])
            loss=task;language=kl=torch.tensor(0.)
            if not is_adapter:
                hz,language=model(hx,hy)
                penalty=sum((p-a).square().sum() for p,a in zip(params,anchors))/sum(p.numel() for p in params)
                loss=loss+tr["l2"]*penalty+tr["replay_weight"]*language
                if name=="memory_lock":
                    with torch.no_grad():teacher,_=parent(hx)
                    temp=tr["temperature"];kl=F.kl_div(F.log_softmax(hz/temp,dim=-1),F.softmax(teacher/temp,dim=-1),reduction="none").sum(-1).mean()*temp*temp
                    loss=loss+tr["kl_weight"]*kl
            req(bool(loss.isfinite()),"FINITE_LOSS")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step()
            if step in (0,79,159,239,319):samples.append({"step":step+1,"task":float(task.detach()),"language":float(language.detach()),"kl":float(kl.detach())})
        if is_adapter:req(frozen_digest(base)==base_pin,"FROZEN_BASE_CHANGED")
        state={"config":parent.config.to_dict(),"kind":"adapter" if is_adapter else "full"}
        if is_adapter:
            state["adapter"]=model.adapter_state()
            if name=="random_adapter":state["random_base"]=base.state_dict()
        else:state["model_state"]=model.state_dict()
        p=Path(out)/(name+".pt");torch.save(state,p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(p.numel() for p in params),"base_frozen":is_adapter,"base_initial_tensor_sha256":base_pin,"base_final_tensor_sha256":frozen_digest(base),"samples":samples}
        print("R71D_ARM "+json.dumps({"name":name,**variants[name]},sort_keys=True),flush=True)
    req(frozen_digest(parent)==pin and sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71d.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"paired_train_cases":len(rows),"train_pairs_sha256":sha(canonical(rows)),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
