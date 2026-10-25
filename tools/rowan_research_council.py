#!/usr/bin/env python3
"""Demiurge Rowan research council, source-bound to EXISTING AURA + Meta Registry.

All inputs are public, read-only, no AURA runtime impersonation.
Produces a ranked research *proposal*, not a hypothesis truth claim or
permission to mutate workflows, train production models or spend Rowan credits.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen

AURA_URL="https://raw.githubusercontent.com/Hawkar-usls/aura-oracle-tg/main/research/rowan/LATEST_HYPOTHESES.json"
META_URL="https://raw.githubusercontent.com/Hawkar-usls/janus-meta-registry/main/data/rowan/CANONICAL_STATE.json"
AURA_SCHEMA="janus.aura.rowan_hypothesis_packet.v1"
STATE_SCHEMA="janus.rowan.observer_state.v1"
HYPOS=("H_CONFIDENCE_SIGNAL","H_NULL_SIGNAL","H_ASSAY_CONFOUND","H_DOMAIN_SHIFT")
FIXED_SEARCH=("RAW_ASSAY_LINEAGE","NEGATIVE_CONTROLS","EXTERNAL_HOLDOUT")

class CouncilHold(ValueError):pass

def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()

def sha(obj):
    return hashlib.sha256(canon(obj)).hexdigest()

def verify(meta,aura):
    if meta.get("schema_id")!=STATE_SCHEMA or aura.get("schema_id")!=AURA_SCHEMA:
        raise CouncilHold("INPUT_SCHEMAS_MISMATCH")
    source=aura.get("source",{})
    run=meta.get("latest_durable_external_run")
    count=meta.get("last_completed_mutants")
    if type(run)!=int or run<=0 or type(count)!=int or not 0<=count<=8:
        raise CouncilHold("INVALID_META_RUN_OR_COUNT")
    if source.get("upstream_run")!=run or source.get("completed_mutants")!=count:
        raise CouncilHold("AURA_NOT_BOUND_TO_LATEST_META_CHECKPOINT")
    if source.get("upstream_artifact_sha256")!=meta.get("underlying_state_is_derived_from"):
        raise CouncilHold("EVIDENCE_SOURCE_DRIFT")
    if source.get("state_sha256")!=sha(meta):
        raise CouncilHold("AURA_STATE_HASH_INVALID")
    without=dict(aura)
    digest=without.pop("packet_digest_sha256",None)
    if digest!=sha(without):
        raise CouncilHold("AURA_PACKET_TAMPERED")
    hypos=aura.get("hypotheses")
    if not isinstance(hypos,list) or tuple(x.get("id") for x in hypos)!=HYPOS:
        raise CouncilHold("FOUR_AURA_HYPOTHESES_CHANGED")
    if any(x.get("status")!="HYPOTHESIS_ONLY__NOT_MEASURED" or x.get("empirical_truth_probability") is not None for x in hypos):
        raise CouncilHold("HYPOTHESIS_PREMATURELY_PROMOTED")
    proposals=aura.get("search_proposals")
    if not isinstance(proposals,list) or tuple(x.get("id") for x in proposals)!=FIXED_SEARCH:
        raise CouncilHold("AURA_SEARCH_ADMISSION_SCOPE_DRIFT")
    authority=aura.get("bounded_authority",{})
    for key in ("may_resolve_own_forecast","may_submit_rowan_jobs","may_modify_rowan_credit_budget",
                "may_change_model_weights","may_promote_TOPA_scientific_gate"):
        if authority.get(key) is not False:
            raise CouncilHold("AURA_AUTHORITY_ESCALATION")
    if aura.get("information_gain")!="NOT_ESTIMATED_NO_CALIBRATED_HYPOTHESIS_PRIORS":
        raise CouncilHold("UNVERIFIED_INFORMATION_GAIN_CLAIM")
    return run,count

def council(meta,aura):
    run,count=verify(meta,aura)
    topa_gate=meta.get("topa_gate")
    if topa_gate not in ("OPEN","INDEPENDENT_REPLAY_PASS","UNKNOWN",None):
        raise CouncilHold("UNRECOGNIZED_TOPA_GATE")
    if count<8:
        next_id="RAW_ASSAY_LINEAGE"
        outcome="PENDING_PRE_REGISTERED_ROWAN_RESULTS"
        control="Locate source assay units, biological replicates, independent controls and processing pipeline"
    else:
        next_id="EXTERNAL_HOLDOUT"
        outcome="ROWAN_EIGHT_READY_FOR_NONCAUSAL_TOPA_REPLAY"
        control="Challenge any structural-confidence correlation with independent external protein holdouts"
    if aura.get("next_discriminating_question_id")!=next_id:
        raise CouncilHold("AURA_NEXT_QUESTION_CHANGED")
    r={
        "schema_id":"janus.demiurge.rowan_council_proposal.v1",
        "mode":"AUTONOMOUS_READ_ONLY_RESEARCH_STEERING",
        "sources":{"meta_registry":{"repository":"Hawkar-usls/janus-meta-registry",
                  "canonical_run":run,"sha256":sha(meta),
                  "source_artifact_sha256":meta["underlying_state_is_derived_from"]},
                  "aura_oracle":{"repository":"Hawkar-usls/aura-oracle-tg",
                    "packet_sha256":sha(aura),"packet_digest":aura["packet_digest_sha256"]}},
        "phase_graph":{
           "SENSE":"Universal Beetle protein_stability_falsifiers metadata discovery",
           "THINK":"AURA four opposing hypotheses and bounded discriminatory question",
           "CHALLENGE":"TOPA adversarial falsification and independent assay checks",
           "REMEMBER":"Meta Registry append-only scientific source receipts"},
        "hypothesis_ids":list(HYPOS),
        "research_status":outcome,
        "completed_pilot_cases":count,
        "next_beetle_direction_id":"protein_stability_falsifiers",
        "next_aura_question_id":next_id,
        "next_independent_control":control,
        "hypothesis_assigned_probability":None,
        "scientific_authority":"NONE__PROPOSAL_NOT_EXPERIMENT",
        "gates":{"rowan_credit_spend_new":False,
                 "rowan_job_submission_new":False,
                 "beetle_candidates_empirical_evidence":False,
                 "aura_predictions_empirical_evidence":False,
                 "topa_external_wetlab_validation":"OPEN",
                 "production_model_weight_promotion":False,
                 "study_scope_expansion":"PROPOSAL_ONLY",
                 "observer_alert_on_routine_snapshot":False},
    }
    r["content_sha256"]=sha(r)
    return r

def read(source):
    with urlopen(Request(source,headers={"User-Agent":"JANUS-DEMIURGE-RESEARCH-COUNCIL/1"}),timeout=25) as resp:
        blob=resp.read(42001)
    if len(blob)>42000:raise CouncilHold("EXTERNAL_SOURCE_OVERSIZED")
    return json.loads(blob.decode("utf-8"))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--meta")
    parser.add_argument("--aura")
    parser.add_argument("--output",default="research/rowan/LATEST_COUNCIL.json")
    args=parser.parse_args()
    try:
        meta=json.loads(Path(args.meta).read_text()) if args.meta else read(META_URL)
        aura=json.loads(Path(args.aura).read_text()) if args.aura else read(AURA_URL)
        result=council(meta,aura)
    except (CouncilHold,TypeError,ValueError,OSError):
        print("DEMIURGE_ROWAN=SOURCE_GATE_HOLD_OR_UPSTREAM_PENDING")
        return 0
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True).encode()+b"\n"
    if not out.exists() or out.read_bytes()!=data:out.write_bytes(data)
    print("DEMIURGE_ROWAN=BOUNDED_RESEARCH_PROPOSAL_COMMITTED_SOURCE_READY")
    print("DEMIURGE_ROWAN_SOURCE_RUN="+str(result["sources"]["meta_registry"]["canonical_run"]))
    print("DEMIURGE_ROWAN_NEW_BILLING_AUTHORITY=FALSE")
    return 0

if __name__=="__main__":raise SystemExit(main())
