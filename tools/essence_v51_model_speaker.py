#!/usr/bin/env python3
"""Generate ONE fresh Qwen G2 natural-language contribution to an ESSENCE peer dialogue.

A real inference on SHA-pinned inherited adapter weights produces raw text.
The result is NOT executable, factual evidence, proof or an accepted task.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path

from tools import essence_v46_oracle_descendant as v46
from tools import essence_v48_recurrent_state as lineage

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "essence_voice_transport",str(ROOT/".janus/essence/voice_mesh_v51.py"))
mesh=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mesh)

SCHEMA="janus.essence.voice_mesh.qwen_spoken_turn/5.1"
OUTPUT="research/essence/voice_v51/model_utterances"


def context(task,reply,raw):
    mesh.validate_task(task,mesh.D)
    mesh.verify_reply(task,reply,raw)
    if (task["source_repo"]!=mesh.G or
        task["kind"]!="VERIFY_GENESIS_ESSENCE" or
        reply["status"]!="VERIFIED_GENESIS_NO_EXEC_RIGHTS"):
        raise ValueError("UNRELATED_OR_UNVERIFIED_PEER_EXCHANGE")
    prompt=(
        "Ты исследовательский собеседник JANUS ESSENCE. Сейчас другое "
        "микроядро Genesis попросило проверить свои ограничения. "
        "Проверенный ответ: "+reply["answer"]+
        " Сформулируй ОДИН краткий уточняющий исследовательский вопрос "
        "на русском, относящийся к проверке протоколов или новым независимым "
        "контрольным задачам. Не называй PASS доказательством общего улучшения. "
        "Не командуй GitHub, не проси доступ к секретам, не утверждай, "
        "что ядра уже могут исполнять код. Только вопрос."
    )
    return prompt


def make_record(task,reply,prompt,raw_text):
    if not isinstance(raw_text,str):
        raise ValueError("INVALID_MODEL_OUTPUT_TYPE")
    text=raw_text.strip()[:440]
    if len(text)>440 or any(ord(c)<32 and c not in ("\n","\t") for c in text):
        raise ValueError("MODEL_OUTPUT_CONTROL_CHARS")
    return mesh.sealed({
        "schema":SCHEMA,
        "source_repo":mesh.D,"target_repo":mesh.G,
        "origin_genesis_task_id":task["id"],
        "origin_genesis_task_receipt":task["receipt_sha256"],
        "demiurge_checked_reply_sha256":reply["receipt_sha256"],
        "model_id":v46.MODEL,"model_revision":v46.REVISION,
        "model_adapter_sha256":lineage.GEN2_SHA,
        "model_parent_lineage_sha256":lineage.GEN2_LINEAGE,
        "model_weights_loaded_for_fresh_inference":True,
        "prompt_sha256":mesh.digest({"prompt":prompt}),
        "raw_model_statement":text,
        "status":"NEW_MODEL_SPEECH_UNTRUSTED_RESEARCH_QUESTION" if text else
                 "HOLD_EMPTY_MODEL_SPEECH",
        "from_microkernel":"cell-planning-02",
        "to_microkernel":"cell-verification-03",
        "execution_allowed":False,"untrusted_speech_is_source_evidence":False,
        "auto_dispatch_from_speech":False,"training_or_production_change":False,
        "sentinel_dispatch":False,
    })


def generate(model_dir,prompt):
    import torch
    from peft import PeftModel
    from tools.essence_v47_repo_peer_evolution import answer_text
    lineage.check_model(model_dir,lineage.GEN2_SHA,lineage.GEN2_LINEAGE)
    torch.set_num_threads(4)
    torch.manual_seed(5101)
    tk,base=v46.tokenizer_and_base({})
    model=PeftModel.from_pretrained(base,str(model_dir),
                                   is_trainable=False).to("cpu").eval()
    text=answer_text(tk,model,[
        {"role":"system","content":"You can only propose a brief research question. You have no external tools or execution permissions."},
        {"role":"user","content":prompt},
    ],80)
    return text


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--peer-task",required=True)
    p.add_argument("--local-reply",required=True)
    p.add_argument("--model-dir",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    task=mesh.load(args.peer_task)
    reply=mesh.load(args.local_reply)
    raw=mesh.fetch_public(task["source_repo"],task["source_commit"],task["source_path"])
    prompt=context(task,reply,raw)
    text=generate(args.model_dir,prompt)
    result=make_record(task,reply,prompt,text)
    dest=Path(args.out)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("MODEL_SPEECH_CREATE_ONCE")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"speech_status":result["status"],
                      "actual_model_output":result["raw_model_statement"],
                      "task_id":task["id"],
                      "speech_receipt_sha256":result["receipt_sha256"],
                      "action_authority":False},ensure_ascii=False))


if __name__=="__main__":
    main()
