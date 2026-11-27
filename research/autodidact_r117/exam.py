"""Run in isolated NumPy-only venv. Read numeric fixtures, not PyTorch files."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import numpy as np
from native_core import NativeCore, AdamW, generate, shapes, seal, require

require(importlib.util.find_spec("torch") is None,"TORCH_PRESENT")
require(importlib.util.find_spec("tensorflow") is None and importlib.util.find_spec("jax") is None,"OTHER_FRAMEWORK_PRESENT")
p=Path(os.environ["RUNNER_TEMP"])/"r117-reference"
r=json.loads((p/"receipt.json").read_text())
require(r["schema"]=="janus.r117.reference.v1" and r["parent_sha256"]=="06d7e6228ca9aef2dc58eb55fe1c805aa3b66e4f8fb90b0e946ce6af47b1a662" and r["source_commit"]=="fc4293c972c231e9b06dd286a74c840b69131baa","REFERENCE_IDENTITY")
require(r["cases"]==[[2,9],[2,32],[1,128]] and r["steps"]==3 and r["parameters"]==446208,"REFERENCE_DESIGN")
require((p/"reference.npz").stat().st_size<100_000_000,"FIXTURE_SIZE")
require(hashlib.sha256((p/"reference.npz").read_bytes()).hexdigest()==r["npz_sha256"],"FIXTURE_SHA")
data=np.load(p/"reference.npz",allow_pickle=False)
names=shapes()
w={k:data["w:"+k] for k in names}
require(sum(a.size for a in w.values())==446208,"PARAMETER_COUNT")
parent_digest=seal(w)
net=NativeCore(w); opt=AdamW(net.w)
def compare(a,b,tol,label):
    require(a.shape==b.shape and np.isfinite(a).all() and np.isfinite(b).all(),"COMPARE_SHAPE:"+label)
    delta=float(np.max(np.abs(a-b)))
    require(delta<=tol,f"{label}:{delta}")
    return delta
def tensor_compare(a,prefix,tol):
    return max(compare(v,data[prefix+k],tol,prefix+k) for k,v in a.items())
# Finite differences independently check a deterministic direction per
# selected parameter group; no PyTorch gradient used in this test.
x=data["x:0"]; y=data["y:0"]
loss,z,g=net.loss_grad(x,y)
rng=np.random.default_rng(117002)
fd=[]
for k in ("token.weight","pos.weight","blocks.layers.0.self_attn.in_proj_weight","blocks.layers.1.linear1.weight","norm.weight","blocks.layers.0.norm1.bias"):
    a=net.w[k]
    direction=rng.normal(size=a.shape); direction/=np.linalg.norm(direction)
    old=a.copy(); eps=1e-5
    a[...]=old+eps*direction
    lp=net.loss_grad(x,y)[0]
    a[...]=old-eps*direction
    lm=net.loss_grad(x,y)[0]
    a[...]=old
    numeric=(lp-lm)/(2*eps); analytic=float(np.sum(g[k]*direction))
    err=abs(numeric-analytic)
    require(err<=1e-7+1e-5*abs(analytic),"FINITE_DIFFERENCE:"+k)
    fd.append({"parameter":k,"analytic":analytic,"numerical":numeric,"absolute_error":err})
require(seal(net.w)==parent_digest,"FD_MUTATION")
# Causality: a changed suffix may not change the prefix logits.
x2=x.copy(); x2[:,5:]=(x2[:,5:]+19)%256
causal_error=compare(net.forward(x)[0][:,:5],net.forward(x2)[0][:,:5],1e-10,"CAUSAL_PREFIX")
steps=[]
for i in range(3):
    x=data[f"x:{i}"]; y=data[f"y:{i}"]
    loss,z,g=net.loss_grad(x,y)
    row={"step":i+1,"shape":list(x.shape),"loss":loss,"loss_error":abs(loss-float(data[f"loss:{i}"])),"logit_error":compare(z,data[f"logits:{i}"],1e-8,"LOGITS"),"top1_agreement":float(np.mean(z.argmax(-1)==data[f"logits:{i}"].argmax(-1))),"gradient_error":tensor_compare(g,f"g:{i}:",1e-8)}
    require(row["loss_error"]<=1e-10 and row["top1_agreement"]==1.,"FORWARD_MATCH")
    opt.step(net.w,g)
    row["weight_error"]=tensor_compare(net.w,f"u:{i}:",1e-8)
    row["moment1_error"]=tensor_compare(opt.m,f"m:{i}:",1e-8)
    row["moment2_error"]=tensor_compare(opt.v,f"v:{i}:",1e-8)
    steps.append(row)
    print("AUTODIDACT_R117_STEP",json.dumps(row,sort_keys=True),flush=True)
gen=[]
for i in range(2):
    actual=generate(net,data[f"prompt:{i}"].tolist(),5)
    expected=data[f"generation:{i}"].tolist()
    require(actual==expected,"GENERATION_MATCH")
    gen.append({"prompt_index":i,"tokens":len(actual),"exact":True})
# A new synthetic batch not included in the reference fixture: actual
# native-only training, repeated fit sanity (not unseen-task learning).
x=rng.integers(0,256,(2,16),dtype=np.int64); x[:,0]=256
y=rng.integers(0,258,(2,16),dtype=np.int64)
baseline=net.loss_grad(x,y)[0]
snap=opt.snapshot(net.w); digest=opt.digest(net.w)
native_losses=[baseline]
for _ in range(3):
    _,_,g=net.loss_grad(x,y)
    opt.step(net.w,g)
    native_losses.append(net.loss_grad(x,y)[0])
require(native_losses[-1]<baseline and opt.digest(net.w)!=digest,"NATIVE_UPDATE")
opt.restore(net.w,snap)
require(opt.digest(net.w)==digest and seal(w)==parent_digest,"EXACT_ROLLBACK")
require(not any(k=="torch" or k.startswith("torch.") for k in sys.modules),"TORCH_IMPORTED")
result={"schema":"janus.autodidact.r117.native_neural_core.v1","status":"NUMPY_NATIVE_PARITY_PASS__PRODUCTION_HOLD","reference":r,"numpy_version":np.__version__,"torch_installed":False,"torch_imported":False,"parameters":446208,"parent_numeric_digest":parent_digest,"native_steps":steps,"finite_difference":fd,"causal_prefix_error":causal_error,"greedy_generation":gen,"native_only_fit_losses":native_losses,"rollback_verified":True,"claims":{"dropout_training_tested":False,"float32_parity_tested":False,"full_curriculum_tested":False,"external_blind_exam":False,"native_training_tested":True,"native_inference_tested":True,"native_runtime_framework_free":True,"numpy_dependency":True,"production_changed":False,"promotion_authority":False,"candidate_exported":False}}
out=Path(os.environ["RUNNER_TEMP"])/"r117-result.json"
out.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
print("AUTODIDACT_R117_RESULT",json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
