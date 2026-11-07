#!/usr/bin/env python3
"""JANUS candidate search: pre-existing EARLY joint witness vs LATE bit.

Investigate whether the pair (early prediction A, precommitted confidence
class C) is related to a later independent OS RNG bit B, even if the
marginals A and C separately appear independent. This is an EXPLORATORY
post-hoc statistic on previously observed trials, not a preregistered
signal or an experimentally realized jamming process.

A and C are derived strictly from early.json. Late target is read only after
those fields have been parsed and scored. No late-outcome conditioning.
Permutation null shuffles B *within each completed trial* (keeps per-trial
B balance fixed and avoids pooling unrelated run drifts).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

from janus_retro_raw_recount_r1 import examine, load, require, validate_bits

CONFIDENCE_DEVIATION_CUTOFF = .25
MAX_BITS = 256 * 64


def total_variation(categories, bits, size=4):
    require(len(categories)==len(bits) and len(bits)>0, "BAD_INPUT_LENGTHS")
    require(all(type(i) is int and 0<=i<size for i in categories),
            "BAD_CATEGORY")
    require(all(type(b) is int and b in (0,1) for b in bits),
            "BAD_FUTURE_BIT")
    counts=[[0,0] for _ in range(size)]
    for i,b in zip(categories,bits):
        counts[i][b]+=1
    n0=sum(x[0] for x in counts)
    n1=sum(x[1] for x in counts)
    require(n0 and n1, "DEGENERATE_FUTURE_SETTINGS")
    return sum(abs(c[0]/n0 - c[1]/n1) for c in counts)/2


def score(a,c,b):
    marginal_a=total_variation(a,b,2)
    marginal_c=total_variation(c,b,2)
    joint=total_variation([2*x+y for x,y in zip(a,c)],b,4)
    # A refined partition has >= the TV of either marginal. The excess is
    # an interaction witness, not itself an operational future message.
    return {
        "A_marginal_tv":marginal_a,
        "C_marginal_tv":marginal_c,
        "A_C_joint_tv":joint,
        "joint_excess_over_largest_marginal":max(0.,joint-max(marginal_a,marginal_c)),
    }


def permutation_pvalue(groups, iterations=999, seed=20261107):
    require(99<=iterations<=9999 and type(seed) is int,
            "INVALID_PERMUTATION_BUDGET")
    arr=[(a,c,b) for a,c,b in groups]
    a_all=[i for a,_,_ in arr for i in a]
    c_all=[i for _,c,_ in arr for i in c]
    b_all=[i for _,_,b in arr for i in b]
    require(0<len(b_all)<=MAX_BITS, "INVALID_ARCHIVE_COUNT")
    observed=score(a_all,c_all,b_all)
    randomizer=random.Random(seed)
    exceed_joint=0
    exceed_excess=0
    for _ in range(iterations):
        permuted=[]
        for _,_,b in arr:
            x=b.copy()
            randomizer.shuffle(x)
            permuted+=x
        test=score(a_all,c_all,permuted)
        exceed_joint += test["A_C_joint_tv"] >= observed["A_C_joint_tv"]-1e-15
        exceed_excess += (
            test["joint_excess_over_largest_marginal"] >=
            observed["joint_excess_over_largest_marginal"]-1e-15
        )
    p_joint=(exceed_joint+1)/(iterations+1)
    p_excess=(exceed_excess+1)/(iterations+1)
    return {
        **observed,
        "permutation_p_joint_tv_within_trial":p_joint,
        "permutation_p_joint_interaction_within_trial":p_excess,
        # Two exploratory views were queried; Bonferroni is conservative.
        # Neither p-value is confirmatory on this retrospective sample.
        "bonferroni_adjusted_min_p_two_views":min(1.,2*min(p_joint,p_excess)),
        "permutations":iterations,
        "permutation_seed":seed,
        "shuffle_scheme":"permute target bits within each completed 256-bit trial",
        "conditional_exchangeability_not_externally_verified":True,
        "exploratory_not_prospective":True
    }


def candidate_groups(root):
    dirs=sorted(d for d in root.iterdir()
                if d.is_dir() and d.name.startswith("janus-retro-"))
    require(0<len(dirs)<=64,"INVALID_ARCHIVE_SIZE")
    groups=[]
    for d in dirs:
        examine(d)  # comprehensive independent bit/hash/chronology audit first
        early=load(d/"early.json")
        predicted=validate_bits(early["predicted_bits"])
        p=early["p1_model_probs"]
        a=[int(i) for i in predicted]
        c=[int(abs(v-.5) >= CONFIDENCE_DEVIATION_CUTOFF) for v in p]
        future=load(d/"future.json")
        b=[int(i) for i in validate_bits(future["future_bits"])]
        require(len(a)==len(c)==len(b)==256,"BAD_TRIAL_SIZE")
        groups.append((a,c,b))
    return groups


def run(root, iterations=999, seed=20261107):
    groups=candidate_groups(root)
    result=permutation_pvalue(groups,iterations,seed)
    return {
        "schema":"janus.retro.early_joint_witness_exploratory.r1",
        "source":"historical JANUS Retro Byte A/B ledger, unmodified",
        "trial_count":len(groups),
        "total_bit_positions":sum(len(b) for _,_,b in groups),
        "early_A":"precommitted model predicted bit",
        "early_C":f"precommitted model confidence class |p1-0.5| >= {CONFIDENCE_DEVIATION_CUTOFF}",
        "late_B":"OS CSPRNG bit, generated after nominal 120-sec ledger delay",
        "observed":result,
        "all_early_and_late_positions_used":True,
        "no_late_herald_postselection":True,
        "historical_research_question_chosen_after_outcomes_existed":True,
        "permutation_test_is_exploratory":True,
        "correlated_bits_within_epoch_and_multiple_testing_not_independently_certified":True,
        "preregistered_for_existing_archive":False,
        "independent_physical_jamming_resource":False,
        "externally_certified_early_log":False,
        "physical_backward_signal_detected":False,
        "promotion_to_production":False,
        "interpretation":"A joint statistical association in past data, if any, is NOT a retrocausal signal; future entropy and physical chronology are not externally certified, the witness was selected after viewing this campaign, and independent future replication would be required."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",type=Path,required=True)
    p.add_argument("--permutations",type=int,default=999)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    require(not a.out.exists(),"REFUSE_OVERWRITE")
    result=run(a.ledger,iterations=a.permutations)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"trial_count":result["trial_count"],
       "observed":result["observed"],
       "physical_backward_signal_detected":False},indent=2))


if __name__=="__main__":
    main()
