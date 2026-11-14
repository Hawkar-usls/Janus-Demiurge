#!/usr/bin/env python3
"""ESSENCE v3.8: real two-generation CODEX GPT neural weight inheritance.

Self-contained bounded experiment with a pre-committed source-blob holdout lock,
strict train/holdout separation, safe tensor-only float32 checkpoints, parent
lineage checks, and a one-shot frozen-parent/child paired exam. No production
promotion, hidden-test retuning, optimizer unpickling, or NAS interactions.
"""
from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import sys

from tools import essence_v37_codex_gpt as core

SCHEMA = "janus.essence.neural_inheritance/3.8"
FREEZE = "janus.essence.frozen_neural_cohort/3.8"
RECEIPT = "janus.essence.neural_cohort_freeze_receipt/3.8"
CHECKPOINT = "janus.essence.float32_weight_checkpoint/3.8"
EXAM = "janus.essence.frozen_two_generation_exam/3.8"
LOCK_REL = "research/essence/codex_v38/frozen_cohort.json"
ROLE_FILES = {
    "train": tuple(core.SPLIT["train"]),
    "val": tuple(core.SPLIT["val"]),
    "holdout": ("tools/essence_v22_source_watch.py",
                "tools/essence_v21_curriculum_sentinel.py"),
}
STEPS = {"parent": 8, "child": 8}
MAX_WEIGHT_BYTES = 2_000_000
MAX_JSON_BYTES = 20_000
MIN_GAIN = 0.0001


def require(condition, code):
    if not condition:
        raise ValueError(code)


def canonical(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(canonical(data)).hexdigest()


def sealed(data, field="receipt_sha256"):
    return dict(data, **{field: sha(data)})


def check_seal(obj, field="receipt_sha256"):
    require(isinstance(obj, dict) and obj.get(field) == sha({
        k:v for k,v in obj.items() if k != field
    }), "INVALID_SHA256_RECEIPT")
    return obj


def read_json(path):
    p = Path(path)
    require(p.is_file() and not p.is_symlink() and
            2 <= p.stat().st_size <= MAX_JSON_BYTES, "INVALID_JSON_INPUT")
    return json.loads(p.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON")))


def immutable_json(path, obj):
    p = Path(path)
    require(not p.exists() and not p.is_symlink(),
            "IMMUTABLE_RECEIPT_COLLISION")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n",
                 encoding="utf-8")


def blob_sha1(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" +
                        content).hexdigest()


def safe_source(root, path, *, max_bytes=core.MAX_FILE_BYTES):
    base = Path(root).resolve(strict=True)
    require(isinstance(path, str) and
            path.startswith("tools/") and path.endswith(".py") and
            ".." not in path.split("/"), "INVALID_ROLE_PATH")
    p = base / path
    require(p.is_file() and not p.is_symlink() and
            p.resolve().is_relative_to(base) and
            128 <= p.stat().st_size <= max_bytes, "INVALID_SOURCE_FILE")
    return p.read_bytes()


def inspect_lock(root, path):
    lock = read_json(path)
    require(lock.get("schema") == FREEZE and
            lock.get("experimental_admission") == "RESEARCH_ONLY" and
            lock.get("external_holdout") is False and
            lock.get("frozen_before_parent_training") is True,
            "INVALID_PRE_REGISTERED_LOCK")
    require(lock.get("criteria") == {
        "min_child_loss_decrease": MIN_GAIN,
        "fail_closed_if_unavailable": True,
        "no_reselection_or_retry_after_exam": True
    } and lock.get("steps") == STEPS,
            "POST_HOC_CRITERION_OR_STEPS_DRIFT")
    rows = lock.get("roles")
    require(isinstance(rows, dict) and set(rows) == set(ROLE_FILES),
            "INVALID_ROLE_SET")
    seen = set()
    digest_set = set()
    checked = {}
    for role in ("train", "val", "holdout"):
        entries = rows[role]
        require(isinstance(entries, list) and
                [r.get("path") for r in entries if isinstance(r, dict)] ==
                list(ROLE_FILES[role]) and
                len(entries) == len(ROLE_FILES[role]),
                "UNREVIEWED_FROZEN_PATH")
        checked[role] = []
        for item in entries:
            require(isinstance(item, dict) and
                    set(item) == {"path", "git_blob_sha1"} and
                    isinstance(item["git_blob_sha1"], str) and
                    len(item["git_blob_sha1"]) == 40,
                    "INVALID_GIT_BLOB_LOCK")
            name = item["path"]
            require(name not in seen, "CROSS_SPLIT_PATH_LEAKAGE")
            seen.add(name)
            data = safe_source(root, name)
            require(blob_sha1(data) == item["git_blob_sha1"],
                    "FROZEN_SOURCE_BLOB_CHANGED")
            digest = hashlib.sha256(data).hexdigest()
            require(digest not in digest_set, "CROSS_SPLIT_CONTENT_LEAKAGE")
            digest_set.add(digest)
            checked[role].append({
                "path": name, "git_blob_sha1": item["git_blob_sha1"],
                "source_sha256": digest, "bytes": len(data),
            })
    receipt = sealed({
        "schema": RECEIPT,
        "lock_sha256": sha(lock),
        "roles": checked,
        "steps": STEPS,
        "criterion_min_decrease": MIN_GAIN,
        "holdout_evaluated": False,
        "source_blob_checks_pass": True,
        "external_independent_cohort": False,
        "production_authority": False,
    })
    return receipt


def check_freeze(receipt):
    check_seal(receipt)
    require(receipt.get("schema") == RECEIPT and
            receipt.get("source_blob_checks_pass") is True and
            receipt.get("holdout_evaluated") is False and
            receipt.get("production_authority") is False and
            receipt.get("steps") == STEPS and
            receipt.get("criterion_min_decrease") == MIN_GAIN and
            set(receipt.get("roles", {})) == set(ROLE_FILES),
            "UNTRUSTED_FREEZE_RECEIPT")
    for role in ROLE_FILES:
        require([v.get("path") for v in receipt["roles"][role]] ==
                list(ROLE_FILES[role]), "FROZEN_ROLE_DRIFT")
    return receipt


def train_bytes(root, freeze):
    # No holdout source read in this function or the entire train path.
    content, files = core.read_corpus(root)
    for role in ("train", "val"):
        expected = freeze["roles"][role]
        require([(v["path"], v["sha256"], v["bytes"]) for v in files[role]]
                == [(v["path"], v["source_sha256"], v["bytes"])
                    for v in expected], "TRAIN_VALIDATION_FREEZE_DRIFT")
    import torch
    return (torch.tensor(list(content["train"]), dtype=torch.long),
            torch.tensor(list(content["val"]), dtype=torch.long))


def weight_bytes(torch, model):
    require(sys.byteorder == "little", "CPU_ENDIAN_NOT_SUPPORTED")
    parts, desc, offset = [], [], 0
    for name, tensor in sorted(model.state_dict().items()):
        values = tensor.detach().float().cpu().contiguous()
        require(bool(torch.isfinite(values).all()), "NONFINITE_WEIGHT")
        raw = array("f", values.reshape(-1).tolist()).tobytes()
        require(len(raw) == 4 * values.numel(), "WRONG_FLOAT_ENCODING")
        desc.append({"name": name, "shape": list(values.shape),
                     "offset": offset, "bytes": len(raw)})
        parts.append(raw)
        offset += len(raw)
    require(0 < offset <= MAX_WEIGHT_BYTES, "CHECKPOINT_TOO_LARGE")
    return b"".join(parts), desc


def save_checkpoint(directory, torch, model, *, generation, freeze,
                    initial_weights_sha256, parent_manifest_sha256,
                    trained_steps, rejected):
    p = Path(directory)
    require(not p.exists() and not p.is_symlink(),
            "CHECKPOINT_DIRECTORY_ALREADY_EXISTS")
    raw, desc = weight_bytes(torch, model)
    require(trained_steps > 0 and rejected < trained_steps,
            "NO_COMPLETED_GRADIENT_STEPS")
    p.mkdir(parents=True)
    (p / "weights.f32").write_bytes(raw)
    manifest = sealed({
        "schema": CHECKPOINT,
        "generation": generation,
        "parent_manifest_sha256": parent_manifest_sha256,
        "inherited_initial_weights_sha256": initial_weights_sha256,
        "weights_sha256": hashlib.sha256(raw).hexdigest(),
        "weights_bytes": len(raw),
        "tensors": desc,
        "freeze_receipt_sha256": freeze["receipt_sha256"],
        "trained_steps": trained_steps,
        "rejected_gradient_steps": rejected,
        "optimizer_state_inherited": False,
        "model_source": core.SOURCE["source_sha256"],
        "checkpoint_format": "STRICT_FLOAT32_ARRAY_NO_PICKLE",
        "production_authority": False,
    }, field="manifest_sha256")
    immutable_json(p / "manifest.json", manifest)
    return manifest


def load_checkpoint(path, torch, expected_freeze):
    p = Path(path)
    require(p.is_dir() and not p.is_symlink(), "INVALID_CHECKPOINT_DIR")
    manifest = read_json(p / "manifest.json")
    check_seal(manifest, "manifest_sha256")
    require(manifest.get("schema") == CHECKPOINT and
            manifest.get("checkpoint_format") == "STRICT_FLOAT32_ARRAY_NO_PICKLE" and
            manifest.get("production_authority") is False and
            manifest.get("model_source") == core.SOURCE["source_sha256"] and
            manifest.get("freeze_receipt_sha256") == expected_freeze["receipt_sha256"],
            "CHECKPOINT_PROVENANCE_INVALID")
    weights = p / "weights.f32"
    require(weights.is_file() and not weights.is_symlink() and
            0 < weights.stat().st_size <= MAX_WEIGHT_BYTES and
            weights.stat().st_size == manifest.get("weights_bytes"),
            "CHECKPOINT_BOUNDS")
    raw = weights.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == manifest["weights_sha256"],
            "CHECKPOINT_BYTES_TAMPERED")
    model = core.new_model(torch)
    expected = dict(sorted(model.state_dict().items()))
    desc = manifest.get("tensors")
    require(isinstance(desc, list) and len(desc) == len(expected),
            "UNTRUSTED_TENSOR_SCHEMA")
    recovered, offset = {}, 0
    for item, (name, tensor) in zip(desc, expected.items()):
        shape = list(tensor.shape)
        count = tensor.numel()
        require(item == {"name": name, "shape": shape,
                         "offset": offset, "bytes": count * 4},
                "TENSOR_SHAPE_OR_OFFSET_TAMPERED")
        arr = array("f")
        arr.frombytes(raw[offset:offset + 4 * count])
        require(len(arr) == count and all(math.isfinite(v) for v in arr),
                "CHECKPOINT_NONFINITE_TENSOR")
        recovered[name] = torch.tensor(arr.tolist(), dtype=torch.float32).reshape(shape)
        offset += count * 4
    require(offset == len(raw), "CHECKPOINT_TRAILING_BYTES")
    model.load_state_dict(recovered, strict=True)
    encoded, _ = weight_bytes(torch, model)
    require(hashlib.sha256(encoded).hexdigest() == manifest["weights_sha256"],
            "WEIGHT_LOAD_NOT_IDENTICAL")
    return model, manifest


def training(root, freeze, *, generation, output, parent=None):
    require(generation in STEPS, "UNSUPPORTED_GENERATION")
    check_freeze(freeze)
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(3801 if generation == "parent" else 3802)
    train, val = train_bytes(root, freeze)
    model = core.new_model(torch)
    parent_digest = None
    if generation == "child":
        require(parent is not None, "PARENT_CHECKPOINT_REQUIRED")
        model, prior = load_checkpoint(parent, torch, freeze)
        require(prior["generation"] == "parent" and
                prior["parent_manifest_sha256"] is None and
                prior["trained_steps"] == STEPS["parent"],
                "INVALID_PARENT_GENERATION")
        parent_digest = prior["manifest_sha256"]
    else:
        require(parent is None, "PARENT_NOT_ALLOWED_FOR_PARENT")
    starting, _ = weight_bytes(torch, model)
    initial = hashlib.sha256(starting).hexdigest()
    if generation == "child":
        require(initial == prior["weights_sha256"], "LOST_PARENT_WEIGHTS")
    opt = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.01)
    rejected = 0
    for k in range(STEPS[generation]):
        model.train()
        ix = torch.randint(len(train) - core.BLOCK - 1, (4,))
        x = torch.stack([train[i:i+core.BLOCK] for i in ix])
        y = torch.stack([train[i+1:i+core.BLOCK+1] for i in ix])
        opt.zero_grad(set_to_none=True)
        logits = model(x)
        loss = torch.nn.functional.cross_entropy(logits.reshape(-1, 256),
                                                  y.reshape(-1))
        if not bool(torch.isfinite(loss)):
            rejected += 1
            continue
        loss.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
            rejected += 1
            opt.zero_grad(set_to_none=True)
            continue
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        if not math.isfinite(float(norm)):
            rejected += 1
            opt.zero_grad(set_to_none=True)
            continue
        opt.step()
    ending, _ = weight_bytes(torch, model)
    require(hashlib.sha256(ending).hexdigest() != initial, "NO_NEURAL_UPDATE")
    validation_loss = core.val_loss(torch, model, val)
    manifest = save_checkpoint(output, torch, model, generation=generation,
                               freeze=freeze,
                               initial_weights_sha256=initial,
                               parent_manifest_sha256=parent_digest,
                               trained_steps=STEPS[generation], rejected=rejected)
    return sealed({
        "schema": SCHEMA,
        "generation": generation,
        "freeze_receipt_sha256": freeze["receipt_sha256"],
        "checkpoint_manifest_sha256": manifest["manifest_sha256"],
        "weights_sha256": manifest["weights_sha256"],
        "inherited_initial_weights_sha256": initial,
        "parent_checkpoint_manifest_sha256": parent_digest,
        "development_val_loss": validation_loss,
        "holdout_accessed_by_training": False,
        "neural_weight_update_completed": True,
        "auto_promote_to_production": False,
    })


def evaluation(root, freeze, parent_dir, child_dir):
    check_freeze(freeze)
    import torch
    torch.set_num_threads(1)
    parent, p = load_checkpoint(parent_dir, torch, freeze)
    child, c = load_checkpoint(child_dir, torch, freeze)
    require(p["generation"] == "parent" and c["generation"] == "child" and
            p["parent_manifest_sha256"] is None and
            c["parent_manifest_sha256"] == p["manifest_sha256"] and
            c["inherited_initial_weights_sha256"] == p["weights_sha256"] and
            p["trained_steps"] == STEPS["parent"] and
            c["trained_steps"] == STEPS["child"],
            "FALSIFIED_PARENT_CHILD_LINEAGE")
    # The heldout bytes are opened ONLY after both immutable checkpoints load.
    holdout = []
    for item in freeze["roles"]["holdout"]:
        raw = safe_source(root, item["path"])
        require(blob_sha1(raw) == item["git_blob_sha1"] and
                hashlib.sha256(raw).hexdigest() == item["source_sha256"],
                "FROZEN_HOLDOUT_CHANGED")
        holdout.append(raw)
    data = torch.tensor(list(b"\n\n".join(holdout)), dtype=torch.long)
    require(len(data) > core.BLOCK * 8, "HOLDOUT_TOO_SHORT")
    p_loss = core.val_loss(torch, parent, data)
    c_loss = core.val_loss(torch, child, data)
    from tools import essence_v36_juxtapose_exact as exact
    witness = exact.field_search([[1,2],[-1,3],[2,-3]], 80)
    require(witness["exact_verifier_has_veto"] is True and
            witness["coverage_ratio"] == 1.0 and
            witness["production_authority"] is False,
            "EXACT_AUTHORITY_BYPASS")
    improved = c_loss <= p_loss - MIN_GAIN
    return sealed({
        "schema": EXAM,
        "status": ("PASS_INTERNAL_FROZEN_PAIRED_GAIN" if improved
                   else "NO_GAIN_FROZEN_HOLDOUT"),
        "freeze_receipt_sha256": freeze["receipt_sha256"],
        "parent_manifest_sha256": p["manifest_sha256"],
        "child_manifest_sha256": c["manifest_sha256"],
        "exact_jux_receipt_sha256": witness["receipt_sha256"],
        "parent_frozen_holdout_loss": p_loss,
        "child_frozen_holdout_loss": c_loss,
        "predeclared_min_decrease": MIN_GAIN,
        "source_files_heldout": [x["path"] for x in freeze["roles"]["holdout"]],
        "evaluation_after_both_checkpoints_sealed": True,
        "child_initial_weights_equal_parent_final": True,
        "holdout_tuning_allowed": False,
        "independent_external_test": False,
        "prospective_original_novel_tasks_tested": False,
        "automatic_working_model_replacement": False,
        "production_authority": False,
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("freeze", "parent", "child", "evaluate"))
    p.add_argument("--repo-root", default=".")
    p.add_argument("--lock", default=LOCK_REL)
    p.add_argument("--freeze", default=None)
    p.add_argument("--parent-dir", default=None)
    p.add_argument("--child-dir", default=None)
    p.add_argument("--checkpoint-dir", default=None)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    if a.mode == "freeze":
        result = inspect_lock(a.repo_root, a.lock)
    else:
        require(a.freeze is not None, "FREEZE_RECEIPT_REQUIRED")
        frozen = check_freeze(read_json(a.freeze))
        if a.mode == "parent":
            result = training(a.repo_root, frozen, generation="parent",
                              output=a.checkpoint_dir)
        elif a.mode == "child":
            result = training(a.repo_root, frozen, generation="child",
                              output=a.checkpoint_dir, parent=a.parent_dir)
        else:
            result = evaluation(a.repo_root, frozen, a.parent_dir, a.child_dir)
    immutable_json(a.out, result)
    print(json.dumps({
        "mode": a.mode,
        "status": result.get("status", "RESEARCH_RECEIPT_SEALED"),
        "receipt_sha256": result["receipt_sha256"],
        "production_authority": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
