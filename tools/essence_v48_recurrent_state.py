#!/usr/bin/env python3
"""ESSENCE v4.8 persistent, bounded, research-only peer evolution ledger.

Pure control-plane functions do not import neural runtimes or execute model text.
Only the explicitly separate Actions state branch may receive a model candidate.
Never promote to production/native JANUS or dispatch Sentinel A/B/C.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

SCHEMA = "janus.essence.recurrent_peer_lock/4.8"
LEDGER = "janus.essence.peer_recursion_ledger/4.8"
PLAN = "janus.essence.peer_recurrent_plan/4.8"
EXAM = "janus.essence.peer_recurrent_exam/4.8"
GEN2_SHA = "1ec5b21689ee5af6eec5345e0f5b91fc0870ffa520a56ef8778ce914ac28f3bc"
GEN2_LINEAGE = "bea00f89a3e03b05faaed901afdb6cdd0c7f5f70293615250c20dec171196b6c"
REV = "7ae557604adf67be50417f59c2c2f167def9a775"
SOURCES = {
    "terminal": ("Hawkar-usls/-Terminal-for-Janus", "config/JANUS_MODEL_PEERS.json",
                 ("status", "primary.role", "reviewer.role", "policy.runtime",
                  "policy.execution", "policy.max_input_chars",
                  "policy.automatic_weight_training",
                  "policy.automatic_production_model_replacement",
                  "policy.cross_repository_write",
                  "policy.external_secrets_required", "policy.peer_feedback_is_truth")),
    "hrain": ("Hawkar-usls/Hrain", "PROJECT_STATUS.json",
              ("schema_id", "project", "portfolio_class", "last_reviewed", "maturity",
               "completion_status", "spider_residence.status",
               "spider_residence.role", "spider_residence.nickname",
               "spider_residence.mode", "spider_residence.home_contract")),
    "genesis": ("Hawkar-usls/Janus_Genesis", "PROJECT_STATUS.json",
                ("schema_id", "project", "portfolio_class", "last_reviewed",
                 "maturity", "completion_status")),
}
ROTATION = {"terminal": "hrain", "hrain": "genesis", "genesis": "terminal"}
HEX = re.compile(r"^[0-9a-f]{64}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SECRET = re.compile(r"(ghp_|github_pat_|sk-[A-Za-z0-9]|-----BEGIN|Bearer\s)", re.I)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sealed(obj):
    return dict(obj, sha256=digest(obj))


def check(obj):
    if not isinstance(obj, dict) or obj.get("sha256") != digest({
            k: v for k, v in obj.items() if k != "sha256"}):
        raise ValueError("RECEIPT_TAMPER")
    return obj


def load(path, maximum=150_000):
    p = Path(path)
    if not p.is_file() or p.is_symlink() or p.stat().st_size > maximum:
        raise ValueError("MISSING_OR_UNSAFE_JSON_FILE")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("INVALID_NONFINITE_JSON")))


def store(path, obj):
    p = Path(path)
    if p.is_symlink() or p.exists():
        raise ValueError("REFUSE_OVERWRITE_RECEIPT")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2)+"\n",
                 encoding="utf-8")


def verify_lock(lock):
    expected = {
        "schema": SCHEMA,
        "parent_base_model": "Qwen/Qwen2.5-0.5B-Instruct",
        "base_revision": REV, "initial_generation": 2,
        "initial_parent_sha256": GEN2_SHA,
        "seed_run_id": 43746247031, "seed": 4801,
        "train_steps": 20, "learning_rate": 0.0005,
        "max_accepted_generations": 8, "max_attempts_total": 32,
        "max_memory_records": 24, "max_response_tokens": 32,
        "required_paraphrase_mean_nll_gain": 0.12,
        "required_paraphrase_exact_gain": 1,
        "maximum_external_repo_nll_regression": 0.20,
        "maximum_retention_nll_regression": 0.20,
        "required_source_examples": 6, "maximum_source_examples": 16,
        "peer_feedback_is_ground_truth": False,
        "baseline_and_child_costs_required": True,
        "prospective_external_exam_available": False,
        "external_custodian": None,
        "automatic_shadow_acceptance": True,
        "automatic_production_promotion": False,
        "native_janus_checkpoint_write": False,
        "sentinel_A_B_C_execution": False,
        "holdout_rotation": ROTATION,
    }
    if not isinstance(lock, dict) or any(lock.get(k) != v for k,v in expected.items()):
        raise ValueError("FROZEN_RESEARCH_LOCK_CHANGED")
    entries = lock.get("sources")
    if (not isinstance(entries, list) or
            [v.get("id") for v in entries if isinstance(v, dict)] != list(SOURCES)):
        raise ValueError("WRONG_REPOSITORY_SOURCE_ORDER")
    for entry in entries:
        repo,path,keys=SOURCES[entry["id"]]
        if (entry.get("repo"),entry.get("path"),entry.get("keys")) != (repo,path,list(keys)):
            raise ValueError("SOURCE_ALLOWLIST_DRIFT")
    return lock


def verify_ledger(ledger):
    if not isinstance(ledger, dict) or ledger.get("schema") != LEDGER:
        raise ValueError("INVALID_ANCESTRY_LEDGER")
    for key in ("production_promotion_authority", "native_janus_modified",
                "sentinel_dispatch_authority"):
        if ledger.get(key) is not False:
            raise ValueError("CONTROL_PLANE_ESCALATION")
    if ledger.get("bootstrap") is True:
        if (ledger.get("current_generation") != 2 or ledger.get("current_adapter_sha256") != GEN2_SHA
                or ledger.get("current_lineage_sha256") != GEN2_LINEAGE
                or ledger.get("current_model_path") != "models/gen0002"
                or ledger.get("origin_experiment_run_id") != 43746247031
                or ledger.get("attempts") != [] or ledger.get("memory") != []
                or ledger.get("ledger_sha256") is not None
                or len(ledger.get("accepted_generations",[])) != 1):
            raise ValueError("BAD_SEEDED_LEDGER")
    else:
        if ledger.get("ledger_sha256") != digest({
                k:v for k,v in ledger.items() if k != "ledger_sha256"}):
            raise ValueError("BROKEN_LEDGER_HASH_CHAIN")
    attempts=ledger.get("attempts")
    generations=ledger.get("accepted_generations")
    memory=ledger.get("memory")
    if (not isinstance(attempts,list) or not isinstance(generations,list)
            or not isinstance(memory,list) or len(attempts)>32 or len(generations)>8
            or len(memory)>24):
        raise ValueError("LEDGER_UNBOUNDED")
    if not generations or generations[-1].get("generation")!=ledger.get("current_generation"):
        raise ValueError("CURRENT_GENERATION_LINEAGE_MISMATCH")
    if generations[-1].get("adapter_sha256")!=ledger.get("current_adapter_sha256"):
        raise ValueError("MUTATED_ACCEPTED_WEIGHT_SHA")
    if len({x.get("id") for x in attempts})!=len(attempts):
        raise ValueError("DUPLICATE_ATTEMPT_ID")
    for row in attempts:
        if row.get("production_promotion") is not False:
            raise ValueError("UNAUTHORIZED_PRODUCTION_ATTEMPT")
    return ledger


def value_at(obj,key):
    val=obj
    for part in key.split("."):
        if not isinstance(val,dict) or part not in val:
            raise ValueError("UNMAPPED_SOURCE_KEY")
        val=val[part]
    if type(val) not in (str,int,bool):
        raise ValueError("NONSIMPLE_SOURCE_FACT")
    value=("true" if val else "false") if isinstance(val,bool) else str(val)
    if not 1 <= len(value) <= 62 or SECRET.search(value):
        raise ValueError("UNSAFE_OR_OVERLONG_SOURCE_FACT")
    return value


def question(repo,key,paraphrase=False):
    if paraphrase:
        return f"Проверь реестр {repo}. Как записано значение поля {key}? Выведи ровно значение, без объяснений."
    return f"JANUS repo fact: for {repo}, what is the exact JSON value of {key}? Answer only its value."


def facts_from_json(repo,keys,obj,paraphrase=False):
    return [{"key":key,"prompt":question(repo,key,paraphrase),
             "answer":value_at(obj,key)} for key in keys]


def source_file(sources,entry):
    root=Path(sources).resolve(strict=True)
    path=root/entry["id"]/entry["path"]
    if (not path.is_file() or path.is_symlink() or
            not path.resolve().is_relative_to(root) or
            path.stat().st_size > 80_000):
        raise ValueError("UNSAFE_PUBLIC_SOURCE_FILE")
    data=path.read_bytes()
    doc=json.loads(data.decode("utf-8"))
    return hashlib.sha256(data).hexdigest(),doc


def source_commit(sources,id):
    p=Path(sources)/id
    commit=subprocess.check_output(["git","-C",str(p),"rev-parse","HEAD"],
                                   text=True,timeout=10).strip()
    if not SHA1.fullmatch(commit):
        raise ValueError("UNVERIFIED_GITHUB_HEAD")
    return commit




def source_fact_memory(repo,source_sha,commit,row):
    """Public exact JSON property, not a model self-label or neural grade."""
    if repo not in (v[0] for v in SOURCES.values()):
        raise ValueError("MEMORY_SOURCE_REPO_NOT_ALLOWED")
    note={
        "source_repo":repo,"source_file_sha256":source_sha,
        "key":row["key"],"answer":row["answer"],
        "source_commit":commit,"training_verified_by_repository_sha":True,
        "external_validation":False,
    }
    return dict(note,fact_digest=digest(note))


def verified_replay(lock,ledger,sources,commit_lookup,exclude_id):
    """Recover prior verified facts only if current public source bytes match.

    Never replay facts from the prospective heldout repo into the training
    process, even if those facts were used by an earlier experiment.
    """
    withheld_repo=SOURCES[exclude_id][0]
    combined=list(ledger["memory"])
    for attempt in ledger["attempts"]:
        id=attempt.get("source_id")
        if id not in SOURCES or id==exclude_id:
            continue
        repo,path,keys=SOURCES[id]
        original={"id":id,"repo":repo,"path":path,"keys":list(keys)}
        file_sha,doc=source_file(sources,original)
        if file_sha!=attempt.get("source_file_sha256"):
            continue
        rows=facts_from_json(repo,keys,doc)
        if digest(rows)!=attempt.get("source_fact_sha256"):
            continue
        commit=commit_lookup(sources,id)
        combined.extend(source_fact_memory(repo,file_sha,commit,row)
                        for row in rows[:4])
    current={}
    for row in combined:
        if row.get("fact_digest")!=digest({k:v for k,v in row.items()
                                           if k!="fact_digest"}):
            raise ValueError("CORRUPT_PERSISTENT_FACT_MEMORY")
        repo=row.get("source_repo")
        if repo==withheld_repo:
            continue
        if repo not in [v[0] for v in SOURCES.values()] or not row.get(
                "training_verified_by_repository_sha"):
            raise ValueError("UNVERIFIED_HISTORICAL_FACT_LABEL")
        key=(repo,row.get("key"))
        current[key]=row  # replace outdated fact at same repo/key
    return list(current.values())[-lock["max_memory_records"]:]

def make_plan(lock,ledger,sources,commit_lookup=source_commit):
    verify_lock(lock)
    verify_ledger(ledger)
    if len(ledger["accepted_generations"]) >= lock["max_accepted_generations"]:
        return sealed({"schema":PLAN,"action":"HOLD_MAX_GENERATIONS","lock_sha256":digest(lock)})
    if len(ledger["attempts"]) >= lock["max_attempts_total"]:
        return sealed({"schema":PLAN,"action":"HOLD_MAX_ATTEMPTS","lock_sha256":digest(lock)})
    seen={a["task_digest"] for a in ledger["attempts"]}
    seen.add("invalid")
    for entry in lock["sources"]:
        source_sha,obj=source_file(sources,entry)
        rows=facts_from_json(entry["repo"],entry["keys"],obj)
        if len(rows)<lock["required_source_examples"]:
            continue
        task=hashlib.sha256((entry["id"]+"|"+digest(rows)).encode()).hexdigest()
        if task in seen:
            continue
        holdout=lock["holdout_rotation"][entry["id"]]
        memory=verified_replay(lock,ledger,sources,commit_lookup,holdout)
        origin_commit=commit_lookup(sources,entry["id"])
        holdout_commit=commit_lookup(sources,holdout)
        return sealed({
            "schema":PLAN,"action":"TRAIN_SHADOW_CANDIDATE",
            "lock_sha256":digest(lock),
            "parent_generation":ledger["current_generation"],
            "parent_adapter_sha256":ledger["current_adapter_sha256"],
            "parent_lineage_sha256":ledger["current_lineage_sha256"],
            "parent_model_path":ledger["current_model_path"],
            "parent_ledger_sha256":ledger.get("ledger_sha256"),
            "candidate_generation":ledger["current_generation"]+1,
            "task_digest":task,
            "source_id":entry["id"],"source_repo":entry["repo"],
            "source_file":entry["path"],"source_commit":origin_commit,
            "source_file_sha256":source_sha,
            "source_fact_sha256":digest(rows),"facts":rows,
            "holdout_id":holdout,"holdout_commit":holdout_commit,
            "memory_replay":memory,
            "external_custodian":False,"model_output_is_truth":False,
            "production_promotion":False,"sentinel_dispatch":False,
        })
    return sealed({"schema":PLAN,"action":"NO_NEW_FACTUAL_COHORT",
                   "lock_sha256":digest(lock),
                   "current_generation":ledger["current_generation"],
                   "production_promotion":False})


def verify_plan(plan,lock,ledger=None):
    check(plan)
    if plan.get("schema")!=PLAN or plan.get("lock_sha256")!=digest(verify_lock(lock)):
        raise ValueError("INVALID_TASK_PLAN")
    if plan.get("action")!="TRAIN_SHADOW_CANDIDATE":
        raise ValueError("NO_TRAIN_TASK")
    if (plan.get("source_id") not in SOURCES or
            plan.get("holdout_id") != ROTATION.get(plan["source_id"])):
        raise ValueError("UNTRUSTED_REPOSITORY_SELECTION")
    repo,path,keys=SOURCES[plan["source_id"]]
    if (plan.get("source_repo"),plan.get("source_file")) != (repo,path):
        raise ValueError("UNAUTHORIZED_SOURCE_OR_PATH")
    facts=plan.get("facts",[])
    if (not isinstance(facts,list) or len(facts)!=len(keys) or
            [r.get("key") for r in facts]!=list(keys)):
        raise ValueError("SOURCE_FACTS_NOT_ALLOWLISTED")
    if digest(facts)!=plan.get("source_fact_sha256"):
        raise ValueError("SOURCE_FACT_CORRUPTION")
    for row in facts:
        if (not isinstance(row.get("answer"),str) or
                not 1<=len(row["answer"])<=62 or SECRET.search(row["answer"]) or
                row.get("prompt")!=question(repo,row["key"])):
            raise ValueError("INJECTED_SOURCE_FACT_TEXT")
    replay=plan.get("memory_replay",[])
    withheld_repo=SOURCES[plan["holdout_id"]][0]
    if not isinstance(replay,list) or len(replay)>lock["max_memory_records"]:
        raise ValueError("UNBOUNDED_MEMORIZED_SOURCE_FACTS")
    for item in replay:
        repo=item.get("source_repo")
        provenance=next((v for v in SOURCES.values() if v[0]==repo),None)
        if (not provenance or repo==withheld_repo or
                item.get("key") not in provenance[2] or
                item.get("training_verified_by_repository_sha") is not True or
                not HEX.fullmatch(item.get("source_file_sha256","")) or
                not SHA1.fullmatch(item.get("source_commit","")) or
                not isinstance(item.get("answer"),str) or
                not 1<=len(item["answer"])<=62 or SECRET.search(item["answer"]) or
                item.get("fact_digest")!=digest({
                    k:v for k,v in item.items() if k!="fact_digest"})):
            raise ValueError("CORRUPT_OR_HOLDOUT_LEAKED_SOURCE_MEMORY")
    if (plan.get("external_custodian") is not False or
            plan.get("production_promotion") is not False or
            plan.get("sentinel_dispatch") is not False):
        raise ValueError("PROMOTION_OR_TOOL_EXECUTION_ESCALATION")
    if ledger is not None:
        verify_ledger(ledger)
        if (plan.get("parent_adapter_sha256")!=ledger["current_adapter_sha256"]
                or plan.get("parent_generation")!=ledger["current_generation"]
                or plan.get("parent_model_path")!=ledger["current_model_path"]
                or plan.get("parent_ledger_sha256")!=ledger.get("ledger_sha256")):
            raise ValueError("STALE_OR_REPLAYED_PARENT_PLAN")
    return plan


def check_model(path,expected_sha,expected_lineage_sha):
    root=Path(path)
    weights=root/"adapter_model.safetensors"
    lineage=root/"lineage.json"
    if (not weights.is_file() or weights.is_symlink() or
            weights.stat().st_size>6_000_000 or
            hashlib.sha256(weights.read_bytes()).hexdigest()!=expected_sha):
        raise ValueError("MODEL_TENSOR_DIGEST_MISMATCH")
    rec=load(lineage,50_000)
    check(rec)
    if (rec["sha256"]!=expected_lineage_sha or
            rec.get("adapter_sha256")!=expected_sha or
            rec.get("sentinel_dispatch") is not False and
            rec.get("sentinel_dispatch") is not None):
        raise ValueError("WRONG_MODEL_LINEAGE")
    return rec


def publish(state,lock,plan,exam,child,seed):
    """Called only with an already verified, no-production exam receipt."""
    lock=verify_lock(lock)
    target=Path(state)
    ledger_file=target/"research/essence/peer_v48_state/ledger.json"
    ledger=verify_ledger(load(ledger_file))
    verify_plan(plan,lock,ledger)
    check(exam)
    if (exam.get("schema")!=EXAM or
            exam.get("plan_sha256")!=plan["sha256"] or
            exam.get("parent_adapter_sha256")!=ledger["current_adapter_sha256"] or
            exam.get("candidate_generation")!=plan["candidate_generation"] or
            exam.get("production_promotion") is not False or
            exam.get("independent_external_validation") is not False):
        raise ValueError("UNVERIFIED_OR_FORGED_NEURAL_EXAM")
    if any(a.get("task_digest")==plan["task_digest"] for a in ledger["attempts"]):
        raise ValueError("TASK_ALREADY_ATTEMPTED")
    # Recover the *original* G2 seed even if the candidate is rejected.
    seed_path=target/"models/gen0002"
    # 2026-11-15 initial state write excluded *.json via a legacy .gitignore.
    # Restore only missing, original G2 model metadata from the SHA-verified
    # source artifact. Never repair tensors with an unverified parent.
    check_model(seed,GEN2_SHA,GEN2_LINEAGE)
    if not seed_path.exists():
        seed_path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(seed,seed_path)
    else:
        existing_weights=seed_path/"adapter_model.safetensors"
        if (not existing_weights.is_file() or
                hashlib.sha256(existing_weights.read_bytes()).hexdigest()!=GEN2_SHA):
            raise ValueError("SEED_TENSORS_DIFFER_FROM_ORIGINAL_G2")
        for name in ("adapter_config.json","lineage.json","README.md"):
            source=Path(seed)/name
            destination=seed_path/name
            if not destination.is_file() and source.is_file():
                shutil.copyfile(source,destination)
        check_model(seed_path,GEN2_SHA,GEN2_LINEAGE)
    approved=exam.get("status")=="PASS_INTERNAL_SHADOW_RETAINED"
    if approved:
        if exam.get("child_adapter_sha256")==ledger["current_adapter_sha256"]:
            raise ValueError("UNCHANGED_CHILD_CANNOT_BE_NEW_GENERATION")
        source_model=Path(child)
        lineage=check_model(source_model,exam["child_adapter_sha256"],
                            exam["child_lineage_sha256"])
        if (lineage.get("parent_adapter_sha256")!=ledger["current_adapter_sha256"]
                or lineage.get("plan_sha256")!=plan["sha256"]):
            raise ValueError("BROKEN_MULTIGENERATION_INHERITANCE")
        destination=target/f"models/gen{plan['candidate_generation']:04d}"
        if destination.exists():
            raise ValueError("GENERATION_ALREADY_ACCEPTED")
        shutil.copytree(source_model,destination)
        ledger["current_model_path"]=f"models/gen{plan['candidate_generation']:04d}"
        ledger["current_generation"]=plan["candidate_generation"]
        ledger["current_adapter_sha256"]=exam["child_adapter_sha256"]
        ledger["current_lineage_sha256"]=exam["child_lineage_sha256"]
        ledger["accepted_generations"].append({
            "generation":ledger["current_generation"],
            "adapter_sha256":ledger["current_adapter_sha256"],
            "lineage_sha256":ledger["current_lineage_sha256"],
            "parent_adapter_sha256":plan["parent_adapter_sha256"],
            "source_repo":plan["source_repo"],
            "source_fact_sha256":plan["source_fact_sha256"],
            "internal_exam_sha256":exam["sha256"],
            "external_validation":False,
        })
    # Verified repository memory survives even when the neural candidate
    # fails. A wrong neural model does not invalidate ground-truth JSON.
    # Keep one active value per repository/key; historical receipts retain
    # the original source SHA and failure verdict.
    merged={}
    for item in ledger["memory"]+plan["memory_replay"]:
        if item.get("fact_digest")!=digest({
                k:v for k,v in item.items() if k!="fact_digest"}):
            raise ValueError("INVALID_REPLAY_MEMORY_IN_ADMISSION")
        merged[(item["source_repo"],item["key"])]=item
    for row in plan["facts"][:4]:
        fact=source_fact_memory(plan["source_repo"],plan["source_file_sha256"],
                                plan["source_commit"],row)
        merged[(fact["source_repo"],fact["key"])]=fact
    ledger["memory"]=list(merged.values())[-lock["max_memory_records"]:]
    attempt = {
        "id":plan["task_digest"][:24],
        "task_digest":plan["task_digest"],"source_id":plan["source_id"],
        "source_file_sha256":plan["source_file_sha256"],
        "source_fact_sha256":plan["source_fact_sha256"],
        "parent_generation":plan["parent_generation"],
        "candidate_generation":plan["candidate_generation"],
        "status":exam["status"],
        "exam_sha256":exam["sha256"],
        "shadow_accepted":bool(approved),
        "external_validation":False,"production_promotion":False,
    }
    # A first live run preserved the ledger but its attempt JSON was ignored.
    # Reconstitute only explicitly labeled metadata from the already signed
    # ledger; do not claim the full original exam bytes have been recovered.
    historical=target/"research/essence/peer_v48_state/attempts"
    for old_attempt in ledger["attempts"]:
        old_path=historical/(old_attempt["id"]+".json")
        if old_path.exists():
            continue
        evidence={
            "schema":"janus.essence.recovered_attempt_metadata/4.8",
            "prior_attempt":old_attempt,
            "recoverable_from_existing_hash_chained_ledger":True,
            "full_original_exam_reembedded":False,
            "original_run_id":43749835808 if old_attempt["id"]=="0afda9803918e9d70abcea15" else None,
            "original_exam_artifact_id":14175742166 if old_attempt["id"]=="0afda9803918e9d70abcea15" else None,
            "production_promotion":False,
        }
        store(old_path,sealed(evidence))
    ledger["attempts"].append(attempt)
    ledger["bootstrap"]=False
    ledger["previous_ledger_sha256"]=ledger.get("ledger_sha256")
    ledger["ledger_sha256"]=digest({k:v for k,v in ledger.items() if k!="ledger_sha256"})
    ledger_file.write_text(json.dumps(ledger,indent=2,ensure_ascii=False,sort_keys=True)+"\n",
                           encoding="utf-8")
    receipts=target/"research/essence/peer_v48_state/attempts"
    store(receipts/f"{plan['task_digest'][:24]}.json",
          sealed({"schema":"janus.essence.recurrent_attempt/4.8",
                  "plan_sha256":plan["sha256"],"exam":exam,
                  "shadow_accepted":bool(approved),
                  "external_validation":False,"production_promotion":False}))
    return {"status":"SHADOW_ACCEPTED" if approved else "CANDIDATE_REJECTED",
            "generation":ledger["current_generation"],
            "attempts":len(ledger["attempts"]),
            "source":plan["source_id"],
            "production_promotion":False,"sentinel_dispatch":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("command",choices=["plan","publish"])
    p.add_argument("--lock",required=True)
    p.add_argument("--state",required=True)
    p.add_argument("--sources")
    p.add_argument("--plan")
    p.add_argument("--exam")
    p.add_argument("--child")
    p.add_argument("--seed")
    p.add_argument("--out")
    args=p.parse_args()
    lock=load(args.lock)
    if args.command=="plan":
        if not args.sources or not args.out:
            raise ValueError("REQUIRED_SOURCE_ROOT_AND_OUTPUT")
        ledger=load(Path(args.state)/"research/essence/peer_v48_state/ledger.json")
        result=make_plan(lock,ledger,args.sources)
        store(args.out,result)
    else:
        if not args.plan or not args.exam or not args.child or not args.seed:
            raise ValueError("REQUIRED_EXAM_CHECKPOINT_AND_SEED")
        result=publish(args.state,lock,load(args.plan),load(args.exam),
                       args.child,args.seed)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
