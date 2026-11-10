#!/usr/bin/env python3
"""JANUS-011C: exact cyclic fixed-point toy vs ordinary forward-time no-go.

The algebra models an assumed future-dependent closed loop; it DOES NOT
implement physical backwards communication. All probabilities are rational
until Shannon bits and approximate power are calculated.

Compare:
- C-dependent, normalized row-stochastic 2-state loop pi_C = pi_C T_C.
- source-independent forward chronological circuit: A=f(U), late do(C).
- externally distinguishable capacity is model-internal only; no hardware.

Nonnegativity and uniqueness are verified without postselection.
Study whether consistency alone constrains a physically meaningful signal:
it does not; an adjustable loop can yield anything from 0 to ~1 bit.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import json
from math import ceil, log2, sqrt
from pathlib import Path
from statistics import NormalDist

SCHEMA="janus.retro011c.closed_loop_and_chronology_no_go.v1"
REFERENCE_N=16384
ALPHA=0.001
POWER=0.9
BASE={
    0:(F(1,5),F(3,10)), # T_0: 0->1 = .2, 1->0 = .3
    1:(F(3,10),F(1,5)), # T_1: 0->1 = .3, 1->0 = .2
}
NOISE=(F(0),F(1,10),F(1,4),F(1,2))
Q_NEAR_DETERMINISTIC=F(1,100)
Q_NULL=F(1,2)

def fstr(x: F)->str:
    return str(x.numerator) if x.denominator==1 else f"{x.numerator}/{x.denominator}"

def transition(u:F,v:F):
    if type(u) is not F or type(v) is not F:
        raise ValueError("ONLY_EXACT_RATIONAL_PROBABILITIES")
    if u<0 or v<0 or u>1 or v>1 or u+v==0:
        raise ValueError("INVALID_OR_NONUNIQUE_TRANSITION")
    return ((1-u,u),(v,1-v))

def fixed_point(u:F,v:F):
    t=transition(u,v)
    p=(v/(u+v),u/(u+v))
    assert sum(p)==1
    assert all(0<=x<=1 for row in t for x in row)
    assert all(sum(row)==1 for row in t)
    assert p[0]*t[0][0]+p[1]*t[1][0]==p[0]
    assert p[0]*t[0][1]+p[1]*t[1][1]==p[1]
    return p

def future_control(c:int,eps:F=F(0)):
    if type(c) is not int or c not in (0,1):raise ValueError("CHOICE_MUST_BE_BINARY")
    if type(eps) is not F or not F(0)<=eps<=F(1,2):
        raise ValueError("CONTROL_NOISE_MUST_BE_0_TO_1_OVER_2")
    u,v=BASE[c]
    other_u,other_v=BASE[1-c]
    u=(1-eps)*u+eps*other_u
    v=(1-eps)*v+eps*other_v
    return {"u":u,"v":v,"p":fixed_point(u,v)}

def binary_entropy(p:F)->float:
    if p==0 or p==1:return 0.
    if p<0 or p>1:raise ValueError("INVALID_ENTROPY_ARGUMENT")
    x=float(p)
    return -x*log2(x)-(1-x)*log2(1-x)

def capacity_for_symmetric_pair(p0:F,p1:F)->float:
    if p0+p1!=1:raise ValueError("NOT_A_BINARY_SYMMETRIC_CHANNEL")
    return 1.-binary_entropy(p0)

def cyclic_family():
    examples=[]
    for eps in NOISE:
        a=future_control(0,eps)
        b=future_control(1,eps)
        delta=b["p"][1]-a["p"][1]
        cap=capacity_for_symmetric_pair(a["p"][1],b["p"][1])
        examples.append({
          "late_choice_flip_probability":float(eps),
          "late_choice_flip_fraction":fstr(eps),
          "full_early_P_A1_given_do_C0":float(a["p"][1]),
          "full_early_P_A1_given_do_C1":float(b["p"][1]),
          "operational_delta_with_ASSUMED_future_loop":float(delta),
          "exact_delta_fraction":fstr(delta),
          "SHANNON_capacity_bits_per_use_UNREALIZED_PHYSICALLY":cap,
          "postselected_trials":0,
          "all_outcome_probabilities_normalized":True
        })
    assert examples[-1]["operational_delta_with_ASSUMED_future_loop"]==0
    return examples

def unconstrained_capacity():
    def family(q:F):
        # Sum u+v = 1/2 in both settings; p1=q and 1-q.
        u0=F(1,2)*q;v0=F(1,2)*(1-q)
        u1=v0;v1=u0
        a=fixed_point(u0,v0)[1];b=fixed_point(u1,v1)[1]
        assert a==q and b==1-q
        return {
          "noise_early_bit_error":float(q),
          "full_stochastic_matrix_rows_positive":0<q<1,
          "P_A1_given_C0":float(a),
          "P_A1_given_C1":float(b),
          "capacity_bits_per_use_in_toy":capacity_for_symmetric_pair(a,b),
          "physical_backward_channel_proven":False
        }
    return {
      "no_signal_symmetric_loop":family(Q_NULL),
      "near_one_bit_symmetric_loop":family(Q_NEAR_DETERMINISTIC),
      "explanation":"Free choice of the loop kernel can make Shannon capacity anywhere near zero to one bit, so positivity, full inclusion and a fixed point do not identify a physical model.",
      "no_experiment_could_select_kernels_without_independent_physics":True
    }

def forward_no_go():
    # Earliest accessible A determined by preexisting exogenous U. Later C
    # generated without any path to A. Intervening on C changes no already
    # committed A distribution, regardless of how late C is chosen.
    U={0:F(1,2),1:F(1,2)}
    outcomes=[]
    for late_c in (0,1):
        P_A1=sum((p for u,p in U.items() if u==1),F(0))
        outcomes.append({"do_C":late_c,"P_committed_early_A1":float(P_A1)})
    return {
      "simple_forward_SCM":"U sampled at t0, A=U written at t1, C chosen independently at t2>t1",
      "chronology":"No future-to-past edge by construction",
      "late_intervention_distributions":outcomes,
      "interventional_delta":outcomes[1]["P_committed_early_A1"]-outcomes[0]["P_committed_early_A1"],
      "quantum_extension":"Any local CPTP map on future B preserves the earlier marginal: Tr_B[(I tensor E_C)(rho_AB)]=Tr_B(rho_AB).",
      "no_go_scope":"Standard forward directed model with later independent C and no backwards physical edge; not a general theorem excluding all exotic physics."
    }

def chronology_audit():
    # Unlike numerical self-consistency, a forward-time algorithm that
    # must COMMIT A before C is provided cannot invoke the C-dependent
    # stationary solution at the earlier time.
    return {
      "required_input_to_compute_pi_C":"late C",
      "is_C_available_at_early_commit_under_forward_computation":False,
      "can_online_early_record_be_computed_by_this_formula_without_future_input":False,
      "new_physical_law_provided_for_returning_C_before_its_generation":False,
      "physically_authenticated_early_record_created":False,
      "mathematical_loop_was_assumed_not_derived":True,
      "separate_independent_custodian_and_hardware_gate":"JANUS-PHYSICAL-LATE-CHOICE-010 / JANUS-010O",
      "consequence":"A solver that evaluates pi_C after seeing C does not send any information to an observer already in the past."
    }

def sample_size():
    # Formula is a planning approximation for independent iid Bernoulli arms
    # near p=.5, 1:1 allocation, ignoring full experimental errors.
    z=NormalDist().inv_cdf(1-ALPHA/2)
    t=NormalDist().inv_cdf(POWER)
    return {
      "two_sided_alpha":ALPHA,"nominal_power":POWER,
      "hypothetical_delta":.2,
      "total_trials_for_90_percent_power_iid_gaussian_approx":ceil((z+t)**2/.2**2),
      "previously_frozen_010_total_trials_unmodified":REFERENCE_N,
      "these_are_not_actual_physical_trials":True,
      "limitations":"Effect size .2 was inserted by model construction. Nominal power ignores all hardware errors, memory and external validation."
    }

def result():
    curve=cyclic_family()
    return {
      "schema":SCHEMA,
      "experiment":"JANUS-011C pure classical stationary fixed-point time-loop TOY and forward-time impossibility baseline",
      "future_dependent_transition":{"C0":[[fstr(x) for x in row] for row in transition(*BASE[0])],
                                      "C1":[[fstr(x) for x in row] for row in transition(*BASE[1])]},
      "base_exact_pi_C0":[fstr(x) for x in fixed_point(*BASE[0])],
      "base_exact_pi_C1":[fstr(x) for x in fixed_point(*BASE[1])],
      "stationary_unique":True,
      "row_stochastic_no_selection":True,
      "noise_robustness":curve,
      "capacity_unidentifiability":unconstrained_capacity(),
      "chronological_forward_control":forward_no_go(),
      "chronology_audit":chronology_audit(),
      "approximate_hypothetical_test_size":sample_size(),
      "citations":[
         "https://doi.org/10.1103/PhysRevD.44.3197",
         "https://doi.org/10.1103/znyd-npk5"
      ],
      "comparison_with_Deutsch_CTC":"Shares self-consistency/fixed-point motif, but this is a classical Markov toy NOT the Deutsch quantum CTC dynamical map.",
      "comparison_with_Ji_Lloyd_Wilde":"This Shannon binary toy capacity is NOT the noisy P-CTC channel capacity theorem of Ji/Lloyd/Wilde; no such quantum channel is constructed.",
      "real_physical_trials":0,
      "observed_early_precommitted_A_data":False,
      "observed_future_generated_C_data":False,
      "source_time_loop_observed":False,
      "operational_retrocausal_signal_proven":False,
      "status":"EXACT_NORMALIZED_CYCLIC_TOY__PHYSICAL_MECHANISM_UNKNOWN"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    data=result()
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(data,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        f.write("\n")
    print("JANUS_011C_RESULT "+json.dumps({
      "early_P1_c0":float(fixed_point(*BASE[0])[1]),
      "early_P1_c1":float(fixed_point(*BASE[1])[1]),
      "mathematical_delta":curve if False else data["noise_robustness"][0]["operational_delta_with_ASSUMED_future_loop"],
      "capacity_bits":data["noise_robustness"][0]["SHANNON_capacity_bits_per_use_UNREALIZED_PHYSICALLY"],
      "capacity_at_flip_half":data["noise_robustness"][-1]["SHANNON_capacity_bits_per_use_UNREALIZED_PHYSICALLY"],
      "near_one_bit_toy":data["capacity_unidentifiability"]["near_one_bit_symmetric_loop"]["capacity_bits_per_use_in_toy"],
      "forward_causal_delta":data["chronological_forward_control"]["interventional_delta"],
      "real_physical_trials":0,
      "retrocausality_proven":False
    },sort_keys=True),flush=True)

if __name__=="__main__":main()
