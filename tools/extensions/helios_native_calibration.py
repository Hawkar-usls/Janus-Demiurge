"""Export fixed public byte-calibration work; independently audit numeric results."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import random
from pathlib import Path
import re

from janus_model.extensions.helios_calibration import (
    canonical, validate_bias, validate_admission, SCHEMA, VOCAB,
)

TASK_SCHEMA = "janus.helios.calibration_task.v1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def split_records(text):
    records = sorted(set(part.strip() for part in re.split(r"\n\s*\n", text) if len(part.strip()) >= 80))
    train, validation = [], []
    for part in records:
        (validation if int(digest(part.encode())[:8], 16) % 5 == 0 else train).append(part)
    if not train or not validation:
        raise ValueError("PUBLIC_TRAIN_HOLDOUT_SPLIT_REQUIRED")
    return "\n\n".join(train), "\n\n".join(validation)


def export_task(checkpoint, text, registry_commit, source_commit, anchor, worker_sha):
    import torch
    from janus_model.train_registry import load_checkpoint
    from janus_model.model import ByteTokenizer
    torch.set_num_threads(1)
    model, _ = load_checkpoint(checkpoint)
    model.eval()
    training, adaptive = split_records(text)

    def examples(content, count, seed):
        ids = ByteTokenizer.encode(content, bos=True, eos=True)
        if len(ids) < model.config.context_length + count:
            raise ValueError("CALIBRATION_CORPUS_TOO_SMALL")
        positions = random.Random(seed).sample(range(model.config.context_length, len(ids)), count)
        result = []
        with torch.inference_mode():
            for at in positions:
                x = torch.tensor([ids[at-model.config.context_length:at]], dtype=torch.long)
                logits, _ = model(x)
                result.append({"logits": [round(float(x), 7) for x in logits[0,-1]], "target": ids[at]})
        return result

    task = {"schema": TASK_SCHEMA, "task_type": "JANUS_NATIVE_BYTE_CALIBRATION_V1",
            "checkpoint_sha256": digest(Path(checkpoint).read_bytes()),
            "native_source_commit": source_commit, "registry_source_commit": registry_commit,
            "worker_sha256": worker_sha, "vocab_size": VOCAB,
            "exporter_sha256": digest(Path(__file__).read_bytes()),
            "model_source_sha256": digest(Path("janus_model/model.py").read_bytes()),
            "torch_version": str(torch.__version__),
            "train": examples(training, 192, 87221),
            "adaptive_eval": examples(adaptive, 64, 87223),
            "anchor_eval": examples(anchor, 64, 87229),
            "training_text": training, "adaptive_text": adaptive,
            "training_sha256": digest(training.encode()),
            "adaptive_sha256": digest(adaptive.encode()), "anchor_sha256": digest(anchor.encode()),
            "anchor_is_training_source": False, "config": model.config.to_dict(),
            "adapter_scope": "INFERENCE_LOGIT_CALIBRATION_ONLY", "initial_bias": [0.0]*VOCAB,"initial_log_scale":0.0}
    return task


def audit(task, candidate, checkpoint, anchor, previous=None):
    import math
    import torch
    import torch.nn.functional as functional
    from janus_model.model import ByteTokenizer
    from janus_model.train_registry import load_checkpoint
    from janus_model.eval_contract import EVAL_BATCHES, EVAL_BATCH_SIZE
    torch.set_num_threads(1)
    checkpoint_sha = digest(Path(checkpoint).read_bytes())
    if (task.get("schema") != TASK_SCHEMA or task.get("checkpoint_sha256") != checkpoint_sha or
            task.get("anchor_sha256") != digest(anchor.encode()) or
            task.get("anchor_is_training_source") is not False or
            digest(task["training_text"].encode()) != task.get("training_sha256") or
            digest(task["adaptive_text"].encode()) != task.get("adaptive_sha256")):
        raise ValueError("CALIBRATION_TASK_BINDING_REJECTED")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", candidate.get("candidate_id", "")):
        raise ValueError("CALIBRATION_CANDIDATE_ID_REJECTED")
    bias = validate_bias(candidate.get("bias"))
    log_scale = candidate.get("log_scale")
    if type(log_scale) not in (int,float) or not math.isfinite(log_scale) or abs(log_scale)>0.05:
        raise ValueError("CALIBRATION_SCALE_REJECTED")
    prior = validate_admission(previous, checkpoint_sha) if previous else [0.0]*VOCAB
    prior_scale = previous["log_scale"] if previous else 0.0
    model, _ = load_checkpoint(checkpoint)
    model.eval()
    metrics = {}
    for kind, text, seed in (("adaptive",task["adaptive_text"],331347), ("anchor",anchor,331349)):
        ids = ByteTokenizer.encode(text, bos=True, eos=True)
        rng, before, after = random.Random(seed), [], []
        with torch.inference_mode():
            for _ in range(EVAL_BATCHES):
                starts = [rng.randrange(len(ids)-model.config.context_length-1) for _ in range(EVAL_BATCH_SIZE)]
                x = torch.tensor([ids[p:p+model.config.context_length] for p in starts],dtype=torch.long)
                y = torch.tensor([ids[p+1:p+model.config.context_length+1] for p in starts],dtype=torch.long)
                logits, _ = model(x)
                before.append(float(functional.cross_entropy((logits*math.exp(prior_scale)+torch.tensor(prior)).reshape(-1,VOCAB),y.reshape(-1))))
                after.append(float(functional.cross_entropy((logits*math.exp(log_scale)+torch.tensor(bias)).reshape(-1,VOCAB),y.reshape(-1))))
        metrics[kind] = {"before":sum(before)/len(before),"after":sum(after)/len(after),
                         "batches":EVAL_BATCHES,"batch_size":EVAL_BATCH_SIZE,"context_length":model.config.context_length}
    receipt = {"schema":SCHEMA,"status":"ADMITTED_NATIVE_CALIBRATION","scope":"INFERENCE_LOGIT_CALIBRATION_ONLY",
               "checkpoint_sha256":checkpoint_sha,"native_auditor_passed":True,
               "task_sha256":candidate["task_sha256"],"candidate_id":candidate["candidate_id"],
               "bias":bias,"log_scale":log_scale,"calibration_sha256":digest(canonical({"bias":bias,"log_scale":log_scale})),"metrics":metrics,
               "anchor_sha256":task["anchor_sha256"],"registry_source_commit":task["registry_source_commit"],
               "created_at":datetime.now(timezone.utc).isoformat(),
               "previous_calibration_sha256":previous.get("calibration_sha256") if previous else None,
               "training_source":"EXPLICIT_CONSENT_HELIOS_BROWSER" if candidate.get("consent_version")=="HELIOS_NATIVE_CALIBRATION_2026_10_31" else "OPERATOR_LOCAL_DRILL","checkpoint_weights_replaced":False}
    try:
        validate_admission(receipt,checkpoint_sha)
    except ValueError:
        receipt.update(status="REJECTED_NATIVE_CALIBRATION",native_auditor_passed=False)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("export","audit"))
    p.add_argument("--checkpoint",type=Path,default=Path("janus_model/checkpoints/promoted.pt"))
    p.add_argument("--anchor",type=Path,default=Path("janus_model/eval/JANUS_ANCHOR_EVAL-v1.txt"))
    p.add_argument("--text",type=Path);p.add_argument("--registry-commit");p.add_argument("--source-commit");p.add_argument("--worker-sha")
    p.add_argument("--task",type=Path);p.add_argument("--candidate",type=Path);p.add_argument("--previous",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.mode=="export":
        if any(not re.fullmatch("[a-f0-9]{"+str(length)+"}",value or "") for value,length in ((a.registry_commit,40),(a.source_commit,40),(a.worker_sha,64))):
            raise ValueError("PINNED_EXPORT_INPUTS_REQUIRED")
        value=export_task(a.checkpoint,a.text.read_text(encoding="utf-8"),a.registry_commit,a.source_commit,a.anchor.read_text(encoding="utf-8"),a.worker_sha)
    else:
        raw=a.task.read_bytes()
        candidate=json.loads(a.candidate.read_text())
        if len(raw)>2000000 or candidate.get("task_sha256")!=digest(raw):
            raise ValueError("CALIBRATION_TASK_HASH_REJECTED")
        previous=json.loads(a.previous.read_text()) if a.previous and a.previous.exists() else None
        value=audit(json.loads(raw),candidate,a.checkpoint,a.anchor.read_text(encoding="utf-8"),previous)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.exists() and a.out.read_bytes()!=canonical(value)+b"\n":
        raise ValueError("CALIBRATION_HISTORY_IS_IMMUTABLE")
    a.out.write_bytes(canonical(value)+b"\n")
    print(json.dumps({"status":value.get("status","TASK_EXPORTED"),"sha256":digest(a.out.read_bytes())}))


if __name__=="__main__":
    main()
