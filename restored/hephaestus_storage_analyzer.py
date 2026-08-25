from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from typing import Any, Iterable

SCHEMA="janus.hephaestus.storage_analysis.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def analyze_sizes(sizes:Iterable[int], *, block_size:int=4096)->dict[str,Any]:
    block=int(block_size)
    if block<=0: raise ValueError("block_size must be positive")
    vals=[int(x) for x in sizes]
    if any(x<0 for x in vals): raise ValueError("file sizes must be non-negative")
    total=sum(vals)
    allocated=sum(((x+block-1)//block)*block if x else 0 for x in vals)
    slack=allocated-total
    entropy=0.0
    if total>0:
        for x in vals:
            if x>0:
                p=x/total
                entropy-=p*math.log2(p)
    body={
      "schema":SCHEMA,"file_count":len(vals),"block_size":block,"logical_bytes":total,
      "estimated_block_allocated_bytes":allocated,"estimated_block_slack_bytes":slack,
      "size_mass_shannon_bits":entropy,
      "interpretation":{
        "slack_is_estimate":True,
        "uses_simple_fixed_block_model":True,
        "proves_p_equals_np":False,
        "quantum_computation_claim":False
      },
      "authority":{"reads_content":False,"moves_files":False,"deletes_files":False,"archives_files":False,"writes_filesystem":False},
      "laws":["STORAGE_SLACK_ESTIMATE_NE_FILESYSTEM_GROUND_TRUTH","ZERO_SLACK_LOWER_BOUND_NE_P_VS_NP_RESULT","ANALYSIS_NE_REPACKING_AUTHORITY"]
    }
    body["analysis_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body

def scan_metadata(root:str|Path, *, block_size:int=4096, max_files:int=100000)->dict[str,Any]:
    base=Path(root).resolve(); rows=[]; findings=[]
    for p in sorted(base.rglob("*"),key=lambda x:x.as_posix()):
        if len(rows)>=max(0,int(max_files)):
            findings.append("MAX_FILES_REACHED"); break
        try:
            if p.is_file():
                rows.append({"path":p.relative_to(base).as_posix(),"size":p.stat().st_size})
        except OSError:
            findings.append("UNREADABLE_METADATA")
    summary=analyze_sizes((r["size"] for r in rows),block_size=block_size)
    manifest={"root_label":base.name,"files":rows}
    manifest_sha=hashlib.sha256(_canon(manifest)).hexdigest()
    return {"schema":"janus.hephaestus.storage_scan.v1","manifest_sha256":manifest_sha,
            "findings":findings,"summary":summary,"files":rows,
            "authority":{"reads_file_metadata":True,"reads_file_content":False,"mutates_filesystem":False}}
