from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

SCHEMA="janus.argus.pressure_observation.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def parse_loadavg(text:str)->dict[str,float]:
    parts=str(text or "").split()
    if len(parts)<3: raise ValueError("invalid /proc/loadavg")
    return {"load_1m":float(parts[0]),"load_5m":float(parts[1]),"load_15m":float(parts[2])}

def parse_meminfo(text:str)->dict[str,Any]:
    values={}
    for line in str(text or "").splitlines():
        if ":" not in line: continue
        key,rest=line.split(":",1); tokens=rest.strip().split()
        if not tokens: continue
        try: values[key]=int(tokens[0])
        except ValueError: continue
    total=values.get("MemTotal",0); avail=values.get("MemAvailable",values.get("MemFree",0))
    if total<=0: raise ValueError("MemTotal missing")
    used=max(0,total-avail); percent=(used/total)*100.0
    return {"mem_total_kib":total,"mem_available_kib":avail,"mem_used_kib":used,"mem_percent":percent}

def classify(*, load_1m:float, mem_percent:float, cpu_warn:float=2.0, mem_warn:float=90.0)->dict[str,Any]:
    findings=[]
    if float(load_1m)>float(cpu_warn): findings.append("CPU_LOAD_HIGH")
    if float(mem_percent)>float(mem_warn): findings.append("MEMORY_PRESSURE_HIGH")
    return {"state":"PRESSURE" if findings else "NOMINAL","findings":findings,
            "thresholds":{"cpu_warn":float(cpu_warn),"mem_warn":float(mem_warn)}}

def observe_from_text(loadavg_text:str, meminfo_text:str, *, cpu_warn:float=2.0, mem_warn:float=90.0)->dict[str,Any]:
    load=parse_loadavg(loadavg_text); mem=parse_meminfo(meminfo_text)
    pressure=classify(load_1m=load["load_1m"],mem_percent=mem["mem_percent"],cpu_warn=cpu_warn,mem_warn=mem_warn)
    body={"schema":SCHEMA,"load":load,"memory":mem,"pressure":pressure,
          "authority":{"adjusts_entropy":False,"runs_gc":False,"kills_services":False,"writes_runtime":False,"observation_only":True},
          "laws":["ARGUS_OBSERVATION_NE_RESOURCE_ACTUATION","PRESSURE_SIGNAL_NE_AUTOMATIC_GC","PRESSURE_SIGNAL_NE_SERVICE_KILL"]}
    body["observation_sha256"]=hashlib.sha256(_canon(body)).hexdigest(); return body

def observe_proc(*, loadavg_path:str|Path="/proc/loadavg", meminfo_path:str|Path="/proc/meminfo", cpu_warn:float=2.0, mem_warn:float=90.0)->dict[str,Any]:
    return observe_from_text(Path(loadavg_path).read_text(encoding="utf-8"),Path(meminfo_path).read_text(encoding="utf-8"),cpu_warn=cpu_warn,mem_warn=mem_warn)
