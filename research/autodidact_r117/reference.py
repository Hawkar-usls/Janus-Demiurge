"""One-off reference only. Export trusted numeric tensors, never pickle output."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import torch
from janus_model.train_registry import load_checkpoint

PIN="06d7e6228ca9aef2dc58eb55fe1c805aa3b66e4f8fb90b0e946ce6af47b1a662"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
torch.backends.mha.set_fastpath_enabled(False)
parent=Path("janus_model/checkpoints/promoted.pt")
require(sha(parent)==PIN,"PARENT_PIN")
model,_=load_checkpoint(parent,expected_sha256=PIN)
cfg=model.config.to_dict()
require(cfg=={"vocab_size":258,"context_length":128,"d_model":128,"n_heads":4,"n_layers":2,"ff_mult":4,"dropout":0.1},"CONFIG")
model=model.double().eval()
require(model.token.weight is model.lm_head.weight,"TIED_WEIGHT")
params=dict(model.named_parameters())
require(sum(p.numel() for p in params.values())==446208,"PARAM_COUNT")
def arr(t): return t.detach().cpu().numpy().copy()
out={"w:"+k:arr(v) for k,v in params.items()}
opt=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01,foreach=False,fused=False)
rng=np.random.default_rng(117001)
cases=[(2,9),(2,32),(1,128)]
# All forward positions and all 258 logits, including maximum context.
for i,(b,t) in enumerate(cases):
    x=rng.integers(0,256,(b,t),dtype=np.int64); x[:,0]=256
    y=rng.integers(0,258,(b,t),dtype=np.int64)
    opt.zero_grad(set_to_none=True)
    logits,_=model(torch.from_numpy(x))
    loss=torch.nn.functional.cross_entropy(logits.reshape(-1,258),torch.from_numpy(y).reshape(-1))
    loss.backward()
    out[f"x:{i}"]=x; out[f"y:{i}"]=y
    out[f"logits:{i}"]=arr(logits); out[f"loss:{i}"]=np.array(loss.item(),dtype=np.float64)
    for k,p in params.items(): out[f"g:{i}:"+k]=arr(p.grad)
    opt.step()
    for k,p in params.items():
        out[f"u:{i}:"+k]=arr(p)
        out[f"m:{i}:"+k]=arr(opt.state[p]["exp_avg"])
        out[f"v:{i}:"+k]=arr(opt.state[p]["exp_avg_sq"])
# Unconstrained autoregressive comparison, not an answer-accuracy test.
with torch.no_grad():
    for i,prompt in enumerate(([256,67,111,112,121,58,32],[256,123,34,120,34,58])):
        ids=list(prompt)
        for _ in range(5):
            z,_=model(torch.tensor([ids],dtype=torch.long))
            ids.append(int(z[0,-1].argmax()))
        out[f"prompt:{i}"]=np.array(prompt,dtype=np.int64)
        out[f"generation:{i}"]=np.array(ids[len(prompt):],dtype=np.int64)
require(sha(parent)==PIN,"PARENT_MUTATION")
dest=Path(os.environ["RUNNER_TEMP"])/"r117-reference"; dest.mkdir()
p=dest/"reference.npz"; np.savez_compressed(p,**out)
receipt={"schema":"janus.r117.reference.v1","parent_sha256":PIN,"source_commit":"fc4293c972c231e9b06dd286a74c840b69131baa","npz_sha256":sha(p),"config":cfg,"parameters":446208,"cases":cases,"dtype":"float64","optimizer":"AdamW","steps":3,"reference_only":True}
(dest/"receipt.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
print("AUTODIDACT_R117_REFERENCE",json.dumps(receipt,sort_keys=True),flush=True)
