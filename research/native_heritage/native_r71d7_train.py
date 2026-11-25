from native_r71d7_common import *
def main():
    root,out=sys.argv[1:3];tr=read("research/native_heritage/R71D7_TRAIN.json")
    torch.set_num_threads(2);torch.manual_seed(tr["seed"]);torch.use_deterministic_algorithms(True)
    parent,Model,T=load_base(root,tr);pin=frozen_digest(parent)
    rows=train_pairs(tr);m=KeyVerifier();opt=torch.optim.AdamW(m.parameters(),lr=tr["lr"]);rng=random.Random(tr["seed"]);losses=[]
    for step in range(tr["steps"]):
        a,b,la,lb,y=key_batch([rng.choice(rows) for _ in range(tr["batch"])])
        z=m(a,b,la,lb);loss=F.binary_cross_entropy_with_logits(z,y);req(bool(loss.isfinite()),"FINITE")
        opt.zero_grad();loss.backward();opt.step()
        if step in (0,79,159,239,319):losses.append(float(loss.detach()))
    req(frozen_digest(parent)==pin,"PARENT_CHANGED")
    p=Path(out)/"verifier.pt";torch.save({"state":m.state_dict()},p)
    report={"schema":"janus.native.r71d7.candidates.v1","parent_sha256":tr["parent_sha256"],"parent_tensor_sha256":pin,"train_spec_sha256":sha(canonical(tr)),"train_pairs":len(rows),"train_sha256":sha(canonical(rows)),"variants":{"verifier":{"sha256":sha(p.read_bytes()),"trainable_parameters":sum(v.numel() for v in m.parameters()),"losses":losses}},"production_changed":False}
    report["receipt_sha256"]=sha(canonical(report));Path(out,"RECEIPT.json").write_bytes(canonical(report));print("R71D7_TRAIN "+json.dumps(report,sort_keys=True))
if __name__=="__main__":main()
