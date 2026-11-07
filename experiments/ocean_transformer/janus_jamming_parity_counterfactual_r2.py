#!/usr/bin/env python3
"""JANUS R2 exact jamming/XOR counterfactual: no physical retrochannel.

A minimal 3-variable model of *joint* dependence on a later B, deliberately
not the full geometry-dependent Vilasini-Colbeck operational certification
protocol. X and Z are two earlier records, B a later independent free choice.

NORMAL: P(X,Z,B)=1/8. Early X,Z cannot jointly predict future B.
HYPOTHETICAL JAMMING: P(X,Z,B)=1/4 for B=X XOR Z. Marginal X,Z
independent of B but joint distribution depends on B. To sample this in an
ordinary CPU, B must be supplied BEFORE X,Z: future leak/causal reversal
is assumed, not created.
POSTSELECTED NORMAL: keep only normal trials with B=X XOR Z. Conditional
joint distribution equals the hypothetical candidate, but acceptance is 1/2
and cannot be known by an earlier observer before B.

Paper motivation: Vilasini & Colbeck, PRR 8 013070 (2026),
DOI 10.1103/h31d-wqyg. This script is an original simplified toy, NOT a
claimed physical reproduction of the postquantum jamming apparatus.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path


def distribution(name):
    if name == "normal":
        return {(x,z,b):Fraction(1,8)
                for x in (0,1) for z in (0,1) for b in (0,1)}
    if name == "ideal_jamming_requires_future_parameter":
        return {(x,z,b):Fraction(1,4) if b==(x^z) else Fraction(0)
                for x in (0,1) for z in (0,1) for b in (0,1)}
    if name == "late_selected_normal":
        raw=distribution("normal")
        acceptance=sum(p for (x,z,b),p in raw.items() if b==(x^z))
        return {k:p/acceptance if k[2]==(k[0]^k[1]) else Fraction(0)
                for k,p in raw.items()}
    raise ValueError("UNKNOWN_HYPOTHETICAL_MODEL")


def summarize(name):
    d=distribution(name)
    assert sum(d.values())==1
    cond={}
    for b in (0,1):
        pb=sum(p for (x,z,bi),p in d.items() if bi==b)
        assert pb==Fraction(1,2)
        joint={(x,z):d[(x,z,b)]/pb for x in (0,1) for z in (0,1)}
        cond[b]=joint
    def distance(c0,c1):
        return sum(abs(c0[key]-c1[key]) for key in c0)/2
    mX={b:{x:sum(cond[b][x,z] for z in (0,1)) for x in (0,1)}
        for b in (0,1)}
    mZ={b:{z:sum(cond[b][x,z] for x in (0,1)) for z in (0,1)}
        for b in (0,1)}
    perfect=sum(p for (x,z,b),p in d.items() if (x^z)==b)
    acceptance=Fraction(1,2) if name=="late_selected_normal" else Fraction(1)
    return {
        "model":name,
        "fraction_joint_conditional_on_B": {
            str(b):{f"{x}{z}":str(cond[b][x,z])
                    for x in (0,1) for z in (0,1)}
            for b in (0,1)},
        "marginal_X_TV_between_B_choices":float(distance(mX[0],mX[1])),
        "marginal_Z_TV_between_B_choices":float(distance(mZ[0],mZ[1])),
        "joint_XZ_TV_between_B_choices":float(distance(cond[0],cond[1])),
        "parity_predicts_B_if_scored_on_distribution":str(perfect),
        "fraction_of_all_original_attempts_retained":str(acceptance),
        "late_herald_required":name=="late_selected_normal",
        "future_B_needed_to_sample_prior_XZ":(
            name=="ideal_jamming_requires_future_parameter"),
        "earlier_receiver_has_operational_future_B":False,
        "physical_backward_transport_implemented":False,
    }


def report():
    all_= {name:summarize(name) for name in
        ("normal","ideal_jamming_requires_future_parameter",
         "late_selected_normal")}
    normal=all_["normal"]
    ideal=all_["ideal_jamming_requires_future_parameter"]
    sifted=all_["late_selected_normal"]
    assert normal["joint_XZ_TV_between_B_choices"]==0
    assert normal["parity_predicts_B_if_scored_on_distribution"]=="1/2"
    assert ideal["joint_XZ_TV_between_B_choices"]==1
    assert ideal["marginal_X_TV_between_B_choices"]==0
    assert ideal["marginal_Z_TV_between_B_choices"]==0
    assert ideal["future_B_needed_to_sample_prior_XZ"]
    assert sifted["joint_XZ_TV_between_B_choices"]==1
    assert sifted["fraction_of_all_original_attempts_retained"]=="1/2"
    assert sifted["late_herald_required"]
    assert ideal["fraction_joint_conditional_on_B"] == sifted["fraction_joint_conditional_on_B"]
    return {
        "schema":"janus.jamming_conditional_correlations.exact_cpu.r2",
        "literature_doi":"10.1103/h31d-wqyg",
        "kind":"original_simplified_parity_toy_not_full_PRC_protocol",
        "comparative_models":all_,
        "fundamental_distinction":"Hypothetical jamming's conditional joint distribution is indistinguishable from a postselected normal process if only later-selected records are compared. To claim usable past effect requires all early records fixed before B, no selection, and a physical mechanism producing the joint distribution without using B as an earlier CPU input.",
        "non_signaling_marginals_are_not_enough_for_joint_causality":True,
        "no_postselection_for_primary_proof":True,
        "no_external_physical_implementation":True,
        "no_backward_in_time_classical_bit_implemented":True,
        "no_production_promotion":True,
        "scientific_verdict":"MATHEMATICAL_CONTRAST_PASS__PHYSICAL_RETROCAUSALITY_NOT_ESTABLISHED"
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    value=report()
    out=Path(args.out)
    if out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n",
                   encoding="utf-8")
    print(json.dumps({
        "normal_joint_TV":value["comparative_models"]["normal"]["joint_XZ_TV_between_B_choices"],
        "hypothetical_joint_TV":value["comparative_models"]["ideal_jamming_requires_future_parameter"]["joint_XZ_TV_between_B_choices"],
        "selected_acceptance":value["comparative_models"]["late_selected_normal"]["fraction_of_all_original_attempts_retained"],
        "physical_retrocausality":False
    }))


if __name__=="__main__":
    main()
