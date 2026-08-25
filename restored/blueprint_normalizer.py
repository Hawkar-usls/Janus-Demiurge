from __future__ import annotations
import hashlib, json
from typing import Any

SCHEMA="janus.module_blueprint.v1"
SUPPORTED={"NEW_MODULE_BLUEPRINT","CODE_GENERATION","NEW_MODULE_IDEA"}

def _canon(x:Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def normalize(event:dict[str,Any], *, source_event_id:str|None=None)->dict[str,Any]:
    observed=str(event.get("type","UNKNOWN"))
    if observed not in SUPPORTED:
        return {"schema":SCHEMA,"status":"HOLD","reason":"UNSUPPORTED_LEGACY_TYPE","observed_type":observed,
                "historical_translation_claim":False}
    title=str(event.get("title") or event.get("label") or "").strip()
    blueprint=event.get("blueprint")
    if blueprint is None: blueprint=event.get("content")
    if blueprint is None: blueprint=event.get("description")
    blueprint="" if blueprint is None else str(blueprint).strip()
    if not title or not blueprint:
        return {"schema":SCHEMA,"status":"HOLD","reason":"MISSING_TITLE_OR_BLUEPRINT","observed_type":observed,
                "historical_translation_claim":False}
    identity={"source_event_id":source_event_id,"observed_type":observed,"title":title,"blueprint":blueprint}
    candidate_id=hashlib.sha256(_canon(identity)).hexdigest()
    return {"schema":SCHEMA,"status":"NORMALIZED_CANDIDATE","candidate_id":candidate_id,
            "source_event_id":source_event_id,"observed_type":observed,"title":title,"blueprint":blueprint,
            "historical_translation_claim":False,
            "authority":{"generates_code":False,"writes_module":False,"promotes_live":False},
            "law":"MODERN_NORMALIZATION_REPAIRS_PROTOCOL_DRIFT; IT_DOES_NOT_PROVE_A_HISTORICAL_TRANSLATOR_EXISTED"}
