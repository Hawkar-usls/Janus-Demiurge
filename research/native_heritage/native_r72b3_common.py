from native_r72b2_common import *
from native_r72b2_common import SemanticHead as B2Head,synthetic as b2_synthetic
GROUP=(3,3,3,3,0,1,2,3)
class SemanticHead(nn.Module):
    def __init__(self,d,byte_only):
        super().__init__();self.byte_only=byte_only
        self.trunk=nn.Sequential(nn.Linear(768+5+3*d,128),nn.LayerNorm(128),nn.GELU(),nn.Dropout(.2))
        self.roles=nn.Linear(128,len(LABELS));self.epistemic=nn.Linear(128,4)
    def logits(self,b,h):
        z=self.trunk(torch.cat([b,torch.zeros_like(h) if self.byte_only else h],-1))
        return self.roles(z),self.epistemic(z)
    def forward(self,b,h):
        r,e=self.logits(b,h);return r+.5*F.log_softmax(e,-1)[:,list(GROUP)]
    def loss(self,b,h,y):
        r,e=self.logits(b,h)
        return F.cross_entropy(r+.5*F.log_softmax(e,-1)[:,list(GROUP)],y)+F.cross_entropy(e,torch.tensor(GROUP,device=y.device)[y])
def synthetic(exam=False):
    rows=[] if exam else b2_synthetic(False)
    if exam:
        triples=[
          ("audit reproduced the measured result","audit has not reproduced the measured result","audit will attempt to reproduce the measured result"),
          ("the independent witness was authenticated","the independent witness could not be authenticated","authenticate the independent witness in the next trial"),
          ("repeated observations confirmed matching timestamps","repeated observations did not establish matching timestamps","repeat observations to determine whether timestamps match"),
          ("the archived output matched its recorded checksum","the recorded checksum is absent and cannot be verified","obtain the checksum for a future comparison"),
          ("the separate replication succeeded","no separate replication has occurred","a separate replication is scheduled"),
          ("the test established numerical agreement within tolerance","the test cannot establish agreement outside the tested conditions","test agreement on a new cohort")]
    else:
        triples=[
          ("the heldout test reproduced the reported value","the heldout test did not verify the reported value","run a heldout test to verify the reported value"),
          ("independent measurements agreed with the prediction","independent measurements are unavailable","collect independent measurements to test the prediction"),
          ("the signed receipt matched the archive","the signed receipt has not been validated","validate the signed receipt before the next experiment"),
          ("the experiment recorded a passing comparison","the experiment did not establish the proposed effect","the experiment is planned to assess the proposed effect"),
          ("the frozen control confirmed identical output","the frozen control was not executed","execute the frozen control in a future trial"),
          ("source integrity was checked successfully","source integrity is not established","check source integrity in the next step"),
          ("the paired replay completed without mismatch","the paired replay has no available result","perform a paired replay to measure mismatch"),
          ("the checksum comparison passed","the checksum comparison could not be performed","perform a checksum comparison after obtaining files"),
          ("the observations demonstrated agreement on the stated metric","the observations cannot establish the broader claim","gather observations to evaluate the broader claim"),
          ("a rerun verified the baseline output","a rerun was unavailable so the baseline is not verified","schedule a rerun to verify baseline output")]
    for i,vals in enumerate(triples):
        for j,path in enumerate((["record","detail"],["entry","note"],["result","statement"],["audit","summary"])):
            for label,val in zip(("evidence_statement","epistemic_limit","hypothesis_plan"),vals):
                rows.append({"source":"synthetic_exam" if exam else "synthetic_train","path":path,"type":"string","value":json.dumps(val),"label":label,"contrast_id":str(i)+":"+str(j)})
    return rows
