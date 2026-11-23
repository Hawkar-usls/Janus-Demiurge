#!/usr/bin/env python3
"""TRINITY R1.4: deterministic mathematics is truth; SmolLM remains advisory.

Supported audited grammar: "Calculate a (+|-|*) b. Answer with one integer."
Bounded nonnegative operands, optional signed result. No eval, AST, network,
dynamic code, Qwen/SmolLM authority or self-labeled teacher data. Any out-of-
grammar question is HOLD_UNSUPPORTED, NOT approval. This module is stdlib only.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

SCHEMA="janus.trinity.r14.verified_critic_oracle/1.0"
FIFTH="research/essence/trinity_parental_school/R14_FIFTH_FROZEN_CASES_20261123.json"
FIFTH_BLOB="a31080b9574305a6d3d1f94754978fd485000b12"
QUESTION=re.compile(r"\ACalculate (0|[1-9][0-9]{0,5}) ([+*-]) (0|[1-9][0-9]{0,5})\. Answer with one integer\.\Z",re.ASCII)
CANONICAL=re.compile(r"\A(?:0|[1-9][0-9]{0,12}|-[1-9][0-9]{0,12})\Z",re.ASCII)
ADVISORY=re.compile(r"\AFORMAT=(CANONICAL|NONCANONICAL|UNKNOWN)\nWHY=([^\n]{1,70})\Z",re.ASCII)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
         separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()


def git_blob(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii")+data).hexdigest()


def parse_problem(problem):
    if not isinstance(problem,str) or len(problem)>110:
        return None
    m=QUESTION.fullmatch(problem)
    if not m:
        return None
    a,op,b=int(m.group(1)),m.group(2),int(m.group(3))
    return (a,op,b)


def exact_reference(problem):
    parsed=parse_problem(problem)
    if parsed is None:
        return None
    a,op,b=parsed
    if op=="+":
        result=a+b
    elif op=="-":
        result=a-b
    elif op=="*":
        result=a*b
    else:
        raise AssertionError("R14_INTERNAL_OPERATOR_SCOPE")
    return str(result)


def verify(problem,proposal):
    """Fail-closed verdict; unsupported problems never become train labels."""
    reference=exact_reference(problem)
    if reference is None:
        status="HOLD_UNSUPPORTED"
    elif not isinstance(proposal,str) or len(proposal)>80 or CANONICAL.fullmatch(proposal) is None:
        status="VETO_FORMAT"
    elif proposal==reference:
        status="APPROVE"
    else:
        status="VETO_WRONG"
    return {
        "verdict":status,
        "oracle":"DETERMINISTIC_BOUNDED_INTEGER_ARITHMETIC",
        "oracle_version":"R14_FIXED_GRAMMAR_V1",
        "answer_sha256":hashlib.sha256(reference.encode("utf-8")).hexdigest() if reference is not None else None,
        "teacher_or_advisory_authority":False,
        "eligible_for_train":status=="APPROVE",
    }


def interpret_advisory(text):
    """Only parse a *format* observation. Never let it vote on math truth."""
    if not isinstance(text,str) or len(text)>100:
        return {"format":"UNKNOWN","valid":False,"text_sha256":None}
    match=ADVISORY.fullmatch(text)
    return {"format":match.group(1) if match else "UNKNOWN",
            "valid":match is not None,
            "text_sha256":hashlib.sha256(text.encode("utf-8")).hexdigest()}


def advisory_prompt(problem,proposed):
    if not isinstance(problem,str) or not isinstance(proposed,str):
        raise ValueError("R14_BAD_ADVISORY_INPUT")
    if len(problem)>110 or len(proposed)>80:
        raise ValueError("R14_ADVISORY_LENGTH_HOLD")
    # The user text is bounded; the output has NO ability to change oracle
    # status. The prompt explicitly excludes mathematical verification.
    return ("You are an assistant that describes ANSWER FORMAT ONLY. "
            "Never judge whether arithmetic is correct. "
            "Output exactly TWO lines: FORMAT=CANONICAL or FORMAT=NONCANONICAL "
            "or FORMAT=UNKNOWN; then WHY=a short formatting explanation. "
            "A canonical answer is exactly one integer with no extra words. "
            "Do not add any other text.\nQuestion: "+problem+
            "\nProposed answer: "+proposed+"\nFormat analysis:")


def read_fifth(root):
    raw=(Path(root)/FIFTH).read_bytes()
    if not 1000<len(raw)<50_000 or git_blob(raw)!=FIFTH_BLOB:
        raise ValueError("R14_FIFTH_EXAM_BLOB_DRIFT")
    data=json.loads(raw)
    if data.get("schema")!="janus.trinity.r14.fifth_exam_frozen/1.0" or data.get("case_count")!=64:
        raise ValueError("R14_FIFTH_SCHEMA_OR_COUNT")
    rows=data.get("cases")
    if not isinstance(rows,list) or len(rows)!=64 or len({x.get("id") for x in rows if isinstance(x,dict)})!=64:
        raise ValueError("R14_FIFTH_CASE_IDENTITIES")
    labels=("CORRECT","WRONG","AMBIGUOUS","UNSUPPORTED")
    if any(sum(isinstance(x,dict) and x.get("kind")==k for x in rows)!=16 for k in labels):
        raise ValueError("R14_FIFTH_BALANCE")
    for x in rows:
        if x.get("partition")!="FIFTH_INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND" or x.get("expected_verdict") not in ("APPROVE","VETO_WRONG","VETO_FORMAT","HOLD_UNSUPPORTED"):
            raise ValueError("R14_FIFTH_PARTITION_OR_LABEL")
        if verify(x["prompt"],x["proposed_answer"])["verdict"]!=x["expected_verdict"]:
            raise ValueError("R14_FIFTH_REFERENCE_DISAGREEMENT")
    return rows


def train_only_cases():
    cases=[]
    for i in range(24):
        a,b=101+13*i,113+17*i
        prompt=f"Calculate {a} + {b}. Answer with one integer."
        cases.append({"id":f"R14-TRAIN-{i:03d}","prompt":prompt,
                      "reference":str(a+b),"partition":"TRAIN_ONLY_SYMBOLIC_ORACLE"})
    return cases


def verified_train_source(rows):
    """Strictly join Qwen proposals to a fixed TRAIN_ONLY curriculum.

    SmolLM comments never grant/revoke a factual label. Qwen must actually
    propose the exact verified answer to contribute an example.
    """
    train=train_only_cases()
    if not isinstance(rows,list) or len(rows)!=len(train):
        raise ValueError("R14_TEACHER_INCOMPLETE_TRAIN_SOURCE")
    accepted=[]
    results=[]
    for task,row in zip(train,rows):
        if not isinstance(row,dict) or row.get("id")!=task["id"]:
            raise ValueError("R14_TRAIN_ORDER_OR_PROVENANCE")
        proposal=row.get("teacher_proposal")
        raw_note=row.get("smollm_advisory")
        if not isinstance(proposal,str) or not isinstance(raw_note,str):
            raise ValueError("R14_MODEL_OUTPUT_NOT_TEXT")
        decision=verify(task["prompt"],proposal)
        note=interpret_advisory(raw_note)
        if decision["verdict"]=="APPROVE":
            accepted.append({"id":task["id"],"prompt":task["prompt"],
                "target":task["reference"],
                "source":"TRAIN_ONLY_SYMBOLIC_ORACLE_WITH_QWEN_VERIFIED"})
        results.append({"id":task["id"],"verdict":decision["verdict"],
                        "advisory":note,"teacher_output_sha256":hashlib.sha256(proposal.encode()).hexdigest()})
    return {"schema":"janus.trinity.r14.verified_training_source/1.0",
        "source_partition":"TRAIN_ONLY","training_source_sha256":digest(train),
        "accepted_cases":accepted,"accepted_count":len(accepted),
        "all_teacher_proposals_verified_by_math_oracle":True,
        "smollm_advisory_never_truth":True,
        "known_genesis_64_not_read":True,"fifth_exam_not_read":True,
        "student_training_executed":False,"may_promote_JANUS":False,
        "production_promotion":False,"rows":results}


def compare_fifth(rows,advisories):
    if len(rows)!=64 or not isinstance(advisories,list) or len(advisories)!=64:
        raise ValueError("R14_INCOMPLETE_FIFTH_MODEL_RESULT")
    metrics={k:{"total":0,"oracle_exact":0,"format_only_exact":0,"advisory_structured":0} for k in ("CORRECT","WRONG","AMBIGUOUS","UNSUPPORTED")}
    records=[]
    for case,raw in zip(rows,advisories):
        oracle=verify(case["prompt"],case["proposed_answer"])
        ref=case["expected_verdict"]
        kind=case["kind"]
        # Explicit weak baseline that categorizes textual *form* but cannot
        # tell that a canonical number is the WRONG numeric value.
        format_only=("HOLD_UNSUPPORTED" if exact_reference(case["prompt"]) is None else
                    "APPROVE" if isinstance(case["proposed_answer"],str) and CANONICAL.fullmatch(case["proposed_answer"]) else
                    "VETO_FORMAT")
        note=interpret_advisory(raw)
        metrics[kind]["total"]+=1
        metrics[kind]["oracle_exact"]+=oracle["verdict"]==ref
        metrics[kind]["format_only_exact"]+=format_only==ref
        metrics[kind]["advisory_structured"]+=note["valid"]
        records.append({"id":case["id"],"category":kind,
                        "oracle_verdict":oracle["verdict"],
                        "format_only_verdict":format_only,
                        "advisory":note,"matched_frozen_reference":oracle["verdict"]==ref})
    result={"schema":"janus.trinity.r14.fifth_internal_firstlook_result/1.0",
            "fifth_blob_sha1":FIFTH_BLOB,"fifth_cases":64,
            "metrics":metrics,"per_case":records,
            "oracle_matches_frozen_reference":all(x["matched_frozen_reference"] for x in records),
            "oracle_not_learned_intelligence":True,
            "llm_advisory_never_overrides_oracle":True,
            "same_owner_internal_only":True,"external_validation":False,
            "independent_exam_completed":False,"janus_model_promoted":False,
            "fifth_used_for_training":False,"automatic_self_training":False,
            "production_promotion":False,
            "status":"PASS_DETERMINISTIC_ORACLE_IMPLEMENTATION_ONLY__TRINITY_GRADUATION_HOLD"
                     if all(x["matched_frozen_reference"] for x in records)
                     else "HOLD_ORACLE_MISMATCH"}
    result["sha256"]=digest(result)
    return result
