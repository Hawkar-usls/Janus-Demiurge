#!/usr/bin/env python3
"""Read-only 128/256/512 JANUS context capacity and synthetic arithmetic probe.

The longer position table is a modulo-repeat of incumbent rows, NOT
learned long-context competence. Old model weights and original 128 rows are
verified unchanged. No Genesis exam, optimizer, checkpoint write or promotion.
"""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import argparse
import json
import resource
import time
from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu

SCHEMA="janus.trinity.disposable_context_probe.v1"
LENGTHS=(128,256,512)

def probes():
    tasks=[{"id":t["id"],"group":"TRAIN_ONLY_SHORT","prompt":t["prompt"],
            "expected":t["expected"]} for t in c.curriculum()]
    for group,n,length in (("PUBLIC_PADDED_MEDIUM",6,125),
                           ("PUBLIC_PADDED_LONG",6,330)):
        for i in range(n):
            a,b=201+17*i,307+11*i
            prompt=("x"*length)+"\n"+f"Compute {a} + {b}. Reply with the integer only."
            tasks.append({"id":group+"-"+str(i),"group":group,
                          "prompt":prompt,"expected":str(a+b)})
    return tasks

def expand(model,length):
    import torch
    from janus_model.model import JanusTinyTransformer
    if type(length) is not int or length not in LENGTHS:
        raise ValueError("TRINITY_CONTEXT_SCOPE_HOLD")
    if model.config.context_length!=128:
        raise ValueError("TRINITY_ORIGINAL_CONTEXT_NOT_128")
    model.eval()
    if length==128:
        return model
    other=JanusTinyTransformer(replace(model.config,context_length=length))
    state=model.state_dict()
    new=other.state_dict()
    for k in state:
        if k!="pos.weight":
            if k not in new or new[k].shape!=state[k].shape:
                raise ValueError("TRINITY_CONTEXT_WEIGHT_SHAPE_HOLD")
            new[k]=state[k].clone()
    new["pos.weight"]=state["pos.weight"][torch.arange(length)%128].clone()
    other.load_state_dict(new,strict=True)
    checked=other.state_dict()
    for k in state:
        if k=="pos.weight":
            ok=torch.equal(checked[k][:128],state[k])
        else:
            ok=torch.equal(checked[k],state[k])
        if not ok: raise ValueError("TRINITY_CONTEXT_OLD_WEIGHTS_CHANGED")
    return other.eval()

def run(context):
    import torch
    from janus_model.model import ByteTokenizer
    from janus_model.train_registry import load_checkpoint
    if context not in LENGTHS or type(context) is not int:
        raise ValueError("TRINITY_CONTEXT_SCOPE_HOLD")
    torch.set_num_threads(4)
    status=json.loads(Path("janus_model/state/JANUS_MODEL_STATE.json").read_text())
    digest=status["checkpoint_sha256"]
    original,_=load_checkpoint(Path("janus_model/checkpoints/promoted.pt"),
                              expected_sha256=digest)
    model=expand(original,context)
    started=time.monotonic()
    measurements=[]
    for task in probes():
        prompt_tokens=len(ByteTokenizer.encode("Q:"+task["prompt"]+"\nJANUS:",bos=True))
        fits=prompt_tokens<context
        answer=cpu.student_answer(model,task["prompt"]) if fits else None
        measurements.append({
            "id":task["id"],"group":task["group"],"tokens":prompt_tokens,
            "fits_without_truncation":fits,
            "exact":answer==task["expected"] if answer is not None else False,
            "answer_sha256":c.digest({"answer":answer}) if answer is not None else None
        })
    summary={}
    for group in sorted({m["group"] for m in measurements}):
        subset=[m for m in measurements if m["group"]==group]
        summary[group]={"total":len(subset),
                        "fit":sum(m["fits_without_truncation"] for m in subset),
                        "exact":sum(m["exact"] for m in subset)}
    return c.sealed({
        "schema":SCHEMA,"status":"SYNTHETIC_CONTEXT_DIAGNOSTIC_NOT_GENERALIZATION",
        "context_length":context,
        "base_context":128,
        "base_checkpoint_sha256":digest,
        "position_extension":"MODULO_REPEAT_UNTRAINED" if context>128 else "NONE",
        "probe_set_sha256":c.digest(probes()),
        "original_weights_unchanged":True,
        "weights_saved":False,"training_performed":False,
        "read_genesis_firstlook":False,"promotion":False,
        "cpu_peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "wall_seconds":round(time.monotonic()-started,3),
        "summary":summary,"cases":measurements,
    })

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--context",required=True,type=int,choices=LENGTHS)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    report=run(a.context)
    cpu.save_new(a.out,report)
    print(json.dumps({"context":a.context,"summary":report["summary"],
                      "cpu_peak_rss_mib":report["cpu_peak_rss_mib"],
                      "no_model_promotion":True}))

if __name__=="__main__":
    main()
