from __future__ import annotations
import hashlib, json
from collections import defaultdict
from typing import Any

SCHEMA="janus.module_integration.plan.v2"

def _canon(value:Any)->bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def plan(manifest: list[dict[str,Any]]) -> dict[str,Any]:
    by_id={}; errors=[]
    for raw in manifest:
        item=dict(raw)
        mid=str(item.get("id","")).strip()
        if not mid or mid in by_id:
            errors.append({"kind":"INVALID_OR_DUPLICATE_ID","id":mid}); continue
        deps=sorted(set(str(x) for x in item.get("dependencies",[])))
        item["id"]=mid; item["dependencies"]=deps
        source_sha=item.get("source_sha256")
        if source_sha is not None and (not isinstance(source_sha,str) or len(source_sha)!=64 or any(c not in "0123456789abcdefABCDEF" for c in source_sha)):
            errors.append({"kind":"INVALID_SOURCE_SHA256","module":mid}); continue
        by_id[mid]=item
    if errors: return {"schema":SCHEMA,"status":"HOLD","errors":errors,"order":[]}
    indeg={m:0 for m in by_id}; edges=defaultdict(list)
    for mid,item in by_id.items():
        for dep in item["dependencies"]:
            if dep not in by_id:
                errors.append({"kind":"MISSING_DEPENDENCY","module":mid,"dependency":dep})
            else:
                edges[dep].append(mid); indeg[mid]+=1
    if errors: return {"schema":SCHEMA,"status":"HOLD","errors":errors,"order":[]}
    ready=sorted(m for m,d in indeg.items() if d==0); order=[]
    while ready:
        cur=ready.pop(0); order.append(cur)
        for nxt in sorted(edges[cur]):
            indeg[nxt]-=1
            if indeg[nxt]==0:
                ready.append(nxt); ready.sort()
    if len(order)!=len(by_id):
        cycle_nodes=sorted(m for m,d in indeg.items() if d>0)
        return {"schema":SCHEMA,"status":"HOLD","errors":[{"kind":"DEPENDENCY_CYCLE","nodes":cycle_nodes}],"order":order,
                "law":"CYCLE -> HOLD; NEVER FALL BACK TO DISCOVERY ORDER"}
    normalized=[by_id[mid] for mid in sorted(by_id)]
    identity={"modules":normalized,"order":order}
    plan_sha=hashlib.sha256(_canon(identity)).hexdigest()
    return {"schema":SCHEMA,"status":"PLAN_ONLY","errors":[],"order":order,"modules":normalized,"plan_sha256":plan_sha,
            "authority":{"imports_modules":False,"executes_code":False,"initializes_modules":False,"writes_live_zone":False},
            "law":"PLAN_IDENTITY_MUST_PRECEDE_RUNTIME_ADMISSION"}
