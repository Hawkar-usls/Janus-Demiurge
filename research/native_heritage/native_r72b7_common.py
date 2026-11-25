from native_r72b6b_common import locked_scope, fresh_cases as b6b_cases
from native_r72b6_common import *
from native_r72b6_common import synthetic as b6_cases
# The student sees raw bytes only, not witness spans, route names or regex features.
# Native arm also sees frozen native representations from 128-byte chunks.
MAX_BYTES=384
def text_rows(items,source):
    out=[]
    for i,(v,e,o,c) in enumerate(items):
        g=int(compose(torch.tensor([e]),torch.tensor([o]))[0]);req(g>=0,"LABEL")
        out.append({"source":source,"path":["record","statement"],"type":"string","value":json.dumps(v),"label":GROUP_NAMES[g],"event":e,"outcome":o,"cohort":c,"family":str(i),"contrast_id":str(i)})
    return out
def training_pool():
    # Each grammar varies both nouns and syntax. Labels are authored first;
    # teacher is used only to admit agreeing examples, never to label exam rows.
    stems=[
      ("vibration trial","an excess signal","the vibration log"),
      ("pressure audit","a measurable drift","the pressure readings"),
      ("thermal experiment","a significant difference","the temperature series"),
      ("calibration exercise","an additional error","the calibration record"),
      ("receiver benchmark","a detectable gain","the receiver log"),
      ("timing check","a timing mismatch","the time series"),
      ("filter comparison","a reproducible effect","the filter trace"),
      ("independent review","an amplitude change","the reference output"),
      ("field survey","an observable deviation","the survey log"),
      ("validation session","a new anomaly","the validation data"),
      ("spectral scan","a new peak","the spectral record"),
      ("measurement series","a correlation","the measured values"),
      ("verification audit","a detectable improvement","the signed record"),
      ("detector evaluation","a response","the detector map"),
      ("controlled test","a significant shift","the control traces"),
      ("numeric comparison","an increase","the stored values"),
      ("replication run","a measurable reduction","the replication log"),
      ("observational study","a variation","the source record"),
      ("stability assessment","a discrepancy","the stability report"),
      ("recovery trial","an unexpected change","the restored checkpoint")
    ]
    out=[]
    for sub,obj,target in stems:
        noun=obj.removeprefix("a ").removeprefix("an ")
        # Shared content across positive/negative/denied cases prevents topic shortcuts.
        for done in ("was conducted","was performed","was completed","was executed","took place","went ahead","was carried out","finished"):
            for obs in ("found","recorded","detected","observed","revealed","identified"):
                out.extend([
                    (f"The {sub} {done} and {obs} {obj}.",0,0,"positive"),
                    (f"The {sub} {done} and {obs} no {noun}.",0,1,"negative_result"),
                    (f"The {sub} {done}; investigators {obs} zero {noun}.",0,1,"negative_result"),
                    (f"After the {sub} {done}, the team {obs} no significant {noun}.",0,1,"negative_result"),
                    (f"The {sub} {done}, but {target} was inconclusive.",0,2,"completed_unknown"),
                    (f"The {sub} {done} and {obs} {obj}, but external validity is not established.",0,3,"mixed_scope")])
        for deny in ("was not conducted","was never performed","has not been carried out","was not executed","did not run","never ran","has yet to be started","was called off before execution","failed to perform"):
            for tail in ("; no result exists.","; the outcome is unknown.","; no findings are available.","; there are no measurements."):
                out.append((f"The {sub} {deny}{tail}",1,2,"negated_execution"))
        for f in ("is scheduled to examine","will be conducted to evaluate","is planned to assess","is proposed to check"):
            out.append((f"The {sub} {f} {target}.",2,2,"future"))
        for f in ("Conduct","Repeat","Perform","Run","Evaluate"):
            out.append((f"{f} the {sub} to determine whether there is {obj}.",2,2,"future"))
        for f in ("It is unknown whether","It remains unclear whether","It is uncertain whether"):
            out.append((f"{f} the {sub} took place; no confirmed result exists.",3,2,"uncertainty"))
        for f in ("may have been performed","might have been completed","could have been conducted"):
            out.append((f"The {sub} {f}; {target} is missing.",3,2,"uncertainty"))
        for f in ("Identifier","Title","Document caption","Reference number","Metadata label"):
            out.append((f"{f} for the {sub}: {target}.",4,4,"other"))
    return text_rows(out,"teacher_train")
def admitted_train():
    generated=training_pool();unique={}
    for row in generated:
        key=row["value"]
        if key in unique: req((unique[key]["event"],unique[key]["outcome"])==(row["event"],row["outcome"]),"CONFLICTING_TRAIN_LABEL")
        else: unique[key]=row
    pool=list(unique.values());accepted=[];reject=collections.Counter()
    for r in pool:
        a,b,route,_=locked_scope(r,-1,-1)
        if (a,b)==(r["event"],r["outcome"]):
            accepted.append(r)
        else:reject[route]+=1
    req(len(accepted)>0,"EMPTY_TEACHER")
    return accepted,{"generated":len(generated),"duplicate_texts_removed":len(generated)-len(pool),"pool":len(pool),"admitted":len(accepted),"rejected":len(pool)-len(accepted),"rejected_routes":dict(reject),"by_cohort":dict(collections.Counter(r["cohort"] for r in accepted))}
def new_exam():
    # Novel construction and content; intentionally includes teacher blind spots.
    # One text per item, no padding by repeated metadata paths.
    items=[]
    stems=[
      ("gravimeter survey","a residual acceleration","the gravimeter readings"),
      ("cryogenic sensor assay","a voltage excursion","the cryogenic traces"),
      ("polarization assessment","an unexpected rotation","the polarimetry data"),
      ("neutron counter check","an excess count","the counter output"),
      ("hydrophone analysis","a transient echo","the acoustic samples"),
      ("orbital reconstruction","an orbital deviation","the reconstructed path"),
      ("photodiode validation","a sensitivity loss","the diode response"),
      ("microfluidic observation","a flow irregularity","the recorded flow")
    ]
    for sub,obj,target in stems:
        noun=obj.removeprefix("a ").removeprefix("an ")
        items.extend([
          (f"No {noun} was found when the {sub} was undertaken.",0,1,"negative_result"),
          (f"The researchers ran the {sub}. They did not observe {obj}.",0,1,"negative_result"),
          (f"Although the {sub} was carried out, the instruments showed no {noun}.",0,1,"negative_result"),
          (f"Zero instances of {noun} appeared in {target} after the {sub} finished.",0,1,"negative_result"),
          (f"The {sub} was never initiated, so {target} does not exist.",1,2,"negated_execution"),
          (f"No actual {sub} took place; the team has no findings.",1,2,"negated_execution"),
          (f"The team did not actually launch the {sub}.",1,2,"negated_execution"),
          (f"Before data collection, the {sub} was cancelled.",1,2,"negated_execution"),
          (f"The {sub} went ahead; {target} showed {obj}.",0,0,"positive"),
          (f"Having completed the {sub}, the investigators confirmed {obj}.",0,0,"positive"),
          (f"The {sub} is to be conducted at the next opportunity.",2,2,"future"),
          (f"Next week, the group will undertake the {sub}.",2,2,"future"),
          (f"Whether the {sub} ever happened remains unclear.",3,2,"uncertainty"),
          (f"The {sub} might have taken place, but no records survive.",3,2,"uncertainty"),
          (f"The {sub} was concluded, but the observations were uninterpretable.",0,2,"completed_unknown"),
          (f"The {sub} was performed; the result cannot be determined from {target}.",0,2,"completed_unknown"),
          (f"The {sub} confirmed internal consistency, but the external validity remains unproven.",0,3,"mixed_scope"),
          (f"The {sub} was completed and the local result matched; however the broader causal conclusion is unsupported.",0,3,"mixed_scope"),
          (f"Catalogue entry for the {sub}: {target}.",4,4,"other"),
          (f"Metadata label: the {sub} archive.",4,4,"other")])
    return text_rows(items,"fresh_exam")
def raw_features(parent,rows,batch=64):
    raw=[]
    for row in rows:
        try:v=json.loads(row["value"])
        except Exception:v=row["value"]
        if not isinstance(v,str):v=row["value"]
        b=v.encode("utf-8");req(len(b)<=MAX_BYTES,"TEXT_TOO_LONG")
        raw.append(list(b))
    x=torch.full((len(rows),MAX_BYTES),256,dtype=torch.long)
    mask=torch.zeros((len(rows),MAX_BYTES),dtype=torch.bool)
    for i,r in enumerate(raw):
        x[i,:len(r)]=torch.tensor(r,dtype=torch.long);mask[i,:len(r)]=True
    # Only active bytes; chunk representation is independent of teacher.
    d=parent.config.d_model
    n=torch.zeros((len(rows),3,d))
    captured=[]
    hook=parent.norm.register_forward_hook(lambda module,args,out: captured.append(out.detach()))
    try:
        with torch.inference_mode():
            for i in range(0,len(rows),batch):
                xx=x[i:i+batch];mm=mask[i:i+batch]
                for j in range(3):
                    a=xx[:,j*128:(j+1)*128];m=mm[:,j*128:(j+1)*128]
                    captured.clear();parent(a)
                    z=captured[-1];n[i:i+len(a),j]=(z*m.unsqueeze(-1)).sum(1)/m.sum(1).clamp_min(1).unsqueeze(-1)
    finally:hook.remove()
    return x,mask,n
class Student(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only
        self.emb=nn.Embedding(257,32,padding_idx=256)
        self.convs=nn.ModuleList(nn.Conv1d(32,48,k,padding=k//2) for k in (3,5,9))
        self.seq=nn.GRU(144,48,batch_first=True,bidirectional=True)
        self.trunk=nn.Sequential(nn.Linear(96*2+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.15))
        self.event=nn.Linear(128,5);self.outcome=nn.Linear(128,5)
    def forward(self,x,mask,n):
        # Truncate padding to longest active sample per batch.
        length=max(1,int(mask.sum(1).max()));x=x[:,:length];mask=mask[:,:length]
        z=self.emb(x).transpose(1,2)
        z=torch.cat([F.gelu(c(z)) for c in self.convs],1).transpose(1,2)
        packed=nn.utils.rnn.pack_padded_sequence(z,mask.sum(1).clamp_min(1).cpu(),batch_first=True,enforce_sorted=False)
        z,_=self.seq(packed);z,_=nn.utils.rnn.pad_packed_sequence(z,batch_first=True,total_length=length)
        avg=(z*mask.unsqueeze(-1)).sum(1)/mask.sum(1).clamp_min(1).unsqueeze(-1)
        mx=z.masked_fill(~mask.unsqueeze(-1),-1e4).amax(1)
        native=torch.zeros_like(n) if self.byte_only else F.normalize(n,dim=-1)
        q=self.trunk(torch.cat([avg,mx,native.flatten(1)],-1))
        return self.event(q),self.outcome(q)
def predict_student(m,x,mask,n,batch=48):
    e=[];o=[]
    with torch.inference_mode():
        for i in range(0,len(x),batch):
            a,b=m(x[i:i+batch],mask[i:i+batch],n[i:i+batch]);e.append(a.argmax(-1));o.append(b.argmax(-1))
    return torch.cat(e),torch.cat(o)
