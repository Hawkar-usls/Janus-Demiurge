"""ESSENCE R1 — real dated Meta Registry JSON, bounded CPU training.

Task: classify archive *document family* using only top-level JSON key names.
No raw values, prose, credentials, or model-generated commands reach training.
Chronological, date-disjoint validation/holdout; completely separate verifier.
This does not predict future events or prove general autonomous intelligence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import re
import time

import torch
import torch.nn.functional as F

from janus_model.model import JanusModelConfig, JanusTinyTransformer

torch.set_num_threads(1)

SCHEMA = "janus.essence.real_registry_training.r1"
DATE = re.compile(r"2026[-_]([01]\d)[-_]([0-3]\d)")
LABELS = ("LINEAR", "TRUMP", "OSIRIS", "ECHO", "CONNECTION",
          "ROWAN", "SCOBY", "EYE", "OTHER")
CELL_ROLES = ("sensing", "memory", "planning", "verification", "recovery", "coding")
CONFIG = JanusModelConfig(vocab_size=256, context_length=16,
                          d_model=32, n_heads=4, n_layers=1,
                          ff_mult=2, dropout=0.0)
MAX_FILES = 4200
MAX_FILE_BYTES = 100_000
MIN_EXAMPLES = 130
MAX_STEPS = 200
REPO = "Hawkar-usls/janus-meta-registry"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def label_for(filename):
    name = filename.upper()
    for index, category in enumerate(LABELS[:-1]):
        if category in ("ROWAN", "SCOBY", "EYE"):
            if name.startswith(category + "-"):
                return index
        elif name.startswith("JANUS-" + category + "-"):
            return index
    return len(LABELS) - 1


def tokenize_keys(keys):
    # Key names only; no values, artifact IDs, credentials, or free-text.
    tokens = [1]
    for key in sorted(k for k in keys if isinstance(k, str))[:15]:
        tokens.append(8 + (int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 248))
    tokens = tokens[:CONFIG.context_length]
    return [0] * (CONFIG.context_length - len(tokens)) + tokens


def source_paths(root):
    root = Path(root).resolve(strict=True)
    paths = sorted(root.rglob("*.json"))
    if len(paths) > MAX_FILES:
        raise ValueError("UNBOUNDED_ARCHIVE")
    return root, paths


def collect(root):
    root, paths = source_paths(root)
    rows = []
    seen = set()
    skipped = {"undated": 0, "invalid_json": 0, "oversize": 0,
               "duplicate": 0, "missing_keys": 0}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("UNSAFE_ARCHIVE_PATH")
        match = DATE.search(path.name)
        if not match:
            skipped["undated"] += 1
            continue
        dt = "2026-" + match.group(1) + "-" + match.group(2)
        try:
            import datetime
            datetime.date.fromisoformat(dt)
        except ValueError:
            skipped["undated"] += 1
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            skipped["oversize"] += 1
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"),
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (UnicodeError, ValueError, OSError, RecursionError):
            skipped["invalid_json"] += 1
            continue
        if not isinstance(obj, dict) or not 1 <= len(obj) <= 300:
            skipped["missing_keys"] += 1
            continue
        # Drop filename copy-version suffix; no copy of the same named event
        # may be counted as an independent training sample.
        stem = path.stem
        stem = re.sub(r"(?:[-_]v\d+(?:[._]\d+)*)$", "", stem, flags=re.I)
        identity = (path.parent.relative_to(root).as_posix(), stem.upper())
        if identity in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(identity)
        rows.append({"date": dt, "x": tokenize_keys(obj.keys()),
                     "label": label_for(path.name),
                     "identity": digest(identity)})
    rows.sort(key=lambda x:(x["date"], x["identity"]))
    dates = sorted(set(r["date"] for r in rows))
    if len(rows) < MIN_EXAMPLES or len(dates) < 30:
        raise ValueError("INSUFFICIENT_DATED_HISTORY")
    # Split by entire date, not by random records. Dates are disjoint.
    cut1 = max(1, int(0.7 * len(dates)))
    cut2 = max(cut1+1, int(0.85 * len(dates)))
    if cut2 >= len(dates):
        raise ValueError("INSUFFICIENT_HELDOUT_DATES")
    boundaries = (dates[cut1], dates[cut2])
    groups = {
        "train": [r for r in rows if r["date"] < boundaries[0]],
        "validation": [r for r in rows if boundaries[0] <= r["date"] < boundaries[1]],
        "test": [r for r in rows if r["date"] >= boundaries[1]],
    }
    if min(len(v) for v in groups.values()) < 12:
        raise ValueError("INSUFFICIENT_DATE_SPLIT")
    ids = [set(r["identity"] for r in group) for group in groups.values()]
    if len(set.union(*ids)) != sum(len(x) for x in ids):
        raise ValueError("CROSS_SPLIT_DUPLICATE")
    # Label distribution shift is reported, never silently balanced.
    desc = {"schema": SCHEMA, "dataset_type": "REAL_HISTORICAL_JSON_STRUCTURE",
            "source_repository": REPO, "count": len(rows),
            "boundaries": {"validation_start": boundaries[0], "test_start": boundaries[1]},
            "split_sizes": {k:len(v) for k,v in groups.items()},
            "split_days": {k: len(set(r["date"] for r in v)) for k,v in groups.items()},
            "label_counts": {k: {LABELS[i]: sum(x["label"] == i for x in v)
                                 for i in range(len(LABELS))}
                             for k,v in groups.items()},
            "skipped": skipped, "keys_only": True, "future_holdout_seen_during_training": False}
    desc["dataset_sha256"] = digest(rows)
    return groups, desc


def tensor_data(rows):
    return (torch.tensor([r["x"] for r in rows], dtype=torch.long),
            torch.tensor([r["label"] for r in rows], dtype=torch.long))


def baseline(train, target):
    counts = torch.bincount(torch.tensor([x["label"] for x in train]),
                            minlength=len(LABELS)).float()
    probs = (counts + 1) / (counts.sum() + len(LABELS))
    y = torch.tensor([x["label"] for x in target],dtype=torch.long)
    return {"nll": round(float(-torch.log(probs[y]).mean()), 6),
            "accuracy": round(float((y == int(probs.argmax())).float().mean()), 6)}


@torch.no_grad()
def evaluate(model, rows):
    model.eval()
    x,y = tensor_data(rows)
    logits = model(x)[0][:,-1,:len(LABELS)].float()
    return {"nll": round(float(F.cross_entropy(logits, y)), 6),
            "accuracy": round(float((logits.argmax(-1) == y).float().mean()), 6)}


def model_for(cell):
    if type(cell) is not int or not 0 <= cell < len(CELL_ROLES):
        raise ValueError("CELL_OUT_OF_RANGE")
    torch.manual_seed(20261113 + cell * 1039)
    return JanusTinyTransformer(CONFIG)


def save(path, obj):
    p=Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False)+"\n")


def train(cell, data_root, source_commit, out, steps=100):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("UNPINNED_REGISTRY_SOURCE")
    if not 20 <= steps <= MAX_STEPS:
        raise ValueError("TRAINING_BUDGET")
    groups, desc = collect(data_root)
    model = model_for(cell)
    before = evaluate(model, groups["validation"])
    x,y = tensor_data(groups["train"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.007, weight_decay=0.0005)
    generator = torch.Generator().manual_seed(84000 + cell * 7919)
    best_val = float("inf")
    best_state = None
    t0=time.monotonic()
    completed=0
    for n in range(steps):
        sample=torch.randint(0, len(x), (min(48,len(x)),), generator=generator)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits=model(x[sample])[0][:,-1,:len(LABELS)]
        loss=F.cross_entropy(logits,y[sample])
        if not torch.isfinite(loss):
            raise ValueError("NONFINITE_LOSS")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.0,error_if_nonfinite=True)
        optimizer.step()
        if any(not bool(torch.isfinite(p).all()) for p in model.parameters()):
            raise ValueError("NONFINITE_WEIGHTS")
        completed+=1
        if n % 10 == 9 or n == steps-1:
            current=evaluate(model, groups["validation"])
            if current["nll"] < best_val:
                best_val=current["nll"]
                best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    if best_state is None:
        raise ValueError("NO_VALID_MODEL")
    model.load_state_dict(best_state)
    checkpoint = {"schema":SCHEMA,"cell":cell,"role":CELL_ROLES[cell],
                  "model_config":CONFIG.to_dict(),
                  "source_repository":REPO,"source_commit":source_commit,
                  "dataset_sha256":desc["dataset_sha256"],
                  "split_boundaries":desc["boundaries"],
                  "model_state":best_state,"production_promotion":False}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    file=out/"weights.pt"
    torch.save(checkpoint,file)
    report={"schema":SCHEMA,"cell":cell,"role":CELL_ROLES[cell],
            "source_commit":source_commit,"data":desc,
            "train_steps":completed,"validation_before":before,
            "validation_after":evaluate(model,groups["validation"]),
            "validation_majority_baseline":baseline(groups["train"],groups["validation"]),
            "checkpoint_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
            "evaluation_holdout_sealed":True,
            "test_metrics":None,"model_trained_on_real_json":True,
            "task":"JSON_KEY_STRUCTURE_TO_DOCUMENT_FAMILY",
            "real_world_forecasting_claim":False,
            "weights_deployed":False,"self_modification_enabled":False,
            "elapsed_seconds":round(time.monotonic()-t0,3)}
    save(out/"receipt.json",report)
    print(json.dumps({"cell":cell,"training_steps":completed,
                      "validation":report["validation_after"],
                      "baseline":report["validation_majority_baseline"]}))
    return report


def verify(data_root, source_commit, input_dir, out):
    groups,desc=collect(data_root)
    holds=[]; cells=[]
    for cell,role in enumerate(CELL_ROLES):
        folder=Path(input_dir)/f"cell-{cell}"
        try:
            rp=folder/"receipt.json"
            wp=folder/"weights.pt"
            report=json.loads(rp.read_text())
            if (report.get("schema")!=SCHEMA or report.get("cell")!=cell or
                report.get("role")!=role or report.get("source_commit")!=source_commit or
                report.get("data",{}).get("dataset_sha256")!=desc["dataset_sha256"] or
                report.get("evaluation_holdout_sealed") is not True or
                report.get("test_metrics") is not None or
                report.get("weights_deployed") is not False or
                report.get("self_modification_enabled") is not False):
                raise ValueError("RECEIPT_MISMATCH")
            if hashlib.sha256(wp.read_bytes()).hexdigest()!=report["checkpoint_sha256"]:
                raise ValueError("CHECKPOINT_HASH_MISMATCH")
            saved=torch.load(wp,map_location="cpu",weights_only=True)
            if (saved.get("schema")!=SCHEMA or saved.get("cell")!=cell or
                saved.get("source_commit")!=source_commit or
                saved.get("dataset_sha256")!=desc["dataset_sha256"] or
                saved.get("split_boundaries")!=desc["boundaries"] or
                saved.get("production_promotion") is not False):
                raise ValueError("MODEL_BINDING_INVALID")
            model=model_for(cell)
            state=saved["model_state"]
            ref=model.state_dict()
            if set(state)!=set(ref) or any(
                state[k].shape!=ref[k].shape or not bool(torch.isfinite(state[k]).all())
                for k in ref):
                raise ValueError("WEIGHT_SHAPE_OR_FINITE")
            model.load_state_dict(state)
            measured=evaluate(model,groups["test"])
            static=baseline(groups["train"],groups["test"])
            # Frozen condition: no trial-and-error selection on this holdout.
            improvement=measured["nll"]<static["nll"]-0.02 and measured["accuracy"]>static["accuracy"]
            cells.append({"cell":cell,"role":role,"heldout":measured,
                         "training_majority_baseline":static,
                         "gate":"PASS_EXPLORATORY_HOLDOUT" if improvement else "HOLD_NO_HOLDOUT_GAIN",
                         "checkpoint_sha256":report["checkpoint_sha256"]})
        except (OSError,ValueError,KeyError,TypeError,RuntimeError) as e:
            holds.append({"cell":cell,"role":role,"reason":type(e).__name__})
    outcome={"schema":"janus.essence.real_registry_verifier.r1",
             "source_commit":source_commit,"dataset":desc,
             "verified_cells":len(cells),"expected_cells":len(CELL_ROLES),
             "cells":cells,"failures":holds,
             "status":"EXPLORATORY_ALL_PASS" if not holds and all(c["gate"].startswith("PASS") for c in cells)
                      else "HOLD_PARTIAL_OR_UNPROVEN",
             "scientific_scope":"ARCHIVAL_DOCUMENT_CLASSIFICATION_ONLY",
             "historical_json_used_for_gradients":True,
             "independent_date_holdout":True,
             "model_promotion_authorized":False,
             "cross_repository_writes":False,"automatic_module_reuse":False,
             "operational_autonomy_accepted":False}
    outcome["report_sha256"]=digest(outcome)
    save(out,outcome)
    print(json.dumps({"status":outcome["status"],"verified_cells":len(cells),
                      "failed_cells":len(holds),"test_size":desc["split_sizes"]["test"]}))
    return outcome


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("train","verify"))
    p.add_argument("--data-root",required=True)
    p.add_argument("--source-commit",required=True)
    p.add_argument("--cell",type=int)
    p.add_argument("--input-dir")
    p.add_argument("--out",required=True)
    p.add_argument("--steps",type=int,default=100)
    a=p.parse_args()
    if a.mode=="train":
        train(a.cell,a.data_root,a.source_commit,a.out,steps=a.steps)
    else:
        verify(a.data_root,a.source_commit,a.input_dir,a.out)


if __name__=="__main__":
    main()
