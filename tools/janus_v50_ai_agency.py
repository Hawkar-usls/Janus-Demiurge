#!/usr/bin/env python3
"""JANUS v5.0 bounded agent: source->TOPA JSON rails->Beetle intent->Meta EYE packet.

The native neural decision may abstain. Model text can select research attention
but cannot confer workflow, source, truth, production or Sentinel authority.
Only explicit user-intent in the checked repository can request execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "janus.agency.source_provenance_packet/5.0"
META_SCHEMA = "janus.agency.meta_json_learning_input/5.0"
SOURCE = "research/essence/peer_v49/FIRST_PROSPECTIVE_READOUT.json"
TOPA_REV = "0890172493d6ed0d3a62e79904c6a7593eb8a9f3"
JSON_RAIL_SCHEMA = "hawkar.topa.json_rails.inspect.v1"
REPOS = ("Hawkar-usls/janus-meta-registry", "Hawkar-usls/Janus_Genesis")
DIRS = ("registry_provenance","formal_proof_verification")
HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def dump(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode()


def sha(obj):
    return hashlib.sha256(dump(obj)).hexdigest()


def sealed(obj):
    return dict(obj,receipt_sha256=sha(obj))


def check(obj):
    if not isinstance(obj,dict) or obj.get("receipt_sha256") != sha({
            k:v for k,v in obj.items() if k!="receipt_sha256"}):
        raise ValueError("AGENCY_RECEIPT_INTEGRITY_FAILURE")
    return obj


def read(file, maxbytes=160_000):
    p=Path(file)
    if not p.is_file() or p.is_symlink() or p.stat().st_size>maxbytes:
        raise ValueError("UNSAFE_OR_MISSING_JSON")
    return json.loads(p.read_text(encoding="utf-8"),parse_constant=lambda x:
                      (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def validate_desire(o, directives):
    if o.get("schema")!="janus.demiurge.beetle.desires.v1":
        raise ValueError("INVALID_BEETLE_INTENT")
    if (o.get("status")!="USER_REQUESTED_BOUNDED_JSON_RESEARCH_ATTENTION"
            or o.get("producer",{}).get("current_writer") !=
            "EXPLICIT_USER_DIRECTIVE_TRANSLATED_TO_DISCOVERY_ATTENTION"):
        raise ValueError("NO_EXPLICIT_RESEARCH_ACTION")
    focus=o.get("focus",[])
    if (not isinstance(focus,list) or len(focus)!=2 or
        {x.get("direction_id") for x in focus} != set(DIRS) or
        any(not 0<=x.get("priority_delta",-1)<=25 for x in focus)):
        raise ValueError("DISALLOWED_BEETLE_DIRECTION")
    allowed=directives.get("base_priorities",{})
    if not all(x["direction_id"] in allowed for x in focus):
        raise ValueError("DIRECTION_NOT_IN_CANONICAL_BEETLE_ALLOWLIST")
    adhoc=o.get("ad_hoc",[])
    if len(adhoc)!=1 or adhoc[0].get("id")!="janus_json_registry_provenance_audit":
        raise ValueError("DISALLOWED_BEETLE_TASK")
    item=adhoc[0]
    if (tuple(item.get("target_repositories",[]))!=REPOS or
            not set(REPOS).issubset(directives.get("allowed_target_repositories",[]))
            or not isinstance(item.get("priority"),int) or item["priority"]>85
            or item.get("title")!="Find verifiable JSON source lineage, uncertainty and negative results for JANUS Meta Registry"
            or not isinstance(item.get("keywords"),list)
            or len(item["keywords"])>10
            or any(not isinstance(x,str) or len(x)>90 for x in item["keywords"])):
        raise ValueError("BEETLE_ADHOC_SCOPE_ESCALATION")
    if o.get("hold") != [] or any(d.get("priority_delta",0)<0 for d in focus):
        raise ValueError("CANNOT_DISABLE_COUNTEREVIDENCE")
    return o


def native_status(o):
    if (o.get("schema")!="janus.native_repair_decision.v1"
            or o.get("native_model_decision") is not True
            or o.get("selected",{}).get("action") not in ("NO_ACTION","PROPOSE_PATCH")
            or o.get("authority",{}).get("direct_repository_mutation") is not False
            or o.get("authority",{}).get("autonomous_merge") is not False
            or o.get("authority",{}).get("topa_is_world_truth") is not False):
        raise ValueError("NATIVE_DECISION_AUTHORITY_DRIFT")
    return {"decision_id":o.get("decision_id"),
            "selected_action":o["selected"]["action"],
            "native_proposed_this_user_task":False,
            "explicit_user_directive_is_separate":True}


def validate_readout(o):
    if (o.get("schema")!="janus.essence.continual_prospective_first_trial_evidence/4.9"
            or o.get("status")!="HOLD_REPLAY_DID_NOT_CLEAR_PREDECLARED_GATES"
            or o.get("experiment",{}).get("run_id")!=43755360999
            or o.get("deployment",{}).get("production_admission") is not False
            or o.get("deployment",{}).get("g2_parent_unchanged") is not True
            or o.get("interpretation",{}).get("external_custodian") is not False):
        raise ValueError("INVALID_V49_ORIGIN_OR_OVERSOLD_MODEL")
    r=o.get("results",{})
    if (r.get("fresh_unseen_legacy_oracle",{}).get("replay_exact")!=16
            or r.get("lapis_paraphrased_source",{}).get("replay_exact")!=0
            or o.get("precommitted_gates",{}).get("threshold_retuned") is not False):
        raise ValueError("EVIDENCE_SOURCE_DRIFT")
    return o


def topa_inspection(o, original_bytes, filename):
    if (o.get("schema")!=JSON_RAIL_SCHEMA
            or o.get("format",{}).get("kind")!="json"
            or o.get("format",{}).get("compression") is not None
            or o.get("records")!=1
            or o.get("malformed_records")!=0
            or o.get("type_counts")!={"object":1}
            or o.get("raw_sha256")!=hashlib.sha256(original_bytes).hexdigest()
            or not HEX64.fullmatch(o.get("semantic_record_stream_sha256",""))
            or o.get("path")!=filename):
        raise ValueError("TOPA_SOURCE_BYTE_OR_RAIL_VERIFICATION_FAILED")
    return o


def build(repo_root, inspect, commit):
    if not HEX40.fullmatch(commit):
        raise ValueError("MISSING_SOURCE_COMMIT")
    root=Path(repo_root)
    desire=validate_desire(read(root/"beetle/JANUS_DESIRES.json"),
                           read(root/"beetle/DEMIURGE_BEETLE_DIRECTIVES.json"))
    native=native_status(read(root/"janus_model/state/JANUS_LATEST_DECISION.json"))
    source_path=root/SOURCE
    data=source_path.read_bytes()
    parsed=validate_readout(read(source_path))
    inspected=topa_inspection(read(inspect),data,str(source_path))
    digest=hashlib.sha256(data).hexdigest()
    # The research task was explicitly directed by the user, not selected by
    # the native decision whose most recent state may be NO_ACTION.
    fact={
        "schema":META_SCHEMA,
        "status":"TOPA_STRUCTURAL_SOURCE_VERIFIED_NOT_SCIENTIFIC_TRUTH",
        "source_repository":"Hawkar-usls/Janus-Demiurge",
        "source_path":SOURCE,
        "source_commit":commit,
        "source_raw_sha256":digest,
        "topa_code_commit":TOPA_REV,
        "topa_semantic_stream_sha256":inspected["semantic_record_stream_sha256"],
        "research_experiment_run_id":43755360999,
        "research_verdict":parsed["status"],
        "confirmed_counts":{
            "replay_fresh_old":16,"naive_fresh_old":8,
            "replay_new_lapis_exact":0,"new_lapis_count":6,
        },
        "epistemic_boundary":{
            "topa_bytes_are_world_truth":False,
            "model_output_is_independent_validation":False,
            "verified_negative_results_preserved":True,
            "used_as_direct_neural_supervision":False,
            "automatic_model_promotion":False,
        },
        "proof_authority":"SOURCE_INTEGRITY_ONLY",
    }
    receipt=sealed({
        "schema":SCHEMA,
        "status":"SOURCE_INTEGRITY_VERIFIED_DISPATCH_REQUEST_ONLY",
        "source_raw_sha256":digest,
        "source_commit":commit,
        "source_path":SOURCE,
        "topa_code_commit":TOPA_REV,
        "topa_inspect_receipt_sha256":sha(inspected),
        "native_model":native,
        "source_beetle_intent":"EXPLICIT_USER_DISCOVERY_STEERING",
        "beetle_task_id":desire["ad_hoc"][0]["id"],
        "allowed_local_workflows":[
            "janus-beetle-director.yml","janus-topa-scout-epistemic.yml"],
        "allowlisted_remote_workflows":[
            {"repo":"Hawkar-usls/TOPA","workflow":"validate-json-rails.yml"},
            {"repo":"Hawkar-usls/janus-meta-registry","workflow":"eye-meta-registry-train.yml"},
        ],
        "remote_execution_requires_separate_token":True,
        "remote_execution_observed":False,
        "beetle_runtime_execution_observed":False,
        "source_fact_json":fact,
        "external_scientific_validation":False,
        "production_write_authority":False,
        "sentinel_dispatch":False,
    })
    return receipt


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",default=".")
    ap.add_argument("--inspect",required=True)
    ap.add_argument("--commit",required=True)
    ap.add_argument("--out",required=True)
    args=ap.parse_args()
    result=build(args.root,args.inspect,args.commit)
    p=Path(args.out)
    if p.exists() or p.is_symlink():
        raise ValueError("APPEND_ONLY_PACKET_OUTPUT")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+"\n",
                 encoding="utf-8")
    print(json.dumps({"packet_sha256":result["receipt_sha256"],
                      "source_sha256":result["source_raw_sha256"],
                      "native_selected":result["native_model"]["selected_action"],
                      "topa_status":"PASS_SOURCE_INTEGRITY_ONLY",
                      "beetle_intent":"USER_REQUESTED_NOT_MODEL_ACTION",
                      "production_authority":False},sort_keys=True))

if __name__=="__main__":
    main()
