from __future__ import annotations
import hashlib, json
from typing import Any, Iterable

SCHEMA="janus.graph_selection.assessment.v1"
DEFAULT_PROTECTED_TYPES=("root","insight","location","artifact","genesis_node","dream","tobi_child")


def _canon(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")


def _id(value:Any)->str:
    if isinstance(value,dict): value=value.get("id","")
    return str(value or "").strip()


def assess(nodes:Iterable[dict[str,Any]], links:Iterable[dict[str,Any]], *, pain_threshold:float=3.0, protected_types:Iterable[str]=DEFAULT_PROTECTED_TYPES)->dict[str,Any]:
    node_list=[dict(n) for n in nodes if isinstance(n,dict)]
    link_list=[dict(l) for l in links if isinstance(l,dict)]
    protected={str(x) for x in protected_types}
    degree={_id(n):0 for n in node_list if _id(n)}
    for link in link_list:
        s=_id(link.get("source")); t=_id(link.get("target"))
        if s in degree: degree[s]+=1
        if t in degree: degree[t]+=1
    assessments=[]; proposals=[]
    for node in sorted(node_list,key=lambda n:_id(n)):
        nid=_id(node); ntype=str(node.get("type","") or "")
        pain=float(node.get("pain_score",0.0) or 0.0)
        reasons=[]
        is_protected=ntype in protected
        if degree.get(nid,0)==0: reasons.append("ISOLATED")
        if pain>float(pain_threshold): reasons.append("HIGH_PAIN")
        status="PROTECTED" if is_protected else ("REVIEW" if reasons else "KEEP")
        rec={"node_id":nid,"type":ntype,"degree":degree.get(nid,0),"pain_score":pain,"status":status,"reasons":reasons}
        assessments.append(rec)
        if status=="REVIEW":
            proposals.append({"node_id":nid,"proposal":"ARCHIVE_OR_QUARANTINE_REVIEW","reasons":reasons})
    identity={"pain_threshold":float(pain_threshold),"protected_types":sorted(protected),"assessments":assessments,"proposals":proposals}
    body={"schema":SCHEMA,"status":"REVIEW_PROPOSALS" if proposals else "NO_REVIEW_REQUIRED",
          "pain_threshold":float(pain_threshold),"protected_types":sorted(protected),"assessments":assessments,"proposals":proposals,
          "authority":{"deletes_nodes":False,"removes_links":False,"archives_nodes":False,"quarantines_nodes":False,"saves_graph":False},
          "laws":["NO_LEARNING_ENTITY_DELETION","SELECTION_ASSESSMENT_NE_PRUNING","PROTECTED_TYPE_NE_PROVEN_TRUTH","PAIN_SCORE_NE_AUTOMATIC_DELETION"]}
    body["assessment_sha256"]=hashlib.sha256(_canon(identity)).hexdigest()
    return body
