from native_r72b3_common import *
from native_r72b3_common import SemanticHead as B3Head,synthetic as b3_synthetic,features as old_features
from native_r72b2_common import SemanticHead as B2Head
GROUP_NAMES=("evidence_statement","hypothesis_plan","epistemic_limit","other")

def groups(y):
    return torch.tensor(GROUP,dtype=torch.long,device=y.device)[y]

CUES=(r"\b(no|not|never|without|unavailable|missing|undefined|cannot|could not|did not|has not|have not|lack|unverified)\b",r"\b(will|plan|planned|propos\w*|next|future|schedule\w*|intend\w*|await\w*|may|might)\b",r"\b(passed|success\w*|reproduc\w*|confirm\w*|verif\w*|matched|completed|recorded|observed|authenticated|established)\b",r"not[_ ]established|not[_ ]supported|not[_ ]observed|hold|not[_ ]tested",r"[_ ]verified|[_ ]passed|[_ ]unchanged|[_ ]preserved|[_ ]completed",r"claim|caveat|limit|boundary|independen|external|blind",r"next|objective|proposal|remaining|future",r"checksum|digest|sha256|commit|artifact|receipt",r"true|false|null",r"\btest\b|\baudit\b|\breplay\b|\breplication\b")
def cue_features(rows,mode="full"):
    vals=[]
    for r in rows:
        k="/".join(map(str,r["path"])).lower().replace("_"," ") if mode!="value" else ""
        v=r["value"].lower().replace("_"," ") if mode!="key" else ""
        vals.append([float(bool(re.search(p,x))) for x in (k,v) for p in CUES])
    return torch.tensor(vals,dtype=torch.float32)
def specialist_features(parent,rows,mode="full"):
    b,h=old_features(parent,rows,mode);return torch.cat([b,cue_features(rows,mode)],-1),h
class Specialist(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only
        self.net=nn.Sequential(nn.Linear(768+5+20+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.15),nn.Linear(128,4))
    def forward(self,b,h):
        return self.net(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1))
def synthetic(exam=False):
    rows=[] if exam else b3_synthetic(False)
    triples=[
      ("the reviewer independently checked the archived result","the reviewer has yet to check the archived result","ask the reviewer to check the archived result"),
      ("the repeat trial returned matching outputs","the repeat trial was never carried out","carry out a repeat trial to compare outputs"),
      ("the witness timestamps were confirmed by a second record","a second record was unavailable to confirm the timestamps","obtain a second record to corroborate timestamps"),
      ("the comparison showed the expected numerical agreement","the comparison does not substantiate the physical interpretation","perform a further comparison to evaluate that interpretation"),
      ("the replay passed the predefined tolerance","the tolerance could not be evaluated","evaluate the tolerance on a separate replay"),
      ("the validation log recorded a matching result","the validation log lacks an independent reference","collect an independent reference for validation")
    ] if exam else [
      ("the test successfully checked the archived data","the archived data have not been checked","check the archived data in a future test"),
      ("the two outputs agreed on the observed case","agreement on other cases has not been established","test agreement on other cases"),
      ("the audit verified the source fingerprint","the fingerprint was missing from the audit","retrieve the fingerprint for the next audit"),
      ("the baseline rerun completed successfully","the baseline rerun could not complete","repeat the baseline run after repair"),
      ("the report recorded reproducible observations","the report does not demonstrate external validity","evaluate external validity with a new cohort"),
      ("the reviewer confirmed the receipt","the reviewer has not confirmed the receipt","request confirmation of the receipt"),
      ("the recorded checks matched","the checks were not performed","perform the checks before review"),
      ("the original result was reproduced","the result is not independently replicated","attempt independent replication"),
      ("the archived traces support the bounded conclusion","the traces do not support a broader conclusion","test the broader conclusion separately"),
      ("the verification established the data match","the data match could not be verified","verify the data match with an additional source")
    ]
    others=["document caption","observed 15 samples","minimum allowed count is 15","source repository beta","checkpoint revision 88abc","worker belongs to parent module"] if exam else ["record title","measured 27 records","required threshold 0.95","archive digest ffa23","agent inherits parent alpha","schema version 1.2"]
    other_labels=("other","measurement","status_policy","relation","provenance","relation") if exam else ("other","measurement","status_policy","provenance","relation","other")
    for i,vals in enumerate(triples):
        for j,path in enumerate((["record","detail"],["entry","note"],["audit","summary"])):
            for label,val in zip(GROUP_NAMES[:3],vals):
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(val),"label":label,"contrast_id":str(i)+":"+str(j)})
    for i,(label,v) in enumerate(zip(other_labels,others)):
        for j,path in enumerate((["record","detail"],["entry","note"],["audit","summary"])):
            rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(v),"label":label,"contrast_id":"other:"+str(i)+":"+str(j)})
    return rows
def group_stats(y,p):
    mat=torch.zeros(4,4,dtype=torch.long)
    for a,b in zip(y.tolist(),p.tolist()):mat[a,b]+=1
    by={}
    for i,k in enumerate(GROUP_NAMES):
        n=int(mat[i].sum());pred=int(mat[:,i].sum());tp=int(mat[i,i])
        by[k]={"n":n,"correct":tp,"recall":tp/n if n else None,"f1":2*tp/(n+pred) if n+pred else 0}
    return {"n":len(y),"exact":int((p==y).sum()),"accuracy":float((p==y).float().mean()),"macro_f1":sum(v["f1"] for v in by.values() if v["n"])/sum(v["n"]>0 for v in by.values()),"by_group":by,"critical_as_evidence":int(mat[1,0]+mat[2,0]),"confusion":mat.tolist()}
def frozen_heads(folder,pin,sha_by,basepin,d,cls):
    receipt=read(Path(folder)/"RECEIPT.json");actual=receipt.pop("receipt_sha256")
    req(actual==pin==sha(canonical(receipt)) and receipt["parent_tensor_sha256"]==basepin,"FROZEN_SEAL")
    out={}
    for name,expected in sha_by.items():
        p=Path(folder)/(name+".pt");req(sha(p.read_bytes())==expected==receipt["variants"][name]["sha256"],"FROZEN_SHA")
        obj=torch.load(p,map_location="cpu",weights_only=True);m=cls(d,obj["byte_only"]);m.load_state_dict(obj["state"],strict=True);m.requires_grad_(False);m.eval();out[name]=m
    return out
