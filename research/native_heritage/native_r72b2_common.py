"""R72B2 separate ancestry, leaf, value and typed features."""
from native_r72b_common import *
from native_r72b_common import features as original_features,synthetic as original_synthetic
TYPES=("integer","number","boolean","null","string")
def split_rows(rows,view):
    out=[]
    for r in rows:
        x=dict(r);p=r["path"]
        if view=="leaf":x["path"]=p[-1:];x["value"]=""
        elif view=="ancestor":x["path"]=p[:-1];x["value"]=""
        else:x["path"]=[]
        out.append(x)
    return out
def features(parent,rows,mode="full"):
    bs=[];hs=[]
    for view in ("ancestor","leaf","value"):
        r=split_rows(rows,view)
        b,h=original_features(parent,r,"full")
        if (mode=="key" and view=="value") or (mode=="value" and view!="value"):b.zero_();h.zero_()
        bs.append(b);hs.append(h)
    typ=torch.tensor([[float(r["type"]==t) for t in TYPES] for r in rows])
    return torch.cat(bs+[typ],-1),torch.cat(hs,-1)
class SemanticHead(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only;self.net=nn.Sequential(nn.Linear(768+5+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.2),nn.Linear(128,len(LABELS)))
    def forward(self,b,h):
        return self.net(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1))
def synthetic(exam=False):
    if not exam:
        rows=original_synthetic(False)
        pairs=[
            ("measurement","evidence_statement","observed 21 candidate traces","replay reproduced the stored output"),
            ("measurement","status_policy","observed error rate 0.08","maximum permitted error rate 0.08"),
            ("evidence_statement","epistemic_limit","independent replication reproduced the result","independent replication has not been performed"),
            ("evidence_statement","hypothesis_plan","benchmark completed and recorded the output","benchmark is planned to test the expected output"),
            ("epistemic_limit","hypothesis_plan","no compatible external samples are available","collect compatible external samples in a future study"),
            ("provenance","relation","source revision c91fbe","source component belongs to worker alpha"),
            ("measurement","epistemic_limit","measured accuracy was 0.92","accuracy is undefined; no predictions issued"),
            ("status_policy","evidence_statement","release is blocked pending review","replay checksum comparison passed")]
    else:
        rows=[]
        pairs=[
            ("measurement","status_policy","recorded 72 completed events","minimum required events is 72"),
            ("measurement","epistemic_limit","observed precision 0.81","precision not evaluated on external data"),
            ("evidence_statement","epistemic_limit","source comparison reproduced the archived trace","source comparison did not establish a real-world effect"),
            ("evidence_statement","hypothesis_plan","the validation run reproduced the result","a subsequent validation run is proposed"),
            ("hypothesis_plan","epistemic_limit","obtain authenticated witnesses in the next experiment","authenticated witnesses have not been obtained"),
            ("provenance","relation","pinned blob checksum 32adfc","supervisor is the parent of this worker"),
            ("status_policy","evidence_statement","automatic activation remains forbidden","the unit test returned success"),
            ("other","provenance","document caption for the experiment","receipt from the immutable source archive")]
    for i,(a,b,x,y) in enumerate(pairs):
        for path in (["record","detail"],["entry","note"],["result","statement"]):
            for label,v in ((a,x),(b,y)):
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(v),"label":label,"contrast_id":str(i)+":"+path[-1]})
    return rows
