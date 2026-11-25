"""R72B: operational semantic-role classification, no truth or promotion authority."""
from native_r72a_common import *
import fnmatch,collections
LABELS=("measurement","status_policy","provenance","relation","evidence_statement","hypothesis_plan","epistemic_limit","other")
def match(path,pattern):
    parts=pattern.split(".")
    return len(parts)==len(path) and all(p=="*" or p==str(q) for p,q in zip(parts,path))
def load_rows(spec,root):
    rows=[];coverage=[]
    for src in spec["sources"]:
        raw=(Path(root)/src["path"]).read_bytes();req(git_blob(raw)==src["blob"],"SOURCE_BLOB")
        doc,nodes=Scan(raw).parse()
        if spec["schema"].endswith("train.v1"):
            req(doc.get("storage_policy")!="reports_only_not_training_input","TRAIN_POLICY")
        matched=[0]*len(src["annotations"]);n=0
        for path,node in nodes.items():
            if node["kind"] in ("object","array"):continue
            found=[(i,a["label"]) for i,a in enumerate(src["annotations"]) if match(path,a["pattern"])]
            if not found:continue
            req(len(set(a for _,a in found))==1,"AMBIGUOUS_ANNOTATION")
            for i,_ in found:matched[i]+=1
            s,e=node["span"];label=found[0][1]
            rows.append({"source":src["path"],"path":list(path),"type":node["kind"],"value":raw[s:e].decode("utf-8"),"span":[s,e],"token_sha256":sha(raw[s:e]),"label":label});n+=1
        req(all(matched),"UNMATCHED_ANNOTATION:"+src["path"]+":"+str([a["pattern"] for a,m in zip(src["annotations"],matched) if not m]))
        coverage.append({"source":src["path"],"labeled":n,"all_leaves":sum(x["kind"] not in ("array","object") for x in nodes.values())})
    return rows,coverage
TRAIN_TEXT={
"measurement":["observed 57 correct detections","measured latency 0.125 seconds","test sample count 320","loss decreased by 0.37","recorded 18 errors"],
"status_policy":["deployment permission denied","required minimum is 100 records","automatic promotion disabled","threshold requires 95 percent","admission is HOLD"],
"provenance":["source commit abcdef012345","artifact digest 8f91a2","recorded by workflow run 231","checkpoint from immutable archive","receipt SHA256 matches archive identifier"],
"relation":["component belongs to parent module","child inherits from generation 4","agent linked to repository alpha","node is a peer of beta","sensor assigned to experiment group"],
"evidence_statement":["CI logs report all unit tests passed","verified replay reproduced result","observed run completed successfully","frozen test recorded identical outputs","archive integrity check passed"],
"hypothesis_plan":["proposed new experiment to test sensitivity","next step will evaluate a new cohort","candidate may improve detection","plan to collect independent observations","prediction requires future testing"],
"epistemic_limit":["not externally blinded","no independent evidence supports claim","causal interpretation remains unverified","accuracy undefined because no predictions","simulation does not establish physical effect"],
"other":["document title","version label r14","2026-07-12","descriptive topic list","schema revision 1.0"]}
EXAM_TEXT={
"measurement":["observations yielded 43 accepted traces","recorded runtime was 19 milliseconds","measured 12 localization errors"],
"status_policy":["service release is forbidden until review","mandatory sample quota 200","automatic merge is not permitted"],
"provenance":["immutable input blob identifier 784abc","originating run receipt digest 88e1","pinned archive revision 40fed"],
"relation":["worker delegates to supervisor gamma","successor references predecessor model","component is attached to the witness node"],
"evidence_statement":["replay test reproduced every stored output","CI report records 31 passing checks","verified checksum comparison matched"],
"hypothesis_plan":["future replication is proposed","candidate might reduce false alarms","schedule a new independent evaluation"],
"epistemic_limit":["test is not evidence of a physical discovery","no compatible independent witness was available","reported uplift is unknown rather than zero"],
"other":["record caption","2026-08-23","schema version tag v2"]}
def synthetic(exam=False):
    src=EXAM_TEXT if exam else TRAIN_TEXT;rows=[]
    for label,values in src.items():
        for i,v in enumerate(values):
            for path in (["record","detail"],["item","note"]):
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(v),"label":label,"contrast_id":str(i)+":"+path[-1]})
    return rows
def payload(row,mode="full"):
    p="/".join(str(x) for x in row["path"]);v=row["value"];t=row["type"]
    if mode=="key":v=""
    elif mode=="value":p=""
    # Keep beginning and leaf of long paths and front/back of value.
    pb=p.encode("utf-8");vb=v.encode("utf-8")
    if len(pb)>48:pb=pb[:16]+b"~"+pb[-31:]
    limit=127-len(pb)-len(t.encode())-4
    if len(vb)>limit:vb=vb[:max(0,limit-17)]+b"~"+vb[-16:]
    return (pb+b"|"+t.encode()+b"|"+vb)[:127]
def byte_features(raw):
    x=torch.zeros(256)
    for size in (1,2,3):
        for i in range(len(raw)-size+1):
            h=int.from_bytes(hashlib.blake2s(raw[i:i+size],digest_size=2).digest(),"big")%256
            x[h]+=1
    return F.normalize(torch.log1p(x),dim=0)
def features(parent,rows,mode="full"):
    byte=[];native=[]
    parent.eval()
    for i in range(0,len(rows),32):
        raws=[payload(r,mode) for r in rows[i:i+32]];ids=torch.zeros((len(raws),128),dtype=torch.long);mask=torch.zeros_like(ids,dtype=torch.bool)
        for j,raw in enumerate(raws):
            seq=[256]+list(raw);ids[j,:len(seq)]=torch.tensor(seq);mask[j,:len(seq)]=True;byte.append(byte_features(raw))
        cap=[];hook=parent.norm.register_forward_hook(lambda mod,inp,out:cap.append(out))
        try:
            with torch.no_grad():parent(ids)
        finally:hook.remove()
        req(len(cap)==1,"HIDDEN")
        h=cap[0];native.extend(F.normalize((h*mask[:,:,None]).sum(1)/mask.sum(1)[:,None],dim=-1).unbind())
    return torch.stack(byte),torch.stack(native)
class SemanticHead(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only;self.net=nn.Sequential(nn.Linear(256+d,96),nn.GELU(),nn.Linear(96,len(LABELS)))
    def forward(self,b,h):
        return self.net(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1))
def targets(rows):return torch.tensor([LABELS.index(r["label"]) for r in rows])
def lexical(row,mode="full"):
    key="/".join(str(x) for x in row["path"]).lower() if mode!="value" else ""
    value=row["value"].lower() if mode!="key" else ""
    x=key+" "+value
    checks=[
      ("epistemic_limit",r"not externally|not .*proof|not .*demonstrated|no independent|unverified|undefined|caveat|epistemic|not .*evidence|no compatible|scientific_interpretation"),
      ("hypothesis_plan",r"next|propos|hypothes|future.*test|plan to|might|objective"),
      ("provenance",r"sha256|sha1|digest|commit|artifact_id|run_id|receipt|source_protocol|source_code|revision"),
      ("status_policy",r"status|policy|allowed|permission|forbid|threshold|required|hold|gate|automatic|quota"),
      ("relation",r"repository|peer|inherits|parent|predecessor|delegates|attached|belongs|linked|specialty"),
      ("evidence_statement",r"pass|success|verified|reproduc|matched|completed"),
      ("measurement",r"count|rows|latency|runtime|auc|accuracy|loss|errors|localized|positives|measured|observed|detections")]
    for label,pattern in checks:
        if re.search(pattern,x):return LABELS.index(label)
    if mode!="key" and row["type"] in ("integer","number"):return 0
    return LABELS.index("other")
def stats(y,p):
    mat=torch.zeros(len(LABELS),len(LABELS),dtype=torch.long)
    for a,b in zip(y.tolist(),p.tolist()):mat[a,b]+=1
    by={}
    for i,k in enumerate(LABELS):
        n=int(mat[i].sum());pred=int(mat[:,i].sum());tp=int(mat[i,i]);rec=tp/n if n else None;pr=tp/pred if pred else 0
        by[k]={"n":n,"correct":tp,"recall":rec,"precision":pr,"f1":2*pr*rec/(pr+rec) if n and pr+rec else 0}
    critical=[LABELS.index(k) for k in ("hypothesis_plan","epistemic_limit")]
    ev=LABELS.index("evidence_statement")
    return {"n":len(y),"exact":int((y==p).sum()),"accuracy":float((y==p).float().mean()),"macro_f1":sum(v["f1"] for v in by.values() if v["n"])/sum(v["n"]>0 for v in by.values()),"by_role":by,"confusion":mat.tolist(),"critical_as_evidence":sum(int(mat[i,ev]) for i in critical)}
