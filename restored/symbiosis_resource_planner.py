from __future__ import annotations
import hashlib, json, math
from typing import Any

SCHEMA="janus.symbiosis.resource_plan.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def _finite(name:str,value:Any)->float:
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)

def propose(*, base_batch:int, gpu_load:float, cpu_load:float, gpu_temp_c:float, igpu_load:float=0.0, cache_ratio:float=1.0, gaming_mode:bool=False)->dict[str,Any]:
    base=max(8,int(base_batch))
    gpu=_finite("gpu_load",gpu_load); cpu=_finite("cpu_load",cpu_load); temp=_finite("gpu_temp_c",gpu_temp_c)
    igpu=_finite("igpu_load",igpu_load); cache=_finite("cache_ratio",cache_ratio)
    findings=[]
    if gaming_mode:
        batch=max(8,base//4); pause_s=3.0; reason="GAMING_MODE"
    elif gpu<30.0 and temp<65.0 and igpu<50.0 and cache<1.1:
        batch=base; pause_s=0.0; reason="LOW_PRESSURE"
    else:
        stress=max(gpu/100.0,cpu/100.0,(temp-50.0)/40.0)
        if igpu>50.0: stress=max(stress,igpu/100.0)
        if cache>1.2: stress=min(1.0,stress*cache)
        stress=max(0.0,min(1.0,stress))
        raw=max(8,int(base*(1.0-stress)))
        batch=2**max(3,int(math.log2(raw)))
        pause_s=stress*2.5
        reason="PRESSURE_ADAPTATION"
        if stress>=0.9: findings.append("HIGH_COMPUTE_PRESSURE")
    body={
      "schema":SCHEMA,"status":"PLAN_ONLY","reason":reason,
      "inputs":{"base_batch":base,"gpu_load":gpu,"cpu_load":cpu,"gpu_temp_c":temp,"igpu_load":igpu,"cache_ratio":cache,"gaming_mode":bool(gaming_mode)},
      "proposal":{"batch_size":int(batch),"pause_seconds":round(float(pause_s),6)},
      "findings":findings,
      "authority":{"changes_batch":False,"sleeps_process":False,"changes_power_limit":False,"changes_affinity":False,"controls_game":False},
      "laws":["RESOURCE_PLAN_NE_RESOURCE_ACTUATION","USER_ACTIVITY_OR_GAME_PRESENCE_NE_AUTOMATIC_TAKEOVER","ARGUS_SIGNAL_CAN_INFORM_PLAN_BUT_NOT_AUTHORIZE_IT"]
    }
    body["plan_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body
