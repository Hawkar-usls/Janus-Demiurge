#!/usr/bin/env python3
"""Opt-in CPU-only Trinity school: source-bound teacher, pupil and critic.

No production weights, autonomous execution or science authority.
"""
from __future__ import annotations
import argparse, gc, json, os
from hashlib import sha256
from pathlib import Path
from tools import trinity_parental_contract as c

def save_new(path, record):
    path=Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("TRINITY_OUTPUT_MUST_BE_NEW")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x",encoding="utf-8") as f:
        json.dump(record,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")

def load_parent(spec):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    if spec not in (c.QWEN,c.SMOL):
        raise ValueError("TRINITY_MODEL_NOT_ALLOWLISTED")
    tk=AutoTokenizer.from_pretrained(spec["repo"],revision=spec["revision"],trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(
        spec["repo"],revision=spec["revision"],trust_remote_code=False,
        use_safetensors=True,torch_dtype=torch.float32).to("cpu").eval()
    if model.config._commit_hash != spec["revision"]:
        raise ValueError("TRINITY_MODEL_REVISION_NOT_CONFIRMED")
    torch.set_num_threads(4)
    return tk,model

def parent_answer(tk,model,prompt,max_tokens=16):
    import torch
    ids=tk.apply_chat_template([{"role":"user","content":prompt}],
         tokenize=True,add_generation_prompt=True,return_tensors="pt")
    if ids.shape[1]>240:
        raise ValueError("TRINITY_PARENT_PROMPT_TOO_LONG")
    with torch.inference_mode():
        out=model.generate(ids,attention_mask=torch.ones_like(ids),
                max_new_tokens=max_tokens,do_sample=False,
                pad_token_id=tk.eos_token_id)
    return tk.decode(out[0,ids.shape[1]:],skip_special_tokens=True).strip()[:100]

def teach(path):
    tasks=c.curriculum()
    tk,model=load_parent(c.QWEN)
    answers=[parent_answer(tk,model,t["prompt"],10) for t in tasks]
    del tk,model;gc.collect()
    tk,model=load_parent(c.SMOL)
    judges=[parent_answer(tk,model,
            "Check the proposed answer to the sum, reply YES or NO only. "
            +t["prompt"]+" Proposed answer: "+a,4)
            for t,a in zip(tasks,answers)]
    del tk,model;gc.collect()
    rows=[{"id":t["id"],"teacher_text":a,"critic_text":j}
          for t,a,j in zip(tasks,answers,judges)]
    checked=c.teach_gate(rows)
    accepted=sum(int(r["eligible_for_train"]) for r in checked)
    result=c.sealed({
        "schema":c.TEACH_SCHEMA,
        "status":"TRAIN_SOURCE_QUALIFIED" if accepted>=4 else "HOLD_NO_QUALIFIED_TRAIN_SOURCE",
        "teachers":{"qwen":c.QWEN,"smollm":c.SMOL},
        "task_generator_sha256":c.digest(tasks),
        "qualified_train_questions":accepted,
        "rows":checked,
        "no_examination_content_read":True,
        "teacher_proposal_is_not_truth":True,
        "symbolic_oracle_veto":True,
        "research_only":True,"production_promotion":False,
    })
    save_new(path,result)
    return result

def train(teacher_path,incumbent_path,out,receipt_path,steps):
    import torch
    from janus_model.model import ByteTokenizer
    from janus_model.train_registry import load_checkpoint,save_checkpoint,sha256_file
    from janus_model.checkpoint_admission import PROMOTED
    if type(steps) is not int or not 1<=steps<=64:
        raise ValueError("TRINITY_TRAIN_STEP_BUDGET")
    if out.resolve() in (incumbent_path.resolve(),Path(PROMOTED).resolve()):
        raise ValueError("TRINITY_CANNOT_WRITE_PROMOTED")
    source=c.checked_seal(json.loads(teacher_path.read_text()))
    if source.get("schema")!=c.TEACH_SCHEMA or source.get("teachers")!={"qwen":c.QWEN,"smollm":c.SMOL}:
        raise ValueError("TRINITY_TEACHER_PROVENANCE_INVALID")
    if source.get("task_generator_sha256")!=c.digest(c.curriculum()) or source.get("no_examination_content_read") is not True:
        raise ValueError("TRINITY_TRAIN_SPLIT_INVALID")
    tasks=c.curriculum(); rows=source.get("rows")
    if not isinstance(rows,list) or len(rows)!=len(tasks):
        raise ValueError("TRINITY_MISSING_TEACHER_CASE")
    qualified=[]
    for t,row in zip(tasks,rows):
        if not isinstance(row,dict) or row.get("id")!=t["id"] or row.get("prompt")!=t["prompt"] or row.get("expected")!=t["expected"]:
            raise ValueError("TRINITY_SYMBOLIC_ORACLE_MISMATCH")
        if row.get("eligible_for_train") is True:
            if row.get("teacher_proposed_correct") is not True or row.get("critic_veto") is not False:
                raise ValueError("TRINITY_FORGED_TEACHER_ACCEPTANCE")
            qualified.append(t)
    if len(qualified)<4 or source.get("qualified_train_questions")!=len(qualified):
        result=c.sealed({"schema":c.TRAIN_SCHEMA,"status":"HOLD_NO_SAFE_TRAINING_SET",
                         "teacher_sha256":source["sha256"],"candidate_sha256":None,
                         "production_promotion":False})
        save_new(receipt_path,result)
        return result
    state=json.loads(Path("janus_model/state/JANUS_MODEL_STATE.json").read_text())
    expected=state.get("checkpoint_sha256")
    model,_=load_checkpoint(incumbent_path,expected_sha256=expected)
    if sha256_file(incumbent_path)!=expected:
        raise ValueError("TRINITY_INCORRECT_INCUMBENT_CHECKPOINT")
    raw=("\n".join("Q:"+t["prompt"]+"\nJANUS:"+t["expected"]+"\n" for t in qualified)+"\n")*40
    ids=torch.tensor(ByteTokenizer.encode(raw,bos=True,eos=True),dtype=torch.long)
    torch.set_num_threads(4);torch.manual_seed(20261123)
    opt=torch.optim.AdamW(model.parameters(),lr=1e-4)
    model.train()
    g=torch.Generator().manual_seed(20261123)
    length=model.config.context_length
    losses=[]
    for _ in range(steps):
        starts=torch.randint(0,len(ids)-length-1,(3,),generator=g)
        xb=torch.stack([ids[j:j+length] for j in starts])
        yb=torch.stack([ids[j+1:j+length+1] for j in starts])
        _,loss=model(xb,yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
        opt.step()
        losses.append(float(loss.item()))
    if not all(0<=n<100 for n in losses):
        raise ValueError("TRINITY_NONFINITE_LOSS")
    save_checkpoint(out,model,{
        "shadow_only":True,"teacher_sha256":source["sha256"],
        "parent_checkpoint_sha256":expected,
        "exam_seen":False,"production_promotion":False,
    })
    child_hash=sha256_file(out)
    if child_hash==expected:
        raise ValueError("TRINITY_WEIGHTS_NOT_CHANGED")
    result=c.sealed({
        "schema":c.TRAIN_SCHEMA,"status":"SEALED_NATIVE_SHADOW_EXAM_PENDING",
        "teacher_sha256":source["sha256"],
        "parent_checkpoint_sha256":expected,
        "candidate_sha256":child_hash,
        "cases":len(qualified),"steps":steps,
        "first_loss":losses[0],"last_loss":losses[-1],
        "no_exam_data_read":True,
        "model_promoted":False,
        "production_promotion":False,
    })
    save_new(receipt_path,result)
    return result

def student_answer(model,prompt):
    from janus_model.model import ByteTokenizer
    import torch
    prefix="Q:"+prompt+"\nJANUS:"
    input_ids=ByteTokenizer.encode(prefix,bos=True)
    if len(input_ids)>=model.config.context_length:
        return None
    with torch.inference_mode():
        out=model.generate(torch.tensor([input_ids],dtype=torch.long),
                           max_new_tokens=16,temperature=1,top_k=1)
    return ByteTokenizer.decode(out[0,len(input_ids):].tolist()).strip()

def exam(teacher_path,train_receipt,student_path,incumbent_path,genesis_root,out):
    from janus_model.train_registry import load_checkpoint,sha256_file
    import torch
    torch.set_num_threads(4)
    source=c.checked_seal(json.loads(teacher_path.read_text()))
    shadow=c.checked_seal(json.loads(train_receipt.read_text()))
    if shadow.get("schema")!=c.TRAIN_SCHEMA or shadow.get("status")!="SEALED_NATIVE_SHADOW_EXAM_PENDING":
        raise ValueError("TRINITY_NO_SEALED_STUDENT")
    if shadow.get("teacher_sha256")!=source.get("sha256"):
        raise ValueError("TRINITY_BROKEN_TEACHER_LINEAGE")
    if sha256_file(student_path)!=shadow.get("candidate_sha256"):
        raise ValueError("TRINITY_STUDENT_CHECKPOINT_HASH_MISMATCH")
    state=json.loads(Path("janus_model/state/JANUS_MODEL_STATE.json").read_text())
    if state.get("checkpoint_sha256")!=shadow.get("parent_checkpoint_sha256"):
        raise ValueError("TRINITY_MAIN_INCUMBENT_DRIFT")
    cases=c.read_verified_cases(genesis_root)
    incumbent,_=load_checkpoint(incumbent_path,expected_sha256=shadow["parent_checkpoint_sha256"])
    student,_=load_checkpoint(student_path,expected_sha256=shadow["candidate_sha256"])
    incumbent.eval();student.eval()
    outcomes={name:[] for name in ("qwen","smollm","janus_incumbent","janus_candidate")}
    hashes={name:[] for name in outcomes}
    for name,model in (("janus_incumbent",incumbent),("janus_candidate",student)):
        for item in cases:
            value=student_answer(model,item["prompt"])
            outcomes[name].append(value==item["expected"])
            hashes[name].append(sha256((value or "").encode()).hexdigest())
    del student,incumbent;gc.collect()
    for name,spec in (("qwen",c.QWEN),("smollm",c.SMOL)):
        tk,model=load_parent(spec)
        for item in cases:
            value=parent_answer(tk,model,item["prompt"],24)
            outcomes[name].append(value==item["expected"])
            hashes[name].append(sha256(value.encode()).hexdigest())
        del tk,model;gc.collect()
    result=c.decide(outcomes,candidate_sha=shadow["candidate_sha256"],
                    checkpoint_sha=shadow["parent_checkpoint_sha256"],first_look=True)
    result.update({
       "teacher_receipt_sha256":source["sha256"],
       "training_receipt_sha256":shadow["sha256"],
       "parent_models":{"qwen":c.QWEN,"smollm":c.SMOL},
       "genesis_suite_branch":"research/essence-g9-frozen-functional-exam-20261123",
       "genesis_suite_git_blobs":[c.LEGACY_SUITE["blob"],c.NEW_SUITE["blob"]],
       "per_case_correct_bools":outcomes,
       "per_case_answer_hashes":hashes,
       "holdout_read_only_in_separate_exam_job":True,
       "source_github_run_id":os.getenv("GITHUB_RUN_ID"),
       "same_owner_internal_exam_not_external_validation":True,
       "production_promotion":False,
    })
    result=c.sealed(result)
    save_new(out,result)
    return result

def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    t=sub.add_parser("teach");t.add_argument("--out",type=Path,required=True)
    t=sub.add_parser("train")
    t.add_argument("--teacher",type=Path,required=True)
    t.add_argument("--incumbent",type=Path,default=Path("janus_model/checkpoints/promoted.pt"))
    t.add_argument("--out",type=Path,required=True);t.add_argument("--receipt",type=Path,required=True)
    t.add_argument("--steps",type=int,default=36)
    t=sub.add_parser("exam")
    t.add_argument("--teacher",type=Path,required=True)
    t.add_argument("--train-receipt",type=Path,required=True)
    t.add_argument("--student",type=Path,required=True)
    t.add_argument("--incumbent",type=Path,default=Path("janus_model/checkpoints/promoted.pt"))
    t.add_argument("--genesis",type=Path,required=True)
    t.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.cmd=="teach": result=teach(a.out)
    elif a.cmd=="train": result=train(a.teacher,a.incumbent,a.out,a.receipt,a.steps)
    else: result=exam(a.teacher,a.train_receipt,a.student,a.incumbent,a.genesis,a.out)
    print(json.dumps({"stage":a.cmd,"status":result["status"],"sha256":result["sha256"],
                      "production_promotion":False},sort_keys=True))

if __name__=="__main__":
    main()
