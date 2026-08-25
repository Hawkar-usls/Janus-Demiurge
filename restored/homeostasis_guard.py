from __future__ import annotations
import hashlib, json, math, os, tempfile
from pathlib import Path
from typing import Any, Iterable

SCHEMA="janus.homeostasis.health.v1"
STATE_SCHEMA="janus.homeostasis.state.v1"


def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")


def _finite_number(value:Any)->bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(float(value))


def evaluate_metrics(*, score:Any, val_loss:Any, diversity:Any, mutual_information:Any, grad_norm_mean:Any, train_loss:Any=None, grad_norm_max:Any=None, grad_norm_limit:float=100.0)->dict[str,Any]:
    findings=[]
    required={"score":score,"val_loss":val_loss,"diversity":diversity,"mutual_information":mutual_information,"grad_norm_mean":grad_norm_mean}
    for name,value in required.items():
        if not _finite_number(value): findings.append({"kind":"NONFINITE_OR_MISSING_METRIC","metric":name})
    if train_loss is not None and not _finite_number(train_loss): findings.append({"kind":"NONFINITE_OR_MISSING_METRIC","metric":"train_loss"})
    if grad_norm_max is not None:
        if not _finite_number(grad_norm_max): findings.append({"kind":"NONFINITE_OR_MISSING_METRIC","metric":"grad_norm_max"})
        elif float(grad_norm_max)>float(grad_norm_limit): findings.append({"kind":"GRADIENT_EXPLOSION_RISK","grad_norm_max":float(grad_norm_max),"limit":float(grad_norm_limit)})
    status="HEALTHY" if not findings else "HOLD"
    recommendation="CONTINUE_ELIGIBLE" if status=="HEALTHY" else "ROLLBACK_OR_DIAGNOSE_PROPOSAL"
    body={"schema":SCHEMA,"status":status,"recommendation":recommendation,"findings":findings,
          "metrics":required|{"train_loss":train_loss,"grad_norm_max":grad_norm_max},
          "thresholds":{"grad_norm_limit":float(grad_norm_limit)},
          "authority":{"rolls_back_model":False,"changes_optimizer":False,"changes_batch":False,"writes_checkpoint":False},
          "laws":["NONFINITE_METRIC_BLOCKS_PROMOTION","HEALTH_SIGNAL_NE_ROLLBACK_AUTHORITY","THRESHOLD_IS_CONFIGURED_GUARD_NOT_THEOREM"]}
    body["health_receipt_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body


def build_state(*, cycle:int, last_score:Any, last_mi:Any, best_score:Any, failed_config_hashes:Iterable[str]=(), predicted_score:Any=None, velocity:Any=None, acceleration:Any=None, purity_score:Any=None)->dict[str,Any]:
    hashes=sorted(set(str(x).lower() for x in failed_config_hashes))
    bad=[x for x in hashes if len(x)!=64 or any(c not in "0123456789abcdef" for c in x)]
    body={"schema":STATE_SCHEMA,"cycle":int(cycle),"last_score":last_score,"last_mi":last_mi,"best_score":best_score,
          "failed_config_sha256":hashes,"predicted_score":predicted_score,"velocity":velocity,"acceleration":acceleration,"purity_score":purity_score,
          "findings":[{"kind":"INVALID_FAILED_CONFIG_SHA256","value":x} for x in bad],
          "authority":{"restores_model":False,"changes_runtime":False}}
    body["state_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body


def verify_state(state:dict[str,Any])->bool:
    copy=dict(state); claimed=copy.pop("state_sha256",None)
    return isinstance(claimed,str) and hashlib.sha256(_canon(copy)).hexdigest()==claimed


def write_state_atomic(path:str|Path,state:dict[str,Any])->None:
    if not verify_state(state): raise ValueError("invalid homeostasis state receipt")
    dst=Path(path); dst.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=dst.name+".",dir=str(dst.parent))
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as f:
            json.dump(state,f,ensure_ascii=False,sort_keys=True,indent=2); f.write("\n")
        os.replace(tmp,dst)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def load_state(path:str|Path)->dict[str,Any]:
    state=json.loads(Path(path).read_text(encoding="utf-8"))
    if not verify_state(state): raise ValueError("homeostasis state hash mismatch")
    return state
