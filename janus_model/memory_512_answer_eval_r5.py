"""R5 real promoted v1: prospective engineering QA, with/without grounded memory.

Question labels were frozen in a prior git commit, after inspecting public
source JSON. They are NOT an independently authored blind sample. Source
fields are explicit known-source oracle data; this evaluates whether the
tiny 128-byte native model can *copy/use* those bytes under bounded context,
not its ability to retrieve sources or prove science. No training or writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from janus_model.memory_512_audit_index_r3 import Hold, audit_catalog, digest, raw_from_tree
from janus_model.memory_512_cache_r5 import (
    EXPECTED_SOURCE_COMMIT, EXPECTED_CATALOG_COMMIT,
    verify_cached_index,
)
from janus_model.model import ByteTokenizer
from janus_model.train_registry import load_checkpoint, sha256_file

SCHEMA = "janus.native.memory_512_r5_native_answer_eval.v1"
CHECKPOINT = "fc767adb812ac3bea54c44cbccfa9680941f95e2c8a77120559b41da044d9463"
FIXTURE = "janus.native.memory_512_r5_new_question_eval.v1"
MAX_ANSWER_BYTES = 80
MAX_PROMPT_BYTES = 127


def source_answer(source_root: Path, row: dict, eligible: list[dict]) -> str:
    path=row["path"]
    claim=next((e for e in eligible if e["path"]==path),None)
    if claim is None or claim["source_commit"] != EXPECTED_SOURCE_COMMIT:
        raise Hold("R5_EVAL_SOURCE_NOT_ELIGIBLE")
    raw=raw_from_tree(source_root,path,1024*1024)
    if digest(raw)!=claim["sha256"] or len(raw)!=claim["size_bytes"]:
        raise Hold("R5_EVAL_SOURCE_SHA_MISMATCH")
    try:
        data=json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise Hold("R5_EVAL_SOURCE_JSON_HOLD") from exc
    val=data.get(row["field"]) if isinstance(data,dict) else None
    if type(val) not in (str,int,bool,float):
        raise Hold("R5_EVAL_TARGET_NOT_SCALAR")
    expected=str(val)
    if expected!=row["expected"]:
        raise Hold("R5_EVAL_FROZEN_GOLD_MISMATCH")
    if len(expected.encode("utf-8"))>MAX_ANSWER_BYTES:
        raise Hold("R5_EVAL_ANSWER_BUDGET_HOLD")
    return expected


def packed_prompt(query: str, field: str, value: str | None, context: int) -> str:
    if (not isinstance(query,str) or not query or len(query.encode())>42 or
            not isinstance(field,str) or not field or len(field.encode())>50):
        raise Hold("R5_EVAL_QUESTION_BUDGET")
    base=f"Q:{query}\n"
    memory="" if value is None else f"C:{field}={value}\n"
    prompt=base+memory+"A:"
    if len(ByteTokenizer.encode(prompt,bos=True))>context:
        raise Hold("R5_EVAL_CONTEXT_OVERFLOW")
    return prompt


def greedy_answer(model, prefix: str, max_new: int) -> str:
    import torch
    ids=torch.tensor([ByteTokenizer.encode(prefix,bos=True)],dtype=torch.long)
    collected=[]
    with torch.no_grad():
        for _ in range(max_new):
            logits,_=model(ids[:,-model.config.context_length:])
            nxt=int(torch.argmax(logits[0,-1]).item())
            if nxt==ByteTokenizer.EOS:
                break
            collected.append(nxt)
            ids=torch.cat([ids,torch.tensor([[nxt]],dtype=torch.long)],dim=1)
    return ByteTokenizer.decode(collected).split("\n")[0].strip()


def target_nll(model, prefix: str, target: str) -> float:
    import torch
    tokens=ByteTokenizer.encode(prefix,bos=True)
    targets=ByteTokenizer.encode(target,eos=True)
    total=0.0
    with torch.no_grad():
        for tgt in targets:
            x=torch.tensor([tokens[-model.config.context_length:]],dtype=torch.long)
            logits,_=model(x)
            log_probs=torch.log_softmax(logits[0,-1],dim=-1)
            p=float(log_probs[tgt].item())
            if not math.isfinite(p):
                raise Hold("R5_EVAL_NONFINITE_NLL")
            total-=p
            tokens.append(tgt)
    return round(total/len(targets),6)


def evaluate_promoted_checkpoint(model_path: Path, source_root: Path,
                                 catalog_root: Path, fixture_path: Path,
                                 db_path: Path, db_receipt: Path) -> dict:
    import torch
    torch.set_num_threads(2)
    if sha256_file(model_path)!=CHECKPOINT:
        raise Hold("R5_EVAL_V1_CHECKPOINT_SHA_MISMATCH")
    model,obj=load_checkpoint(model_path,expected_sha256=CHECKPOINT)
    if model.config.context_length!=128:
        raise Hold("R5_EVAL_V1_CONTEXT_CHANGED")
    model.eval()
    source_root=source_root.resolve(strict=True)
    audit,eligible=audit_catalog(catalog_root.resolve(strict=True),source_root)
    cache=verify_cached_index(db_path,db_receipt,catalog_root,source_root,
                              eligible=eligible,audit=audit)
    fixture=json.loads(fixture_path.read_text(encoding="utf-8"))
    if (fixture.get("schema")!=FIXTURE or
            fixture.get("status")!="VISIBLE_PROSPECTIVE_ENGINEERING_EVAL_NOT_INDEPENDENT_HOLDOUT" or
            fixture.get("source_commit")!=EXPECTED_SOURCE_COMMIT or
            fixture.get("base_checkpoint_sha256")!=CHECKPOINT or
            fixture.get("limitations",{}).get("independent_evaluator") is not False or
            fixture.get("limitations",{}).get("not_used_for_training") is not True or
            len(fixture.get("cases",[]))!=5):
        raise Hold("R5_EVAL_FIXTURE_GATE")
    case_ids=set()
    results=[]
    max_new=int(fixture["max_new_tokens"])
    if not 1<=max_new<=40:
        raise Hold("R5_EVAL_TOKEN_BUDGET")
    for row in fixture["cases"]:
        if row["id"] in case_ids:
            raise Hold("R5_EVAL_CASE_DUPLICATE")
        case_ids.add(row["id"])
        target=source_answer(source_root,row,eligible)
        prompt_base=packed_prompt(row["query"],row["field"],None,128)
        prompt_memory=packed_prompt(row["query"],row["field"],target,128)
        output_base=greedy_answer(model,prompt_base,max_new)
        output_mem=greedy_answer(model,prompt_memory,max_new)
        results.append({
            "id":row["id"],
            "target_sha256":digest(target.encode("utf-8")),
            "source_sha256":next(x["sha256"] for x in eligible if x["path"]==row["path"]),
            "source_path":row["path"],"field":row["field"],
            "baseline_prompt_bytes":len(prompt_base.encode()),
            "memory_prompt_bytes":len(prompt_memory.encode()),
            "memory_value_bytes_in_attention":len(target.encode()),
            "baseline_exact":output_base==target,
            "memory_exact":output_mem==target,
            "baseline_generated_sha256":digest(output_base.encode("utf-8")),
            "memory_generated_sha256":digest(output_mem.encode("utf-8")),
            "baseline_target_byte_nll":target_nll(model,prompt_base,target),
            "memory_target_byte_nll":target_nll(model,prompt_memory,target),
        })
    baseline_exact=sum(x["baseline_exact"] for x in results)
    memory_exact=sum(x["memory_exact"] for x in results)
    body={
        "schema":SCHEMA,
        "status":"MODEL_ANSWER_EVALUATED_PROSPECTIVE_VISIBLE_DEV_NOT_BLIND",
        "checkpoint_sha256":CHECKPOINT,
        "context_bytes":128,
        "sources_git_commit":EXPECTED_SOURCE_COMMIT,
        "cache_sha256":cache["sqlite_sha256"],
        "questions":len(results),
        "baseline_exact_count":baseline_exact,
        "memory_exact_count":memory_exact,
        "baseline_average_target_byte_nll":round(sum(x["baseline_target_byte_nll"] for x in results)/len(results),6),
        "memory_average_target_byte_nll":round(sum(x["memory_target_byte_nll"] for x in results)/len(results),6),
        "memory_demonstrated_more_correct_answers":memory_exact>baseline_exact,
        "per_question":results,
        "retrieval_oracle_supplied_exact_field":True,
        "model_ran_real_checkpoint":True,
        "independent_blind_holdout":False,
        "generalization_established":False,
        "source_governance_training_approval":False,
        "model_checkpoint_modified":False,
        "model_promoted":False,
        "scientific_authority_delta":0,
    }
    body["receipt_sha256"]=digest(json.dumps(
        body,sort_keys=True,separators=(",", ":"),ensure_ascii=False).encode())
    return body


def main()->None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--checkpoint",type=Path,required=True)
    ap.add_argument("--source-root",type=Path,required=True)
    ap.add_argument("--catalog-root",type=Path,required=True)
    ap.add_argument("--fixture",type=Path,required=True)
    ap.add_argument("--db",type=Path,required=True)
    ap.add_argument("--cache-receipt",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    if a.out.exists() or a.out.resolve().is_relative_to(a.source_root.resolve()):
        raise Hold("R5_EVAL_REPORT_MUTATION_HOLD")
    report=evaluate_promoted_checkpoint(
        a.checkpoint,a.source_root,a.catalog_root,a.fixture,a.db,a.cache_receipt)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "status":report["status"],
        "questions":report["questions"],
        "baseline_exact":report["baseline_exact_count"],
        "memory_exact":report["memory_exact_count"],
        "baseline_nll":report["baseline_average_target_byte_nll"],
        "memory_nll":report["memory_average_target_byte_nll"],
        "independent_blind_holdout":False,
        "checkpoint_modified":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
