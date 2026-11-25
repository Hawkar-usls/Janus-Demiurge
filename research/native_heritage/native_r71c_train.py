from native_r71c_common import *
import torch.nn.functional as F
def main():
    root,pool,hist,manifest,out=sys.argv[1:6];tr=read("research/native_heritage/R71C_TRAIN.json");bt=read("research/native_heritage/R71B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    base,Model,T=load_base(root,tr);old=build(bt,pool)
    req(len(old)==512 and sha(canonical(old))==tr["old_rows_sha256"],"EXACT_B_REPLAY")
    rows=augment(old);req(len(rows)==640,"CONTRAST_COUNT")
    docs=historical(hist,manifest,tr,tr["replay"],"train")
    buckets={g:[i for i,r in enumerate(rows) if r["group"]==g] for g in GROUPS};variants={}
    for name,lr,reg,lang in (("standard",tr["standard_lr"],0,0),("low_lr",tr["lower_lr"],0,0),("l2",tr["lower_lr"],tr["l2_lambda"],0),("replay",tr["lower_lr"],0,tr["replay_weight"]),("combined",tr["lower_lr"],tr["l2_lambda"],tr["replay_weight"])):
        torch.manual_seed(tr["seed"]);m=Model(base.config);m.load_state_dict(base.state_dict(),strict=True);m.train()
        anchors=[v.detach().clone() for v in m.parameters()];opt=torch.optim.AdamW(m.parameters(),lr=lr)
        rng=random.Random(tr["seed"]);lrng=random.Random(tr["seed"]+1);samples=[]
        for step in range(tr["steps"]):
            groups=list(GROUPS)*2;rng.shuffle(groups)
            idx=[2*rng.choice(buckets[g])+rng.randrange(2) for g in groups]
            x,y=batch(rows,idx,T);z,_=m(x);task=F.cross_entropy(z.reshape(-1,258),y.reshape(-1),ignore_index=-100)
            hx,hy=sample_text(docs,lrng,tr["replay_batch"]);_,language=m(hx,hy)
            penalty=sum((v-a).square().sum() for v,a in zip(m.parameters(),anchors))/sum(v.numel() for v in m.parameters())
            loss=task+lang*language+reg*penalty;req(bool(loss.isfinite()),"FINITE")
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.0);opt.step()
            if step in (0,59,119,179,239):samples.append({"step":step+1,"task":float(task.detach()),"language":float(language.detach()),"l2":float(penalty.detach())})
        path=Path(out)/(name+".pt");torch.save({"config":m.config.to_dict(),"model_state":m.state_dict()},path)
        variants[name]={"sha256":sha(path.read_bytes()),"lr":lr,"l2_lambda":reg,"replay_weight":lang,"samples":samples,"weight_l2":float(sum((v-a).square().sum() for v,a in zip(m.parameters(),anchors)).sqrt().item())}
        print("R71C_ARM "+json.dumps({"arm":name,**variants[name]},sort_keys=True),flush=True)
    req(sha((Path(root)/"janus_model/checkpoints/promoted.pt").read_bytes())==tr["parent_sha256"],"PARENT_CHANGED")
    report={"schema":"janus.native.r71c.candidates.v1","parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"functional_rows":len(rows),"functional_sha256":sha(canonical(rows)),"historical_records":len(docs),"replay_bytes":sum(map(len,docs)),"replay_sha256":sha(canonical([sha(d) for d in docs])),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71C_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
