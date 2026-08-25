from __future__ import annotations
import hashlib, json
from collections import defaultdict
from typing import Any

SCHEMA="janus.hrain.graph_flow_projection.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def project(*, nodes:dict[str,dict[str,Any]], edges:dict[str,dict[str,Any]], edge_decay:float=0.995, energy_decay:float=0.99, energy_flow_rate:float=0.1, node_energy_threshold:float=0.01, edge_drop_threshold:float=0.01, edge_reinforce:float=0.01, active_threshold:float=0.5)->dict[str,Any]:
    projected_nodes={str(k):dict(v) for k,v in nodes.items() if isinstance(v,dict)}
    projected_edges={str(k):dict(v) for k,v in edges.items() if isinstance(v,dict)}
    findings=[]
    # Historical order: edge decay -> node decay -> propagate -> reinforcement.
    for key,edge in sorted(projected_edges.items()):
        old=float(edge.get("weight",0.0) or 0.0)
        edge["weight_before"]=old
        edge["weight_after_decay"]=old*float(edge_decay)
        edge["historical_drop_candidate"]=edge["weight_after_decay"]<float(edge_drop_threshold)
    for nid,node in sorted(projected_nodes.items()):
        old=float(node.get("energy",0.0) or 0.0)
        node["energy_before"]=old
        node["energy_after_decay"]=old*float(energy_decay)
        node["historical_drop_candidate"]=node["energy_after_decay"]<float(node_energy_threshold)
    transfers=defaultdict(float); transfer_rows=[]
    for key,edge in sorted(projected_edges.items()):
        if "->" not in key:
            findings.append({"kind":"INVALID_EDGE_KEY","edge":key}); continue
        src,dst=key.split("->",1)
        if src not in projected_nodes or dst not in projected_nodes:
            findings.append({"kind":"MISSING_EDGE_ENDPOINT","edge":key}); continue
        src_energy=float(projected_nodes[src]["energy_after_decay"])
        weight=float(edge["weight_after_decay"])
        flow=min(src_energy,src_energy*weight*float(energy_flow_rate))
        if flow>0:
            transfers[src]-=flow; transfers[dst]+=flow
            transfer_rows.append({"edge":key,"source":src,"target":dst,"flow":flow})
    for nid,node in projected_nodes.items():
        node["energy_after_flow"]=max(0.0,float(node["energy_after_decay"])+transfers.get(nid,0.0))
    reinforce=[]
    for key,edge in sorted(projected_edges.items()):
        if "->" not in key: continue
        src,dst=key.split("->",1)
        if src in projected_nodes and dst in projected_nodes:
            if projected_nodes[src]["energy_after_flow"]>float(active_threshold) and projected_nodes[dst]["energy_after_flow"]>float(active_threshold):
                proposed=float(edge["weight_after_decay"])+float(edge_reinforce)*0.5
                reinforce.append({"edge":key,"weight_after_decay":edge["weight_after_decay"],"proposed_reinforced_weight":proposed})
    identity={"nodes":projected_nodes,"edges":projected_edges,"transfers":transfer_rows,"reinforcement_proposals":reinforce,"findings":findings}
    body={"schema":SCHEMA,"status":"PROJECTION_ONLY","nodes":projected_nodes,"edges":projected_edges,"transfers":transfer_rows,"reinforcement_proposals":reinforce,"findings":findings,
          "config":{"edge_decay":float(edge_decay),"energy_decay":float(energy_decay),"energy_flow_rate":float(energy_flow_rate),"node_energy_threshold":float(node_energy_threshold),"edge_drop_threshold":float(edge_drop_threshold),"edge_reinforce":float(edge_reinforce),"active_threshold":float(active_threshold)},
          "authority":{"mutates_graph":False,"deletes_nodes":False,"deletes_edges":False,"reinforces_edges":False,"adds_random_edges":False,"compresses_clusters":False},
          "laws":["GRAPH_PHYSICS_PROJECTION_NE_GRAPH_MUTATION","HISTORICAL_DROP_RULE_BECOMES_DIAGNOSTIC_ONLY","REINFORCEMENT_PROPOSAL_REQUIRES_SEPARATE_WRITE_GATE"]}
    body["projection_sha256"]=hashlib.sha256(_canon(identity)).hexdigest()
    return body
