#!/usr/bin/env python3
"""Demiurge's bounded read-only consumer of DemiHead Unified Memory v2 search receipts.

This is an evidence candidate / graph-context projection only; never a live
control-plane action, memory write, provenance promotion or autonomous dispatcher.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

INPUT_SCHEMA="janus.demihead.unified_memory_search.v1"
OUTPUT_SCHEMA="janus.demiurge.unified_memory_context.v1"
REPO="Hawkar-usls/janus-meta-registry"
SHA40=re.compile(r"^[0-9a-f]{40}$")
SHA256=re.compile(r"^[0-9a-f]{64}$")
MAX_PACKET_BYTES=160_000
MAX_MATCHES=20
MAX_RELATED=8

def canonical(value:Any)->bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")

def digest(value:Any)->str:
    return hashlib.sha256(canonical(value)).hexdigest()

def _safe_link(commit: str,path: str,url: str,sha: str)->None:
    if not isinstance(path,str) or not path.endswith(".json") or not path or "\\" in path or any(p in ("",".","..") for p in path.split("/")) or any(ord(c)<32 for c in path) or "?" in path or "#" in path:
        raise ValueError("UNSAFE_DOCUMENT_PATH_HOLD")
    expected="https://github.com/"+REPO+"/blob/"+commit+"/"+path
    if url!=expected or not isinstance(sha,str) or not SHA256.fullmatch(sha):
        raise ValueError("DOCUMENT_SOURCE_PROVENANCE_HOLD")

def validate(packet:dict, *, source_commit: str, manifest_sha256: str)->None:
    if not SHA40.fullmatch(source_commit) or not SHA256.fullmatch(manifest_sha256):
        raise ValueError("TRUSTED_SOURCE_PINS_REQUIRED")
    if not isinstance(packet,dict) or packet.get("schema")!=INPUT_SCHEMA:
        raise ValueError("DEMIHEAD_SCHEMA_HOLD")
    alleged=packet.get("packet_sha256")
    if not isinstance(alleged,str) or not SHA256.fullmatch(alleged):
        raise ValueError("PACKET_SHA256_MISSING")
    unhashed={k:v for k,v in packet.items() if k!="packet_sha256"}
    if digest(unhashed)!=alleged:
        raise ValueError("PACKET_INTEGRITY_HOLD")
    source=packet.get("origin")
    if not isinstance(source,dict) or source.get("repository")!=REPO or source.get("source_commit")!=source_commit or source.get("source_manifest_sha256")!=manifest_sha256:
        raise ValueError("SOURCE_PIN_MISMATCH")
    if not SHA256.fullmatch(str(source.get("index_sha256",""))):
        raise ValueError("INDEX_DIGEST_MISSING")
    n=source.get("indexed_json"); rel=source.get("explicit_relations")
    if type(n) is not int or n < 1 or type(rel) is not int or rel<0:
        raise ValueError("INDEX_COUNTS_HOLD")
    control=packet.get("control",{})
    exact={"read_only":True,"external_effect_permitted":False,
           "direct_graph_mutation_permitted":False,"github_write_permitted":False,
           "authority_delta":0,"mass_effect_budget_delta":0}
    if not isinstance(control,dict) or any(type(control.get(k)) is not type(v) or control.get(k)!=v for k,v in exact.items()):
        raise ValueError("AUTHORITY_DELTA_HOLD")
    ceiling=packet.get("claim_ceiling",{})
    required=("catalog_presence_is_truth","reference_is_independent_evidence","memory_proposal_is_admission","receipts_are_authentication")
    if not isinstance(ceiling,dict) or any(ceiling.get(k) is not False for k in required):
        raise ValueError("CLAIM_PROMOTION_HOLD")
    query=packet.get("query",{})
    matches=packet.get("matches")
    if not isinstance(query,dict) or not isinstance(query.get("text"),str) or not isinstance(query.get("fts_literal"),str) or type(query.get("limit")) is not int or query["limit"] not in range(1,21):
        raise ValueError("QUERY_CONTRACT_HOLD")
    if not isinstance(matches,list) or len(matches)>min(query["limit"],MAX_MATCHES):
        raise ValueError("MATCH_BUDGET_HOLD")
    seen=set()
    for item in matches:
        if not isinstance(item,dict) or type(item.get("id")) is not int or item["id"]<1 or item["id"]>n or item["id"] in seen:
            raise ValueError("DOCUMENT_ID_HOLD")
        seen.add(item["id"])
        _safe_link(source_commit,item.get("path"),item.get("url"),item.get("sha256"))
        if not isinstance(item.get("title"),str) or not isinstance(item.get("excerpt"),str) or len(item["excerpt"])>500 or item.get("parse_status") not in ("OK","MALFORMED"):
            raise ValueError("DOCUMENT_METADATA_HOLD")
        links=item.get("related")
        if not isinstance(links,list) or len(links)>MAX_RELATED:
            raise ValueError("RELATED_BUDGET_HOLD")
        for link in links:
            if not isinstance(link,dict) or type(link.get("id")) is not int or link["id"]<1 or link["id"]>n or link.get("kind") not in ("EXPLICIT_PATH","EXPLICIT_URL"):
                raise ValueError("EDGE_KIND_HOLD")
            _safe_link(source_commit,link.get("path"),link.get("url"),link.get("sha256"))

def project(packet:dict, *, source_commit:str, manifest_sha256:str)->dict:
    validate(packet,source_commit=source_commit,manifest_sha256=manifest_sha256)
    nodes={}
    edges={}
    for hit in packet["matches"]:
        path=hit["path"]
        nodes[path]={"id":path,"label":hit["title"],"path":path,"sha256":hit["sha256"],
                     "source_url":hit["url"],"observation_tier":"CATALOG_ENTRY_NOT_CLAIM_PROOF"}
        for link in hit["related"]:
            target=link["path"]
            nodes.setdefault(target,{"id":target,"label":target,"path":target,"sha256":link["sha256"],
                                     "source_url":link["url"],"observation_tier":"EXPLICIT_REFERENCE_NOT_INDEPENDENT_SOURCE"})
            key=(path,target,link["kind"])
            edges[key]={"source":path,"target":target,"relation":link["kind"],"weight":1.0}
    body={
        "schema":OUTPUT_SCHEMA,"status":"CONTEXT_CANDIDATE_READ_ONLY",
        "input_receipt_sha256":packet["packet_sha256"],
        "source_commit":source_commit,"source_manifest_sha256":manifest_sha256,
        "query":packet["query"]["text"],
        "matches":len(packet["matches"]),
        "graph":{"nodes":[nodes[k] for k in sorted(nodes)],
                 "edges":[edges[k] for k in sorted(edges)]},
        "routing":{"recipient":"JANUS_DEMIURGE_READONLY_CONTEXT_REVIEW",
                   "scout_context_candidate":True,
                   "self_training_authorized":False,
                   "graph_mutation_authorized":False,"module_admission_authorized":False,
                   "network_dispatch_authorized":False,"mass_effect_budget_delta":0,
                   "authority_delta":0},
        "claim_ceiling":{"source_content_verified_independently":False,
                         "scientific_truth_established":False,"independent_source_roots_counted":False,
                         "synthesis_evidence_promoted":False}
    }
    body["receipt_sha256"]=digest(body)
    return body

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--expect-source-commit",required=True)
    p.add_argument("--expect-manifest-sha256",required=True)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.packet.is_symlink() or not a.packet.is_file() or a.packet.stat().st_size>MAX_PACKET_BYTES:
        raise ValueError("PACKET_FILE_HOLD")
    value=json.loads(a.packet.read_text(encoding="utf-8"))
    result=project(value,source_commit=a.expect_source_commit,manifest_sha256=a.expect_manifest_sha256)
    body=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if a.output:
        with a.output.open("x",encoding="utf-8") as fh:
            fh.write(body)
    else:print(body,end="")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
