#!/usr/bin/env python3
"""JANUS Spacetime + Hoffman: bounded CPU adaptation of EXISTING native Transformer.

Training is from a *copy* of janus_model/checkpoints/promoted.pt, never new
weights from scratch and never overwriting/promoting the incumbent. Source
card provenance, cautious epistemic status, split IDs and critic/avian transfer
warnings are hard requirements. No full-text copyrighted articles are used.

This tiny byte-level next-token LM is not a physicist, a gull connectome, or
a validated scientific QA engine. Report validation/test/anchor next-token loss,
not unmeasured factual competence. Candidate research artifact only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random

SCHEMA="janus.spacetime.science_corpus.v1"
VALID_STATUSES={"ESTABLISHED","ESTABLISHED_THEORY","ESTABLISHED_MODEL",
                "OBSERVATION","ACTIVE_RESEARCH","PHILOSOPHICAL","METHODOLOGICAL"}
SPLITS=("train","validation","test")
HOFFMAN_REQUIRED={"hoffman_2000_shape_illusion","hoffman_2015_interface_perception",
  "hoffman_2021_fitness_truth","hoffman_2014_markov_agents",
  "hoffman_2023_fusions","hoffman_2020_fact_fiction",
  "hoffman_2024_time_projection","hoffman_2024_interfacing_consciousness",
  "hoffman_2026_mattes_critique","hoffman_2024_traces_preprint",
  "hoffman_to_gull_caution"}


def require(value,why):
    if not value:
        raise ValueError(why)


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def corpus(path):
    original=Path(path).read_bytes()
    obj=json.loads(original)
    require(type(obj) is dict and obj.get("schema")==SCHEMA,
            "SCIENCE_SCHEMA_CHANGED")
    rows=obj.get("records")
    require(type(rows) is list and len(rows)>=30,
            "SCIENCE_CORPUS_INCOMPLETE")
    groups={s:[] for s in SPLITS}
    seen=set()
    for r in rows:
        require(type(r) is dict and type(r.get("id")) is str
                and r["id"] not in seen,"DUPLICATE_OR_INVALID_TOPIC_ID")
        seen.add(r["id"])
        require(r.get("split") in groups,"UNKNOWN_SPLIT")
        require(r.get("status") in VALID_STATUSES,
                "MISSING_EVIDENCE_CONFIDENCE_LABEL")
        require(type(r.get("source_url")) is str and
                r["source_url"].startswith("https://") and
                type(r.get("source_org")) is str and r["source_org"],
                "MISSING_PRIMARY_SOURCE")
        for key in ("question","answer","context"):
            require(type(r.get(key)) is str and
                    len(r[key].strip())>=12,
                    "SHORT_OR_MISSING_"+key.upper())
        groups[r["split"]].append(r)
    require(HOFFMAN_REQUIRED <= seen,"HOFFMAN_OR_COUNTEREVIDENCE_MISSING")
    source_ids=set((obj.get("hoffman_research") or {}).get("research_ids") or [])
    require(source_ids==HOFFMAN_REQUIRED,"HOFFMAN_SOURCE_SET_CHANGED")
    require(len(groups["train"])>=23 and
            len(groups["validation"])>=6 and len(groups["test"])>=8,
            "INCOMPLETE_PREDECLARED_SPLIT")
    for key in ("hoffman_2026_mattes_critique","hoffman_to_gull_caution",
                "hoffman_2024_traces_preprint"):
        require(any(r["id"]==key for r in groups["test"]),
                "CRITICAL_OUT_OF_TRAIN_HOLDOUT_LOST")
    require(all(r["status"] in ("ACTIVE_RESEARCH","PHILOSOPHICAL","METHODOLOGICAL")
                for r in rows if r["id"].startswith("hoffman_") and
                r["id"] not in ("hoffman_2000_shape_illusion",)),
            "HOFFMAN_SPECULATION_LAUNDERED_AS_FACT")
    video=obj.get("excluded_user_reference") or {}
    require(video.get("video_id")=="wPRyiDMJ0ro" and
            video.get("training_included") is False and
            video.get("transcript_obtained") is False,
            "UNTRANSCRIBED_VIDEO_NOT_AUTHORIZED_AS_TRAINING")
    policy=obj.get("training_policy") or {}
    require(policy.get("production_checkpoint_unchanged") is True
            and policy.get("data_leakage_prohibited") is True,
            "TRAINING_POLICY_INSECURE")
    return obj,groups,digest(original)


def render(rows):
    out=[]
    for row in rows:
        out.append(
          "JANUS SCIENCE SOURCE | "+row["id"]+"\n"
          "Domain: "+row["domain"]+"\n"
          "Evidence: "+row["status"]+"\n"
          "Source: "+row["source_url"]+"\n"
          "Q: "+row["question"]+"\n"
          "A: "+row["answer"]+"\n"
          "Limits: "+row["context"]+"\n"
          "END SCIENCE SOURCE\n"
        )
    return "\n".join(out)


def prepare(path,output_dir):
    obj,groups,source_sha=corpus(path)
    dest=Path(output_dir)
    dest.mkdir(parents=True,exist_ok=True)
    manifest={
        "schema":"janus.spacetime_hoffman.research_manifest.v1",
        "source_sha256":source_sha,
        "source_record_count":sum(len(g) for g in groups.values()),
        "hoffman_research_cards":len(HOFFMAN_REQUIRED),
        "one_per_topic_frozen_split":True,
        "complete_original_sources_no_unlicensed_fulltexts":True,
        "untranscribed_video_excluded":True,
        "train_isolated_from_validation_and_test":True,
        "candidate_only_production_never_mutated":True,
        "splits":{}
    }
    for key,records in groups.items():
        raw=render(records).encode("utf-8")
        require(len(raw)>1000,"TOO_LITTLE_"+key.upper()+"_TEXT")
        file=dest/(key+".txt")
        require(not file.exists(),"REFUSE_TO_OVERWRITE_DATA_SPLIT")
        file.write_bytes(raw)
        manifest["splits"][key]={
          "sha256":digest(raw),
          "num_topics":len(records),
          "num_bytes":len(raw),
          "ids":[r["id"] for r in records]
        }
    file=dest/"manifest.json"
    require(not file.exists(),"REFUSE_TO_OVERWRITE_MANIFEST")
    file.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,
                               sort_keys=True)+"\n",encoding="utf-8")
    return manifest


def train(args):
    import torch
    from janus_model.model import ByteTokenizer, parameter_count
    from janus_model.train_registry import (
        load_checkpoint,save_checkpoint,batch_from,eval_loss
    )
    from janus_model.eval_contract import DEFAULT_ANCHOR
    require(8<=args.steps<=100 and 2<=args.batch_size<=8,
            "RESEARCH_RESOURCE_BUDGET_EXCEEDED")
    torch.set_num_threads(2)
    random.seed(20261108)
    torch.manual_seed(20261108)
    model_dir=Path(args.data_dir)
    man=json.loads((model_dir/"manifest.json").read_text(encoding="utf8"))
    for key in SPLITS:
        require(digest((model_dir/(key+".txt")).read_bytes())==
                man["splits"][key]["sha256"],
                "CORPUS_SPLIT_DIGEST_CHANGED")
    incumbent_file=Path(args.incumbent)
    require(incumbent_file.exists() and incumbent_file.name=="promoted.pt",
            "ONLY_PROMOTED_CHECKPOINT_ALLOWED")
    require(incumbent_file.resolve()!=Path(args.candidate).resolve(),
            "MUST_NOT_OVERWRITE_PRODUCTION_CHECKPOINT")
    model,original=load_checkpoint(incumbent_file)
    source_model_sha=digest(incumbent_file.read_bytes())
    device="cpu"
    def tokenize(path):
        return torch.tensor(ByteTokenizer.encode(
            Path(path).read_text(encoding="utf8"),bos=True,eos=True
        ),dtype=torch.long,device=device)
    streams={k:tokenize(model_dir/(k+".txt")) for k in SPLITS}
    anchor_stream=tokenize(DEFAULT_ANCHOR)
    ctx=model.config.context_length
    for k,stream in {**streams,"anchor":anchor_stream}.items():
        require(stream.numel()>ctx+8,"INSUFFICIENT_BYTE_STREAM_"+k)
    def evals(network):
        return {
          "validation":eval_loss(network,streams["validation"],batches=8,
                                 batch_size=4,seed=191011),
          "test":eval_loss(network,streams["test"],batches=8,
                          batch_size=4,seed=191021),
          "frozen_anchor":eval_loss(network,anchor_stream,batches=8,
                                    batch_size=4,seed=191031)
        }
    before=evals(model)
    model.train()
    optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01)
    gen=torch.Generator().manual_seed(20261109)
    losses=[]
    for step in range(args.steps):
        inputs,targets=batch_from(streams["train"],args.batch_size,ctx,gen)
        _,loss=model(inputs,targets)
        require(bool(torch.isfinite(loss).item()),"NONFINITE_TRAIN_LOSS")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
        optimizer.step()
        losses.append(float(loss.item()))
    after=evals(model)
    require(all(math.isfinite(v) for v in (*before.values(),*after.values())),
            "NONFINITE_EVALUATION")
    # More stringent than generic control; no automatic promotion at all.
    validation_improved=after["validation"] < before["validation"]
    old_anchor_preserved=after["frozen_anchor"] <= before["frozen_anchor"]*1.01
    test_improved=after["test"] < before["test"]
    promotion_candidate_gate=validation_improved and old_anchor_preserved
    target=Path(args.candidate)
    receipt=Path(args.receipt)
    require(not target.exists() and not receipt.exists(),
            "REFUSE_TO_OVERWRITE_RESEARCH_OUTPUT")
    meta={
      "model_role":"RESEARCH_ONLY_SPACETIME_HOFFMAN",
      "source_model_sha256":source_model_sha,
      "training_source_sha256":man["source_sha256"],
      "train_steps":args.steps,
      "validation_improved":validation_improved,
      "frozen_anchor_preserved_within_one_percent":old_anchor_preserved,
      "production_promotion":False,
      "not_proof_of_any_physics":True,
      "scientific_claim":"BYTE_LEVEL_NEXT_TOKEN_TRAINING_NOT_CONFIRMED_QA_OR_VISUAL_SPATIAL_INTELLIGENCE"
    }
    save_checkpoint(target,model,meta)
    target_sha=digest(target.read_bytes())
    out={
      "schema":"janus.spacetime_hoffman.research_training_receipt.v1",
      "source_model":"existing JanusTinyTransformer promoted.pt, weights continued",
      "source_model_sha256":source_model_sha,
      "candidate_model_sha256":target_sha,
      "corpus_sha256":man["source_sha256"],
      "training_steps":args.steps,
      "batch_size":args.batch_size,
      "context_bytes":ctx,
      "parameter_count":parameter_count(model),
      "loss_mean_train":sum(losses)/len(losses),
      "loss_final_train":losses[-1],
      "next_token_cross_entropy_baseline":before,
      "next_token_cross_entropy_candidate":after,
      "validation_improved":validation_improved,
      "test_improved":test_improved,
      "anchor_nonregression_one_percent":old_anchor_preserved,
      "research_evaluation_gate":promotion_candidate_gate,
      "automatic_promotion_allowed":False,
      "actually_promoted":False,
      "user_supplied_untranscribed_video_used":False,
      "actual_3d_visual_system_or_bird_connectome_trained":False,
      "knowledge_or_science_correctness_validated":False,
      "scientific_interpretation":"Only next-byte losses are measured; held-out QA and physical theory inference remain unvalidated."
    }
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf8")
    return out


def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="mode",required=True)
    p=sub.add_parser("prepare")
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--data-dir",type=Path,required=True)
    t=sub.add_parser("train")
    t.add_argument("--data-dir",type=Path,required=True)
    t.add_argument("--incumbent",type=Path,required=True)
    t.add_argument("--candidate",type=Path,required=True)
    t.add_argument("--receipt",type=Path,required=True)
    t.add_argument("--steps",type=int,default=40)
    t.add_argument("--batch-size",type=int,default=6)
    args=ap.parse_args()
    if args.mode=="prepare":
        result=prepare(args.source,args.data_dir)
        print(json.dumps({"state":"SPLITS_READY","topics":result["source_record_count"],
                          "hoffman":result["hoffman_research_cards"]}))
    else:
        result=train(args)
        print(json.dumps({"state":"CPU_TRAINING_COMPLETED",
                          "validation_loss":result["next_token_cross_entropy_candidate"]["validation"],
                          "anchor_loss":result["next_token_cross_entropy_candidate"]["frozen_anchor"],
                          "gate":result["research_evaluation_gate"],
                          "auto_promotion":False}))


if __name__=="__main__":
    main()
