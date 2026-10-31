#!/usr/bin/env python3
"""Replay *individual* Beetle input packets, triage results and receipts.

Read-only; checks all recorded processed sequences, including historical
failures and bounds. Reproduces deterministic triage using the pinned local
consumer implementation, not an independent external source verification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from beetle_runtime_consumer import (
    CAPABILITIES, PROCESSOR, STATUS, CLAIM_CEILING, REPOSITORY,
    _context, _read, digest, load_context, triage,
)

class LedgerHold(ValueError):
    pass

def git_head(root):
    cp=subprocess.run(["git","rev-parse","--verify","HEAD"],cwd=root,check=True,
                      text=True,capture_output=True,timeout=10)
    commit=cp.stdout.strip()
    if not re.fullmatch("[0-9a-f]{40}",commit):
        raise LedgerHold("GIT_HEAD_INVALID")
    return commit

def replay(root:Path,source_commit:str, max_processed:int=128)->dict:
    if not re.fullmatch("[0-9a-f]{40}",source_commit):
        raise LedgerHold("BEETLE_SOURCE_COMMIT_INVALID")
    if type(max_processed) is not int or not 1<=max_processed<=128:
        raise LedgerHold("BEETLE_BOUND_INVALID")
    state=root/"data"/"beetle-runtime"
    inbox=root/"data"/"beetle-inbox"/"batches"
    context=load_context(state/"CONTEXT.json")
    ack,_=_read(state/"PROCESSING_ACK.json",100_000)
    total=context["last_processed_sequence"]
    if type(total) is not int or not 1<=total<=max_processed \
            or total!=ack.get("last_sequence") or ack.get("schema")!="janus.beetle.processing_ack.v1" \
            or ack.get("status")!=STATUS or ack.get("target_repository")!=REPOSITORY:
        raise LedgerHold("BEETLE_CURSOR_CONTEXT_DISAGREEMENT")
    receipts=state/"receipts";results=state/"results"
    receipt_files=list(receipts.glob("*.json"))
    result_files=list(results.glob("*.json"))
    if len(receipt_files)!=total or len(result_files)!=total:
        raise LedgerHold("BEETLE_LEDGER_CARDINALITY")
    seen_batches=set()
    by_sequence={}
    for receipt_path in receipt_files:
        receipt,receipt_raw=_read(receipt_path,100_000)
        sequence=receipt.get("sequence");bid=receipt.get("batch_id")
        if type(sequence) is not int or not 1<=sequence<=total \
                or not isinstance(bid,str) or not re.fullmatch("[a-f0-9]{20}",bid) \
                or bid!=receipt_path.stem or sequence in by_sequence or bid in seen_batches:
            raise LedgerHold("BEETLE_LEDGER_DUPLICATE_OR_GAP")
        if receipt.get("schema")!="janus.beetle.processing_receipt.v1" \
                or receipt.get("status")!=STATUS or receipt.get("processor_id")!=PROCESSOR \
                or type(receipt.get("authority_delta")) is not int or receipt["authority_delta"]!=0 \
                or not isinstance(receipt.get("processor_sha256"),str) \
                or not re.fullmatch("[0-9a-f]{64}",receipt["processor_sha256"]):
            raise LedgerHold("BEETLE_RECEIPT_AUTHORITY_MISMATCH")
        for field in ("consumer_source_commit","delivery_source_commit"):
            if not isinstance(receipt.get(field),str) or not re.fullmatch("[0-9a-f]{40}",receipt[field]):
                raise LedgerHold("BEETLE_ORIGIN_COMMIT_INVALID")
        for field in ("delivery_manifest_sha256","input_sha256","result_sha256"):
            if not isinstance(receipt.get(field),str) or not re.fullmatch("[0-9a-f]{64}",receipt[field]):
                raise LedgerHold("BEETLE_RECEIPT_HASH_INVALID")
        result_path=results/(bid+".json");packet_path=inbox/(bid+".json")
        result,result_raw=_read(result_path,8_000_000)
        packet,packet_raw=_read(packet_path,4_000_000)
        if digest(result_raw)!=receipt["result_sha256"] or digest(packet_raw)!=receipt["input_sha256"]:
            raise LedgerHold("BEETLE_RESULT_OR_INPUT_BYTES_CHANGED")
        if packet.get("schema")!="janus.beetle.repo_memory_batch.v1" \
                or packet.get("batch_id")!=bid or packet.get("target_repository")!=REPOSITORY \
                or packet.get("claim_ceiling")!=CLAIM_CEILING:
            raise LedgerHold("BEETLE_SOURCE_PACKET_NOT_ALLOWED")
        entry={"batch_id":bid,"sequence":sequence,"sha256":receipt["input_sha256"]}
        expected=triage(packet,entry,receipt["processor_sha256"])
        if result!=expected or result.get("capabilities")!=CAPABILITIES:
            raise LedgerHold("BEETLE_INDIVIDUAL_TRIAGE_REPLAY_MISMATCH")
        if ack.get("processor_sha256")!=receipt["processor_sha256"]:
            raise LedgerHold("BEETLE_PROCESSOR_GENERATION_DRIFT")
        seen_batches.add(bid)
        by_sequence[sequence]=(result,receipt,digest(receipt_raw),digest(packet_raw),digest(result_raw))
    if set(by_sequence)!=set(range(1,total+1)):
        raise LedgerHold("BEETLE_SEQUENCE_NOT_CONTIGUOUS")
    last=by_sequence[total]
    if ack.get("batch_id")!=last[1]["batch_id"] or ack.get("receipt_sha256")!=last[2]:
        raise LedgerHold("BEETLE_FINAL_RECEIPT_ACK_MISMATCH")
    reconstructed=_context([by_sequence[i][0] for i in range(1,total+1)],total)
    if reconstructed!=context:
        raise LedgerHold("BEETLE_CONTEXT_NOT_REPLAYABLE")
    return {
        "schema":"janus.beetle.individual_ledger_replay.v1",
        "status":"ALL_RECORDED_BATCHES_RESULT_AND_RECEIPT_REPLAYED",
        "beetle_source_commit":source_commit,
        "validated_batches":total,
        "validated_input_packets":total,
        "validated_results":total,
        "validated_receipts":total,
        "cursor_receipt_sha256":ack["receipt_sha256"],
        "recomputed_context_sha256":context["context_sha256"],
        "source_truth_independently_established":False,
        "external_links_fetched":False,
        "processor_version_independently_reimplemented":False,
        "full_delivery_manifest_history_recomputed":False,
        "authority_delta":0,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--beetle-state",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    root=args.beetle_state
    result=replay(root,git_head(root))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"batches":result["validated_batches"]}))
if __name__=="__main__":
    main()
