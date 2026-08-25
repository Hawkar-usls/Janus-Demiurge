from __future__ import annotations
import hashlib, json
from typing import Any

SCHEMA="janus.yaks.phase_backbone.v1"
PHASES=("SURVIVAL","STABILITY","MEANING","CREATION","HIBERNATE")
POLICY={
  "SURVIVAL":{"prefer":["navigator"],"suppress":["prism"],"facet_hint":None},
  "STABILITY":{"prefer":["ouroboros","prism"],"suppress":[],"facet_hint":None},
  "MEANING":{"prefer":["prism"],"suppress":[],"facet_hint":"MYTHOS"},
  "CREATION":{"prefer":["prism"],"suppress":[],"facet_hint":"PATHOS"},
  "HIBERNATE":{"prefer":[],"suppress":["navigator","ouroboros"],"facet_hint":None}
}

def _canon(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def phase_policy(phase:str)->dict[str,Any]:
    if phase not in PHASES:
        return {"schema":SCHEMA,"status":"HOLD","reason":"UNKNOWN_PHASE","phase":phase}
    return {"schema":SCHEMA,"status":"POLICY_ONLY","phase":phase,**POLICY[phase],
            "authority":{"starts_services":False,"stops_services":False,"changes_prism_facet":False,"executes_actions":False},
            "law":"PHASE_BACKBONE_DESCRIBES_ADMISSIBILITY_NOT_ACTUATION"}

def transition(previous:str, requested:str, reason:str="", evidence_sha256:str|None=None)->dict[str,Any]:
    if previous not in PHASES or requested not in PHASES:
        return {"schema":SCHEMA,"status":"HOLD","previous":previous,"requested":requested,"reason":"UNKNOWN_PHASE"}
    if evidence_sha256 is not None and (len(evidence_sha256)!=64 or any(c not in "0123456789abcdefABCDEF" for c in evidence_sha256)):
        return {"schema":SCHEMA,"status":"HOLD","previous":previous,"requested":requested,"reason":"INVALID_EVIDENCE_SHA256"}
    body={"schema":SCHEMA,"status":"TRANSITION_PROPOSAL" if previous!=requested else "NO_CHANGE",
          "previous":previous,"requested":requested,"reason":reason,"evidence_sha256":evidence_sha256,
          "policy":phase_policy(requested),
          "authority":{"applies_transition":False,"starts_services":False,"stops_services":False}}
    body["transition_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body
