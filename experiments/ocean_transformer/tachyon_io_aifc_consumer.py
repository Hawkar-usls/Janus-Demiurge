"""Ocean read-only consumer for Tachyon Proof-of-Observation/AIFC eligibility receipts.

This consumes an integrity-checked *assessment*, never a direct neural training
target, proof of a future channel, or command to change source experiments.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA="janus.tachyon.io_aifc_observation_gate.v1"
OUT_SCHEMA="janus.ocean.tachyon_external_evidence_context.v1"
PRECOMMIT_SHA="1d4ba8d4dc7200510c1ee743e6f8a81de50819871d5d586d2d600425c5a7dd2d"
REVIEW_SHA="47faf50bc654fdccb30573cc6ed84cb5f629a7ad4808633db7a6306c4fbe9227"
HEX=re.compile(r"^[0-9a-f]{64}$")

def canonical(o):
    return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def consume(receipt):
    if not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA:
        raise ValueError("IO_AIFC_SCHEMA_INVALID")
    body=dict(receipt)
    claim=body.pop("receipt_sha256",None)
    if not isinstance(claim,str) or not HEX.fullmatch(claim) or sha(canonical(body))!=claim:
        raise ValueError("IO_AIFC_RECEIPT_DIGEST_MISMATCH")
    src=receipt.get("input")
    io=receipt.get("proof_of_observation")
    aifc=receipt.get("aifc")
    topa=receipt.get("topa")
    if (not isinstance(src,dict) or
            src.get("ocean_run_id")!=42878578752 or
            src.get("ocean_artifact_id")!=13793425503 or
            src.get("frozen_precommit_sha256")!=PRECOMMIT_SHA or
            src.get("tachyon_review_sha256")!=REVIEW_SHA):
        raise ValueError("ORIGINAL_OCEAN_PRECOMMIT_NOT_BOUND")
    if (not isinstance(io,dict) or
            io.get("source_repo")!="Hawkar-usls/janus-io-public" or
            not HEX.fullmatch(str(io.get("source_sha256",""))) or
            io.get("status")!="OBSERVATION_ONLY_PARTIAL_CHAIN" or
            io.get("live_github_artifact_binding_pass") is not True or
            io.get("independent_source_truth_verified") is not False or
            io.get("full_independent_observation_chain") is not False or
            io.get("future_outcomes_not_available_to_this_audit") is not True):
        raise ValueError("IO_INTEGRITY_OR_INDEPENDENCE_ESCALATION")
    if (not isinstance(aifc,dict) or
            aifc.get("source_repo")!="Hawkar-usls/AIFC" or
            not HEX.fullmatch(str(aifc.get("grades_source_sha256",""))) or
            aifc.get("scope")!="ELIGIBILITY_SCREEN_NOT_FULL_AIFC_VERIFIER" or
            aifc.get("grade")!="NOT_ADMITTED" or
            len(aifc.get("missing_or_unverified",[]))<5 or
            aifc.get("physical_retrocausality_established") is not False):
        raise ValueError("AIFC_CLAIM_PROMOTION_OR_GAPS_HIDDEN")
    if (not isinstance(topa,dict) or topa.get("claim_status")!="HYPOTHESIS_ONLY"
            or topa.get("promoted") is not False or
            receipt.get("weights_changed") is not False or
            receipt.get("eligible_as_gradient_label") is not False or
            receipt.get("authority_delta")!=0):
        raise ValueError("TOPA_OR_MODEL_AUTHORITY_ESCALATION")
    output={
        "schema":OUT_SCHEMA,
        "status":"EXTERNAL_OBSERVATION_AUDIT_IMPORTED_NOT_TRAINING",
        "source":{"tachyon_gate_sha256":claim,"ocean_original_precommit_sha256":PRECOMMIT_SHA,
                  "ocean_original_run":42878578752,"io_source_sha256":io["source_sha256"],
                  "aifc_grades_sha256":aifc["grades_source_sha256"]},
        "observation_status":io["status"],
        "aifc_grade":aifc["grade"],
        "topa_claim_status":"HYPOTHESIS_ONLY",
        "scientific_claim_promoted":False,
        "future_outcomes_imported":False,
        "ocean_weights_changed":False,
        "tachyon_training_labels_admitted":False,
        "rights":{"may_edit_original_009b":False,"may_score_future_beacons":False,
                  "may_trigger_training":False,"may_promote_claim":False,
                  "may_mutate_repositories":False},
        "authority_delta":0,
    }
    output["receipt_sha256"]=sha(canonical(output))
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--tachyon-io-aifc-gate",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    raw=Path(args.tachyon_io_aifc_gate).read_bytes()
    if len(raw)>150000:
        raise ValueError("UNBOUNDED_IO_AIFC_INPUT")
    output=consume(json.loads(raw))
    dst=Path(args.out);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf-8") as f:
        json.dump(output,f,indent=2,sort_keys=True,ensure_ascii=False)
        f.write("\n")
    print(json.dumps({"status":output["status"],"receipt_sha256":output["receipt_sha256"]}))

if __name__=="__main__":
    main()
