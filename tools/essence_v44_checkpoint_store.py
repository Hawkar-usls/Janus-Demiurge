#!/usr/bin/env python3
"""Persist exactly sealed research G4 tensors into GitHub state branch once.

Actions artifacts expire. A one-time GitHub-only bootstrap copies the
original SHA-locked FP32 bytes into the data-only essence-actions-state branch,
so future short-lived Actions runners can wake and load them without the
90-day artifact URL. Never overwrites or rewrites changed existing weights.
No unpickling and no imported model/trainer.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from tools.essence_v44_actions_async import immutable, seal, require

SCHEMA="janus.essence.github_checkpoint_store/4.4"
EXPECTED={
  "baseline14":{
    "weights_sha256":"a0a8a878fd784235e390f441ec192d973e079714321b5d8a6b2cbb343d3bd174",
    "manifest_sha256":"49158892f8dc1674897465d84e45ecf02f19d96d79b72ae3aceb167599c61f5a",
    "generation":"g4_fixed_budget14",
    "source_actions_run":43652825898,
  },
  "physarum":{
    "weights_sha256":"dfbe1214f6e6f954b3f999d7d8802c89e2aa5fe45e75ffe9a68a73d76953683f",
    "manifest_sha256":"a8397385b2703d5cca7b15b9b12626960d8105e976f10b628451fe330dbcf003",
    "generation":"g4_physarum",
    "source_actions_run":43650540561,
  },
}
G3_SHA="7ae346fff869dc14eec9e32ffa0e00419d98faa2150f79a763e927e0fc2cd299"
G3_MANIFEST="ed63cc6f143a71e00a3867d1b465be8a6c5f4aa061f20dbd37f85a007e8cd3e7"


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode()


def read_one(root,label):
    p=Path(root)
    require(label in EXPECTED,"UNKNOWN_CHECKPOINT_STORE")
    expect=EXPECTED[label]
    manifest=p/"manifest.json"
    weights=p/"weights.f32"
    for f in (manifest,weights):
        require(f.is_file() and not f.is_symlink() and
                100<=f.stat().st_size<=500000,
                "UNSAFE_OR_MISSING_SEALED_CHECKPOINT")
    raw=weights.read_bytes()
    m=json.loads(manifest.read_text("utf-8"))
    actual=hashlib.sha256(raw).hexdigest()
    require(actual==expect["weights_sha256"] and
            m.get("weights_sha256")==actual and
            m.get("weights_bytes")==len(raw) and
            m.get("checkpoint_format")=="STRICT_FLOAT32_ARRAY_NO_PICKLE" and
            m.get("generation")==expect["generation"] and
            m.get("parent_manifest_sha256")==G3_MANIFEST and
            m.get("inherited_initial_weights_sha256")==G3_SHA and
            m.get("production_authority") is False,
            "FROZEN_TENSOR_OR_LINEAGE_HASH_FAILURE")
    body={key:value for key,value in m.items() if key!="manifest_sha256"}
    require(m.get("manifest_sha256")==expect["manifest_sha256"] and
            hashlib.sha256(canonical(body)).hexdigest()==expect["manifest_sha256"],
            "CHECKPOINT_MANIFEST_HASH_FAILURE")
    return {"generation":expect["generation"],
            "weights_sha256":actual,
            "manifest_sha256":expect["manifest_sha256"],
            "weights_bytes":len(raw)}


def verify_store(store):
    root=Path(store)
    require(root.is_dir() and not root.is_symlink(),
            "SEALED_STORE_NOT_READY")
    result={key:read_one(root/key,key) for key in EXPECTED}
    meta=root/"index.json"
    require(meta.is_file() and not meta.is_symlink(),"STORE_INDEX_MISSING")
    index=json.loads(meta.read_text("utf-8"))
    require(index.get("schema")==SCHEMA and
            index.get("model_digests")==result and
            index.get("production_authority") is False and
            index.get("trainable_weights") is False,
            "STORE_INDEX_NOT_TRUSTED")
    return result


def expected_index(model_digests):
    return {
        "schema":SCHEMA,
        "model_digests":model_digests,
        "artifacts_originally_from":{
          label:info["source_actions_run"] for label,info in EXPECTED.items()},
        "status":"RESEARCH_ONLY_SHA_LOCKED",
        "production_authority":False,
        "trainable_weights":False,
        "source_of_truth":"original_GitHub_Actions_fp32_byte_artifacts",
    }


def bootstrap(store,source_fixed,source_physarum,out):
    target=Path(store)
    require(not target.is_symlink(),"STORE_PATH_SYMLINK_REFUSED")
    sources=((Path(source_fixed),"baseline14"),
             (Path(source_physarum),"physarum"))
    fixed=read_one(source_fixed,"baseline14")
    phys=read_one(source_physarum,"physarum")
    model_digests={"baseline14":fixed,"physarum":phys}
    index=expected_index(model_digests)

    if target.exists():
        require(target.is_dir(),"UNSAFE_MODEL_STORE")
        try:
            done=verify_store(target)
        except ValueError:
            # Recover ONLY the exact original JSON files missing because
            # repo-wide *.json in .gitignore excluded them from git add.
            # Existing FP32 bytes must match their frozen SHA unchanged.
            for source,label in sources:
                dest=target/label
                require(dest.is_dir() and not dest.is_symlink(),
                        "INCOMPLETE_STORE_MODEL_DIRECTORY")
                weight=dest/"weights.f32"
                require(weight.is_file() and not weight.is_symlink() and
                        hashlib.sha256(weight.read_bytes()).hexdigest()==
                        EXPECTED[label]["weights_sha256"],
                        "INCOMPLETE_STORE_WEIGHT_IDENTITY_CHANGED")
                require(weight.read_bytes()==(source/"weights.f32").read_bytes(),
                        "RECOVERED_WEIGHT_BYTES_NOT_IDENTICAL")
                src_manifest=source/"manifest.json"
                dst_manifest=dest/"manifest.json"
                require(not dst_manifest.is_symlink(),
                        "UNSAFE_STORED_MANIFEST_SYMLINK")
                if dst_manifest.exists():
                    require(dst_manifest.read_bytes()==src_manifest.read_bytes(),
                            "EXISTING_MODEL_MANIFEST_CANNOT_BE_REWRITTEN")
                else:
                    shutil.copyfile(src_manifest,dst_manifest)
            indexed=target/"index.json"
            require(not indexed.is_symlink(),"UNSAFE_STORE_INDEX_SYMLINK")
            if indexed.exists():
                require(json.loads(indexed.read_text("utf-8"))==index,
                        "EXISTING_STORE_INDEX_CANNOT_BE_REWRITTEN")
            else:
                immutable(indexed,index)
            done=verify_store(target)
            require(done==model_digests,"RESTORED_MODEL_STORE_NOT_SOURCE_IDENTICAL")
            status="RESTORED_ONLY_MISSING_JSON_FILES_UNDER_EXACT_ORIGINAL_WEIGHT_HASHES"
        else:
            status="ALREADY_PRESENT_SHA_VERIFIED"
        immutable(out,seal({
            "schema":SCHEMA,
            "status":status,
            "model_digests":done,
            "production_authority":False,
            "trainable_weights":False,
            "external_independent_validation":False,
        }))
        return done
    target.mkdir(parents=True)
    for source,label in sources:
        dest=target/label
        dest.mkdir(mode=0o700)
        for filename in ("manifest.json","weights.f32"):
            shutil.copyfile(source/filename,dest/filename)
    immutable(target/"index.json",index)
    require(verify_store(target)==model_digests,
            "PERSISTENT_CHECKPOINT_STORE_RECHECK_FAILED")
    immutable(out,seal({
        "schema":SCHEMA,
        "status":"BOOTSTRAP_SEALED_RESEARCH_WEIGHTS_COMPLETE",
        "model_digests":model_digests,
        "production_authority":False,
        "trainable_weights":False,
        "external_independent_validation":False,
    }))
    return model_digests


def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    a=sub.add_parser("verify")
    a.add_argument("--store",required=True)
    a=sub.add_parser("bootstrap")
    a.add_argument("--store",required=True)
    a.add_argument("--source-fixed",required=True)
    a.add_argument("--source-physarum",required=True)
    a.add_argument("--out",required=True)
    args=p.parse_args()
    if args.mode=="verify":
        result=verify_store(args.store)
    else:
        result=bootstrap(args.store,args.source_fixed,args.source_physarum,args.out)
    print(json.dumps({"status":"SHA_VERIFIED","models":result,
                      "production_authority":False},sort_keys=True))


if __name__=="__main__":
    main()
