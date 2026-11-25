from native_r72b6_common import *
def main():
    root,registry,out=sys.argv[1:4];tr=read("research/native_heritage/R72B6_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);parent.requires_grad_(False);pin=frozen_digest(parent);req(pin==tr["parent_tensor_sha256"],"PARENT")
    real,cov=load_rows(tr,registry);syn=synthetic();rows=real+syn
    b,h=scope_features(parent,rows);y=groups(targets(rows));e=torch.tensor([r.get("event",-100) for r in rows]);o=torch.tensor([r.get("outcome",-100) for r in rows])
    counts=torch.bincount(y,minlength=4);weights=counts.float().reciprocal()[y];weights/=weights.sum()
    ix_scope=torch.where(e>=0)[0];req(len(ix_scope)>0,"SCOPE_SUPPORT")
    variants={}
    for name in ("native_semantics","byte_semantics"):
        torch.manual_seed(tr["seed"]);m=ScopeHead(parent.config.d_model,name=="byte_semantics");opt=torch.optim.AdamW(m.parameters(),lr=tr["lr"]);g=torch.Generator().manual_seed(tr["seed"]);losses=[]
        for step in range(tr["steps"]):
            ix=torch.cat([torch.multinomial(weights,tr["batch"],replacement=True,generator=g),ix_scope[torch.randint(len(ix_scope),(tr["batch"],),generator=g)]])
            p,a,z=m(b[ix],h[ix]);loss=F.cross_entropy(p,y[ix])+F.cross_entropy(a,e[ix],ignore_index=-100)+F.cross_entropy(z,o[ix],ignore_index=-100)
            req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();opt.step()
            if step in (0,199,399,599,799):losses.append(float(loss.detach()))
        p=Path(out)/(name+".pt");torch.save({"state":m.state_dict(),"byte_only":m.byte_only},p)
        variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(x.numel() for x in m.parameters()),"losses":losses}
    req(frozen_digest(parent)==pin,"PARENT_CHANGED")
    report={"schema":"janus.native.r72b6.candidates.v1","parent_tensor_sha256":pin,"parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"train_sha256":sha(canonical(rows)),"real_rows":len(real),"synthetic_rows":len(syn),"scope_labeled":len(ix_scope),"coverage":cov,"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R72B6_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
