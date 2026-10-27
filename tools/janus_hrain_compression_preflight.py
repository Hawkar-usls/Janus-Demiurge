#!/usr/bin/env python3
"""NON-MUTATING hazard gate for legacy All Star HRAiN compression.

Checks the *current* source's group-contraction behaviour: compress_clusters
creates meta<->member edges then remove_node(member) erases them and every
pre-existing edge that touches that member.

The result is a PROVENANCE/LIVENESS warning, not an alternative compressor,
scientific result or permission to mutate source data. No arbitrary modules
imported, network calls, graph writes, node labels or device metrics emitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA="janus.demiurge.hrain_legacy_compression_preflight.v1"
MAX_BYTES=32_000_000
MAX_NODES=1000
MAX_EDGES=30000

def _score(n1, n2):
    d1=n1.get("data",{})
    d2=n2.get("data",{})
    if not isinstance(d1,dict) or not isinstance(d2,dict):
        raise ValueError("NODE_DATA_SCHEMA_HOLD")
    values=[]
    for field in ("purity","temp"):
        x,y=d1.get(field),d2.get(field)
        if x is not None and y is not None:
            if type(x) not in (int,float) or type(y) not in (int,float):
                raise ValueError("NUMERIC_SIMILARITY_SCHEMA_HOLD")
            if not math.isfinite(float(x)) or not math.isfinite(float(y)):
                raise ValueError("NONFINITE_SIMILARITY_HOLD")
            values.append(1-min(1,abs(float(x)-float(y))/100))
    for field in ("agent_id","role"):
        x,y=d1.get(field),d2.get(field)
        if x and y:
            values.append(1.0 if x==y else 0.0)
    return sum(values)/len(values) if values else 0.0

def assess(nodes,edges,threshold=0.7):
    if not isinstance(nodes,dict) or not isinstance(edges,dict):
        raise ValueError("GRAPH_SCHEMA_HOLD")
    if len(nodes)>MAX_NODES or len(edges)>MAX_EDGES:
        raise ValueError("PREFLIGHT_SIZE_BOUND_HOLD")
    if type(threshold) not in (int,float) or not math.isfinite(threshold) or not 0<=threshold<=1:
        raise ValueError("CLUSTER_THRESHOLD_HOLD")
    ids=list(nodes)
    for name in ids:
        if not isinstance(name,str) or not name or "->" in name or not isinstance(nodes[name],dict):
            raise ValueError("UNSAFE_NODE_ID_OR_SCHEMA_HOLD")
    node_set=set(ids)
    visited=set()
    clusters=[]
    for name in ids:
        if name in visited:
            continue
        c=[name]
        visited.add(name)
        for other in ids:
            if other not in visited and _score(nodes[name],nodes[other])>threshold:
                visited.add(other)
                c.append(other)
        if len(c)>1:clusters.append(c)
    members=set(m for c in clusters for m in c)
    lost=0
    dangling=0
    for name in edges:
        if not isinstance(name,str) or name.count("->")!=1:
            raise ValueError("UNSAFE_EDGE_ID_HOLD")
        a,b=name.split("->")
        if a not in node_set or b not in node_set:
            dangling+=1
        if a in members or b in members:
            lost+=1
    return {
        "schema":SCHEMA,
        "status":"BLOCK_LEGACY_DESTRUCTIVE_COMPRESSION" if clusters or dangling else "NO_CLUSTER_LOSS_PREDICTED_FOR_THIS_SNAPSHOT",
        "productionUseAuthorized":False,
        "sourceGraphModified":False,
        "nodeCount":len(nodes),
        "originalEdgeCount":len(edges),
        "clustersDetected":len(clusters),
        "memberNodesAtRisk":len(members),
        "existingEdgesAtRisk":lost,
        "alreadyDanglingEdges":dangling,
        "newMetaMemberEdgesDeletedByOriginalRoutine":sum(2*len(c) for c in clusters),
        "reason":"Original implementation creates meta->member and member->meta, then remove_node deletes all edges touching members",
        "note":"Source-version-specific preflight; not a proof of data conservation under future mutations",
        "scientificVerdict":"NOT_TOPA_ADJUDICATED"
    }

def run_file(path:Path):
    if path.name!="hrain_graph_state.json" or path.parent.name!="raw_logs" or path.is_symlink():
        raise ValueError("ONLY_LOCAL_RAW_LOGS_SNAPSHOT_ALLOWED")
    n=path.stat().st_size
    if not 1<=n<=MAX_BYTES:
        raise ValueError("PRIVATE_SNAPSHOT_SIZE_HOLD")
    body=path.read_bytes()
    if len(body)!=n:
        raise ValueError("SOURCE_CHANGED_DURING_READ_HOLD")
    data=json.loads(body)
    if not isinstance(data,dict):
        raise ValueError("GRAPH_ROOT_OBJECT_HOLD")
    out=assess(data.get("nodes"),data.get("edges"))
    out["inputSha256"]=hashlib.sha256(body).hexdigest()
    out["sourceBytes"]=n
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run_file(args.snapshot),sort_keys=True))

if __name__=="__main__":
    main()
