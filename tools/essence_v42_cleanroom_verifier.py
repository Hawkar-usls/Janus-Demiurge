#!/usr/bin/env python3
"""ESSENCE v4.2 independent clean-room G4 Physarum verifier.

This file intentionally imports no JANUS model/trainer/metric code. An outside
custodian runs it offline on never-shared tasks, with a signed task manifest
and a prepublished commitment. It verifies frozen G3/G4 FP32 tensor identities
and measures model inference locally. Search+train cost must be supplied by a
separately audited, hardware-matched cost replay.

CRITICAL: A cryptographically valid signature does not prove that the signer
is independent. The output NEVER grants production authority. No private
holdout contents or task paths need to enter JANUS's GitHub Actions.
"""
from __future__ import annotations
from array import array
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import sys
import time
from zipfile import ZipFile

SCHEMA = "janus.essence.physarum_cleanroom_external_exam/4.2"
CHALLENGE = "janus.essence.custodian_hidden_challenge/4.2"
PRECOMMIT = "janus.essence.custodian_precommit/4.2"
POLICY = "janus.essence.physarum_external_replication_contract/4.2"
COST = "janus.essence.external_cost_replay/4.2"
G3_SHA = "7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299"
G3_MANIFEST = "ed63cc6f143a71e00a3867d1b465be8a6c5f4aa061f20dbd37f85a007e8cd3e7"
G2_MANIFEST = "7233dd73acc54a0f9080806615a9b2148a6bd39771548b923dd6848ad8b0425f"
G4 = {
    "control": {
        "weights": "a5c5924acccdf47bfb9c3b6bc5ca9a8ba455e0cad4ef6d928ff684624634e57b",
        "manifest": "563bcf05a97c67f5723c4f5414bf7621197105eae654a8133a439c91fe4575f0",
    },
    "physarum": {
        "weights": "dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
        "manifest": "a8397385b2703d5cca7b15b9b12626960d8105e976f10b628451fe330dbcf003",
    },
}
BUDGET14_SHA = "a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174"
BUDGET14_MANIFEST = "49158892f8dc1674897465d84e45ecf02f19d96d79b72ae3aceb167599c61f5a"
BLOCK = 24
DIM = 32
WINDOWS = 32
MIN_FAMILIES = 5
MIN_TASKS = 10
MIN_RELATIVE_GAIN = 0.01
MIN_EFFICIENCY_GAIN = 1.05
MAX_FAMILY_REGRESSION = 0.001
MAX_SIGN_P = 0.05
MAX_SOURCE_SIZE = 100000
HASH64 = re.compile(r"^[0-9a-f]{64}$")


def demand(ok, code):
    if not ok:
        raise ValueError(code)


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def load_json(path, max_bytes=128000):
    p=Path(path)
    demand(p.is_file() and not p.is_symlink() and
           2 <= p.stat().st_size <= max_bytes, "MISSING_OR_OVERSIZED_JSON")
    return json.loads(p.read_text("utf-8"), parse_constant=lambda _: (
        _ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def seal(data):
    return dict(data, receipt_sha256=sha(data))


def safe_write(path, data):
    p=Path(path)
    demand(not p.exists() and not p.is_symlink(),
           "RECEIPT_MUST_BE_IMMUTABLE")
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data, sort_keys=True, indent=2)+"\n",
                 encoding="utf-8")


def read_zip_small(path, prefix):
    p=Path(path)
    demand(p.is_file() and not p.is_symlink() and
           256 < p.stat().st_size < 2000000, "INVALID_CHECKPOINT_ZIP")
    with ZipFile(p) as z:
        names = z.namelist()
        allowed={prefix+"manifest.json", prefix+"weights.f32"}
        demand(set(names) == allowed and len(names)==2,
               "ZIP_MUST_CONTAIN_ONLY_TWO_CHECKPOINT_FILES")
        for member in z.infolist():
            demand(0 < member.file_size <= 500000 and
                   member.compress_size > 0, "OVERSIZED_CHECKPOINT_ZIP_MEMBER")
        manifest=json.loads(z.read(prefix+"manifest.json").decode("utf-8"))
        raw=z.read(prefix+"weights.f32")
    return manifest,raw


def clean_model(torch):
    """Independent re-implementation of published 24x32 causal ByteTransformer."""
    nn=torch.nn

    class CleanByteTransformer(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok=nn.Embedding(256,DIM)
            self.pos=nn.Embedding(BLOCK,DIM)
            layer=nn.TransformerEncoderLayer(
                d_model=DIM,nhead=4,dim_feedforward=4*DIM,
                dropout=0.0,activation="gelu",
                batch_first=True,norm_first=True)
            self.transformer=nn.TransformerEncoder(
                layer,num_layers=1,enable_nested_tensor=False)
            self.norm=nn.LayerNorm(DIM)
            self.head=nn.Linear(DIM,256,bias=False)

        def forward(self,idx):
            length=idx.shape[1]
            demand(0 < length <= BLOCK, "INVALID_CONTEXT_LENGTH")
            x=self.tok(idx)+self.pos(
                torch.arange(length,device=idx.device))[None,:,:]
            causal=torch.triu(torch.full(
                (length,length),float("-inf"),device=idx.device),diagonal=1)
            return self.head(self.norm(self.transformer(x,mask=causal)))

    return CleanByteTransformer()


def restore_model(torch, manifest, raw, target, generation):
    require_sha = (G3_SHA if target == "g3" else
                   BUDGET14_SHA if target == "baseline14" else
                   G4[target]["weights"])
    require_manifest = (G3_MANIFEST if target == "g3" else
                        BUDGET14_MANIFEST if target == "baseline14" else
                        G4[target]["manifest"])
    demand(sys.byteorder == "little", "BIG_ENDIAN_UNSUPPORTED")
    demand(manifest.get("weights_sha256") == require_sha and
           hashlib.sha256(raw).hexdigest() == require_sha,
           "FROZEN_WEIGHT_HASH_MISMATCH")
    body={k:v for k,v in manifest.items() if k!="manifest_sha256"}
    demand(sha(body)==manifest.get("manifest_sha256")==require_manifest,
           "FROZEN_MANIFEST_HASH_MISMATCH")
    demand(manifest.get("checkpoint_format") ==
           "STRICT_FLOAT32_ARRAY_NO_PICKLE" and
           manifest.get("production_authority") is False and
           manifest.get("generation") == generation and
           manifest.get("weights_bytes") == len(raw) and
           1000 < len(raw) <= 500000, "UNSAFE_MODEL_CHECKPOINT")
    if target=="g3":
        demand(manifest.get("parent_manifest_sha256")==G2_MANIFEST,
               "G3_PARENT_NOT_SEALED")
    elif target=="baseline14":
        demand(manifest.get("inherited_initial_weights_sha256")==G3_SHA and
               manifest.get("parent_manifest_sha256")==G3_MANIFEST and
               manifest.get("trained_steps")==14, "COSTMATCHED14_LINEAGE_INVALID")
    else:
        demand(manifest.get("inherited_initial_weights_sha256")==G3_SHA and
               manifest.get("parent_manifest_sha256")==G3_MANIFEST and
               manifest.get("trained_steps")==8, "G4_LINEAGE_INVALID")
    model=clean_model(torch)
    expected=dict(sorted(model.state_dict().items()))
    items=manifest.get("tensors")
    demand(isinstance(items,list) and len(items)==len(expected),
           "TENSOR_SCHEMA_MISSING")
    offset=0
    converted={}
    for desc,(name,tensor) in zip(items,expected.items()):
        length=tensor.numel()*4
        demand(desc=={"name":name,"shape":list(tensor.shape),
                      "offset":offset,"bytes":length},
               "TENSOR_NAME_SHAPE_OR_OFFSET_INVALID")
        vec=array("f")
        vec.frombytes(raw[offset:offset+length])
        demand(len(vec)==tensor.numel() and
               all(math.isfinite(v) for v in vec), "NONFINITE_WEIGHT")
        converted[name]=torch.tensor(vec.tolist(),dtype=torch.float32).reshape(tensor.shape)
        offset+=length
    demand(offset==len(raw), "WEIGHT_TRAILING_BYTES")
    model.load_state_dict(converted,strict=True)
    model.eval()
    return model


def load_fixed_models(torch, g3_zip, g4_zip, baseline14_zip):
    g3m,g3w=read_zip_small(g3_zip,"")
    # Require exactly four G4 files; the archive may include only the JSON
    # research receipt from the original trial as an extra.
    p=Path(g4_zip)
    demand(p.is_file() and not p.is_symlink() and
           256 < p.stat().st_size < 2000000, "INVALID_G4_ARCHIVE")
    models={"g3":restore_model(torch,g3m,g3w,"g3","g3")}
    with ZipFile(p) as z:
        expected={f"{a}/{b}" for a in G4 for b in ("manifest.json","weights.f32")}
        allowed=expected|{"physarum-development-trial.json"}
        demand(set(z.namelist()) == allowed, "G4_ARCHIVE_CONTENTS_CHANGED")
        for member in z.infolist():
            demand(0 < member.file_size <= 500000 and
                   member.compress_size > 0, "G4_ARCHIVE_OVERSIZED")
        for name in ("control","physarum"):
            meta=json.loads(z.read(f"{name}/manifest.json").decode())
            raw=z.read(f"{name}/weights.f32")
            models[name]=restore_model(torch,meta,raw,name,"g4_"+name)
    sealed14=Path(baseline14_zip)
    demand(sealed14.is_file() and not sealed14.is_symlink() and
           sealed14.stat().st_size < 2000000,
           "MISSING_COSTMATCHED14_ARTIFACT")
    with ZipFile(sealed14) as z:
        demand(set(z.namelist())=={
            "baseline14/manifest.json","baseline14/weights.f32",
            "full-cost-receipt.json"} and len(z.namelist())==3,
            "COSTMATCHED14_ARTIFACT_CONTENT_CHANGED")
        for item in z.infolist():
            demand(0 < item.file_size <= 500000,
                   "OVERSIZED_COSTMATCHED14_MEMBER")
        manifest=json.loads(z.read("baseline14/manifest.json").decode())
        raw=z.read("baseline14/weights.f32")
        cost_receipt=json.loads(z.read("full-cost-receipt.json").decode())
    demand(cost_receipt.get("baseline14_weights_sha256")==BUDGET14_SHA and
           cost_receipt.get("baseline14_manifest_sha256")==BUDGET14_MANIFEST and
           cost_receipt.get("external_exam_bytes_read") is False,
           "COSTMATCHED14_NOT_FROZEN_BEFORE_EXTERNAL")
    models["baseline14"]=restore_model(
        torch,manifest,raw,"baseline14","g4_fixed_budget14")
    return models


def load_protocol(policy_path):
    contract=load_json(policy_path)
    demand(contract.get("schema")==POLICY and
           contract.get("frozen_g3_sha256")==G3_SHA and
           contract.get("frozen_g4_weights")=={
               k:v["weights"] for k,v in G4.items()} and
           contract.get("frozen_budget14_weights_sha256")==BUDGET14_SHA and
           contract.get("score_metric")==
           "32_EVENLY_SPACED_CONTEXT24_NEXT_BYTE_CE_EQUAL_FILE_WEIGHT" and
           contract.get("min_source_families")==MIN_FAMILIES and
           contract.get("min_files")==MIN_TASKS and
           contract.get("min_relative_physarum_gain")==MIN_RELATIVE_GAIN and
           contract.get("min_gain_per_cpu_ratio")==MIN_EFFICIENCY_GAIN and
           contract.get("max_family_loss_regression")==MAX_FAMILY_REGRESSION and
           contract.get("one_sided_family_sign_p_max")==MAX_SIGN_P and
           contract.get("external_custodian_status")=="AWAITING_KEY_AND_SEALED_TASKS" and
           contract.get("production_authority") is False,
           "POST_HOC_PROTOCOL_CHANGE")
    return contract


def verify_signature(pubkey, message, signature):
    """Ed25519 authenticates bytes, not the real-world independence of signer."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key=base64.b64decode(pubkey,validate=True)
    demand(len(key)==32,"INVALID_ED25519_PUBKEY")
    sig=base64.b64decode(signature,validate=True)
    demand(len(sig)==64,"INVALID_ED25519_SIGNATURE")
    Ed25519PublicKey.from_public_bytes(key).verify(sig,canonical(message))
    return hashlib.sha256(key).hexdigest()


def verify_commitment(contract, challenge, precommit, pubkey, signature,
                      expected_fingerprint):
    demand(challenge.get("schema")==CHALLENGE and
           challenge.get("protocol_sha256")==sha(contract) and
           challenge.get("challenge_id") and
           challenge.get("made_after_model_freeze") is True and
           challenge.get("task_data_stays_with_external_custodian") is True,
           "INVALID_EXTERNAL_CHALLENGE")
    demand(precommit.get("schema")==PRECOMMIT and
           precommit.get("challenge_sha256")==sha(challenge) and
           precommit.get("protocol_sha256")==sha(contract) and
           precommit.get("public_external_commit_url") and
           precommit.get("external_custodian_identity") and
           precommit.get("independent_organization") and
           precommit.get("published_before_exam") is True,
           "MISSING_PUBLIC_PRIOR_COMMIT")
    fingerprint=verify_signature(pubkey,challenge,signature)
    demand(fingerprint==expected_fingerprint and
           bool(HASH64.fullmatch(fingerprint)),
           "UNREGISTERED_CUSTODIAN_FINGERPRINT")
    files=challenge.get("files")
    demand(isinstance(files,list) and MIN_TASKS<=len(files)<=64,
           "INVALID_HIDDEN_SAMPLE_SIZE")
    families={}
    seen_paths=set()
    seen_hash=set()
    for item in files:
        demand(isinstance(item,dict) and
               set(item)=={"path","family","sha256","bytes"} and
               isinstance(item["family"],str) and
               2<=len(item["family"])<=60 and
               isinstance(item["path"],str) and
               item["path"].endswith(".py") and
               item["path"].startswith("tasks/") and
               ".." not in item["path"].split("/") and
               4096<=item["bytes"]<=MAX_SOURCE_SIZE and
               bool(HASH64.fullmatch(item["sha256"])),
               "INVALID_HIDDEN_TASK_MANIFEST")
        demand(item["path"] not in seen_paths and
               item["sha256"] not in seen_hash, "DUPLICATED_TEST_SAMPLE")
        seen_paths.add(item["path"]);seen_hash.add(item["sha256"])
        families[item["family"]]=families.get(item["family"],0)+1
    demand(len(families)>=MIN_FAMILIES and
           all(n>=2 for n in families.values()),
           "INSUFFICIENT_INDEPENDENT_TASK_FAMILIES")
    return fingerprint


def measured_loss(torch, model, raw):
    """Original evaluation target, but independent 32-window scorer."""
    n=len(raw)
    demand(n > BLOCK+40,"TOO_SHORT_FOR_HIDDEN_EXAM")
    starts=[i*(n-BLOCK-1)//(WINDOWS-1) for i in range(WINDOWS)]
    data=torch.tensor(list(raw),dtype=torch.long)
    x=torch.stack([data[i:i+BLOCK] for i in starts])
    y=torch.stack([data[i+1:i+BLOCK+1] for i in starts])
    start_cpu=time.process_time_ns()
    start_wall=time.perf_counter_ns()
    with torch.inference_mode():
        logits=model(x)
        loss=torch.nn.functional.cross_entropy(
            logits.reshape(-1,256),y.reshape(-1))
    cpu=(time.process_time_ns()-start_cpu)/1e9
    wall=(time.perf_counter_ns()-start_wall)/1e9
    score=float(loss.item())
    demand(math.isfinite(score) and cpu>=0 and wall>=0,
           "NONFINITE_OR_INVALID_SCORE")
    return {"cross_entropy":score,"inference_cpu_seconds":cpu,
            "inference_wall_seconds":wall}


def signed_cost_ledger(cost_path, contract, precommit, pubkey,
                       signature, fingerprint):
    data=load_json(cost_path)
    demand(data.get("schema")==COST and
           data.get("protocol_sha256")==sha(contract) and
           data.get("challenge_sha256")==precommit["challenge_sha256"] and
           data.get("g4_weights_sha256")=={
               k:v["weights"] for k,v in G4.items()} and
           data.get("measured_on_same_cpu") is True and
           data.get("full_probe_steps")==6 and
           data.get("per_sibling_steps")==8 and
           data.get("costmatched_baseline_steps")==14 and
           data.get("baseline14_weights_sha256")==BUDGET14_SHA and
           data.get("no_cost_imputation") is True and
           data.get("hardware_description") and
           data.get("measurement_method")=="CPU_PROCESS_TIME_SECONDS_REPLAY",
           "UNVERIFIABLE_FULL_SEARCH_COST")
    fields=("control_training_cpu_seconds","physarum_probes_cpu_seconds",
            "physarum_network_search_cpu_seconds",
            "physarum_training_cpu_seconds",
            "baseline14_training_cpu_seconds")
    for f in fields:
        demand(type(data.get(f)) in (float,int) and
               math.isfinite(data[f]) and data[f]>0,
               "INVALID_COST_VALUE")
    demand(verify_signature(pubkey,data,signature)==fingerprint,
           "COST_NOT_SIGNED_BY_REGISTERED_CUSTODIAN")
    return data


def sign_pvalue(n,wins):
    demand(0<=wins<=n and n>=1,"INVALID_FAMILY_SIGN_TEST")
    return sum(math.comb(n,k) for k in range(wins,n+1))/(2**n)


def grade(files,cost,contract):
    """Both old control and 14-step costmatched control must be beaten."""
    names=("g3","control","baseline14","physarum")
    families=sorted(set(x["family"] for x in files))
    means={k:sum(x[k]["cross_entropy"] for x in files)/len(files)
           for k in names}
    family=[]
    for fam in families:
        group=[x for x in files if x["family"]==fam]
        row={"family":fam}
        row.update({name:sum(x[name]["cross_entropy"] for x in group)/len(group)
                    for name in means})
        family.append(row)
    wins=sum(x["physarum"]<x["baseline14"] for x in family)
    p=sign_pvalue(len(family),wins)
    inference={k:sum(x[k]["inference_cpu_seconds"] for x in files)
               for k in means}
    control8_cost=cost["control_training_cpu_seconds"]+inference["control"]
    baseline14_cost=cost["baseline14_training_cpu_seconds"]+inference["baseline14"]
    phys_cost=(cost["physarum_probes_cpu_seconds"]+
               cost["physarum_network_search_cpu_seconds"]+
               cost["physarum_training_cpu_seconds"]+
               inference["physarum"])
    improvement8=(means["control"]-means["physarum"])/means["control"]
    improvement14=(means["baseline14"]-means["physarum"])/means["baseline14"]
    per_family=all(
        x["physarum"]<=x["control"]+MAX_FAMILY_REGRESSION and
        x["physarum"]<=x["baseline14"]+MAX_FAMILY_REGRESSION
        for x in family)
    gain14=means["g3"]-means["baseline14"]
    gain8=means["g3"]-means["control"]
    gainphys=means["g3"]-means["physarum"]
    efficiency14=max(0.0,gain14)/baseline14_cost
    efficiency8=max(0.0,gain8)/control8_cost
    efficiency_phys=max(0.0,gainphys)/phys_cost
    # The cost-aware success must beat the stronger fair-budget baseline,
    # not merely the cheap-to-train old 8-step baseline.
    ratio=(efficiency_phys/efficiency14 if efficiency14>0 else 0.0)
    pass_all=(improvement14>=MIN_RELATIVE_GAIN and
              improvement8>=MIN_RELATIVE_GAIN and
              per_family and p<=MAX_SIGN_P and
              gainphys>0 and gain14>0 and gain8>0 and
              ratio>=MIN_EFFICIENCY_GAIN)
    return {
        "statistical_status":("PASS_COSTMATCHED_14STEP_EXTERNAL_GAIN"
                              if pass_all else "NO_COSTMATCHED_14STEP_EXTERNAL_GAIN"),
        "means":means,
        "family":family,
        "family_sign_test_wins_over_14step":wins,
        "family_sign_test_total":len(family),
        "family_sign_test_one_sided_p":p,
        "relative_loss_improvement_vs_old_control8":improvement8,
        "relative_loss_improvement_vs_14step_baseline":improvement14,
        "all_families_nonregressing_vs_both_controls":per_family,
        "total_control8_cpu_seconds":control8_cost,
        "total_baseline14_cpu_seconds":baseline14_cost,
        "total_physarum_cpu_seconds":phys_cost,
        "inference_cpu_seconds":inference,
        "gain_per_cpu_vs_g3_control8":efficiency8,
        "gain_per_cpu_vs_g3_baseline14":efficiency14,
        "gain_per_cpu_vs_g3_physarum":efficiency_phys,
        "physarum_vs_costmatched_efficiency_ratio":ratio,
        "requirement_both_controls_beaten":
            improvement8>=MIN_RELATIVE_GAIN and
            improvement14>=MIN_RELATIVE_GAIN,
        "requirement_family_stability":per_family,
        "requirement_family_sign_test":p<=MAX_SIGN_P,
        "requirement_cost_efficiency":ratio>=MIN_EFFICIENCY_GAIN,
    }


def run(args):
    contract=load_protocol(args.policy)
    demand(args.expected_fingerprint and
           bool(HASH64.fullmatch(args.expected_fingerprint)),
           "EXTERNALLY_REGISTERED_KEY_FINGERPRINT_REQUIRED")
    challenge=load_json(args.challenge)
    precommit=load_json(args.precommit)
    pubkey=Path(args.public_key).read_text().strip()
    signature=Path(args.challenge_signature).read_text().strip()
    fingerprint=verify_commitment(contract,challenge,precommit,pubkey,
                                  signature,args.expected_fingerprint)
    cost=signed_cost_ledger(args.cost,contract,precommit,pubkey,
                            Path(args.cost_signature).read_text().strip(),
                            fingerprint)
    import torch
    torch.set_num_threads(1)
    models=load_fixed_models(torch,args.g3_zip,args.g4_zip,
                             args.baseline14_zip)
    tasks_root=Path(args.tasks_dir).resolve(strict=True)
    results=[]
    for item in challenge["files"]:
        p=tasks_root/item["path"]
        demand(p.is_file() and not p.is_symlink() and
               p.resolve().is_relative_to(tasks_root) and
               p.stat().st_size==item["bytes"] and
               p.stat().st_size<=MAX_SOURCE_SIZE,
               "SEALED_HIDDEN_TASK_FILE_MISSING")
        data=p.read_bytes()
        demand(hashlib.sha256(data).hexdigest()==item["sha256"],
               "HIDDEN_DATA_COMMITMENT_TAMPER")
        row={"family":item["family"],"source_sha256":item["sha256"],
             "bytes":len(data)}
        for name,m in models.items():
            row[name]=measured_loss(torch,m,data)
        results.append(row)
    graded=grade(results,cost,contract)
    result=seal({
        "schema":SCHEMA,
        "protocol_sha256":sha(contract),
        "challenge_sha256":sha(challenge),
        "custodian_key_fingerprint":fingerprint,
        "cost_ledger_sha256":sha(cost),
        "models": {"g3":G3_SHA,
                   "baseline14":BUDGET14_SHA,
                   **{k:v["weights"] for k,v in G4.items()}},
        "file_hash_only_results":results,
        "grade":graded,
        "ram_peak_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cryptographic_signature_verified":True,
        "external_custodian_real_world_identity_independently_audited":False,
        "precommit_publication_time_independently_audited":False,
        "external_independent_replication_proven":False,
        "production_admission_allowed":False,
        "promotion_gate":"HOLD_PENDING_INDEPENDENT_IDENTITY_AND_PRECOMMIT_AUDIT",
        "private_task_bytes_published":False,
    })
    safe_write(args.out,result)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--policy",required=True)
    p.add_argument("--g3-zip",required=True)
    p.add_argument("--g4-zip",required=True)
    p.add_argument("--baseline14-zip",required=True)
    p.add_argument("--challenge",required=True)
    p.add_argument("--precommit",required=True)
    p.add_argument("--public-key",required=True)
    p.add_argument("--expected-fingerprint",required=True)
    p.add_argument("--challenge-signature",required=True)
    p.add_argument("--cost",required=True)
    p.add_argument("--cost-signature",required=True)
    p.add_argument("--tasks-dir",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    receipt=run(a)
    print(json.dumps({
        "status":receipt["grade"]["statistical_status"],
        "cryptographic_signature_verified":True,
        "external_independent_replication_proven":False,
        "promotion_gate":receipt["promotion_gate"],
        "receipt_sha256":receipt["receipt_sha256"]
    },sort_keys=True))


if __name__=="__main__":
    main()
