from native_r72b8_common import *
def main():
    root,registry,oldfolder,out=sys.argv[1:5]
    tr=read("research/native_heritage/R72B8_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,_,_=load_base(root,tr);parent.eval();parent.requires_grad_(False);pin=frozen_digest(parent);req(pin==tr["parent_tensor_sha256"],"PARENT")
    old=frozen_heads(oldfolder,tr["baseline"]["receipt"],tr["baseline"]["artifacts"],pin,parent.config.d_model,Student)
    real=registry_rows(tr,registry);syn,teacher=admitted_train();req(all(r["event"]>=0 for r in real),"REAL_LABELS")
    req(not set(r["value"] for r in real)&set(r["value"] for r in syn),"TRAIN_DUPLICATE")
    rows=real+syn;x,mask,n=raw_features(parent,rows);e,o=labels(rows);rw=balanced(real);sw=balanced(syn);nr=len(real)
    variants={}
    for base in old:
        for mode in ("grounded","replay_only"):
            name=base+"_"+mode
            torch.manual_seed(tr["seed"]);m=Student(parent.config.d_model,base=="byte_semantics");m.load_state_dict(old[base].state_dict(),strict=True);m.train();opt=torch.optim.AdamW(m.parameters(),lr=tr["lr"]);g=torch.Generator().manual_seed(tr["seed"]);losses=[]
            for step in range(tr["steps"]):
                s=torch.multinomial(sw,tr["batch"]-tr["real_per_batch"],replacement=True,generator=g)+nr
                second=torch.multinomial(rw if mode=="grounded" else sw,tr["real_per_batch"],replacement=True,generator=g)+(0 if mode=="grounded" else nr)
                ix=torch.cat([s,second]);a,b=m(x[ix],mask[ix],n[ix]);loss=F.cross_entropy(a,e[ix])+F.cross_entropy(b,o[ix])
                req(bool(loss.isfinite()),"FINITE");opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),1.);opt.step()
                if step in (0,79,159,239,319):losses.append(float(loss.detach()))
            p=Path(out)/(name+".pt");torch.save({"state":m.state_dict(),"byte_only":m.byte_only},p)
            variants[name]={"sha256":sha(p.read_bytes()),"trainable_parameters":sum(v.numel() for v in m.parameters()),"losses":losses}
    req(frozen_digest(parent)==pin,"PARENT_CHANGED")
    report={"schema":"janus.native.r72b8.candidates.v1","parent_tensor_sha256":pin,"parent_sha256":tr["parent_sha256"],"train_spec_sha256":sha(canonical(tr)),"baseline_receipt":tr["baseline"]["receipt"],"train_sha256":sha(canonical(rows)),"train_text_sha256":sorted(sha(r["value"].encode()) for r in rows),"real_n":nr,"real_by_cohort":dict(collections.Counter(r["cohort"] for r in real)),"replay_n":len(syn),"variants":variants,"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R72B8_TRAIN "+json.dumps({k:v for k,v in report.items() if k!="train_text_sha256"},sort_keys=True))
if __name__=="__main__":main()
