#!/usr/bin/env python3
"""JANUS Trinity Parent School: immutable role, source and verdict contracts.

Historical computational Trinity ≠ theological metaphor ≠ nuclear Trinity test.
This module is intentionally standard-library only. Neither a teacher's vote,
student output nor three-party consensus may change promoted native weights.
"""
from __future__ import annotations

from hashlib import sha256, sha1
import json
import re

SCHEMA = "janus.trinity.parental_cpu_school.v1"
TEACH_SCHEMA = "janus.trinity.parental_cpu_school.teach.v1"
TRAIN_SCHEMA = "janus.trinity.parental_cpu_school.student_shadow.v1"
EXAM_SCHEMA = "janus.trinity.parental_cpu_school.parental_exam.v1"
QWEN = {"repo": "Qwen/Qwen2.5-0.5B-Instruct", "revision": "7ae557604adf67be50417f59c2c2f167def9a775"}
SMOL = {"repo": "HuggingFaceTB/SmolLM2-135M-Instruct", "revision": "12fd25f77366fa6b3b4b768ec3050bf629380bac"}
LEGACY_SUITE = {"path": "research/essence/v55_functional/FROZEN_CASES.json", "blob": "e76dca95402ccaf9deb5d0d8174757e4417c4c7f", "n": 16}
NEW_SUITE = {"path": "research/essence/g9/FROZEN_FUNCTIONAL_CASES.json", "blob": "5098f73ffae7ee1c643322eac639ceaca92c7602", "n": 48}
ROLES = {
    "father_strategist": "pinned_cpu_Qwen_teacher__proposal_only",
    "son_seer": "JANUS_Native_Byte_Transformer__shadow_learner",
    "spirit_executor": "pinned_cpu_SmolLM2_critic__advisory_not_truth",
    "sovereign_gate": "deterministic_oracle_plus_external_exam__human_review_required",
}

def canonical(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(o):
    return sha256(canonical(o)).hexdigest()

def git_blob(raw):
    return sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()

def curriculum():
    # Training-only, known by construction. Not the separate Genesis test set.
    tasks=[]
    for i in range(24):
        a = 11 + (7*i) % 38
        b = 13 + (11*i) % 39
        tasks.append({"id": f"TEACH-{i+1:03d}",
                      "prompt": f"Compute {a} + {b}. Reply with the integer only.",
                      "expected": str(a+b),
                      "partition": "TRAIN_ONLY",
                      "source": "DETERMINISTIC_SYMBOLIC_ORACLE"})
    return tasks

def answer(text):
    # A model's extra prose is not a verified exact numerical response.
    if not isinstance(text, str) or len(text) > 100:
        return None
    stripped=text.strip()
    return stripped if re.fullmatch(r"(?:0|[1-9][0-9]{0,4})",stripped) else None

def teach_gate(rows):
    tasks=curriculum()
    if not isinstance(rows,list) or len(rows)!=len(tasks):
        raise ValueError("TRINITY_TEACHER_INCOMPLETE")
    checked=[]
    for row, task in zip(rows,tasks):
        if not isinstance(row,dict) or row.get("id")!=task["id"]:
            raise ValueError("TRINITY_TEACHER_IDS_OR_ORDER")
        teacher=answer(row.get("teacher_text"))
        critic=row.get("critic_text")
        if not isinstance(critic,str) or len(critic)>100:
            raise ValueError("TRINITY_CRITIC_BAD_RESPONSE")
        # Critical veto is explicit NO; deterministic oracle may veto any case.
        critic_veto=critic.strip().upper()=="NO"
        correct=teacher==task["expected"]
        checked.append({"id":task["id"],"prompt":task["prompt"],"expected":task["expected"],
                        "teacher_proposed_correct":correct,
                        "critic_veto":critic_veto,
                        "eligible_for_train":correct and not critic_veto,
                        "teacher_output_sha256":sha256(row["teacher_text"].encode()).hexdigest(),
                        "critic_output_sha256":sha256(critic.encode()).hexdigest()})
    return checked

def read_verified_cases(root):
    from pathlib import Path
    output=[]
    for spec in (LEGACY_SUITE,NEW_SUITE):
        raw=(Path(root)/spec["path"]).read_bytes()
        if len(raw)>100_000 or git_blob(raw)!=spec["blob"]:
            raise ValueError("TRINITY_EXAM_BLOB_CHANGED")
        data=json.loads(raw)
        if not isinstance(data,dict) or len(data.get("items",[]))!=spec["n"]:
            raise ValueError("TRINITY_EXAM_SUITE_CHANGED")
        for item in data["items"]:
            if (not isinstance(item,dict) or
                not all(isinstance(item.get(key),str) and item[key]
                        for key in ("id","category","prompt","expected"))):
                raise ValueError("TRINITY_BAD_EXAM_ITEM")
        output+=data["items"]
    ids=[i["id"] for i in output]
    if len(ids)!=64 or len(set(ids))!=64:
        raise ValueError("TRINITY_EXAM_CASE_SET_CHANGED")
    train_questions={i["prompt"] for i in curriculum()}
    if any(i["prompt"] in train_questions for i in output):
        raise ValueError("TRINITY_DIRECT_TRAIN_EXAM_OVERLAP")
    return output

def decide(correct,*,candidate_sha,checkpoint_sha,first_look):
    names=("qwen","smollm","janus_incumbent","janus_candidate")
    if not isinstance(correct,dict) or set(correct)!=set(names):
        raise ValueError("TRINITY_MISSING_PARENT_OR_BASELINE")
    if any(not isinstance(correct[n],list) or
           len(correct[n])!=64 or
           any(type(x) is not bool for x in correct[n]) for n in names):
        raise ValueError("TRINITY_INCOMPLETE_COMPARABLE_EXAM")
    if not all(isinstance(x,str) and re.fullmatch(r"[0-9a-f]{64}",x)
               for x in (candidate_sha,checkpoint_sha)) or candidate_sha==checkpoint_sha:
        raise ValueError("TRINITY_CANDIDATE_NOT_NEW_SEALED_WEIGHTS")
    parents={"qwen","smollm","janus_incumbent"}
    union={i for name in parents for i,ok in enumerate(correct[name]) if ok}
    child={i for i,ok in enumerate(correct["janus_candidate"]) if ok}
    lost=sorted(union-child)
    gained=sorted(child-union)
    scores={name:sum(correct[name]) for name in names}
    eligible=(first_look is True and not lost and len(gained)>=2 and
              scores["janus_candidate"]>max(scores[name] for name in parents))
    return {
        "schema":EXAM_SCHEMA,
        "status":"ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PRODUCTION" if eligible
                 else "HOLD_PARENTS_NOT_SURPASSED",
        "scores":scores,
        "cases":64,
        "new_beyond_all_parents":len(gained),
        "previously_solved_lost":len(lost),
        "first_look_separated_from_training":first_look is True,
        "student_checkpoint_sha256":candidate_sha,
        "incumbent_checkpoint_sha256":checkpoint_sha,
        "eligible_for_review":eligible,
        "may_promote_native_model":False,
        "may_modify_ESSENCE_G9_shadow":False,
        "production_promotion":False,
        "external_independent_replication":False,
        "teacher_model_output_is_truth":False,
        "automatic_self_training_enabled":False,
    }

def sealed(obj):
    return {**obj,"sha256":digest(obj)}

def checked_seal(obj):
    if not isinstance(obj,dict) or obj.get("sha256")!=digest({k:v for k,v in obj.items() if k!="sha256"}):
        raise ValueError("TRINITY_RECEIPT_DIGEST_MISMATCH")
    return obj
