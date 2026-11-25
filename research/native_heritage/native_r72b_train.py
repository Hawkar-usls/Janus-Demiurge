from native_r72b_common import *
def main():
    root,registry,out=sys.argv[1:4];tr=read("research/native_heritage/R72B_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);pin=frozen_digest(parent);req(pin==tr["parent_tensor_sha256"],"PARENT")
    real,cov=load_rows(tr,registry);syn=synthetic();rows=real+syn
    b,h=features(parent,rows);y=targets(rows);counts=torch.bincount(y,minlength=len(LABELS));req(bool((counts>0).all()),"CLASS_SUPPORT")
    weights=counts.float().reciprocal()[y];weights/=weights.sum();variants={}
    for name in ("native_semantics","byte_semantics"):
        torch.manual_seed(tr["seed"]);m=SemanticHead(parent.config.d_model,name=="byte_semantics");opt=torch.optim.AdamW(m.parameters(),lr=tr["lr"]);g=torch.Generator().manual_seed(tr["seed"]);losses=[]
        for step in range(tr["steps"]):
            ix=torch.multinomial(weights,tr["batch"],replacement=True,generator=g)
            loss=F.cross_entropy(m(b[ix],h[ix]),y[ix]);req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();opt.step()
            if step in (0,119,239,359,479):losses.append(float(loss.detach()))
        p=Path(out)/(name+".pt");torch.save({"state":m.state_dict(),"byte_only":m.byte_only},p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(x.numel() for x in m.parameters()),"losses":losses}
    req(frozen_digest(parent)==pin,"PARENT_CHANGED")
    report={"schema":"janus.native.r72b.candidates.v1","parent_tensor_sha256":pin,"parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"train_sha256":sha(canonical(rows)),"real_rows":len(real),"synthetic_rows":len(syn),"counts":dict(zip(LABELS,counts.tolist())),"coverage":cov,"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R72B_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
