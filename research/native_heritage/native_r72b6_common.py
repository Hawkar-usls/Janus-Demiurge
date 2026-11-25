from native_r72b5_common import *
from native_r72b5_common import Specialist as B5Head,synthetic as b5_synthetic,specialist_features as b5_features
EVENTS=("completed","not_performed","planned","uncertain","other")
OUTCOMES=("positive","negative","unknown","mixed","not_applicable")
# Ordered clause patterns are explicit inductive biases, not learned language understanding.
PATTERNS=(
r"\b(?:performed|conducted|completed|executed|carried out|ran|finished|took place|was run|has run|was completed)\b",
r"\b(?:not|never|yet to|failed to|unable to|could not|didn't|hasn't|wasn't)\s+(?:be\s+|been\s+|actually\s+|independently\s+){0,3}(?:perform|conduct|complete|execut|carry|run|test|finish|take place)",
r"\b(?:did not|never|has not|have not|had not)\s+(?:run|carry out|perform|conduct|complete|execute|test|finish)",
r"\b(?:no|zero|without|absence of|none)\b",
r"\b(?:found|detected|observed|measured|showed|reported|yielded|returned|recorded|revealed|identified|produced|registered|saw)\b",
r"\b(?:no|zero|without|absence of|none)\s+(?:statistically\s+|significant\s+|measurable\s+|detectable\s+){0,3}(?:difference|effect|gain|improvement|signal|error|mismatch|change|discrepanc|anomal|shift|deviation|increase|reduction|advantage|correlation)",
r"\b(?:did not|failed to|could not|never)\s+(?:find|detect|observe|measure|show|identify|produce|reveal|register)\b",
r"\b(?:may|might|could|possibly|uncertain|unknown|unverified|inconclusive|insufficient|unavailable|pending|cannot tell)\b",
r"\b(?:will|shall|planned|scheduled|proposed|future|next|intends? to|is to be)\b",
r"^[\"']?\s*(?:conduct|perform|run|repeat|test|measure|evaluate|check|collect|obtain|compare|assess)\b",
r"\b(?:but|however|although|yet|whereas|while|only|within)\b",
r"\b(?:match(?:ed|ing)?|agreed|reproduc(?:ed|ible)|confirm(?:ed)?|verified|passed|detected|found|showed|measured)\b",
r"\b(?:external|independent|physical|causal|scientific|generaliz|broader)\w*\b",
r"\b(?:not|no|cannot|unable|lack|insufficient)\b.{0,50}\b(?:external|independent|physical|causal|scientific|generaliz|broader)\w*\b"
)
def scope_vector(rows):
    out=[]
    for r in rows:
        v=r["value"].lower().replace("_"," ");matches=[list(re.finditer(p,v)) for p in PATTERNS]
        # Presence + normalized first/last position + ordered pair features.
        x=[]
        for m in matches:x.extend((float(bool(m)),m[0].start()/max(1,len(v)) if m else 0.,m[-1].end()/max(1,len(v)) if m else 0.))
        for a,b in ((0,3),(0,4),(4,3),(3,4),(1,4),(2,4),(0,6),(10,13),(0,10),(7,10)):
            x.append(float(bool(matches[a] and matches[b] and matches[a][0].start()<matches[b][-1].start())))
        out.append(x)
    return torch.tensor(out,dtype=torch.float32)
def scope_features(parent,rows):
    b,h=b5_features(parent,rows);return torch.cat([b,scope_vector(rows)],-1),h
class ScopeHead(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only
        self.trunk=nn.Sequential(nn.Linear(768+5+20+24+52+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.15))
        self.role=nn.Linear(128,4);self.event=nn.Linear(128,5);self.outcome=nn.Linear(128,5)
    def forward(self,b,h):
        z=self.trunk(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1));return self.role(z),self.event(z),self.outcome(z)
def compose(e,o):
    # Explicit semantics; incompatible tuples abstain, not guessed evidence.
    p=torch.full_like(e,-1)
    p[(e==0)&((o==0)|(o==1))]=0
    p[(e==0)&((o==2)|(o==3))]=2
    p[((e==1)|(e==3))&(o==2)]=2
    p[(e==2)&(o==2)]=1
    p[(e==4)&(o==4)]=3
    return p
def rule_scope(row):
    m=[bool(re.search(p,row["value"].lower().replace("_"," "))) for p in PATTERNS]
    if m[8] or m[9]:return 2,2
    if m[1] or m[2]:return 1,2
    if m[0] and m[10] and m[13]:return 0,3
    if m[7]:return 3,2
    if m[0] and (m[5] or m[6] or (m[3] and m[4])):return 0,1
    if m[0] and m[11]:return 0,0
    return 4,4
def synthetic(exam=False):
    rows=[] if exam else b5_synthetic(False)
    stems=[
      ("the seismology survey","an amplitude deviation","the vibration trace"),
      ("the optical spectrometer trial","a spectral shift","the optical record"),
      ("the magnetometer comparison","a correlation","the field map"),
      ("the thermal calibration","a temperature increase","the thermal log"),
      ("the orbital timing assessment","a timing discrepancy","the ephemeris"),
      ("the acoustic reconstruction","a detectable echo","the acoustic trace"),
      ("the independent microscope assay","an unexpected anomaly","the image set"),
      ("the receiver qualification","a measurable reduction","the receiver output")
    ] if exam else [
      ("the baseline audit","a measurable gain","the archived trace"),
      ("the controlled replay","a checksum mismatch","the replay data"),
      ("the sensitivity experiment","a significant effect","the candidate signal"),
      ("the verification benchmark","a runtime difference","the verified record"),
      ("the repeated comparison","a frequency change","the source file"),
      ("the field observation","a signal","the measured response"),
      ("the numeric replication","a scoring error","the numeric output"),
      ("the independent validation","a detectable improvement","the validation report"),
      ("the instrument check","a deviation","the instrument data"),
      ("the test of the filter","an unexpected shift","the filter output"),
      ("the recovery rehearsal","a lost response","the checkpoint"),
      ("the software evaluation","a performance advantage","the test corpus")
    ]
    for i,(sub,obj,target) in enumerate(stems):
        noun=obj.removeprefix("a ").removeprefix("an ")
        if exam:
            cases=[
              (f"After {sub} took place, the report recorded no {noun}.",0,1,"negative_result"),
              (f"{sub} was run, yet the team did not observe {obj}.",0,1,"negative_result"),
              (f"No {noun} was found when {sub} was completed.",0,1,"negative_result"),
              (f"{sub} has not been carried out, so its outcome is unknown.",1,2,"negated_execution"),
              (f"The team never ran {sub}; there are no measurements.",1,2,"negated_execution"),
              (f"{sub} finished and confirmed {obj} in {target}.",0,0,"positive"),
              (f"{sub} is scheduled to examine {target}.",2,2,"future"),
              (f"Repeat {sub} to determine whether {obj} exists.",2,2,"future"),
              (f"Whether {sub} happened is uncertain; no verified result is available.",3,2,"uncertainty"),
              (f"{sub} was completed; internal agreement was observed but external validity was not established.",0,3,"mixed_scope"),
              (f"Identifier for {sub}: record {i+101}.",4,4,"other"),
              (f"{sub} took place, but the result was inconclusive.",0,2,"completed_unknown")]
        else:
            cases=[
              (f"{sub} was performed and detected no {noun}.",0,1,"negative_result"),
              (f"{sub} completed; investigators found zero {noun}.",0,1,"negative_result"),
              (f"During {sub}, which was conducted, observers did not find {obj}.",0,1,"negative_result"),
              (f"{sub} was never performed; no findings are available.",1,2,"negated_execution"),
              (f"{sub} did not run and the outcome remains unknown.",1,2,"negated_execution"),
              (f"{sub} was executed and measured {obj} in {target}.",0,0,"positive"),
              (f"{sub} will be conducted to evaluate {target}.",2,2,"future"),
              (f"Conduct {sub} in order to investigate {obj}.",2,2,"future"),
              (f"It is unknown whether {sub} was executed; the outcome is unverified.",3,2,"uncertainty"),
              (f"{sub} was performed and reproduced internal values but cannot verify independent provenance.",0,3,"mixed_scope"),
              (f"Title of {sub}: {target}.",4,4,"other"),
              (f"{sub} completed but its outcome is undetermined.",0,2,"completed_unknown"),
              (f"{sub} was conducted and found no significant {noun}.",0,1,"negative_result"),
              (f"{sub} was not conducted; no {noun} can be evaluated.",1,2,"negated_execution"),
              (f"{sub} was performed and found {obj}.",0,0,"positive"),
              (f"{sub} was performed, without finding {obj}.",0,1,"negative_result")]
        for j,path in enumerate((["record","detail"],["audit","statement"],["entry","note"])):
            for k,(v,e,o,c) in enumerate(cases):
                g=int(compose(torch.tensor([e]),torch.tensor([o]))[0]);req(g>=0,"LABEL_COMPOSE")
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(v),"label":GROUP_NAMES[g],"event":e,"outcome":o,"cohort":c,"family":str(i),"contrast_id":f"{i}:{j}:{k}"})
    return rows
