#!/usr/bin/env python3
"""One new blinded retro-Lab A/B trial AFTER JDTC Deutsch v2 training.

Compare pinned BEFORE (JDTC v1) and AFTER (JDTC v2) model using identical
past-only JSON sequences, on the SAME future 256 bits sampled by OS CSPRNG
at least two minutes after early precommit is committed.

Does NOT implement a real physical past-directed channel. Conditional gains
are evaluated without postselection; both models remain DEVELOPMENT ONLY.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from janus_model.model import JanusTinyTransformer
import janus_principle_deutsch_v2 as jdtc

torch.set_num_threads(1)
N=256
ALPHA=0.001
BOOK_URL="https://www.penguinrandomhouse.com/books/330123/the-fabric-of-reality-by-david-deutsch/"


def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():raise RuntimeError("REFUSE_REWRITE_SEALED_TRIAL")
    p.write_text(json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def load_net(path,snapshot_hash):
    c=torch.load(path,map_location="cpu",weights_only=True)
    if c["config"]!=jdtc.CFG.to_dict() or c["snapshot_sha256"]!=snapshot_hash:
        raise RuntimeError("SNAPSHOT_ARCHITECTURE_OR_MODEL_PROVENANCE_MISMATCH")
    net=jdtc.model()
    net.load_state_dict(c["state"],strict=True);net.eval()
    return net,float(c["calibration_temperature"]),float(c["validation_model_blend"])


def tail(n,k):
    if not 0<=k<=n:raise RuntimeError("BINOMIAL_BOUND")
    return sum(math.comb(n,i) for i in range(k,n+1))/2**n


@torch.no_grad()
def predictions(net,snap,trial,temp,mix):
    seq,tr,va,te,c=jdtc.split(snap)
    prior=jdtc.train_distribution(seq,tr,c)
    results=[]
    for idx in range(N):
        selector=hashlib.sha256(f"JANUS-DEUTSCH-V2|{trial}|{idx}".encode()).digest()
        target_idx=jdtc.CONTEXT+int.from_bytes(selector[:8],"big")%(min(tr)-jdtc.CONTEXT+len(tr)-1)
        # Map to *training* region, no validation/test or future bits.
        target_idx=tr[int.from_bytes(selector[:8],"big")%len(tr)]
        x=torch.tensor([seq[target_idx-jdtc.CONTEXT:target_idx]])
        logits,_=net(x)
        p=mix*jdtc.born_rule(logits[0,-1,:c],temp)+(1-mix)*prior
        # Arbitrary fixed bit extraction from categorical output. It cannot
        # predict independent future random bits without a physical signal.
        p1=float(p[1::2].sum())
        if not 0<=p1<=1:raise RuntimeError("INVALID_BORN_BIT_PROBABILITY")
        results.append(round(p1,9))
    return {
      "probabilities_p1":results,
      "bits":"".join("1" if p>=.5 else "0" for p in results),
      "bit_extraction":"Sum Born-normalized probabilities of odd category IDs in a past JSON window",
      "class_count":c,
      "trained_input_split":"TRAIN_ONLY",
      "temperature":temp,
      "validation_model_blend":mix
    }


def predict(args):
    snap=read(args.snapshot)
    h=sha(args.snapshot)
    before,bt,bm=load_net(args.before,h)
    after,at,am=load_net(args.after,h)
    early_epoch=time.time()
    comparison={
        "schema":"janus.principle.deutsch_v2.blinded_before_after_early.v1",
        "trial_id":args.trial_id,
        "issued_at_epoch_utc":early_epoch,
        "issued_at_utc":datetime.fromtimestamp(early_epoch,timezone.utc).isoformat(),
        "future_target_already_known":False,
        "future_target_source":"OS secrets.token_bytes 32 bytes in later independent GitHub runner after t0+120s",
        "primary_null":"P(correct bit)=0.5 for independently generated future OS random bits; no past communication",
        "model_before":{"source":"JDTC v1 40-river run 42137543171", "weights_sha256":sha(args.before),
                        **predictions(before,snap,args.trial_id,bt,bm)},
        "model_after":{"source":"JDTC v2 Deutsch-inspired 40-river new model", "weights_sha256":sha(args.after),
                       **predictions(after,snap,args.trial_id,at,am)},
        "snapshot_sha256":h,
        "source_head":snap["source_head"],
        "primary_test":"256 unselected future bits; fixed early predictions before independent late RNG",
        "paired_model_comparison":"Exact one-sided binomial McNemar on discordant bits, AFTER greater than BEFORE; 0.001 alpha",
        "secondary_test":"32 complete 8-bit messages, chance full-byte match 1/256 each",
        "alpha":ALPHA,
        "no_physical_time_channel":True,
        "unconditional_only":True,
        "physical_past_message_proven":False,
        "book_guidance":"Deutsch's quantum computation, epistemology, evolution and quantum physics supply falsifiability/normalization constraints, not a channel from the future.",
        "book_url":BOOK_URL,
    }
    write(args.output,comparison)
    print(json.dumps({k:v for k,v in comparison.items() if k not in ("model_before","model_after")},
                     indent=2))


def compare(args):
    early=read(args.early);later=read(args.late)
    if early["schema"]!="janus.principle.deutsch_v2.blinded_before_after_early.v1":
        raise RuntimeError("INVALID_EARLY_SCHEMA")
    if later["schema"]!="janus.retro.lab.independent_future_rng.v1" or early["trial_id"]!=later["trial_id"]:
        raise RuntimeError("BAD_FUTURE_SCHEMA_OR_TRIAL_ID")
    a=time.time()
    confirmed=float(later["receiver_commit_confirmed_epoch"])
    generated=float(later["future_generated_epoch_utc"])
    if not (early["issued_at_epoch_utc"]<=confirmed and generated>=confirmed+120):
        raise RuntimeError("INVALID_REAL_TIME_ORDER")
    payload=bytes.fromhex(later["target_payload_hex"])
    if len(payload)!=32 or hashlib.sha256(payload).hexdigest()!=later["target_sha256"]:
        raise RuntimeError("TARGET_DIGEST_INVALID")
    future="".join(f"{z:08b}" for z in payload)
    if future!=later["future_bits"] or len(future)!=N:raise RuntimeError("TARGET_BITS_CORRUPT")
    comp={}
    bitstrings={}
    for key in ("model_before","model_after"):
        d=early[key]
        bits=d["bits"];probs=d["probabilities_p1"]
        if len(bits)!=N or len(probs)!=N or set(bits)-{"0","1"}:raise RuntimeError("BAD_EARLY_VECTOR")
        if any(not math.isfinite(p) or not 0<=p<=1 for p in probs):raise RuntimeError("INVALID_PROBABILITIES")
        correct=sum(x==y for x,y in zip(bits,future))
        byte_correct=sum(bits[i:i+8]==future[i:i+8] for i in range(0,N,8))
        score=sum((p-int(y))**2 for p,y in zip(probs,future))/N
        comp[key]={
            "correct_bits":correct,
            "total_bits":N,
            "accuracy":round(correct/N,6),
            "binomial_one_sided_pvalue":tail(N,correct),
            "brier":round(score,8),
            "correct_complete_bytes":byte_correct,
            "complete_bytes":N//8,
            "full_256_bit_exact_match":bits==future,
            "null_expected_accuracy":.5,
            "null_expected_brier_for_constant_half":.25,
        }
        bitstrings[key]=bits
    b0,b1=bitstrings["model_before"],bitstrings["model_after"]
    gain=sum(b1[i]==future[i] and b0[i]!=future[i] for i in range(N))
    loss=sum(b0[i]==future[i] and b1[i]!=future[i] for i in range(N))
    discordant=gain+loss
    result={
        "schema":"janus.principle.deutsch_v2.blinded_before_after_result.v1",
        "trial_id":early["trial_id"],
        "early_issued_at_utc":early["issued_at_utc"],
        "future_created_utc":later["future_generated_utc"],
        "seconds_after_committed_early_A":round(generated-confirmed,6),
        "early_file_sha256":sha(args.early),
        "future_target_sha256":later["target_sha256"],
        "models":comp,
        "difference":{
            "correct_bit_delta_v2_minus_v1":comp["model_after"]["correct_bits"]-comp["model_before"]["correct_bits"],
            "brier_delta_v2_minus_v1":round(comp["model_after"]["brier"]-comp["model_before"]["brier"],8),
            "new_model_only_correct":gain,
            "old_model_only_correct":loss,
            "paired_discordant_bits":discordant,
            "mcnemar_exact_one_sided_pvalue":tail(discordant,gain) if discordant else 1.,
            "v2_beats_v1_at_preregistered_alpha_001":(tail(discordant,gain)<ALPHA) if discordant else False,
            "v2_beats_chance_alpha_001":comp["model_after"]["binomial_one_sided_pvalue"]<ALPHA
        },
        "all_attempts_included":True,
        "no_postselection":True,
        "physical_backward_channel_connected":False,
        "claim_status":"NO_PHYSICAL_RETROCAUSALITY_ESTABLISHED",
        "runtime_seconds":round(time.time()-a,6)
    }
    write(args.output,result)
    print(json.dumps(result,indent=2))


def cli():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="mode",required=True)
    pre=sub.add_parser("predict")
    for a in ("trial-id","before","after","snapshot","output"):pre.add_argument("--"+a,required=True)
    post=sub.add_parser("compare")
    for a in ("early","late","output"):post.add_argument("--"+a,required=True)
    args=p.parse_args()
    if args.mode=="predict":predict(args)
    else:compare(args)


if __name__=="__main__":cli()
