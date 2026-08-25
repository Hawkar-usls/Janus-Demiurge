from __future__ import annotations
import hashlib, json
from typing import Any, Iterable

SCHEMA="janus.hrain.action_score.v1"

def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def score_actions(*, nodes:dict[str,dict[str,Any]], edges:dict[str,dict[str,Any]], available_actions:Iterable[str], top_k:int=10, edge_threshold:float=0.1)->dict[str,Any]:
    actions=sorted({str(a) for a in available_actions if str(a)})
    if not actions:
        return {"schema":SCHEMA,"status":"HOLD","reason":"NO_AVAILABLE_ACTIONS","scores":{},"authority":{"executes_action":False,"mutates_graph":False}}
    active=sorted(
        ((str(node_id),node) for node_id,node in nodes.items() if isinstance(node,dict)),
        key=lambda item:(-float(item[1].get("energy",0.0) or 0.0),item[0])
    )[:max(0,int(top_k))]
    scores={a:0.0 for a in actions}; evidence={a:[] for a in actions}
    for node_id,node in active:
        energy=float(node.get("energy",0.0) or 0.0)
        data=node.get("data",{}) if isinstance(node.get("data",{}),dict) else {}
        direct=data.get("action")
        if direct in scores:
            scores[direct]+=energy
            evidence[direct].append({"kind":"NODE_ACTION","node_id":node_id,"energy":energy,"contribution":energy})
        prefix=node_id+"->"
        for key,edge in sorted(edges.items()):
            if not str(key).startswith(prefix) or not isinstance(edge,dict):
                continue
            weight=float(edge.get("weight",0.0) or 0.0)
            if weight<=float(edge_threshold):
                continue
            dst=str(key).split("->",1)[1]
            dst_node=nodes.get(dst)
            if not isinstance(dst_node,dict) or str(dst_node.get("type",""))!="action":
                continue
            dst_data=dst_node.get("data",{}) if isinstance(dst_node.get("data",{}),dict) else {}
            action=str(dst_data.get("action") or dst)
            if action not in scores:
                continue
            contribution=weight*energy
            scores[action]+=contribution
            evidence[action].append({"kind":"EDGE_TO_ACTION","source":node_id,"target":dst,"weight":weight,"energy":energy,"contribution":contribution})
    rounded={a:round(scores[a],12) for a in actions}
    best=max(rounded.values()) if rounded else 0.0
    winners=sorted([a for a,v in rounded.items() if v==best and v>0.0])
    status="PROPOSAL" if winners else "NO_SIGNAL"
    selected=winners[0] if len(winners)==1 else None
    body={
      "schema":SCHEMA,"status":status,"selected_action":selected,"tied_actions":winners if len(winners)>1 else [],
      "scores":rounded,"evidence":evidence,"active_nodes":[node_id for node_id,_ in active],
      "config":{"top_k":max(0,int(top_k)),"edge_threshold":float(edge_threshold)},
      "authority":{"executes_action":False,"mutates_graph":False,"adds_outcome_node":False,"reinforces_edges":False},
      "laws":["GRAPH_SCORE_NE_ACTION_AUTHORITY","NO_SIGNAL_NE_RANDOM_ACTION","OUTCOME_LEARNING_REQUIRES_SEPARATE_WRITE_GATE"]
    }
    body["score_receipt_sha256"]=hashlib.sha256(_canon(body)).hexdigest()
    return body
