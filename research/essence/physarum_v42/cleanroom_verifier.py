#!/usr/bin/env python3
"""Clean-room ESSENCE G4 verifier: NO imports from tools.essence*, Physarum or JANUS.

Reads only raw float32 arrays + sealed manifests, frozen external Git blob IDs,
and full-cost receipt created BEFORE held-out data are accessed. Model math is
independently restated here to avoid invoking training/evolution/verifier code.
This is self-run clean-room code, NOT independently run by an external scientist.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import struct
from time import perf_counter, process_time
from urllib.request import Request, urlopen

import torch
from torch import nn

SCHEMA = "janus.essence.cleanroom_costmatched_holdout/4.2"
G3_HASH = "7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299"
FREEZE_HASH = "d1633f6c6172c46014a675b4cccf7c72a466ad959d4aa844120e73f3bc31cd56"
KNOWN_OLD_G4 = {
    "control8": {
        "weights_sha256": "a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b",
        "manifest_sha256": "563bcf05a97c67f5723c4f5414bf7621197105eae654a8133a439c91fe4575f0",
        "generation": "g4_control", "steps": 8,
    },
    "physarum": {
        "weights_sha256": "dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
        "manifest_sha256": "a8397385b2703d5cca7b15b9b12626960d8105e976f10b628451fe330dbcf003",
        "generation": "g4_physarum", "steps": 8,
    },
}
SOURCE_PROJECTS = (
    "pallets/werkzeug", "Textualize/rich",
    "python-trio/trio", "pydantic/pydantic"
)
MEAN_GAIN = 0.0001
MAX_FAMILY_REGRESSION = 0.0001


def require(value, code):
    if not value:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def safe_json(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and
            2 <= path.stat().st_size <= 30000, "INVALID_JSON_OR_SIZE")
    return json.loads(path.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("JSON_NONFINITE")))


def check_seal(value, field):
    require(value.get(field) == digest({
        k:v for k,v in value.items() if k != field
    }), "SHA256_SEAL_VETO")
    return value


def policy(path):
    item = safe_json(path)
    require(item.get("schema") ==
            "janus.essence.physarum_costmatched_cleanroom_holdout/4.2" and
            item.get("frozen_before_any_v42_costmatched_model_training") is True and
            item.get("source_scoring_executed_before_seal") is False and
            item.get("status") == "PREREGISTERED_NOT_EVALUATED" and
            item.get("external_custodian_independent") is False and
            item.get("external_sources_are_public") is True and
            item.get("g3_checkpoint_sha256") == G3_HASH and
            item.get("cost_contract", {}).get("physarum_total_model_train_steps") == 14 and
            item.get("cost_contract", {}).get("baseline14_model_train_steps") == 14 and
            item.get("exam_contract", {}).get("threshold_loss_decrease") == MEAN_GAIN and
            item.get("exam_contract", {}).get("max_repo_family_loss_regression") ==
            MAX_FAMILY_REGRESSION and item.get("production_authority") is False,
            "PREREGISTRATION_DRIFT")
    families = item.get("source_repos")
    require(isinstance(families, list) and
            [x.get("repo") for x in families] == list(SOURCE_PROJECTS) and
            all(len(x["paths"]) == 3 for x in families),
            "SOURCE_COHORT_NOT_LOCKED")
    for fam in families:
        require(len(fam["commit"]) == 40 and
                all(ch in "0123456789abcdef" for ch in fam["commit"]),
                "INVALID_SOURCE_COMMIT")
        names = set()
        for row in fam["paths"]:
            require(set(row) == {"path","git_blob_sha1"} and
                    isinstance(row["path"], str) and
                    ".." not in row["path"].split("/") and
                    row["path"].endswith(".py") and
                    len(row["git_blob_sha1"]) == 40 and
                    all(x in "0123456789abcdef"
                        for x in row["git_blob_sha1"]) and
                    row["path"] not in names, "SOURCE_PATH_OR_HASH_VETO")
            names.add(row["path"])
    return item


class IndependentlyRestatedByteTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.tok = nn.Embedding(256, 32)
        self.pos = nn.Embedding(24, 32)
        block = nn.TransformerEncoderLayer(
            d_model=32, nhead=4, dim_feedforward=128,
            dropout=0.0, activation="gelu", batch_first=True,
            norm_first=True)
        self.transformer = nn.TransformerEncoder(
            block, num_layers=1, enable_nested_tensor=False)
        self.norm = nn.LayerNorm(32)
        self.head = nn.Linear(32, 256, bias=False)

    def forward(self, token_ids):
        n = token_ids.shape[1]
        x = self.tok(token_ids) + self.pos(
            torch.arange(n,device=token_ids.device))[None,:,:]
        causal = torch.triu(torch.full((n,n),float("-inf"),
                                       device=token_ids.device), diagonal=1)
        return self.head(self.norm(self.transformer(x,mask=causal)))


def checkpoint(path, expected):
    folder=Path(path)
    require(folder.is_dir() and not folder.is_symlink(),
            "UNSAFE_CHECKPOINT_DIRECTORY")
    info=check_seal(safe_json(folder/"manifest.json"),"manifest_sha256")
    require(info.get("schema") ==
            "janus.essence.float32_weight_checkpoint/3.8" and
            info.get("checkpoint_format")=="STRICT_FLOAT32_ARRAY_NO_PICKLE" and
            info.get("generation")==expected["generation"] and
            info.get("manifest_sha256")==expected["manifest_sha256"] and
            info.get("weights_sha256")==expected["weights_sha256"] and
            info.get("trained_steps")==expected["steps"] and
            info.get("inherited_initial_weights_sha256")==G3_HASH and
            info.get("freeze_receipt_sha256")==FREEZE_HASH and
            info.get("production_authority") is False,
            "FORGED_GENERATIONAL_CHECKPOINT")
    weights=folder/"weights.f32"
    require(weights.is_file() and not weights.is_symlink() and
            0<weights.stat().st_size<=2000000 and
            weights.stat().st_size==info["weights_bytes"],
            "UNSAFE_CHECKPOINT_BYTES")
    raw=weights.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==info["weights_sha256"],
            "CHECKPOINT_BYTES_SHA256_MISMATCH")
    model=IndependentlyRestatedByteTransformer()
    refs=dict(sorted(model.state_dict().items()))
    descriptors=info["tensors"]
    require(len(descriptors)==len(refs),"TENSOR_COUNT_CHANGED")
    recreated={}
    offset=0
    for item,(name,tensor) in zip(descriptors, refs.items()):
        count=tensor.numel()
        require(item=={"name":name,"shape":list(tensor.shape),
                       "offset":offset,"bytes":count*4},
                "TENSOR_OFFSET_OR_SHAPE_CHANGED")
        numbers=struct.unpack("<"+str(count)+"f",
                              raw[offset:offset+count*4])
        require(all(math.isfinite(v) for v in numbers),
                "NONFINITE_UNSAFE_CHECKPOINT")
        recreated[name]=torch.tensor(numbers,dtype=torch.float32).reshape(
            tuple(tensor.shape))
        offset+=4*count
    require(offset==len(raw),"UNEXPECTED_TRAILING_TENSOR_DATA")
    model.load_state_dict(recreated,strict=True)
    model.eval()
    return model,info


def verified_source(entry, row):
    repo=entry["repo"]
    require(repo in SOURCE_PROJECTS,"EXTERNAL_REPOSITORY_NOT_ALLOWED")
    url=("https://raw.githubusercontent.com/"+repo+"/"+
         entry["commit"]+"/"+row["path"])
    req=Request(url,headers={"User-Agent":"JANUS-Independent-Runtime-Cleanroom-v4.2",
                             "Accept":"application/octet-stream"})
    with urlopen(req,timeout=25) as handle:
        raw=handle.read(90001)
    require(2048<=len(raw)<=90000,"EXTERNAL_SOURCE_BOUNDS_VETO")
    blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    require(blob==row["git_blob_sha1"],
            "EXTERNAL_SOURCE_GIT_BLOB_MISMATCH")
    return raw


def infer(model, raw, *, repeats=3):
    require(type(raw) is bytes and len(raw)>25, "EMPTY_EXAM_SOURCE")
    torch.set_num_threads(1)
    token=torch.tensor(list(raw),dtype=torch.long)
    starts=[k*(len(token)-25)//15 for k in range(16)]
    x=torch.stack([token[pos:pos+24] for pos in starts])
    y=torch.stack([token[pos+1:pos+25] for pos in starts])
    sample=[]
    with torch.no_grad():
        for _ in range(repeats):
            a=perf_counter()
            logits=model(x)
            loss=torch.nn.functional.cross_entropy(
                logits.reshape(-1,256), y.reshape(-1))
            sample.append({"loss":float(loss.item()),
                           "elapsed_seconds":perf_counter()-a})
    require(all(math.isfinite(z["loss"]) for z in sample) and
            max(z["loss"] for z in sample) -
            min(z["loss"] for z in sample)<1e-5,
            "NONDETERMINISTIC_INFERENCE_LOSS")
    return {"loss": sample[0]["loss"],
            "mean_inference_seconds":sum(z["elapsed_seconds"] for z in sample)/repeats,
            "tokens":384}


def evaluate(lock_file, cost_file, baseline14_dir, control8_dir,
             physarum_dir, *, source_fetch=verified_source):
    torch.set_num_threads(1)
    full=policy(lock_file)
    cost=check_seal(safe_json(cost_file),"receipt_sha256")
    require(cost.get("schema")=="janus.essence.physarum_full_cost_replay/4.2" and
            cost.get("lock_sha256")==digest(full) and
            cost.get("g3_source_sha256")==G3_HASH and
            cost.get("physarum_source_sha256")==KNOWN_OLD_G4["physarum"]["weights_sha256"] and
            cost.get("physarum",{}).get("total_training_steps")==14 and
            cost.get("baseline14",{}).get("train_steps")==14 and
            cost.get("full_cost_includes_all_probes_and_selection") is True and
            cost.get("external_exam_bytes_read") is False and
            cost.get("production_authority") is False,
            "FULL_COST_PROVENANCE_INVALID")
    expected14={
        "weights_sha256":cost["baseline14_weights_sha256"],
        "manifest_sha256":cost["baseline14_manifest_sha256"],
        "generation":"g4_fixed_budget14","steps":14}
    # All three checkpoints must be sealed and verified BEFORE fetching
    # the first external byte. The scoring implementation never imports
    # Physarum or the JANUS model/training code.
    models={
        "baseline14":checkpoint(baseline14_dir,expected14)[0],
        "control8":checkpoint(control8_dir,KNOWN_OLD_G4["control8"])[0],
        "physarum":checkpoint(physarum_dir,KNOWN_OLD_G4["physarum"])[0],
    }
    seen=set()
    tasks=[]
    families=[]
    for family in full["source_repos"]:
        entries=[]
        for row in family["paths"]:
            content=source_fetch(family,row)
            require(type(content) is bytes and 2048 <= len(content) <= 90000,
                    "SOURCE_LENGTH_VETO")
            actual_blob=hashlib.sha1(b"blob "+str(len(content)).encode()+
                                     b"\0"+content).hexdigest()
            require(actual_blob==row["git_blob_sha1"],
                    "CLEANROOM_GIT_BLOB_SHA_VETO")
            sha=hashlib.sha256(content).hexdigest()
            require(sha not in seen,"DUPLICATED_SOURCE_CONTENT")
            seen.add(sha)
            scores={name:infer(model,content) for name,model in models.items()}
            record={"repo":family["repo"],"path":row["path"],
                    "source_commit":family["commit"],
                    "source_git_blob_sha1":row["git_blob_sha1"],
                    "content_sha256":sha,
                    "bytes":len(content),
                    "scores":scores}
            entries.append(record)
            tasks.append(record)
        families.append({
            "repo":family["repo"],
            "mean_loss":{name:sum(x["scores"][name]["loss"] for x in entries)/3
                         for name in models},
        })
    require(len(tasks)==12 and len(seen)==12,"INCOMPLETE_V42_EXAM")
    aggregate={name:sum(x["scores"][name]["loss"] for x in tasks)/12
               for name in models}
    def beats(name):
        return (aggregate[name]-aggregate["physarum"]>=MEAN_GAIN and
                all(fam["mean_loss"]["physarum"]-
                    fam["mean_loss"][name]<=MAX_FAMILY_REGRESSION
                    for fam in families))
    phys_cpu = (
        cost["physarum"]["probes_duration_including_dev_validation"]["process_cpu_seconds"]+
        cost["physarum"]["network_and_swarm_duration"]["process_cpu_seconds"]+
        cost["physarum"]["final_train_duration"]["process_cpu_seconds"]+
        cost["physarum"]["final_dev_score_duration"]["process_cpu_seconds"])
    fixed_cpu = (
        cost["baseline14"]["train_duration"]["process_cpu_seconds"]+
        cost["baseline14"]["validation_duration"]["process_cpu_seconds"])
    infer_cost={name:sum(x["scores"][name]["mean_inference_seconds"]
                         for x in tasks) for name in models}
    # The actual inference cost is observed separately and counted for
    # both policies, not omitted from a favorable quality-only claim.
    ratio=(phys_cpu+infer_cost["physarum"])/(fixed_cpu+infer_cost["baseline14"])
    quality_gain = beats("baseline14") and beats("control8")
    # Conservative predeclared cost rule: no >25% CPU time increase
    # for a 14-step Physarum policy on the SAME runner.
    within_cost = ratio <= 1.25
    status=("PASS_SELF_VERIFIED_COST_AWARE_FRESH_SOURCE_GAIN"
            if quality_gain and within_cost else
            "NO_COST_AWARE_PHYSARUM_GAIN_ON_FROZEN_COHORT")
    return {
        "schema":SCHEMA,
        "status":status,
        "preregistered_lock_sha256":digest(full),
        "full_cost_receipt_sha256":cost["receipt_sha256"],
        "verifier_code_sha256":hashlib.sha256(
            Path(__file__).read_bytes()).hexdigest(),
        "verifier_architecture":"CLEANROOM_RESTATED_BYTE_TRANSFORMER_STANDALONE",
        "thirdparty_origins":list(SOURCE_PROJECTS),
        "all_models_checked_before_new_external_data":True,
        "full_cost_includes_physarum_probes":True,
        "mean_loss":aggregate,
        "repo_families":families,
        "raw_tasks":tasks,
        "quality_beats_8_step_control":beats("control8"),
        "quality_beats_costmatched_14_step_control":beats("baseline14"),
        "physarum_training_search_cpu_seconds":phys_cpu,
        "control14_training_cpu_seconds":fixed_cpu,
        "inference_elapsed_seconds_for_12_files":infer_cost,
        "physarum_to_fixed_full_cpu_cost_ratio":ratio,
        "cost_ratio_max_for_pass":1.25,
        "independent_implementation":True,
        "independent_execution_by_external_researcher":False,
        "secret_external_custodian":False,
        "external_sources_public":True,
        "no_promotion_to_working_models":True,
        "production_authority":False,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--lock",required=True)
    parser.add_argument("--cost",required=True)
    parser.add_argument("--baseline14-dir",required=True)
    parser.add_argument("--control8-dir",required=True)
    parser.add_argument("--physarum-dir",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=evaluate(args.lock,args.cost,args.baseline14_dir,
                    args.control8_dir,args.physarum_dir)
    result["receipt_sha256"]=digest(result)
    output=Path(args.out)
    require(not output.exists() and not output.is_symlink(),
            "IMMUTABLE_EXAM_ARTIFACT_REQUIRED")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "status":result["status"],
        "mean_loss":result["mean_loss"],
        "full_cpu_cost_ratio":result["physarum_to_fixed_full_cpu_cost_ratio"],
        "receipt_sha256":result["receipt_sha256"],
        "production_authority":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
