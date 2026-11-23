#!/usr/bin/env python3
"""JANUS-011A: four exact mathematical tests that LOCATE falsifiable hypotheses.

This is a theorem/TOY-MODEL and power study, not a physical quantum lab
measurement or time-travel discovery. No observations fitted, no stochastic
"lucky" selection, no QPU and no external network. Frozen examples:
  1) Bell |Phi+>: delayed Z vs X Bob basis does NOT change Alice's
     unconditioned distribution, although Bob-conditioned fringes vary.
  2) Non-trace-preserving future acceptance produces large selection-only
     *apparent* retrocausality; absent an early available success flag it
     yields no operational backwards channel.
  3) Retrocausal latent coupling may exist in a toy joint distribution
     while ALL accessible earlier observables have exactly zero information.
  4) Classical common-cause drift mimics an apparent future->past
     correlation but differs under the mathematical do(C) intervention.
  5) Predeclared detectable signal power, N and effect sizes for an
     externally witnessed independent physically late binary C.

Paper references documented in README; this script never claims an
ordinary classical CPU can construct a quantum backward-time channel.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

SCHEMA="janus.research.011a.retrocausality_math_candidate_map.v1"
ALPHA=0.001
TARGET_POWER=0.9
PHYSICAL010_N=16384
PLANNING_DELTAS=(0.005,0.01,0.02,0.03,0.04,0.05,0.1)
CTC_POST_RATES=(Fraction(0,1),Fraction(1,20),Fraction(1,2),Fraction(1,1))
HIDDEN_MISMATCH=Fraction(1,10)
CONFOUND_COPY_PROB=Fraction(11,20)
HYPOTHETICAL_SIGNAL_DELTA=Fraction(1,25)

def born_joint(a,b,c):
    """|Phi+> with Alice Z and Bob Z(c=0) or X(c=1) projectors."""
    if a not in (0,1) or b not in (0,1) or c not in (0,1):
        raise ValueError("BINARY_QUBIT_BASIS_REQUIRED")
    # Amplitude of (|00>+|11>)/sqrt(2), project Bob into
    # |0>,|1> for Z, or |+>,|-> for X.
    if c==0:return .5 if a==b else 0.
    return .25

def quantum_bell():
    conditional={}
    marginals={}
    raw={}
    for c in (0,1):
        key=str(c)
        table={f"{a}{b}":born_joint(a,b,c) for a in (0,1) for b in (0,1)}
        if abs(sum(table.values())-1)>1e-12:raise AssertionError("BORN_NOT_NORMALIZED")
        raw[key]=table
        marginals[key]={str(a):sum(born_joint(a,b,c) for b in (0,1)) for a in (0,1)}
        pb0=sum(born_joint(a,0,c) for a in (0,1))
        conditional[key]={"P_A0_given_B0":born_joint(0,0,c)/pb0}
    gap=marginals["1"]["0"]-marginals["0"]["0"]
    return {
       "source":"analytic_Bell_state_Phi_plus_standard_Born_rule",
       "causal_action":"Bob chooses measurement basis Z or X after Alice result",
       "joint_distributions":raw,
       "earlier_A_unconditional_P_A0_by_later_choice":{c:marginals[c]["0"] for c in ("0","1")},
       "after_B_outcome_selection_P_A0_given_B0_by_choice":{
           c:conditional[c]["P_A0_given_B0"] for c in ("0","1")},
       "unconditional_later_C_effect":gap,
       "operational_future_to_past_signal":False,
       "theorem":"For any local trace-preserving quantum channel E_C on B, Tr_B[(I tensor E_C)rho_AB] = Tr_B rho_AB. Nonselective local future operations do not change Alice's marginal."
    }

def postselect(r):
    if not isinstance(r,Fraction) or not 0<=r<=1:raise ValueError("INVALID_POSTSELECTION_RATE")
    # A and C are independent fair bits. Success S weights equal pairs 1,
    # unequal pairs r. The success flag is available only post factum.
    agree=1/(1+r)
    disagree=r/(1+r)
    d=agree-disagree
    return {
      "mismatch_acceptance_ratio":float(r),
      "unconditional_P_A1_given_C0":.5,
      "unconditional_P_A1_given_C1":.5,
      "unconditional_signal_delta":0.,
      "success_fraction":float((1+r)/2),
      "selected_P_A1_given_C0":float(disagree),
      "selected_P_A1_given_C1":float(agree),
      "apparent_selected_signal_delta":float(d),
      "precommitted_early_A_records_affected":False,
      "selection_is_not_a_backwards_usable_channel":True
    }

def entropy_bit(p):
    p=float(p)
    if not 0<=p<=1:raise ValueError("INVALID_PROBABILITY")
    if p==0 or p==1:return 0.
    return -p*math.log2(p)-(1-p)*math.log2(1-p)

def latent_retro_model(q):
    """C->lambda by MODEL stipulation, but lambda XOR fair R = observed A."""
    if not isinstance(q,Fraction) or not 0<=q<=1:raise ValueError("INVALID_NOISE")
    return {
       "C_is_uniform":True,
       "latent_lambda_matches_future_C_probability":float(1-q),
       "latent_lambda_future_C_mutual_information_bits":1-entropy_bit(q),
       "accessible_A_equals_lambda_xor_independent_fair_R":True,
       "accessible_A_future_C_mutual_information_bits":0.,
       "unconditional_signal_delta":0.,
       "note":"A future-dependent hidden-state model can be observationally equivalent to no-signalling QM. It cannot be singled out by operational A/C probability data without additional constraints."
    }

def common_cause_model(copy_probability):
    """U->A early and U->C late; observational and do(C) differ."""
    if not isinstance(copy_probability,Fraction) or not .5<=copy_probability<=1:
        raise ValueError("INVALID_CONFOUND_STRENGTH")
    d=2*copy_probability-1
    return {
       "early_U_uniform":True,
       "early_A_equals_U":True,
       "late_C_equals_U_probability":float(copy_probability),
       "observational_P_A1_given_C0":float(1-copy_probability),
       "observational_P_A1_given_C1":float(copy_probability),
       "observational_apparent_future_past_delta":float(d),
       "interventional_do_C_effect_on_early_A":0.,
       "explanation":"U is an earlier common cause; no future event changes the past. Independence of the physical late choice from early hidden variables is indispensable."
    }

def power_calculation():
    normal=NormalDist()
    za=normal.inv_cdf(1-ALPHA/2)
    zp=normal.inv_cdf(TARGET_POWER)
    def n_required(delta):
        return math.ceil((za+zp)**2/delta**2)
    def approximate_power(delta,n):
        mu=delta*math.sqrt(n)
        return normal.cdf(-za-mu)+(1-normal.cdf(za-mu))
    return {
       "null":"A unconditional P(+1|do(C=0)) equals P(+1|do(C=1))",
       "model":"Two equal-size independent binomial arms, baseline near p=.5, balanced C, Gaussian 2-sided test, fixed alpha, no optional stopping",
       "statistical_alpha_two_sided":ALPHA,
       "target_power":TARGET_POWER,
       "N_previously_sealed_010":PHYSICAL010_N,
       "nominal_alpha_critical_z":za,
       "nominal_90_percent_power_z":zp,
       "approximate_formula_total_N":"ceil((z_(1-alpha/2)+z_power)^2 / delta^2) for p approximately 1/2, balanced C",
       "N_required_by_hypothetical_probability_difference":[
          {"absolute_effect_probability_points":100*d,
           "absolute_delta":d,
           "total_N_for_90_percent_power_approx":n_required(d),
           "power_with_N_16384_approx":approximate_power(d,PHYSICAL010_N)} for d in PLANNING_DELTAS],
       "delta_probability_difference_for_90_percent_power_given_N_16384_approx":
           (za+zp)/math.sqrt(PHYSICAL010_N),
       "fully_independent_physically_late_intervention_required":True,
       "postselected_trials_not_admissible":True,
       "limitations":"Normal approximation assumes independent balanced trials and no drift, leakage, trial exclusions or hidden looks. Actual lab sample size needs effect uncertainty, multiplicity, device survival and full exact-test simulation."
    }

def candidate_map(q,post,latent,common,power):
    # These are logically derived engineering distinctions, NOT Bayesian
    # probabilities of physical retrocausality or evidence ratings.
    return [
      {
        "candidate":"Ordinary delayed-basis Bell / quantum eraser",
        "mathematical_location":"Bob outcome-conditioned subensembles",
        "unconditional_operational_delta":q["unconditional_later_C_effect"],
        "observed_or_model_implied_distinguishing_signature":"Large conditional contrast but exactly zero unconditional Alice effect",
        "usable_future_to_past_communication":False,
        "next_test":"Compare all raw early A records by late C vs B-conditioned records; never mix them"
      },
      {
        "candidate":"Nonlinear/postselected CTC-like filter (TOY ONLY)",
        "mathematical_location":"S=success selection after later boundary condition",
        "unconditional_operational_delta":0.,
        "selected_conditional_delta_at_r_0_05":post[1]["apparent_selected_signal_delta"],
        "usable_future_to_past_communication":False,
        "next_test":"Ask whether success is itself an early independently readable record; if no, conditional counts cannot carry a backwards message"
      },
      {
        "candidate":"Ontological retrocausal hidden-state toy",
        "mathematical_location":"Future C influences hidden lambda, but A is masked by a fair bit",
        "hidden_information_bits":latent["latent_lambda_future_C_mutual_information_bits"],
        "accessible_information_bits":0.,
        "usable_future_to_past_communication":False,
        "next_test":"Requires independent empirically testable model restrictions; unobservable lambda coupling alone is not falsifiable by A/C"
      },
      {
        "candidate":"Classical common-cause/QRNG leakage false signal",
        "mathematical_location":"Early U influences both A and later C",
        "observational_delta":common["observational_apparent_future_past_delta"],
        "interventional_delta":0.,
        "usable_future_to_past_communication":False,
        "next_test":"Separate externally shielded late QRNG from all earlier variables; physically verify independence and absence of feedforward"
      },
      {
        "candidate":"Genuinely operational future-to-early observable effect (HYPOTHETICAL)",
        "mathematical_location":"Unconditional P(A|do(C)) with C physically created after A was committed",
        "hypothetical_delta":float(HYPOTHETICAL_SIGNAL_DELTA),
        "theoretical_mechanism_identified":False,
        "currently_physically_observed":False,
        "sample_size_90_percent_approx":math.ceil(
            (NormalDist().inv_cdf(1-ALPHA/2)+NormalDist().inv_cdf(TARGET_POWER))**2 /
            float(HYPOTHETICAL_SIGNAL_DELTA)**2),
        "next_test":"Only promising operational target: physical early immutable A, newly generated independent late C, independently certified common clock, all trials; then repeated external blind replication"
      }
    ]

def evaluate():
    quantum=quantum_bell()
    post=[postselect(r) for r in CTC_POST_RATES]
    latent=latent_retro_model(HIDDEN_MISMATCH)
    common=common_cause_model(CONFOUND_COPY_PROB)
    power=power_calculation()
    if quantum["unconditional_later_C_effect"]!=0.:raise AssertionError("QM_FALSE_SIGNAL")
    if post[1]["unconditional_signal_delta"]!=0.:raise AssertionError("POSTSELECTION_RELABELED_AS_SIGNAL")
    if common["interventional_do_C_effect_on_early_A"]!=0.:raise AssertionError("COMMON_CAUSE_RELABELED_CAUSAL")
    return {
      "schema":SCHEMA,
      "status":"COMPLETE_MATHEMATICAL_TOY_COMPARISONS_NOT_PHYSICAL_RETROCAUSAL_EVIDENCE",
      "all_inputs_are_math_or_frozen_design_values":True,
      "empirical_new_physical_trials":0,
      "retrocausality_proven":False,
      "quantum_bell_exact_two_qubit":quantum,
      "postselection_filter_exact":[*post],
      "retrocausal_latent_coupling_toy":latent,
      "classical_common_cause_false_positive":common,
      "hypothetical_physical_intervention_power":power,
      "falsifiable_candidate_map":candidate_map(quantum,post,latent,common,power),
      "references":[
         "https://plato.stanford.edu/archives/win2025/entries/qm-retrocausality/",
         "https://pubmed.ncbi.nlm.nih.gov/38281717/",
         "https://repository.tudelft.nl/record/uuid:cf475a74-24fe-4f30-b133-c8bec3155acb",
         "https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.106.040403",
         "https://www.nature.com/articles/s42254-024-00739-8"
      ],
      "source_warning":"None of these mathematics establishes that a real freely chosen future setting can alter an already witnessed earlier local outcome.",
      "unchanged_original_JANUS_physical_010":True
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    result=evaluate()
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
        f.write("\n")
    power=result["hypothetical_physical_intervention_power"]
    print("JANUS_011A_RESULT "+json.dumps({
        "quantum_unconditional_delta":result["quantum_bell_exact_two_qubit"]["unconditional_later_C_effect"],
        "PCTC_selected_delta_at_r_0_05":result["postselection_filter_exact"][1]["apparent_selected_signal_delta"],
        "PCTC_unconditional_delta":result["postselection_filter_exact"][1]["unconditional_signal_delta"],
        "hidden_retro_bits_not_observed":result["retrocausal_latent_coupling_toy"]["latent_lambda_future_C_mutual_information_bits"],
        "false_common_cause_obs_delta":result["classical_common_cause_false_positive"]["observational_apparent_future_past_delta"],
        "false_common_cause_do_delta":result["classical_common_cause_false_positive"]["interventional_do_C_effect_on_early_A"],
        "N_for_delta_0_01":next(q["total_N_for_90_percent_power_approx"] for q in power["N_required_by_hypothetical_probability_difference"] if q["absolute_delta"]==.01),
        "N_for_delta_0_04":next(q["total_N_for_90_percent_power_approx"] for q in power["N_required_by_hypothetical_probability_difference"] if q["absolute_delta"]==.04),
        "delta_detectable_N_16384":power["delta_probability_difference_for_90_percent_power_given_N_16384_approx"],
        "retrocausality_proven":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
