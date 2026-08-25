from __future__ import annotations
from collections import defaultdict
from typing import Any

SCHEMA="janus.module_integration.plan.v1"

def plan(manifest: list[dict[str,Any]]) -> dict[str,Any]:
    by_id={}
    errors=[]
    for item in manifest:
        mid=str(item.get("id","")).strip()
        if not mid or mid in by_id:
            errors.append({"kind":"INVALID_OR_DUPLICATE_ID","id":mid})
            continue
        by_id[mid]=item
    if errors: return {"schema":SCHEMA,"status":"HOLD","errors":errors,"order":[]}
    indeg={m:0 for m in by_id}; edges=defaultdict(list)
    for mid,item in by_id.items():
        for dep in sorted(set(item.get("dependencies",[]))):
            if dep not in by_id:
                errors.append({"kind":"MISSING_DEPENDENCY","module":mid,"dependency":dep})
            else:
                edges[dep].append(mid); indeg[mid]+=1
    if errors: return {"schema":SCHEMA,"status":"HOLD","errors":errors,"order":[]}
    ready=sorted([m for m,d in indeg.items() if d==0]); order=[]
    while ready:
        cur=ready.pop(0); order.append(cur)
        for nxt in sorted(edges[cur]):
            indeg[nxt]-=1
            if indeg[nxt]==0:
                ready.append(nxt); ready.sort()
    if len(order)!=len(by_id):
        cycle_nodes=sorted([m for m,d in indeg.items() if d>0])
        return {"schema":SCHEMA,"status":"HOLD","errors":[{"kind":"DEPENDENCY_CYCLE","nodes":cycle_nodes}],"order":order}
    return {"schema":SCHEMA,"status":"PLAN_ONLY","errors":[],"order":order,
            "authority":{"imports_modules":False,"executes_code":False,"writes_live_zone":False}}
