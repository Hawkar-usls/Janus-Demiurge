#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA="janus.pnp.corpus_training_memory.v1"
UA="JANUS-Demiurge-PNP-CorpusMemory/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)"
BASE="https://raw.githubusercontent.com/Hawkar-usls/TOPA/janus/pnp-autoresearch-state/data/pnp-autoresearch"
URLS={
  "corpus":BASE+"/CORPUS.json",
  "ledger":BASE+"/CORPUS_WEIGHT_LEDGER.json",
  "drive_receipt":BASE+"/DRIVE_INDEX_RECEIPT.json",
}

def canonical(obj:Any)->bytes:
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")

def sh(obj:Any)->str:
    return hashlib.sha256(canonical(obj)).hexdigest()

def sha_bytes(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def fetch_json(url:str,optional:bool=False)->dict:
    try:
        req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=35) as r:
            return json.load(r)
    except Exception as exc:
        if optional:
            return {"status":"UNAVAILABLE","error":f"{type(exc).__name__}:{exc}"}
        raise

def validate(corpus:dict,ledger:dict)->None:
    if corpus.get("schema")!="janus.topa.pnp_corpus.v1":
        raise RuntimeError("PNP_CORPUS_SCHEMA_REJECTED")
    if corpus.get("P_VS_NP")!="OPEN":
        raise RuntimeError("PNP_CORPUS_P_VS_NP_MUST_REMAIN_OPEN")
    if corpus.get("successor_algorithm")!="LOCKED":
        raise RuntimeError("PNP_CORPUS_SUCCESSOR_LOCK_REQUIRED")
    auth=corpus.get("authority") or {}
    if auth.get("truth") is not False or auth.get("proof") is not False or auth.get("scientific_claim_promotion") is not False:
        raise RuntimeError("PNP_CORPUS_AUTHORITY_REJECTED")
    if ledger.get("schema")!="janus.topa.pnp_corpus_weight_ledger.v1":
        raise RuntimeError("PNP_WEIGHT_LEDGER_SCHEMA_REJECTED")
    la=ledger.get("authority") or {}
    if la.get("weights_are_truth") is not False or la.get("weights_are_evidence") is not False:
        raise RuntimeError("PNP_WEIGHT_LEDGER_AUTHORITY_REJECTED")
    if la.get("source_documents_immutable") is not True:
        raise RuntimeError("PNP_WEIGHT_LEDGER_SOURCE_IMMUTABILITY_REQUIRED")

def render_record(row:dict)->str:
    routing=row.get("routing") or {}
    fields={
      "record_id":row.get("record_id"),
      "publication_key":row.get("publication_key"),
      "title":row.get("title"),
      "status":row.get("status"),
      "provider":row.get("provider"),
      "corpus_kind":row.get("corpus_kind"),
      "source_url":row.get("source_url"),
      "why_relevant":row.get("why_relevant"),
      "blocker":row.get("blocker"),
      "attention_priority":routing.get("attention_priority"),
      "source_quality_hint":routing.get("source_quality_hint"),
      "frontier_relevance_weight":routing.get("frontier_relevance_weight"),
      "novelty_weight":routing.get("novelty_weight"),
      "authority":"CORPUS_ROUTING_MEMORY_REQUIRES_PRIMARY_SOURCE_VERIFICATION",
    }
    text=str(row.get("text") or "")[:3500]
    return (
      "\n<JANUS_PNP_CORPUS_RECORD "
      + " ".join(f'{k}={json.dumps(v,ensure_ascii=False)}' for k,v in fields.items())
      + ">\n"+text+"\n</JANUS_PNP_CORPUS_RECORD>\n"
    )

def build(corpus:dict,ledger:dict,drive_receipt:dict,max_bytes:int)->tuple[str,dict]:
    validate(corpus,ledger)
    rows=list(corpus.get("records") or [])
    rows.sort(key=lambda r:(-float((r.get("routing") or {}).get("attention_priority") or 0),str(r.get("record_id") or "")))
    chunks=[];used=0;selected=[]
    for row in rows:
        chunk=render_record(row).encode("utf-8")
        if used+len(chunk)>max_bytes:
            continue
        chunks.append(chunk.decode("utf-8"))
        used+=len(chunk)
        selected.append({
          "record_id":row.get("record_id"),
          "publication_key":row.get("publication_key"),
          "attention_priority":(row.get("routing") or {}).get("attention_priority"),
          "source_url":row.get("source_url"),
        })
    text="".join(chunks)
    raw=text.encode("utf-8")
    manifest={
      "schema":SCHEMA,
      "status":"READY_READ_ONLY_TRAINING_MEMORY",
      "P_VS_NP":"OPEN",
      "source_repository":"Hawkar-usls/TOPA",
      "source_branch":"janus/pnp-autoresearch-state",
      "source_corpus_semantic_sha256":corpus.get("semantic_sha256"),
      "source_ledger_semantic_sha256":ledger.get("semantic_sha256"),
      "drive_index_status":drive_receipt.get("status"),
      "training_pack_sha256":sha_bytes(raw),
      "training_bytes":len(raw),
      "included_record_count":len(selected),
      "available_record_count":len(rows),
      "selected_records":selected,
      "training_only":True,
      "adaptive_holdout_inclusion":False,
      "frozen_anchor_inclusion":False,
      "training_material_is_truth":False,
      "contribution_grants_authority":False,
      "source_execution":False,
      "cross_repository_write":False,
      "authority":{
        "read_only_source":True,
        "authority_delta":0,
        "may_mutate_source_repository":False,
        "may_change_active_lineage":False,
        "may_change_proof_ladder":False,
        "may_promote_theorem":False,
        "may_promote_runtime":False,
      },
      "laws":[
        "TOPA_CORPUS != WORLD_TRUTH",
        "ATTENTION_WEIGHT != SCIENTIFIC_EVIDENCE",
        "TRAINING_MEMORY != PROOF",
        "P_VS_NP = OPEN",
      ],
    }
    manifest["manifest_sha256"]=sh(manifest)
    return text,manifest

def self_test()->dict:
    corpus={
      "schema":"janus.topa.pnp_corpus.v1","P_VS_NP":"OPEN","successor_algorithm":"LOCKED",
      "semantic_sha256":"c","authority":{"truth":False,"proof":False,"scientific_claim_promotion":False},
      "records":[{"record_id":"r1","publication_key":"k","title":"T","source_url":"u","text":"x","routing":{"attention_priority":0.8}}]
    }
    ledger={
      "schema":"janus.topa.pnp_corpus_weight_ledger.v1","semantic_sha256":"w",
      "authority":{"weights_are_truth":False,"weights_are_evidence":False,"source_documents_immutable":True}
    }
    text,m=build(corpus,ledger,{"status":"TEST"},10000)
    assert "JANUS_PNP_CORPUS_RECORD" in text
    assert m["training_material_is_truth"] is False
    assert m["authority"]["authority_delta"]==0
    return {"schema":"janus.pnp.corpus_training_memory.self_test.v1","status":"PASS","authority_delta":0}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--out-text")
    ap.add_argument("--out-manifest")
    ap.add_argument("--max-bytes",type=int,default=300000)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:
        print(json.dumps(self_test(),indent=2,sort_keys=True));return 0
    if not a.out_text or not a.out_manifest:
        raise SystemExit("OUT_TEXT_AND_MANIFEST_REQUIRED")
    corpus=fetch_json(URLS["corpus"])
    ledger=fetch_json(URLS["ledger"])
    drive=fetch_json(URLS["drive_receipt"],optional=True)
    text,manifest=build(corpus,ledger,drive,a.max_bytes)
    tp=Path(a.out_text);mp=Path(a.out_manifest)
    tp.parent.mkdir(parents=True,exist_ok=True);mp.parent.mkdir(parents=True,exist_ok=True)
    tp.write_text(text,encoding="utf-8")
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
      "status":manifest["status"],
      "included_record_count":manifest["included_record_count"],
      "training_bytes":manifest["training_bytes"],
      "training_pack_sha256":manifest["training_pack_sha256"],
      "drive_index_status":manifest["drive_index_status"],
    },indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
