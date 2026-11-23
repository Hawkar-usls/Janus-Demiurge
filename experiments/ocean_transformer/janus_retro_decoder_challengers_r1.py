#!/usr/bin/env python3
"""Four PRECOMMITTED early-only decoders for a future blind JANUS test.

Exactly four fixed transformations of early (A,C) registers; no retrospective
selection of a winning model or peeking at B to generate a guess.
The result can identify a reproducible predictive anomaly IF a future source
has exploitable structure. It cannot itself create a physical retrochannel.
"""
from __future__ import annotations

from janus_retro_raw_recount_r1 import require, tail_fair_bits

IDS = ("RAW", "INVERTED", "CONFIDENCE_HIGH_FLIP",
       "CONFIDENCE_LOW_FLIP")
ALPHA_FAMILYWISE = 1e-4


def precommitted_decoders(early_bits, early_confidence_class):
    a=early_bits
    c=early_confidence_class
    require(type(a) is list and type(c) is list and
            len(a)==len(c)==256 and
            all(type(x) is int and x in (0,1) for x in a+c),
            "INVALID_PRECOMMITTED_EARLY_REGISTERS")
    # All four models were frozen BEFORE the new future test window.
    return {
        "RAW":a[:],
        "INVERTED":[x^1 for x in a],
        "CONFIDENCE_HIGH_FLIP":[x^y for x,y in zip(a,c)],
        "CONFIDENCE_LOW_FLIP":[x^(1^y) for x,y in zip(a,c)],
    }


def validate_addendum(info):
    require(type(info) is dict and
            info.get("schema")=="janus.retro.prospective_early_decoder_addendum.v1" and
            info.get("candidate_count")==4 and
            info.get("alpha_familywise")==ALPHA_FAMILYWISE and
            info.get("decision_locked_before_eligible_future_data") is True and
            info.get("retrospective_fit_or_best_candidate_selection") is False,
            "INVALID_OR_UNFROZEN_ADDENDUM")
    require(tuple(x.get("id") for x in info.get("candidates",[]))==IDS,
            "CANDIDATE_FAMILY_CHANGED")
    return True


def score_challengers(groups, manifest):
    validate_addendum(manifest)
    require(type(groups) is list and len(groups)==24,
            "FROZEN_SAMPLE_SIZE_MISMATCH")
    correct={name:0 for name in IDS}
    for a,c,b in groups:
        require(type(b) is list and len(b)==256 and
                all(type(x) is int and x in (0,1) for x in b),
                "INVALID_FUTURE_BITS")
        for name,early_forecast in precommitted_decoders(a,c).items():
            correct[name]+=sum(x==y for x,y in zip(early_forecast,b))
    total=24*256
    score={name:{
        "correct":correct[name],
        "total":total,
        "accuracy":correct[name]/total,
        "exact_one_sided_binomial_p":tail_fair_bits(total,correct[name])
    } for name in IDS}
    minimum=min(row["exact_one_sided_binomial_p"] for row in score.values())
    adjusted=min(1.,4*minimum)
    return {
        "schema":"janus.retro.prospective_early_decoder_challengers.v1",
        "candidate_ids":list(IDS),
        "all_precommitted_candidates":score,
        "familywise_bonferroni_min_p":adjusted,
        "alpha_familywise":ALPHA_FAMILYWISE,
        "candidate_familywise_anomaly":adjusted<ALPHA_FAMILYWISE,
        "late_bit_used_to_generate_early_decoder":False,
        "all_24_x_256_bits_scored":True,
        "no_postselection":True,
        "candidate_chosen_posthoc":False,
        "future_entropy_independence_external_proof":False,
        "physical_retrocausality_proven":False,
        "promotion_allowed":False,
        "note":"No real physical information can be recovered from a truly independent future fair bit without a physical influence or leakage. This only checks whether any precommitted decoder scores unusually well on new trials."
    }
