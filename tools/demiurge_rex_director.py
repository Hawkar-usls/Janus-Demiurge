#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, re
from typing import Any

MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def load(path: pathlib.Path) -> dict[str, Any]:
    obj=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj,dict): raise SystemExit(f"JSON object required: {path}")
    return obj


def write_if_changed(path: pathlib.Path, obj: dict[str, Any]) -> bool:
    raw=json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if path.exists() and path.read_text(encoding="utf-8")==raw: return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(raw,encoding="utf-8")
    return True


def main() -> int:
    ap=argparse.ArgumentParser(description="JANUS Rex Director: bounded desire -> ModuleSpec")
    ap.add_argument("--desires",default="rex/JANUS_REX_DESIRES.json")
    ap.add_argument("--policy",default="rex/policy.json")
    ap.add_argument("--nexus-policy",default="rex/nexus_policy.json")
    ap.add_argument("--out-dir",default="rex/specs/generated")
    a=ap.parse_args()
    desires=load(pathlib.Path(a.desires)); policy=load(pathlib.Path(a.policy)); nexus=load(pathlib.Path(a.nexus_policy))
    if desires.get("schema")!="janus.rex.desires.v1": raise SystemExit("unsupported desires schema")
    if policy.get("schema")!="janus.rex.policy.v1": raise SystemExit("unsupported Rex policy")
    if nexus.get("schema")!="janus.nexus.rex_low_risk_policy.v1": raise SystemExit("unsupported Nexus policy")
    if (desires.get("authority") or {}).get("authority_delta")!=0: raise SystemExit("desire authority delta must be zero")
    allowed=set(policy.get("allowed_templates") or [])
    auto_allowed=set(nexus.get("allowed_autorun_templates") or [])
    made=[]; unchanged=[]; skipped=[]
    for row in desires.get("requests",[]):
        if not isinstance(row,dict): continue
        desire_id=str(row.get("desire_id") or "")
        if row.get("status")!="REQUESTED":
            skipped.append({"desire_id":desire_id,"reason":"status_not_requested"}); continue
        mid=str(row.get("module_id") or "")
        if not MODULE_ID_RE.fullmatch(mid): raise SystemExit(f"invalid module_id for desire {desire_id}")
        template=str(row.get("template") or "")
        if template not in allowed: raise SystemExit(f"template not allowed for desire {desire_id}")
        purpose=row.get("purpose")
        if not isinstance(purpose,str) or not purpose.strip(): raise SystemExit(f"purpose required for desire {desire_id}")
        cfg=row.get("config") or {}
        if not isinstance(cfg,dict): raise SystemExit(f"config must be object for desire {desire_id}")
        nx=row.get("nexus") or {}
        if not isinstance(nx,dict): raise SystemExit(f"nexus must be object for desire {desire_id}")
        autorun=nx.get("request_autorun") is True
        if autorun and (not nexus.get("enabled") or template not in auto_allowed):
            raise SystemExit(f"Nexus autorun policy refuses desire {desire_id}")
        input_obj=nx.get("input",{})
        if not isinstance(input_obj,dict): raise SystemExit(f"Nexus input must be object for desire {desire_id}")
        spec={
            "schema":"janus.rex.module_spec.v1",
            "module_id":mid,
            "version":str(row.get("version") or "1.0.0"),
            "purpose":purpose[:int(policy["limits"]["max_purpose_length"])],
            "template":template,
            "config":cfg,
            "nexus":{"request_autorun":autorun,"input":input_obj},
            "provenance":{
                "desire_id":desire_id,
                "desire_status":"REQUESTED",
                "generated_by":"JANUS_DEMIURGE_REX_DIRECTOR_V1_1",
                "desire_is_source_code":False,
                "desire_grants_admission":False,
                "authority_delta":0
            }
        }
        out=pathlib.Path(a.out_dir)/f"{mid}.json"
        (made if write_if_changed(out,spec) else unchanged).append(out.as_posix())
    result={"schema":"janus.rex.director_receipt.v1","status":"PASS","created_or_changed":made,"unchanged":unchanged,"skipped":skipped,"authority_delta":0,"law":"DESIRE_TO_SPEC_NE_ADMISSION"}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
