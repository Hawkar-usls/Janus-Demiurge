#!/usr/bin/env python3
"""Independent read-only Demiurge ACK for a *dynamic* Genesis parent run.

The source Git commit is checked out as data. No scripts, commands, or model
instructions from it are executed. The actual native model remains pinned to
a trusted Demiurge commit, and raw inference is verified by a second runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA="janus.nexus.dynamic_external_organ_ack.v1"
RUN_RE=re.compile(r"[1-9][0-9]{3,23}\Z")
SHA_RE=re.compile(r"[0-9a-f]{40}\Z")
HEX64=re.compile(r"[0-9a-f]{64}\Z")
MODEL_COMMIT="c8c890206f53591d6bfe444d103ed5dd07ec2296"
MODEL_CHECKPOINT_SHA256="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
GENESIS="Hawkar-usls/Janus_Genesis"
DEMIURGE="Hawkar-usls/Janus-Demiurge"
PREFIX="JANUS EXTERNAL ORGAN CAUSAL R1 (READONLY) "
MAX_PROMPT=160

class DynamicAckHold(ValueError):
    pass

def require(ok: bool, why: str)->None:
    if not ok:
        raise DynamicAckHold(why)

def hash_raw(raw: bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def digest(row: dict)->str:
    return hash_raw(json.dumps(row,sort_keys=True,
                 separators=(",",":"),ensure_ascii=False,
                 allow_nan=False).encode("utf-8"))

def identities(source_run: str, attempt: int, source_sha: str,
               b_head: str, receiver_run: str, receiver_sha: str)->None:
    require(isinstance(source_run,str) and RUN_RE.fullmatch(source_run)!=None
            and isinstance(receiver_run,str) and RUN_RE.fullmatch(receiver_run)!=None,
            "RUN_ID_INVALID")
    require(type(attempt)==int and 1<=attempt<=1000,"ATTEMPT_INVALID")
    for sha in (source_sha,b_head,receiver_sha):
        require(isinstance(sha,str) and SHA_RE.fullmatch(sha)!=None,
                "SOURCE_OR_RECEIVER_SHA_INVALID")

def read(path: Path)->dict:
    require(path.is_file() and not path.is_symlink() and
            not any(p.is_symlink() for p in path.parents) and
            0<path.stat().st_size<=64_000,"MISSING_OR_UNSAFE_SOURCE")
    row=json.loads(path.read_text("utf-8"))
    require(isinstance(row,dict),"RECEIPT_NOT_OBJECT")
    return row

def validate_source(root: Path, run: str, attempt: int,
                    source_sha: str)->tuple[dict,dict,dict,dict,dict]:
    base=root/"data/nexus_integrated_native_lab/runs"/(run+"-"+str(attempt))
    chk=read(base/"checkpoint.json")
    variants=read(base/"variants.json")
    b=read(base/"worker-b.json")
    receiver=read(base/"receiver.json")
    a=read(base/"worker-a.json")
    require(chk.get("schema")=="janus.nexus.integrated_native_git_lab.v1.checkpoint"
            and chk.get("run_id")==run and chk.get("attempt")==attempt
            and chk.get("code_sha")==source_sha and
            chk.get("model_commit")==MODEL_COMMIT and
            chk.get("checkpoint_model_sha256")==MODEL_CHECKPOINT_SHA256 and
            chk.get("authority_delta")==0 and
            chk.get("source_writeback") is False,
            "GENESIS_CHECKPOINT_NOT_PINNED")
    require(variants.get("schema")=="janus.nexus.integrated_native_git_lab.v1.variants"
            and variants.get("model_generated_count")>=2
            and variants.get("selected_variant_id")==chk.get("selected_variant_id")
            and chk.get("variant_digest")==digest(variants)
            and a.get("variant_digest")==digest(variants)
            and a.get("checkpoint_digest")==digest(chk),
            "VARIANT_PROVENANCE_DRIFT")
    require(b.get("run_id")==run and b.get("attempt")==attempt
            and b.get("status")=="LAB_CONSUMED_COMPLETED_ONCE"
            and b.get("variants_digest")==digest(variants)
            and b.get("checkpoint_digest")==digest(chk)
            and b.get("receiver_digest")==digest(receiver)
            and b.get("authority_delta")==0 and
            b.get("source_writeback") is False,
            "GENESIS_WORKER_B_RECEIPT_DRIFT")
    proposals=variants.get("candidates")
    require(isinstance(proposals,list) and len(proposals)>=2 and
            len(variants.get("rejected_variant_ids_retained",[]))>=1,
            "GENESIS_VARIANTS_INCOMPLETE")
    selected=next((x for x in proposals
        if x.get("variant_id")==variants["selected_variant_id"]),None)
    require(isinstance(selected,dict)
            and selected.get("source")=="PINNED_REAL_NATIVE_MODEL_CALL"
            and isinstance(selected.get("proposal"),dict),
            "NOT_A_NATIVE_MODEL_PROPOSAL")
    proposal=selected["proposal"]
    text=proposal.get("text")
    require(isinstance(text,str) and 0<len(text.encode("utf-8"))<=512
            and proposal.get("model_generated") is True
            and hash_raw(text.encode("utf-8"))==proposal.get("proposal_sha256")
            and receiver.get("consumed_proposal_sha256")==proposal["proposal_sha256"],
            "SELECTED_MODEL_TEXT_NOT_VERIFIED")
    return chk,variants,b,receiver,proposal

def bound_prompt(run: str, proposal:dict)->str:
    pre=PREFIX+run+" :: "
    budget=MAX_PROMPT-len(pre.encode("utf-8"))
    require(budget>=8,"NO_PROMPT_BUDGET")
    text=proposal["text"].encode("utf-8")[:budget].decode("utf-8","ignore")
    require(bool(text.strip()),"SELECTED_TEXT_EMPTY")
    result=pre+text
    require(len(result.encode("utf-8"))<=MAX_PROMPT,"PROMPT_BOUNDS")
    return result

def verify_model(path:Path)->None:
    require(path.is_file() and not path.is_symlink()
            and 0<path.stat().st_size<=120_000_000,
            "MODEL_CHECKPOINT_MISSING")
    require(hash_raw(path.read_bytes())==MODEL_CHECKPOINT_SHA256,
            "MODEL_CHECKPOINT_SHA_DRIFT")

def make_receipt(root: Path, checkpoint: Path, output:bytes,
                 source_run:str, attempt:int, source_sha:str,
                 b_head:str, receiver_run:str, receiver_sha:str)->dict:
    identities(source_run,attempt,source_sha,b_head,receiver_run,receiver_sha)
    chk,variants,b,receiver,proposal=validate_source(
        root,source_run,attempt,source_sha)
    verify_model(checkpoint)
    require(0<len(output)<=12_000,"MODEL_STDOUT_BOUNDS")
    try:
        body=output.decode("utf-8")
    except UnicodeError as exc:
        raise DynamicAckHold("MODEL_OUTPUT_NOT_UTF8") from exc
    prompt=bound_prompt(source_run,proposal)
    require(body.startswith(prompt),"MODEL_NOT_CONSUMING_EXACT_GENESIS_TEXT")
    suffix=body[len(prompt):].strip()
    require(bool(suffix),"MODEL_GENERATION_EMPTY")
    require(isinstance(b["completion_id"],str) and
            HEX64.fullmatch(b["completion_id"]) is not None,
            "COMPLETION_DIGEST_INVALID")
    return {
      "schema":SCHEMA,
      "status":"PASS_REAL_EXTERNAL_DEMIURGE_NATIVE_CONSUMPTION_SCOPED",
      "sender_repository":GENESIS,
      "receiver_repository":DEMIURGE,
      "sender_source_run_id":source_run,
      "sender_source_attempt":attempt,
      "sender_code_sha":source_sha,
      "sender_b_git_head":b_head,
      "sender_checkpoint_digest":digest(chk),
      "sender_variants_digest":digest(variants),
      "sender_worker_b_digest":digest(b),
      "sender_completion_id":b["completion_id"],
      "selected_proposal_sha256":proposal["proposal_sha256"],
      "external_receiver_run_id":receiver_run,
      "external_receiver_source_sha":receiver_sha,
      "receiver_model_commit":MODEL_COMMIT,
      "receiver_model_checkpoint_sha256":MODEL_CHECKPOINT_SHA256,
      "received":"RECEIVED","parsed":"PARSED","loaded":"LOADED",
      "executed":"EXECUTED_ACTUAL_PINNED_DEMIURGE_MODEL_INFERENCE",
      "model_input_sha256":hash_raw(prompt.encode("utf-8")),
      "raw_model_stdout_sha256":hash_raw(output),
      "native_generated_suffix_sha256":hash_raw(suffix.encode("utf-8")),
      "real_external_organ_readonly_consumption_proven":True,
      "external_organ_is_separate_git_repository_and_runner":True,
      "production_integration_consumption_proven":False,
      "untrusted_genesis_text_executed_as_command":False,
      "source_writeback":False,"authority_delta":0,
      "full_issue_162_acceptance":False,
    }

def save(path:Path, row:dict)->None:
    require(not path.exists() and not path.is_symlink()
            and not any(p.is_symlink() for p in path.parents),
            "DURABLE_ACK_OVERWRITE_DENIED")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(row,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("phase",choices=["prompt","receipt","verify"])
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--model-checkpoint",type=Path)
    ap.add_argument("--raw-output",type=Path)
    ap.add_argument("--ack",type=Path)
    ap.add_argument("--out",type=Path)
    ap.add_argument("--source-run",required=True)
    ap.add_argument("--attempt",type=int,default=1)
    ap.add_argument("--source-sha",required=True)
    ap.add_argument("--b-head",required=True)
    ap.add_argument("--receiver-run",required=True)
    ap.add_argument("--receiver-sha",required=True)
    args=ap.parse_args()
    try:
        identities(args.source_run,args.attempt,args.source_sha,
                   args.b_head,args.receiver_run,args.receiver_sha)
        if args.phase=="prompt":
            _,_,_,_,proposal=validate_source(args.source_root,
                           args.source_run,args.attempt,args.source_sha)
            require(args.out is not None,"PROMPT_OUTPUT_REQUIRED")
            require(not args.out.exists(),"PROMPT_OVERWRITE_DENIED")
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(bound_prompt(args.source_run,proposal),
                                encoding="utf-8")
            print("JANUS_DYNAMIC_DEMIURGE_PROMPT=PINNED")
        else:
            require(args.model_checkpoint is not None and
                    args.raw_output is not None and
                    args.raw_output.is_file() and not args.raw_output.is_symlink()
                    and args.raw_output.stat().st_size<=12_000,
                    "MODEL_RAW_BYTES_REQUIRED")
            raw=args.raw_output.read_bytes()
            receipt=make_receipt(args.source_root,args.model_checkpoint,raw,
                        args.source_run,args.attempt,args.source_sha,
                        args.b_head,args.receiver_run,args.receiver_sha)
            if args.phase=="receipt":
                require(args.out is not None,"OUTPUT_REQUIRED")
                save(args.out,receipt)
                print("JANUS_DYNAMIC_DEMIURGE_ACK="+receipt["status"])
            else:
                require(args.ack is not None and read(args.ack)==receipt,
                        "INDEPENDENT_RAW_RESPONSE_ACK_REPLAY_MISMATCH")
                print("JANUS_DYNAMIC_DEMIURGE_ACK=INDEPENDENT_RAW_REPLAY_PASS")
        return 0
    except (DynamicAckHold,KeyError,ValueError,OSError,TypeError,
            UnicodeError) as exc:
        why=str(exc) if isinstance(exc,DynamicAckHold) else "INPUT_OR_IO"
        print("JANUS_DYNAMIC_DEMIURGE_ACK=HOLD:"+why,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
