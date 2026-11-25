from native_r72b4_common import *
from native_r72b4_common import Specialist as B4Head,synthetic as b4_synthetic,specialist_features as b4_features
# Separate negated action, uncertainty, temporal intent, and observed null outcome.
SCOPE_CUES=(
r"\b(?:not|never|no|yet to|failed to|unable to|could not|cannot|couldn't|hasn't|haven't|didn't|wasn't|weren't)\b",
r"\b(?:uncertain|unknown|unavailable|undetermined|unresolved|inconclusive|unconfirmed|unverified|missing|pending|insufficient|lacks?|not yet)\b",
r"\b(?:may|might|could|possibly|potentially|suggests?|appears?|seems?|hypothetical)\b",
r"\b(?:will|shall|should|planned|proposed|scheduled|intend\w*|future|next|await\w*|to be)\b",
r"^(?:[\"']?\s*)?(?:perform|conduct|collect|obtain|repeat|evaluate|test|verify|check|request|compare|seek|measure|assess|run|gather|ask|establish|authenticate)\b",
r"\b(?:completed|conducted|performed|executed|ran|recorded|observed|measured|reported|found|detected|returned|reproduced|confirmed|matched|verified|passed)\b",
r"\b(?:no|zero|without|absence of|none)\s+(?:significant\s+)?(?:difference|effect|gain|improvement|signal|errors?|mismatch|change|discrepanc|detections?)",
r"\b(?:not|never|yet to|failed to|could not|unable to)\s+(?:be\s+|been\s+|independently\s+|successfully\s+){0,3}(?:conduct|perform|run|execut|test|verif|confirm|evaluat|obtain|establish|replicat|measur|reproduc|authenticat)",
r"\b(?:not|no|never|cannot|unable|insufficient|lack)\b.{0,45}\b(?:independent|external|blind|physical|scientific|proof|evidence|validity|causal|witness)\b",
r"\b(?:although|but|however|yet|only|within|limited|not beyond)\b",
r"\b(?:if|unless|conditional|assuming|would|requires?|needed|must)\b",
r"\b(?:null|false|true|hold|pass|success|blocked)\b")
def scope_cues(rows):
    data=[]
    for row in rows:
        key="/".join(map(str,row["path"])).lower().replace("_"," ")
        val=row["value"].lower().replace("_"," ")
        data.append([float(bool(re.search(p,x))) for x in (key,val) for p in SCOPE_CUES])
    return torch.tensor(data,dtype=torch.float32)
def specialist_features(parent,rows,mode="full"):
    b,h=b4_features(parent,rows,mode);return torch.cat([b,scope_cues(rows)],-1),h
class Specialist(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only
        self.net=nn.Sequential(nn.Linear(768+5+20+24+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.15),nn.Linear(128,4))
    def forward(self,b,h):
        return self.net(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1))
def synthetic(exam=False):
    rows=[] if exam else b4_synthetic(False)
    # Distinct training/exam stems and templates, not random split of paraphrase rows.
    stems=[
      ("the independent calibration","a timing discrepancy","the timing standard"),
      ("the external reconstruction","a difference in amplitude","the source trace"),
      ("the second laboratory trial","a reproducible effect","the reference samples"),
      ("the separate detector audit","a mismatch in labels","the detector output"),
      ("the witness validation","a significant shift","the event record"),
      ("the archived replay","a change in score","the replay manifest")
    ] if exam else [
      ("the baseline comparison","a detectable improvement","the archived output"),
      ("the source integrity test","a checksum mismatch","the source data"),
      ("the independent benchmark","a latency difference","the benchmark record"),
      ("the controlled experiment","a measurable gain","the test cases"),
      ("the verification run","a scoring error","the frozen candidate"),
      ("the repeated measurement","a change in frequency","the recorded signal"),
      ("the paired replication","a difference in accuracy","the response log"),
      ("the historical audit","an unexpected result","the audit manifest"),
      ("the sensitivity trial","a significant effect","the control group"),
      ("the recovery exercise","a lost response","the saved checkpoint")
    ]
    for i,(subject,outcome,target) in enumerate(stems):
        if exam:
            cases=[
              ("evidence_statement",f"{subject} was performed and found no {outcome.removeprefix('a ').removeprefix('an ')}","negative_result"),
              ("epistemic_limit",f"{subject} has yet to be performed; {target} remains unverified","negated_execution"),
              ("hypothesis_plan",f"conduct {subject} to determine whether there is {outcome}","future"),
              ("epistemic_limit",f"{subject} may indicate {outcome}, but evidence is inconclusive","uncertainty"),
              ("evidence_statement",f"{subject} returned matching records for {target}","positive"),
              ("epistemic_limit",f"{subject} confirmed the internal record but not the independent provenance of {target}","mixed_scope"),
              ("hypothesis_plan",f"{subject} is scheduled to assess {target}","future"),
              ("other",f"identifier for {subject}: {i+700}","other")]
        else:
            cases=[
              ("evidence_statement",f"{subject} completed and detected zero {outcome.removeprefix('a ').removeprefix('an ')}","negative_result"),
              ("epistemic_limit",f"{subject} was not conducted and no result is available","negated_execution"),
              ("hypothesis_plan",f"perform {subject} in a future evaluation of {target}","future"),
              ("epistemic_limit",f"{subject} might suggest {outcome}; independent confirmation is missing","uncertainty"),
              ("evidence_statement",f"{subject} reproduced the recorded values of {target}","positive"),
              ("epistemic_limit",f"{subject} passed internally but cannot establish external validity of {target}","mixed_scope"),
              ("hypothesis_plan",f"the next step will evaluate {target} using {subject}","future"),
              ("other",f"record name for {subject}","other")]
        for j,path in enumerate((["record","detail"],["audit","statement"],["entry","note"])):
            for k,(label,val,cohort) in enumerate(cases):
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(val),"label":label,"contrast_id":f"{i}:{j}:{k}","cohort":cohort,"family":str(i)})
    return rows
def guard_decision(old,new):
    # Standalone guard proposes a class. Conservative public evidence route
    # requires agreement with frozen B4; disagreement is abstention, not a correct answer.
    return torch.where((new==0)&(old!=0),torch.full_like(new,-1),new)
def selective_stats(y,p):
    keep=p>=0;correct=keep&(p==y);crit=(y==1)|(y==2)
    return {"n":len(y),"accepted":int(keep.sum()),"correct":int(correct.sum()),"wrong":int((keep&~correct).sum()),"abstained":int((~keep).sum()),"critical_as_evidence":int((crit&(p==0)).sum()),"evidence_accepted_correct":int(((y==0)&(p==0)).sum()),"evidence_n":int((y==0).sum())}
