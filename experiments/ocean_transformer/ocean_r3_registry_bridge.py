"""JANUS Ocean R3: read-only attestation of Meta Registry source/quality pairs.

The Ocean model still trains on historical JSON-addition *metadata* only.
Unverified R3 source/quality files are excluded from model chronology.
This bridge never imports source content as a gradient label, fetches private
data, modifies weights, or elevates the scientific admission gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

QUARANTINE="data/observations/public_source_quarantine/"
QUALITY="data/observations/public_source_quality/"
FEEDBACK=("JANUS-META-NEXT-","JANUS-AIR-ALERT-")
SHA20=re.compile(r"^[a-f0-9]{20}$")
SHA64=re.compile(r"^[a-f0-9]{64}$")
SHA40=re.compile(r"^[a-f0-9]{40}$")
SOURCE_PREFIX="JANUS-PUBLIC-SOURCES-"
QUALITY_PREFIX="JANUS-R3-QUALITY-"
SOURCE_SCHEMA="janus.public_source_intake.quarantine.v1"
QUALITY_SCHEMA="janus.r3.public_source_quality_review.v1"
OCEAN_SCHEMA="janus.ocean.r3.registry_witness.v1"
COMBINED_SCHEMA="janus.ocean.r3.research_comparison.v1"
MAX_FILES=1000
LEGACY_SOURCE={"JANUS-PUBLIC-SOURCES-5277ff2d788de4b43f27.json"}

def require(ok, msg):
    if not ok:
        raise ValueError(msg)

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf8")

def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def read(path):
    obj=json.loads(Path(path).read_text(encoding="utf8"))
    require(isinstance(obj,dict),"NON_OBJECT_JSON")
    return obj

def chronology_allowed(path):
    """Block unreviewed provenance from the neural forecast target and features."""
    require(isinstance(path,str),"INVALID_JSON_PATH")
    norm=path.replace("\\","/")
    if norm.startswith(QUARANTINE) or norm.startswith(QUALITY):
        return False
    if any(Path(norm).name.upper().startswith(pre) for pre in FEEDBACK):
        return False
    return norm.endswith(".json")

def verify_pair(source,quality):
    require(source.get("schema")==SOURCE_SCHEMA,"R3_SOURCE_SCHEMA")
    ident=source.get("record_id","")
    require(isinstance(ident,str) and ident.startswith(SOURCE_PREFIX) and
            SHA20.fullmatch(ident[len(SOURCE_PREFIX):]),"R3_SOURCE_ID")
    require(source.get("source_digest_sha256")==digest(source.get("sources")),
            "R3_SOURCE_CONTENT_HASH")
    require(ident==SOURCE_PREFIX+source["source_digest_sha256"][:20],
            "R3_SOURCE_ID_HASH")
    require(source.get("receipt_sha256")==digest({
        k:v for k,v in source.items() if k!="receipt_sha256"
    }),"R3_SOURCE_RECEIPT_HASH")
    require(source.get("source_class")=="PUBLIC_UNTRUSTED_METADATA_QUARANTINE"
            and source.get("training_permitted") is False
            and source.get("factual_claims_verified") is False
            and source.get("scientific_admission")=="HOLD",
            "R3_QUARANTINE_BYPASS")

    require(quality.get("schema")==QUALITY_SCHEMA,
            "R3_QUALITY_SCHEMA")
    # Strictly bound to the source receipt, not merely an equal filename.
    require(quality.get("source_record_id")==ident and
            quality.get("source_receipt_sha256")==source["receipt_sha256"] and
            quality.get("source_digest_sha256")==source["source_digest_sha256"],
            "R3_QUALITY_WRONG_SOURCE")
    require(quality.get("quality_receipt_sha256")==digest({
        k:v for k,v in quality.items() if k!="quality_receipt_sha256"
    }),"R3_QUALITY_CHECKSUM")
    for field in ("model_training_authorized","model_training_dispatched",
                  "scientific_knowledge_promoted","neural_model_improved",
                  "news_claims_fact_checked",
                  "article_claims_independently_verified",
                  "external_blind_science_evaluator_used"):
        require(quality.get(field) is False,"R3_QUALITY_UNTRUSTED_PROMOTION")
    require(quality.get("proposed_action")=="HUMAN_REVIEW_ONLY",
            "R3_QUALITY_NOT_REVIEW_ONLY")
    require(type(quality.get("new_metadata_id_count")) is int and
            0<=quality["new_metadata_id_count"]<=1000,
            "R3_BAD_NOVELTY_COUNT")
    return {
        "source_record_id":ident,
        "source_receipt_sha256":source["receipt_sha256"],
        "quality_receipt_sha256":quality["quality_receipt_sha256"],
        "new_metadata_id_count":quality["new_metadata_id_count"],
        "metadata_sources_with_integrity":quality.get(
            "metadata_sources_with_integrity"),
        "observed_at_utc":source.get("observed_at_utc"),
        "quality_role":"METADATA_NOVELTY_NOT_SCIENCE_VERIFICATION"
    }

def registry_witness(meta_root,meta_head):
    root=Path(meta_root)
    require(SHA40.fullmatch(meta_head) is not None,"META_HEAD_NOT_A_SHA")
    q=root/QUARANTINE
    quality=root/QUALITY
    src_files=sorted(q.glob("JANUS-PUBLIC-SOURCES-*.json")) if q.exists() else []
    reports=sorted(quality.glob("JANUS-R3-QUALITY-*.json")) if quality.exists() else []
    require(len(src_files)<=MAX_FILES and len(reports)<=MAX_FILES,
            "R3_RECEIPT_COUNT_LIMIT")
    src_names={p.name:p for p in src_files}
    pairs=[]
    matching=set()
    for r in reports:
        suffix=r.name.removeprefix(QUALITY_PREFIX).removesuffix(".json")
        require(SHA20.fullmatch(suffix) is not None,"R3_QUALITY_FILENAME")
        name=SOURCE_PREFIX+suffix+".json"
        require(name in src_names,"R3_ORPHAN_QUALITY")
        pairs.append(verify_pair(read(src_names[name]),read(r)))
        matching.add(name)
    unpaired=set(src_names)-matching
    require(unpaired.issubset(LEGACY_SOURCE),
            "R3_NEW_UNPAIRED_QUARANTINE_SOURCE")
    latest=sorted(pairs,key=lambda p:(
        str(p["observed_at_utc"]),p["source_record_id"]),reverse=True)[:4]
    record={
        "schema":OCEAN_SCHEMA,
        "meta_registry_repository":"Hawkar-usls/janus-meta-registry",
        "meta_registry_source_head":meta_head,
        "paired_reviewed_metadata_records":len(pairs),
        "legacy_source_without_r3_quality":len(unpaired),
        "newest_pairs":latest,
        "status":("R3_METADATA_PRESENT_REVIEW_ONLY" if pairs else
                  "WAITING_FOR_FIRST_MERGED_R3_PAIR"),
        "model_input_contains_quarantined_source":False,
        "quality_metadata_used_as_gradient_labels":False,
        "raw_news_used_for_training":False,
        "trust_level":"REVIEWED_MERGE_IS_NOT_SCIENTIFIC_TRUTH",
        "ocean_model_weights_changed_by_witness":False,
        "ocean_production_promotion":False,
        "retrocausality_proven":False,
        "scientific_admission":"HOLD",
    }
    record["witness_sha256"]=digest(record)
    return record

def combine(ocean_result,witness):
    require(witness.get("schema")==OCEAN_SCHEMA and
            witness.get("witness_sha256")==digest({
                k:v for k,v in witness.items() if k!="witness_sha256"
            }),"R3_WITNESS_HASH_MISMATCH")
    require(ocean_result.get("schema")=="janus.meta_next.train_result.v1"
            and ocean_result.get("production_promotion") is False,
            "OCEAN_CANDIDATE_NOT_RESEARCH_ONLY")
    require(SHA64.fullmatch(ocean_result.get("candidate_weights_sha256",""))
            is not None,"OCEAN_CHECKPOINT_SHA_BAD")
    model=ocean_result.get("test_model",{})
    base=ocean_result.get("test_baselines",{})
    require(type(model.get("accuracy")) in (float,int) and
            0<=model["accuracy"]<=1,"OCEAN_EVAL_BAD")
    need={"majority_accuracy","markov_accuracy"}
    require(need.issubset(base) and
            all(type(base[k]) in (float,int) and 0<=base[k]<=1 for k in need),
            "OCEAN_BASELINES_MISSING")
    obj={
        "schema":COMBINED_SCHEMA,
        "ocean_meta_training_data":"HISTORICAL_JSON_PATH_CATEGORIES_ONLY",
        "ocean_architecture":ocean_result.get("architecture"),
        "ocean_meta_snapshot_head":ocean_result.get("meta_head"),
        "ocean_candidate_weights_sha256":ocean_result["candidate_weights_sha256"],
        "model_test_accuracy":model["accuracy"],
        "majority_test_accuracy":base["majority_accuracy"],
        "markov_test_accuracy":base["markov_accuracy"],
        "witness_sha256":witness["witness_sha256"],
        "source_meta_head":witness["meta_registry_source_head"],
        "source_metadata_pairs_accepted_as_research_context":witness[
            "paired_reviewed_metadata_records"],
        "model_used_r3_sources_as_training":False,
        "model_improvement_not_established_by_metadata":True,
        "scientific_admission":"HOLD",
        "model_auto_promoted":False,
        "target_outcome":"NEXT_JSON_CATEGORY_NOT_PHYSICS_FACTS",
    }
    obj["comparison_sha256"]=digest(obj)
    return obj

def cli():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="action",required=True)
    a=sub.add_parser("witness")
    a.add_argument("--registry",required=True)
    a.add_argument("--head",required=True)
    a.add_argument("--out",required=True)
    b=sub.add_parser("combine")
    b.add_argument("--witness",required=True)
    b.add_argument("--model-report",required=True)
    b.add_argument("--out",required=True)
    args=p.parse_args()
    if args.action=="witness":
        obj=registry_witness(args.registry,args.head)
    else:
        obj=combine(read(args.model_report),read(args.witness))
    out=Path(args.out)
    require(not out.exists(),"R3_OCEAN_REFUSE_OVERWRITE")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
                   encoding="utf8")
    print(json.dumps({k:v for k,v in obj.items() if k in (
        "status","witness_sha256","comparison_sha256",
        "paired_reviewed_metadata_records","model_test_accuracy",
        "model_auto_promoted","scientific_admission")},sort_keys=True))

if __name__=="__main__":
    cli()
