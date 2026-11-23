#!/usr/bin/env python3
"""JANUS Addressed Handshake R2: CPU-only 2x2 late-choice research pilot.

The TESTABLE question comes from JANUS-RETRO-TAHYON-ADDRESSING-DEPENDENCE:
does a future intentional ADDRESS to a previous request change the ability of
a precommitted request-aware guess to predict a later *independent* bit, vs a
precommitted topic-only guess and sham routing on the SAME target?

This script does not send a message into the past, and it cannot certify
independence of OS RNG or physical time ordering. In a forward-causal model
with independent late choice, any such effect should vanish in expectation.

Three isolated CLI modes (early, future, score). The future generator is not
passed an early filename and MUST NEVER inspect the earlier guess or key.
GitHub Actions uses separate jobs and uploads both full ledgers before scoring.
All 64 requests are included. A 2x2 interaction is compared to a restricted
permutation null; the pilot is not powered to prove a physical mechanism.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import secrets
import time

N = 64
PERMUTATIONS = 1999
SCHEMA_EARLY = "janus.addressed_handshake.early.r2"
SCHEMA_FUTURE = "janus.addressed_handshake.future.r2"
SCHEMA_SCORE = "janus.addressed_handshake.score.r2"
LABELS = ("matched_request", "control_request")
MODES = ("addressed", "sham")


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(x):
    return hashlib.sha256(x).hexdigest()


def onebit(*parts):
    raw=b"\0".join(x.encode("utf-8") for x in parts)
    return hashlib.sha256(raw).digest()[0] & 1


def utc():
    return datetime.now(timezone.utc).isoformat()


def create_early(trial_id, nonce=None):
    require(type(trial_id) is str and trial_id.isdigit() and
            len(trial_id) <= 30, "INVALID_TRIAL_ID")
    nonce = nonce if nonce is not None else secrets.token_hex(32)
    require(type(nonce) is str and len(nonce)==64 and
            all(c in "0123456789abcdef" for c in nonce),
            "INVALID_NONCE")
    rows=[]
    for i in range(N):
        request_type=LABELS[i % 2]
        topic=f"topic-{i % 4}"
        key=sha(f"janus-r2|request-key|{nonce}|{i}".encode())
        # This early request ID is a public label, not an entanglement or
        # physical retrocausal address. Future choice ignores it.
        a=onebit("addressed", nonce, key, str(i))
        u=onebit("topic_only", nonce, topic, str(i))
        rows.append({
            "trial_index":i, "request_type":request_type,
            "request_key_sha256":key, "topic":topic,
            "guess_addressed":a, "guess_unaddressed":u,
        })
    result={
        "schema":SCHEMA_EARLY,
        "trial_id":trial_id,
        "created_at_utc":utc(),
        "created_epoch_utc":time.time(),
        "trial_count":N,
        "records":rows,
        "records_sha256":sha(canonical(rows)),
        "future_target_not_generated":True,
        "late_routing_mode_not_yet_generated":True,
        "physical_early_clock_attested":False,
        "physical_retrocausal_channel":False,
    }
    return result


def create_future(trial_id):
    require(type(trial_id) is str and trial_id.isdigit() and
            len(trial_id)<=30, "INVALID_TRIAL_ID")
    # Balanced routing within each predeclared request type. Neither
    # early predictors nor request keys are loaded by this function.
    modes={}
    for k in (0,1):
        allocation=["addressed"]*16+["sham"]*16
        secrets.SystemRandom().shuffle(allocation)
        for j,m in enumerate(allocation):
            modes[2*j+k]=m
    rows=[{"trial_index":i, "route_mode":modes[i],
           "future_target_bit":secrets.randbits(1)}
          for i in range(N)]
    return {
        "schema":SCHEMA_FUTURE,
        "trial_id":trial_id,
        "created_at_utc":utc(),
        "generated_epoch_utc":time.time(),
        "trial_count":N,
        "records":rows,
        "records_sha256":sha(canonical(rows)),
        "randomness":"secrets.SystemRandom() and secrets.randbits(1)",
        "early_predictions_or_request_keys_loaded":False,
        "external_independent_QRNG_attested":False,
        "physical_backwards_transport":False
    }


def verify(e,l):
    require(type(e) is dict and type(l) is dict and
            e.get("schema")==SCHEMA_EARLY and
            l.get("schema")==SCHEMA_FUTURE, "INVALID_RECORD_SCHEMAS")
    require(e.get("trial_id")==l.get("trial_id") and
            type(e["trial_id"]) is str,"TRIAL_ID_MISMATCH")
    require(e.get("trial_count")==l.get("trial_count")==N,
            "INCOMPLETE_TRIAL_COUNTS")
    a,b=e.get("records"),l.get("records")
    require(type(a) is list and type(b) is list and
            len(a)==len(b)==N, "MISSING_TRIAL_RECORD")
    require(sha(canonical(a))==e.get("records_sha256") and
            sha(canonical(b))==l.get("records_sha256"),
            "RECORD_DIGEST_CONTRADICTION")
    require(type(e.get("created_epoch_utc")) in (int,float) and
            type(l.get("generated_epoch_utc")) in (int,float) and
            math.isfinite(e["created_epoch_utc"]) and
            math.isfinite(l["generated_epoch_utc"]) and
            e["created_epoch_utc"]<l["generated_epoch_utc"],
            "INTERNAL_CLOCK_ORDER_FAILED")
    counts={(rt,mode):0 for rt in LABELS for mode in MODES}
    for i,(a_i,b_i) in enumerate(zip(a,b)):
        require(type(a_i) is dict and
                set(a_i)=={"trial_index","request_type","request_key_sha256",
                            "topic","guess_addressed","guess_unaddressed"} and
                type(b_i) is dict and
                set(b_i)=={"trial_index","route_mode","future_target_bit"},
                "UNEXPECTED_OR_MISSING_FIELD")
        require(a_i["trial_index"]==b_i["trial_index"]==i and
                type(a_i["trial_index"]) is int and
                type(b_i["trial_index"]) is int,
                "TRIAL_INDEX_MISMATCH")
        require(a_i["request_type"]==LABELS[i%2] and
                b_i["route_mode"] in MODES, "INVALID_GROUP_DESIGN")
        require(type(a_i["topic"]) is str and
                a_i["topic"]==f"topic-{i%4}" and
                type(a_i["request_key_sha256"]) is str and
                len(a_i["request_key_sha256"])==64 and
                all(c in "0123456789abcdef"
                    for c in a_i["request_key_sha256"]),
                "INVALID_PRECOMMITTED_ADDRESS")
        require(all(type(v) is int and v in (0,1) for v in (
                a_i["guess_addressed"],a_i["guess_unaddressed"],
                b_i["future_target_bit"])), "NON_BINARY_VALUES")
        counts[(a_i["request_type"],b_i["route_mode"])]+=1
    require(all(v==16 for v in counts.values()), "UNBALANCED_FOUR_CELLS")
    return True


def exact_onesided_fair_tail(n,k):
    require(type(n) is int and type(k) is int and
            0<=k<=n<=N, "INVALID_MATCHED_PAIRS")
    return sum(math.comb(n,j) for j in range(k,n+1))/(2**n)


def interaction(rows):
    cells={(kind,route):[] for kind in LABELS for route in MODES}
    for r in rows:
        cells[(r["request_type"],r["route_mode"])].append(r["advantage"])
    if any(not v for v in cells.values()):
        raise ValueError("FOUR_CELLS_NOT_POPULATED")
    mean={k:sum(v)/len(v) for k,v in cells.items()}
    delta=(mean[("matched_request","addressed")] -
           mean[("matched_request","sham")] -
           mean[("control_request","addressed")] +
           mean[("control_request","sham")])
    return delta,mean


def score(early, future, permutations=PERMUTATIONS, seed=20261107):
    verify(early,future)
    require(type(permutations) is int and 99<=permutations<=9999,
            "PERMUTATION_BUDGET")
    rows=[]
    for a,b in zip(early["records"],future["records"]):
        target=b["future_target_bit"]
        success_a=int(a["guess_addressed"]==target)
        success_u=int(a["guess_unaddressed"]==target)
        rows.append({
            "request_type":a["request_type"],
            "route_mode":b["route_mode"],
            "target_bit":target,
            "guess_addressed_correct":success_a,
            "guess_unaddressed_correct":success_u,
            "advantage":success_a-success_u
        })
    delta,means=interaction(rows)
    # Paired discriminator. Predictions were both generated before B;
    # if the guesses disagree exactly one must be right for a fair bit.
    subset=[r for r in rows if r["request_type"]=="matched_request"
            and r["route_mode"]=="addressed"]
    plus=sum(r["advantage"]==1 for r in subset)
    minus=sum(r["advantage"]==-1 for r in subset)
    paired_p=exact_onesided_fair_tail(plus+minus, plus)
    rng=random.Random(seed)
    count_ge=0
    for _ in range(permutations):
        shuffled={}
        for kind in LABELS:
            modes=[r["route_mode"] for r in rows if r["request_type"]==kind]
            rng.shuffle(modes)
            shuffled[kind]=iter(modes)
        perm=[{**r, "route_mode":next(shuffled[r["request_type"]])}
              for r in rows]
        trial_delta,_=interaction(perm)
        count_ge+=trial_delta>=delta-1e-12
    permutation_p=(count_ge+1)/(permutations+1)
    return {
        "schema":SCHEMA_SCORE,
        "trial_id":early["trial_id"],
        "trials":N,
        "all_64_trials_included":True,
        "four_cells_n":{f"{kind}|{route}":16
                        for kind in LABELS for route in MODES},
        "prediction_advantage_by_cell":{
            f"{kind}|{route}":means[(kind,route)]
            for kind in LABELS for route in MODES},
        "addressing_interaction_difference_in_differences":delta,
        "paired_addressed_matched_discordant_plus":plus,
        "paired_addressed_matched_discordant_minus":minus,
        "paired_exact_one_sided_p":paired_p,
        "routing_label_permutation_p":permutation_p,
        "permutation_iterations":permutations,
        "permutation_seed":seed,
        "interpretation_limit":"The future OS RNG and routing are generated by ordinary software in forward time. An interaction, if statistically unusual, is not a physical retrocausal demonstration; multiple experiments and independent physical corroboration are required.",
        "precommit_digest":early["records_sha256"],
        "future_digest":future["records_sha256"],
        "no_postselection":True,
        "late_bits_generated_without_early_file":True,
        "external_early_timestamp_attested":False,
        "external_late_entropy_attested":False,
        "actual_message_in_past":False,
        "physical_retrocausal_signal_proven":False,
        "production_promote":False
    }


def write_new(path,object_):
    out=Path(path)
    if out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(object_,sort_keys=True,indent=2)+"\n",
                   encoding="utf-8")


def main():
    p=argparse.ArgumentParser()
    s=p.add_subparsers(dest="mode",required=True)
    e=s.add_parser("early")
    e.add_argument("--trial-id",required=True)
    e.add_argument("--out",required=True)
    f=s.add_parser("future")
    f.add_argument("--trial-id",required=True)
    f.add_argument("--out",required=True)
    sc=s.add_parser("score")
    sc.add_argument("--early",required=True)
    sc.add_argument("--future",required=True)
    sc.add_argument("--out",required=True)
    args=p.parse_args()
    if args.mode=="early":
        value=create_early(args.trial_id)
    elif args.mode=="future":
        value=create_future(args.trial_id)
    else:
        value=score(json.loads(Path(args.early).read_text()),
                    json.loads(Path(args.future).read_text()))
    write_new(args.out,value)
    print(json.dumps({
        "stage":args.mode,"trial_id":value["trial_id"],
        "model_verdict":"NO_PHYSICAL_RETROCAUSAL_SIGNAL",
        "statistic":value.get("addressing_interaction_difference_in_differences"),
        "p":value.get("routing_label_permutation_p")
    },sort_keys=True))


if __name__=="__main__":
    main()
