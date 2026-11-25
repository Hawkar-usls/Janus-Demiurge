from native_r72b7_common import *
def main():
    root,out=sys.argv[1:3];tr=read("research/native_heritage/R72B7_PROTOCOL.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,_,_=load_base(root,tr);parent.requires_grad_(False);parent.eval();pin=frozen_digest(parent);req(pin==tr["parent_tensor_sha256"],"PARENT")
    rows,teacher=admitted_train()
    # Unique raw texts only; balanced strata.
    req(len({r["value"] for r in rows})==len(rows),"DUPLICATE_TRAIN")
    x,mask,n=raw_features(parent,rows)
    e=torch.tensor([r["event"] for r in rows]);o=torch.tensor([r["outcome"] for r in rows])
    cohort=sorted(set(r["cohort"] for r in rows));ids=torch.tensor([cohort.index(r["cohort"]) for r in rows])
    counts=torch.bincount(ids);weights=counts.float().reciprocal()[ids];weights/=weights.sum()
    variants={}
    for name in ("native_semantics","byte_semantics"):
        torch.manual_seed(tr["seed"]);m=Student(parent.config.d_model,name=="byte_semantics");opt=torch.optim.AdamW(m.parameters(),lr=tr["lr"]);g=torch.Generator().manual_seed(tr["seed"]);losses=[]
        for step in range(tr["steps"]):
            ix=torch.multinomial(weights,tr["batch"],replacement=True,generator=g)
            a,b=m(x[ix],mask[ix],n[ix]);loss=F.cross_entropy(a,e[ix])+F.cross_entropy(b,o[ix])
            req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.);opt.step()
            if step in (0,299,599,899,1199):losses.append(float(loss.detach()))
        p=Path(out)/(name+".pt");torch.save({"state":m.state_dict(),"byte_only":m.byte_only},p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(v.numel() for v in m.parameters()),"losses":losses}
    req(frozen_digest(parent)==pin,"PARENT_CHANGED")
    report={"schema":"janus.native.r72b7.candidates.v1","parent_tensor_sha256":pin,"parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"train_sha256":sha(canonical(rows)),"train_text_sha256":sorted(sha(r["value"].encode()) for r in rows),"teacher":teacher,"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R72B7_TRAIN "+json.dumps({k:v for k,v in report.items() if k!="train_text_sha256"},sort_keys=True))
if __name__=="__main__":main()
