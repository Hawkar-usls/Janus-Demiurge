from __future__ import annotations
import hashlib, json
from typing import Any

SCHEMA="janus.hrain.similarity_plan.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def similarity(n1:dict[str,Any],n2:dict[str,Any])->float:
    d1=n1.get("data",{}) if isinstance(n1.get("data",{}),dict) else {}
    d2=n2.get("data",{}) if isinstance(n2.get("data",{}),dict) else {}
    purity_diff=abs(float(d1.get("purity",0) or 0)-float(d2.get("purity",0) or 0))/100.0
    temp_diff=abs(float(d1.get("temp",0) or 0)-float(d2.get("temp",0) or 0))/100.0
    a1=d1.get("agent_id"); a2=d2.get("agent_id")
    agent_same=1.0 if a1 not in (None,"") and a2 not in (None,"") and a1==a2 else 0.0
    return (1.0-min(1.0,purity_diff))*0.4+(1.0-min(1.0,temp_diff))*0.4+agent_same*0.2

def _edge_pairs(edges:dict[str,dict[str,Any]])->set[tuple[str,str]]:
    out=set()
    for key in edges:
        if "->" in str(key):
            a,b=str(key).split("->",1); out.add(tuple(sorted((a,b))))
    return out

def plan(*, nodes:dict[str,dict[str,Any]], edges:dict[str,dict[str,Any]]|None=None, similarity_threshold:float=0.8, cluster_similarity:float=0.9, max_nodes:int=500)->dict[str,Any]:
    ids=sorted(str(k) for k,v in nodes.items() if isinstance(v,dict))
    if len(ids)>int(max_nodes):
        return {"schema":SCHEMA,"status":"HOLD","reason":"MAX_NODES_EXCEEDED","node_count":len(ids),"max_nodes":int(max_nodes),"authority":{"mutates_graph":False}}
    existing=_edge_pairs(edges or {})
    links=[]; pair_scores=[]
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            sim=similarity(nodes[a],nodes[b])
            pair_scores.append({"a":a,"b":b,"similarity":sim})
            if sim>float(similarity_threshold) and tuple(sorted((a,b))) not in existing:
                links.append({"source":a,"target":b,"weight":sim,"reason":"SIMILARITY_PROPOSAL"})
    # Deterministic source-like representative clustering, but proposal-only.
    visited=set(); clusters=[]
    for nid in ids:
        if nid in visited: continue
        cluster=[nid]; visited.add(nid)
        for other in ids:
            if other in visited: continue
            if similarity(nodes[nid],nodes[other])>float(cluster_similarity):
                cluster.append(other); visited.add(other)
        if len(cluster)>1:
            avg={}
            for key in ("purity","temp","loss"):
                vals=[float((nodes[x].get("data",{}) or {}).get(key,0) or 0) for x in cluster]
                avg[key]=sum(vals)/len(vals)
            total_energy=sum(float(nodes[x].get("energy",0) or 0) for x in cluster)
            clusters.append({"representative":nid,"members":cluster,"mean_data":avg,"total_energy":total_energy})
    identity={"pair_scores":pair_scores,"link_proposals":links,"cluster_proposals":clusters,"thresholds":{"similarity":float(similarity_threshold),"cluster":float(cluster_similarity)}}
    body={"schema":SCHEMA,"status":"PLAN_ONLY","pair_scores":pair_scores,"link_proposals":links,"cluster_proposals":clusters,
          "historical_repairs":["MISSING_AGENT_ID_DOES_NOT_COUNT_AS_MATCH","NO_RANDOM_SAMPLE_NONDETERMINISM"],
          "authority":{"adds_edges":False,"creates_meta_nodes":False,"removes_nodes":False,"compresses_clusters":False,"mutates_graph":False},
          "laws":["SIMILARITY_NE_SEMANTIC_TRUTH","LINK_PROPOSAL_NE_GRAPH_WRITE","CLUSTER_PROPOSAL_NE_NODE_DELETION","MISSING_VALUE_NE_SHARED_IDENTITY"]}
    body["plan_sha256"]=hashlib.sha256(_canon(identity)).hexdigest()
    return body
