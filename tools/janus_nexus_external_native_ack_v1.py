#!/usr/bin/env python3
"""Independent JANUS Demiurge organ consumes a pinned Genesis lab model output.

Read-only external-organ R0 research evidence. Does not write any Genesis
source/state, does not execute generated instructions, and does not advance
scientific or production authority. The receiver's own Git repository records
one durable, source-bound real-model-consumption ACK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA="janus.nexus.external_demiurge_consumption_ack.v1"
GENESIS="Hawkar-usls/Janus_Genesis"
RECEIVER="Hawkar-usls/Janus-Demiurge"
SOURCE_RUN="43275243138"
SOURCE_ATTEMPT=1
SOURCE_CODE_SHA="664f706fad7cbb02cefe82a5c141876117985ce2"
SOURCE_STATE_SHA="a29e90d4910ebde68ca4e73cc30701af0e484837"
SOURCE_VARIANT_GIT_BLOB="85715c27257f546977f282cfd24736845cbd3ce0"
MODEL_COMMIT="c8c890206f53591d6bfe444d103ed5dd07ec2296"
MODEL_CHECKPOINT_SHA256="fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
SOURCE_ROOT=Path("data/nexus_integrated_native_lab/runs/43275243138-1")
PROMPT_PREFIX="JANUS EXTERNAL ORGAN R0 READONLY: "
PROMPT_MAX=112
SHA40=re.compile(r"[0-9a-f]{40}\Z")
SHA64=re.compile(r"[0-9a-f]{64}\Z")
RUN_ID=re.compile(r"[1-9][0-9]{3,23}\Z")


class ExternalHold(ValueError):
    pass


def require(value: bool, code: str) -> None:
    if not value:
        raise ExternalHold(code)


def canonical(value: dict) -> bytes:
    return json.dumps(value,sort_keys=True,separators=(",",":"),
                      ensure_ascii=False,allow_nan=False).encode("utf-8")


def raw_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(value: dict) -> str:
    return raw_sha(canonical(value))


def read(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(),"SOURCE_FILE_MISSING")
    require(0<path.stat().st_size<=60_000,"SOURCE_FILE_BOUNDS")
    value=json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value,dict),"SOURCE_NOT_OBJECT")
    return value


def source(root: Path) -> tuple[dict,dict,dict]:
    variants=read(root/SOURCE_ROOT/"variants.json")
    checkpoint=read(root/SOURCE_ROOT/"checkpoint.json")
    require(checkpoint.get("schema")==
            "janus.nexus.integrated_native_git_lab.v1.checkpoint",
            "GENESIS_CHECKPOINT_SCHEMA")
    require(checkpoint.get("run_id")==SOURCE_RUN and
            checkpoint.get("attempt")==SOURCE_ATTEMPT and
            checkpoint.get("code_sha")==SOURCE_CODE_SHA and
            checkpoint.get("model_commit")==MODEL_COMMIT and
            checkpoint.get("checkpoint_model_sha256")==MODEL_CHECKPOINT_SHA256 and
            checkpoint.get("full_issue_162_acceptance") is False and
            checkpoint.get("source_writeback") is False and
            checkpoint.get("authority_delta")==0,
            "GENESIS_CHECKPOINT_PIN_MISMATCH")
    require(variants.get("schema")=="janus.nexus.integrated_native_git_lab.v1.variants"
            and checkpoint.get("variant_digest")==digest(variants)
            and variants.get("model_generated_count")==2
            and variants.get("code_patch_generated_or_tested") is False
            and variants.get("authority_delta")==0,
            "GENESIS_VARIANTS_INTEGRITY")
    selected=variants.get("selected_variant_id")
    rows=variants.get("candidates")
    require(isinstance(rows,list) and len(rows)==2,
            "GENESIS_VARIANT_COUNT")
    selected_rows=[row for row in rows if row.get("variant_id")==selected]
    require(len(selected_rows)==1,"GENESIS_SELECTED_VARIANT_MISMATCH")
    proposal=selected_rows[0].get("proposal")
    require(isinstance(proposal,dict) and
            proposal.get("model_generated") is True and
            isinstance(proposal.get("text"),str),
            "GENESIS_SELECTED_NOT_MODEL_TEXT")
    val=proposal["text"]
    require(0<len(val.encode("utf-8"))<=512 and
            raw_sha(val.encode("utf-8"))==proposal.get("proposal_sha256"),
            "GENESIS_SELECTED_TEXT_SHA_MISMATCH")
    return checkpoint,variants,proposal


def consumer_prompt(proposal: dict) -> str:
    text=proposal["text"]
    budget=PROMPT_MAX-len(PROMPT_PREFIX.encode("utf-8"))
    excerpt=text.encode("utf-8")[:budget].decode("utf-8","ignore")
    require(bool(excerpt.strip()),"EXTERNAL_INPUT_EMPTY")
    result=PROMPT_PREFIX+excerpt
    require(len(result.encode("utf-8"))<=PROMPT_MAX,"EXTERNAL_PROMPT_OVERFLOW")
    return result


def verify_checkpoint(path: Path) -> None:
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size<=100_000_000,
            "MODEL_CHECKPOINT_MISSING_OR_LARGE")
    require(raw_sha(path.read_bytes())==MODEL_CHECKPOINT_SHA256,
            "MODEL_CHECKPOINT_HASH_MISMATCH")


def make_receipt(root: Path,checkpoint_file: Path,response: bytes,
                 external_run_id: str,receiver_code_sha: str) -> dict:
    require(isinstance(external_run_id,str) and
            RUN_ID.fullmatch(external_run_id) is not None,
            "EXTERNAL_RUN_ID_INVALID")
    require(isinstance(receiver_code_sha,str) and
            SHA40.fullmatch(receiver_code_sha) is not None,
            "RECEIVER_SOURCE_SHA_INVALID")
    check,variants,proposal=source(root)
    verify_checkpoint(checkpoint_file)
    require(0<len(response)<=12_000,"MODEL_RAW_RESPONSE_BOUNDS")
    try:
        body=response.decode("utf-8")
    except UnicodeError as exc:
        raise ExternalHold("MODEL_RAW_RESPONSE_NOT_UTF8") from exc
    prompt=consumer_prompt(proposal)
    require(body.startswith(prompt),"EXTERNAL_MODEL_INPUT_NOT_CONSUMED")
    suffix=body[len(prompt):].strip()
    require(bool(suffix),"EXTERNAL_MODEL_NO_GENERATED_SUFFIX")
    return {
        "schema":SCHEMA,"status":"PASS_EXTERNAL_DEMIURGE_NATIVE_MODEL_CONSUMED_PINNED_GENESIS_LAB_TEXT",
        "sender_repository":GENESIS,"receiver_repository":RECEIVER,
        "sender_source_run_id":SOURCE_RUN,"sender_source_attempt":SOURCE_ATTEMPT,
        "sender_code_sha":SOURCE_CODE_SHA,"sender_git_state_commit":SOURCE_STATE_SHA,
        "sender_checkpoint_digest":digest(check),
        "sender_variants_digest":digest(variants),
        "selected_variant_id":variants["selected_variant_id"],
        "selected_proposal_sha256":proposal["proposal_sha256"],
        "external_receiver_run_id":external_run_id,
        "external_receiver_source_sha":receiver_code_sha,
        "receiver_model_commit":MODEL_COMMIT,
        "receiver_checkpoint_sha256":MODEL_CHECKPOINT_SHA256,
        "received":"RECEIVED","parsed":"PARSED","loaded":"LOADED",
        "executed":"EXECUTED_ACTUAL_PINNED_DEMIURGE_MODEL_INFERENCE",
        "model_input_sha256":raw_sha(prompt.encode("utf-8")),
        "model_stdout_sha256":raw_sha(response),
        "model_generated_suffix_sha256":raw_sha(suffix.encode("utf-8")),
        "untrusted_generated_text_executed_as_command":False,
        "external_organ_is_separate_git_repository_and_runner":True,
        "production_integration_consumption_proven":False,
        "real_external_organ_readonly_consumption_proven":True,
        "scientific_authority_delta":0,"source_writeback":False,
        "external_effect_authority_delta":0,
        "full_issue_162_acceptance":False,
    }


def verify_receipt(root: Path,checkpoint_file: Path,response: bytes,
                   receipt: dict) -> None:
    require(isinstance(receipt,dict) and receipt.get("schema")==SCHEMA,
            "EXTERNAL_ACK_SCHEMA_INVALID")
    expected=make_receipt(root,checkpoint_file,response,
                          str(receipt.get("external_receiver_run_id")),
                          str(receipt.get("external_receiver_source_sha")))
    require(receipt==expected,"EXTERNAL_ACK_REPLAY_MISMATCH")


def save_once(path: Path,receipt: dict) -> None:
    require(not path.is_symlink(),"OUTPUT_SYMLINK_REJECTED")
    data=json.dumps(receipt,sort_keys=True,indent=2,ensure_ascii=False)+"\n"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        require(path.read_text("utf-8")==data,
                "DURABLE_ACK_IMMUTABLE_CONFLICT")
        return
    with path.open("x",encoding="utf-8") as stream:
        stream.write(data)


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("prompt","receive","verify"))
    parser.add_argument("--source-root",type=Path,required=True)
    parser.add_argument("--model-checkpoint",type=Path)
    parser.add_argument("--response",type=Path)
    parser.add_argument("--ack",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--run-id",default="")
    parser.add_argument("--receiver-source-sha",default="")
    a=parser.parse_args()
    try:
        if a.phase=="prompt":
            require(a.output is not None and not a.output.exists(),
                    "PROMPT_OUTPUT_REQUIRED_NEW")
            _,_,proposal=source(a.source_root)
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(consumer_prompt(proposal),encoding="utf-8")
            print("JANUS_EXTERNAL_ORGAN_INPUT=PINNED")
        else:
            require(a.model_checkpoint is not None and a.response is not None,
                    "MODEL_AND_RAW_RESPONSE_REQUIRED")
            require(a.response.is_file() and not a.response.is_symlink() and
                    a.response.stat().st_size<=12_000,"RAW_MODEL_RESPONSE_UNSAFE")
            raw=a.response.read_bytes()
            if a.phase=="receive":
                require(a.output is not None,"RECEIPT_OUTPUT_REQUIRED")
                ack=make_receipt(a.source_root,a.model_checkpoint,raw,
                                 a.run_id,a.receiver_source_sha)
                save_once(a.output,ack)
                print("JANUS_EXTERNAL_ORGAN_ACK="+ack["status"])
            else:
                require(a.ack is not None,"ORGAN_ACK_FILE_REQUIRED")
                verify_receipt(a.source_root,a.model_checkpoint,raw,
                               read(a.ack))
                print("JANUS_EXTERNAL_ORGAN_ACK=INDEPENDENT_REPLAY_PASS")
        return 0
    except (ExternalHold,OSError,ValueError,KeyError,TypeError) as exc:
        print("JANUS_EXTERNAL_ORGAN_ACK=HOLD:"+
              (str(exc) if isinstance(exc,ExternalHold) else "INPUT_OR_IO"),
              file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
