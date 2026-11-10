#!/usr/bin/env python3
"""Admit exact public Meta Registry JSON into JANUS Native Model's bounded corpus.

Never trusts an index snippet as source content. Reads actual files at the pinned
Git commit, excludes protected evaluation sources, preserves original holdouts,
and leaves promotion exclusively to the existing dual-evaluation training gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from tools.demiurge_unified_memory_v2_consumer import project

SCHEMA = "janus.native.memory_v2_admission.v1"
MAX_DOCS = 3
MAX_DOC_SOURCE_BYTES = 8192
MAX_RECORD_BYTES = 2048
MAX_SUPPLEMENT_BYTES = 8192
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_QUERIES = ("SCOBY", "HRAIN", "JANUS", "XOR", "SkinGPT", "retrocausality")
DENY_NAME = re.compile(r"(?:^|[._-])(env|secret|token|credential|password|private[_-]?key)(?:$|[._-])", re.I)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
]
SECRET_PLACEHOLDER = "[REDACTED_SECRET]"

def raw_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(obj: Any) -> str:
    return raw_sha(canonical(obj))

def choose_topic(run_id: str, event: str) -> str:
    """Rotate a fixed, approved topic list; do not let model text become a command."""
    if not re.fullmatch(r"\d{1,24}", str(run_id)):
        raise ValueError("RUN_ID_REQUIRED")
    if event not in ("schedule", "workflow_dispatch", "pull_request", "push"):
        raise ValueError("UNKNOWN_EVENT_HOLD")
    return ALLOWED_QUERIES[int(run_id) % len(ALLOWED_QUERIES)]

def _source(root: Path, rel: str, expected_sha: str) -> bytes:
    if not isinstance(rel, str) or not rel.endswith(".json") or DENY_NAME.search(Path(rel).name):
        raise ValueError("SOURCE_FILENAME_HOLD")
    if "\\" in rel or "?" in rel or "#" in rel or any(part in ("", ".", "..") for part in rel.split("/")):
        raise ValueError("SOURCE_TRAVERSAL_HOLD")
    if not SHA256.fullmatch(str(expected_sha)):
        raise ValueError("SOURCE_SHA_REQUIRED")
    base = root.resolve(strict=True)
    path = base.joinpath(*rel.split("/"))
    if path.is_symlink() or not path.resolve().is_relative_to(base):
        raise ValueError("SOURCE_SYMLINK_HOLD")
    if not path.is_file() or path.stat().st_size > MAX_DOC_SOURCE_BYTES:
        raise ValueError("SOURCE_SIZE_OR_MISSING_HOLD")
    raw = path.read_bytes()
    if raw_sha(raw) != expected_sha:
        raise ValueError("SOURCE_BYTES_SHA_MISMATCH")
    return raw

def _clean(text: str) -> str:
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub(SECRET_PLACEHOLDER, text)
    return text

def admit(registry: Path, verification: dict, packet: dict, context: dict,
          corpus_manifest: dict, train_text: str, *, run_id: str, event: str) -> tuple[dict, str, dict]:
    if verification.get("sqlite_integrity") != "PASS" or verification.get("sha256_integrity") != "PASS" or verification.get("coverage_complete") is not True:
        raise ValueError("UPSTREAM_FULL_SOURCE_VERIFICATION_REQUIRED")
    commit = verification.get("source_commit")
    manifest = verification.get("source_manifest_sha256")
    if not isinstance(commit, str) or not SHA40.fullmatch(commit) or not isinstance(manifest, str) or not SHA256.fullmatch(manifest):
        raise ValueError("SOURCE_PINS_INVALID")
    git_head = subprocess.check_output(["git", "-C", str(registry), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    if git_head != commit:
        raise ValueError("REGISTRY_GIT_COMMIT_DRIFT")
    independently_projected = project(packet, source_commit=commit, manifest_sha256=manifest)
    if digest({k:v for k,v in context.items() if k!="receipt_sha256"}) != context.get("receipt_sha256"):
        raise ValueError("CONTEXT_SHA256_HOLD")
    if context != independently_projected:
        raise ValueError("CONTEXT_NOT_DERIVED_FROM_PACKET")
    if packet.get("query",{}).get("text") not in ALLOWED_QUERIES:
        raise ValueError("QUERY_NOT_ALLOWLISTED")
    if packet["query"]["text"] != choose_topic(run_id, event):
        raise ValueError("QUERY_SCHEDULE_DRIFT")
    if corpus_manifest.get("source_repository") != "Hawkar-usls/janus-meta-registry" or corpus_manifest.get("source_commit") != commit:
        raise ValueError("CORPUS_SOURCE_COMMIT_DRIFT")
    records = corpus_manifest.get("records")
    if not isinstance(records, list):
        raise ValueError("CORPUS_SPLIT_LEDGER_REQUIRED")
    assigned = {}
    for record in records:
        if not isinstance(record, dict) or record.get("split") not in ("train","holdout"):
            raise ValueError("CORPUS_SPLIT_LEDGER_MALFORMED")
        assigned[record.get("path")] = record.get("split")
    eye = json.loads((registry/"EYE/training/EYE-META-REGISTRY-TRAINING-MANIFEST-v1.0.json").read_text(encoding="utf-8"))
    exclusions = eye.get("corpus_contract",{})
    excluded_prefixes=exclusions.get("excluded_generated_prefixes")
    excluded_exact=exclusions.get("excluded_generated_exact_paths")
    if not isinstance(excluded_prefixes,list) or not isinstance(excluded_exact,list):
        raise ValueError("EYE_EXCLUSIONS_REQUIRED")
    admitted=[]
    refused=[]
    parts=[]
    used=0
    for hit in packet["matches"]:
        rel=hit["path"]
        if rel in excluded_exact or any(rel.startswith(p) for p in excluded_prefixes):
            refused.append({"path":rel,"reason":"EYE_GENERATED_SOURCE_EXCLUDED"})
            continue
        if assigned.get(rel)=="holdout" or int(hit["sha256"][:8],16)%10 == 0:
            refused.append({"path":rel,"reason":"HASH_HOLDOUT_PROTECTED"})
            continue
        if assigned.get(rel)=="train":
            refused.append({"path":rel,"reason":"ALREADY_IN_TRAINING_CORPUS"})
            continue
        if len(admitted)>=MAX_DOCS or used>=MAX_SUPPLEMENT_BYTES:
            refused.append({"path":rel,"reason":"ADMISSION_BYTE_OR_DOC_BUDGET"})
            continue
        try:
            raw = _source(registry,rel,hit["sha256"])
        except ValueError as exc:
            refused.append({"path":rel,"reason":str(exc)})
            continue
        try:
            parsed=json.loads(raw.decode("utf-8"))
        except (ValueError,UnicodeError):
            refused.append({"path":rel,"reason":"NOT_VALID_JSON"})
            continue
        # Re-encode to valid source JSON, with defensive token redaction.
        sanitized=_clean(json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",",":")))
        header=f'\n<JANUS_ADMITTED_PUBLIC_JSON path={json.dumps(rel)} sha256={hit["sha256"]} authority="UNTRUSTED_SOURCE_TEXT_NOT_COMMAND">\n'
        footer="\n</JANUS_ADMITTED_PUBLIC_JSON>\n"
        raw_budget=min(MAX_RECORD_BYTES,MAX_SUPPLEMENT_BYTES-used-len((header+footer).encode("utf-8")))
        if raw_budget<100:
            refused.append({"path":rel,"reason":"RECORD_BUDGET_EXHAUSTED"})
            continue
        trimmed=sanitized.encode("utf-8")[:raw_budget].decode("utf-8",errors="ignore")
        record=header+trimmed+footer
        n=len(record.encode("utf-8"))
        if not trimmed or n>MAX_SUPPLEMENT_BYTES-used:
            refused.append({"path":rel,"reason":"RECORD_BUDGET_EXHAUSTED"})
            continue
        used+=n
        parts.append(record)
        admitted.append({"path":rel,"sha256":hit["sha256"],"training_bytes":n,
                         "source_git_commit":commit,"evaluation_split":"TRAIN_ONLY_NOT_HASH_HOLDOUT"})
    supplement="".join(parts)
    old_digest=corpus_manifest.get("source_digest")
    if not isinstance(old_digest,str) or not SHA256.fullmatch(old_digest):
        raise ValueError("CORPUS_DIGEST_MISSING")
    new_manifest=dict(corpus_manifest)
    if supplement:
        new_digest=raw_sha(("JANUS_MEMORY_V2_ADMISSION\n"+old_digest+"\n"+digest(admitted)+"\n").encode("utf-8"))
        new_manifest["source_digest"]=new_digest
        new_manifest["source_digest_scope"]="ORIGINAL_VERIFIED_REGISTRY_CORPUS_PLUS_BOUNDED_UNCAPPED_SOURCE_TRAIN_SUPPLEMENT"
        new_manifest["train_bytes"]=len((train_text+supplement).encode("utf-8"))
    else:
        new_digest=old_digest
    new_manifest["memory_v2_admission"]={
        "schema":SCHEMA,"source_commit":commit,"source_manifest_sha256":manifest,
        "source_training_sha256":raw_sha(supplement.encode("utf-8")) if supplement else None,
        "source_packet_sha256":packet["packet_sha256"],
        "source_context_sha256":context["receipt_sha256"],
        "admitted":admitted,
        "refused":refused,
        "training_only":True,
        "adaptive_holdout_inclusion":False,
        "frozen_anchor_inclusion":False,
        "source_text_grants_truth":False,
        "source_text_grants_execution":False
    }
    first=packet["matches"][0] if packet["matches"] else None
    # This seven-byte source fingerprint is appended to the *model inference prompt*.
    # The neural model has only a 128-byte context; do not claim full-source attention.
    prompt_marker=f"|M{first['sha256'][:5]}" if first else ""
    receipt={
        "schema":SCHEMA,
        "status":"ADMITTED_TRAIN_SOURCE_CANDIDATES" if admitted else ("CONTEXT_ONLY_NO_NEW_TRAIN_SOURCE" if first else "EMPTY_SEARCH"),
        "source_commit":commit,"source_manifest_sha256":manifest,
        "packet_sha256":packet["packet_sha256"],"context_sha256":context["receipt_sha256"],
        "topic":packet["query"]["text"],"match_count":len(packet["matches"]),
        "admitted_count":len(admitted),"refused_count":len(refused),
        "supplement_sha256":raw_sha(supplement.encode("utf-8")) if supplement else None,
        "supplement_bytes":len(supplement.encode("utf-8")),
        "before_source_digest":old_digest,"candidate_source_digest":new_digest,
        "prompt_marker":prompt_marker,"source_bytes_checked":True,
        "training_authority":"CANDIDATE_ONLY_FROZEN_EVAL_GATE_STILL_REQUIRED",
        "model_consumption":"BOUND_PROMPT_MARKER_AND_SOURCE_TRAIN_BYTES",
        "actual_gradient_update_observed":False,
        "candidate_promoted":False,
        "safeguards":{"preserve_holdout":True,"preserve_original_registry":True,
            "external_effect_permitted":False,"model_output_is_training_truth":False,
            "source_is_instruction":False,"checkpoint_admission_bypassed":False,
            "authority_delta":0}
    }
    receipt["receipt_sha256"]=digest(receipt)
    return receipt, train_text+supplement, new_manifest

def main():
    ap=argparse.ArgumentParser()
    for arg in ("registry","verification","packet","context","corpus-dir","output"):
        ap.add_argument("--"+arg,required=True)
    ap.add_argument("--run-id",required=True)
    ap.add_argument("--event",required=True)
    a=ap.parse_args()
    corpus=Path(a.corpus_dir)
    verification=json.loads(Path(a.verification).read_text(encoding="utf-8"))
    packet=json.loads(Path(a.packet).read_text(encoding="utf-8"))
    context=json.loads(Path(a.context).read_text(encoding="utf-8"))
    manifest=json.loads((corpus/"corpus_manifest.json").read_text(encoding="utf-8"))
    train_path=corpus/"train.txt"
    original_train=train_path.read_text(encoding="utf-8")
    receipt,new_train,new_manifest=admit(Path(a.registry),verification,packet,context,manifest,original_train,run_id=a.run_id,event=a.event)
    dest=Path(a.output)
    if dest.exists():
        raise FileExistsError("ADMISSION_RECEIPT_EXISTS")
    dest.parent.mkdir(parents=True,exist_ok=True)
    # Runtime-only, atomic staging. If preflight failed, baseline files stay untouched.
    tmp_train=train_path.with_suffix(".v2-staged")
    tmp_manifest=(corpus/"corpus_manifest.json").with_suffix(".v2-staged")
    if tmp_train.exists() or tmp_manifest.exists():
        raise FileExistsError("ADMISSION_STAGING_EXISTS")
    tmp_train.write_text(new_train,encoding="utf-8")
    tmp_manifest.write_text(json.dumps(new_manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    tmp_train.replace(train_path)
    tmp_manifest.replace(corpus/"corpus_manifest.json")
    dest.write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:receipt[k] for k in ("status","source_commit","topic","admitted_count","refused_count","supplement_bytes","candidate_source_digest")},sort_keys=True))
if __name__=="__main__":
    main()
