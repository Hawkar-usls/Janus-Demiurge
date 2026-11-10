#!/usr/bin/env python3
"""JANUS-011D: compare ABL two-boundary probabilities and Deutsch-CTC SWAP.

All calculations deterministic and no original quantum lab data are used.
ABL: ordinary sequential preselection (|+>), early Z measurement A,
     later choice C=(Z/X), with *all* late outcomes versus postselect B=0.
D-CTC: genuine quantum 2-qubit SWAP unitary, fixed-point constraint
     sigma_C = Tr_CR[SWAP (rho_C tensor sigma_C) SWAP], so sigma_C=rho_C.
     Optional depolarization on RETURNING CTC state, NOT on early records.
     This is a Deutsch-model mathematical assumption, not physical evidence.
Forward open-loop: initial sigma=I/2 independent C, same early record.
Do not label the model-internal CTC information as measured retrocapacity.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path

SCHEMA="janus.retro011d.abl_vs_deutsch_ctc_quantum_swap.v1"
NOISE=(F(0),F(1,10),F(1,4),F(1,2),F(1))
HYPOTHETICAL_C_PRIOR=F(1,2)
DOI_ABL="10.1103/PhysRev.134.B1410"
DOI_DEUTSCH="10.1103/PhysRevD.44.3197"
DOI_JLW="10.1103/znyd-npk5"

def frac(x):
    return str(x.numerator) if x.denominator==1 else f"{x.numerator}/{x.denominator}"

def rho_z(c):
    if type(c) is not int or c not in (0,1):
        raise ValueError("C_NOT_BINARY")
    return [[complex(int(i==j==c)) for j in (0,1)] for i in (0,1)]

def rho_plus():
    return [[.5+0j,.5+0j],[.5+0j,.5+0j]]

def rho_mix():
    return [[.5+0j,0j],[0j,.5+0j]]

def validate_density(mat):
    if not isinstance(mat,list) or len(mat)!=2 or any(not isinstance(row,list) or len(row)!=2 for row in mat):
        raise ValueError("RHO_MUST_BE_QUBIT_2X2")
    if any(not math.isfinite(complex(x).real) or not math.isfinite(complex(x).imag)
           for row in mat for x in row):
        raise ValueError("NONFINITE_DENSITY")
    if abs(complex(mat[0][1])-complex(mat[1][0]).conjugate())>1e-12:
        raise ValueError("NON_HERMITIAN_DENSITY")
    a=float(complex(mat[0][0]).real)
    b=float(complex(mat[1][1]).real)
    if abs(complex(mat[0][0]).imag)>1e-12 or abs(complex(mat[1][1]).imag)>1e-12:
        raise ValueError("DIAGONAL_NOT_REAL")
    det=a*b-abs(complex(mat[0][1]))**2
    if a<0 or b<0 or abs(a+b-1)>1e-12 or det < -1e-12:
        raise ValueError("INVALID_DENSITY_POSITIVITY_OR_TRACE")
    return mat

def tensor(rho,sigma):
    validate_density(rho);validate_density(sigma)
    return [[complex(rho[i//2][j//2])*complex(sigma[i%2][j%2])
             for j in range(4)] for i in range(4)]

def swap(rho,sigma):
    """U=SWAP on CR (first) and CTC (second) qubits: U^2=I."""
    M=tensor(rho,sigma)
    p=(0,2,1,3)
    return [[M[p[i]][p[j]] for j in range(4)] for i in range(4)]

def partial_trace_CR(joint):
    """Trace out first qubit: resulting CTC 2x2."""
    return [[sum(joint[2*i+j][2*i+k] for i in (0,1))
             for k in (0,1)] for j in (0,1)]

def partial_trace_CTC(joint):
    """Trace out second qubit: resulting CR 2x2."""
    return [[sum(joint[2*i+j][2*k+j] for j in (0,1))
             for k in (0,1)] for i in (0,1)]

def same_matrix(a,b,tol=1e-12):
    return all(abs(a[i][j]-b[i][j])<tol for i in (0,1) for j in (0,1))

def noisy_return(rho,eta:F):
    if type(eta) is not F or not F(0)<=eta<=F(1):
        raise ValueError("DEPOLARIZING_RATE_NOT_0_TO_1")
    validate_density(rho)
    return [[(1-float(eta))*rho[i][j]+float(eta)*rho_mix()[i][j]
             for j in (0,1)] for i in (0,1)]

def h2(p):
    if not 0<=p<=1:raise ValueError("INVALID_BIT_PROBABILITY")
    return 0. if p in (0.,1.) else -p*math.log2(p)-(1-p)*math.log2(1-p)

def abl_two_boundary():
    """Pre |+>, early projective Z measurement, late selectable Z/X basis."""
    out=[]
    for c in (0,1):
        # c=0 Z basis postselection on |0>; c=1 X basis on |+>.
        # Born rule after early Z collapse: P(A=a)=1/2,
        # P(B=0|A=a,C=Z)=1[a=0], P(B=0|A=a,C=X)=1/2.
        joint={}
        for a in (0,1):
            pb0 = float(a==0) if c==0 else .5
            joint[f"A{a}B0"] = .5*pb0
            joint[f"A{a}B1"] = .5*(1-pb0)
        success=joint["A0B0"]+joint["A1B0"]
        if success<=0:raise AssertionError("NO_SUCCESS")
        early_p0=joint["A0B0"]+joint["A0B1"]
        out.append({
            "late_basis":"Z" if c==0 else "X",
            "late_C":c,
            "complete_joint_P_A_and_B":joint,
            "sum_all_outcomes":sum(joint.values()),
            "unconditional_early_P_A0":early_p0,
            "postselect_B0_success_rate":success,
            "ABL_P_early_A0_given_late_B0":joint["A0B0"]/success,
            "postselection_NOT_early_readable":True
        })
    return {
        "source":"ABL 1964, initial |+>, early Z, late postmeasurement basis Z or X",
        "per_choice_all_outcome":out,
        "unconditional_early_delta_A0":out[1]["unconditional_early_P_A0"]-out[0]["unconditional_early_P_A0"],
        "conditional_postselection_delta_A0":out[1]["ABL_P_early_A0_given_late_B0"]-out[0]["ABL_P_early_A0_given_late_B0"],
        "ABL_formula":"P(A=a|pre i,post f)=|<f|P_a|i>|^2 / sum_k |<f|P_k|i>|^2",
        "retrodictive_smoothing_is_not_operational_backward_transmission":True,
        "physically_late_C_changes_precommitted_A":False
    }

def deutsch_swap(eta:F):
    """Full quantum SWAP self-consistency, optionally noisy CTC return."""
    if type(eta) is not F or not F(0)<=eta<=F(1):
        raise ValueError("DEPOLARIZING_RATE_NOT_0_TO_1")
    by_choice=[]
    for c in (0,1):
        rho=rho_z(c)
        # SWAP=>CTC output=rho, independent of incoming sigma.
        # Unique noisy fixed point: sigma=(1-eta)*rho+eta*I/2.
        sigma=noisy_return(rho,eta)
        joint=swap(rho,sigma)
        actual_return=noisy_return(partial_trace_CR(joint),eta)
        if not same_matrix(actual_return,sigma):
            raise AssertionError("DEUTSCH_FIXED_POINT_NOT_SATISFIED")
        CR_out=partial_trace_CTC(joint)
        if not same_matrix(CR_out,sigma):
            raise AssertionError("SWAP_OUTPUT_NOT_INCOMING_CTC")
        open_sigma=rho_mix() # Fixed prior for ordinary forward open-loop SWAP.
        open_joint=swap(rho,open_sigma)
        if not same_matrix(partial_trace_CTC(open_joint),open_sigma):
            raise AssertionError("OPEN_FORWARD_CR_OUTPUT_CHANGED")
        by_choice.append({
            "C":c,
            "late_CR_input_state":"|0><0|" if c==0 else "|1><1|",
            "fixed_point_CTC_input_P_L1":float(sigma[1][1].real),
            "CTC_input_state_matches_noisy_return_map":True,
            "late_CR_output_P_1":float(CR_out[1][1].real),
            "open_forward_no_CTC_early_P_L1":float(open_sigma[1][1].real),
            "open_forward_CR_output_P_1":float(partial_trace_CTC(open_joint)[1][1].real),
            "experimentally_early_loop_L_record_present":False
        })
    p0=by_choice[0]["fixed_point_CTC_input_P_L1"]
    p1=by_choice[1]["fixed_point_CTC_input_P_L1"]
    assert abs(p0-float(eta)/2)<1e-12
    assert abs(p1-(1-float(eta)/2))<1e-12
    return {
        "return_depolarizing_fraction":float(eta),
        "return_depolarizing_fraction_exact":frac(eta),
        "quantum_interaction":"genuine two-qubit unitary SWAP, plus optional trace-preserving depolarizing return channel",
        "Deutsch_assumption":"CTC input sigma must equal its output after SWAP interaction and returning noise",
        "unique_self_consistent_sigma":"sigma_C=(1-eta)|C><C|+eta*I/2 (constant fixed-point map)",
        "all_outcomes_kept":True,
        "late_choice_probabilities":by_choice,
        "theory_internal_early_loop_P_L1_delta":p1-p0,
        "model_internal_binary_Shannon_capacity_bits_per_use":1-h2(float(eta)/2),
        "ordinary_open_loop_early_P_L1_delta":0.,
        "physically_accessible_early_precommitted_record_authenticated":False,
        "timeline_consistency_imposed_as_postulate_not_observed":True,
        "actual_independent_lab_timeline_test_performed":False
    }

def hypotheses():
    return {
        "Janus_Principle_mapping":{
           "two_boundary_forward_filter":"Prior state and later postselected outcome used for retrospective ABL smoothing; no early available future data",
           "Deutsch_fixed_point":"Entire CTC loop state fixed using hypothesized later input; this is an added global boundary/self-consistency law, not inferred from ordinary quantum dynamics",
           "Janus_principle_derivation_from_physical_law":False,
           "operational_retrocausal_prediction_observed":False
        },
        "comparison":{
           "ABL_conditional_information":"Later outcome selection correlates with early A, but complete early sample is independent of late basis.",
           "DCTC_internal_information":"SWAP+Deutsch fixed point yields a future-dependent loop input by assumption, without postselection; model-internal bit capacity can reach 1.",
           "forward_open_loop_control":"Same ordinary SWAP unitary with independent preexisting I/2 loop input leaves early data fixed; later C affects later CTC output only.",
           "which_new_physical_hypothesis_is_required":"Existence of real closed timelike curves and access to an independently witnessed early CTC state without destroying loop consistency.",
           "outcome_of_mathematical_comparison":"NO_PHYSICAL_RETROCHANNEL_IDENTIFIED"
        },
        "admission":{
           "non_postselected_normalized_probabilities":True,
           "genuinely_after_A_physical_C_generation_evidenced":False,
           "externally_timestamped_early_L_witness_evidenced":False,
           "independent_QRNG_isolated_from_earlier_variables":False,
           "device_return_path_backwards_time_observed":False,
           "alternate_mechanism_independent_of_assumed_CTC":False,
           "measured_future_to_past_information_capacity":False,
           "scientific_status":"THEORETICAL_ABL_VS_DEUTSCH_SWAP_CONTROL_ONLY"
        }
    }

def result():
    abl=abl_two_boundary()
    ctc=[deutsch_swap(eta) for eta in NOISE]
    return {
        "schema":SCHEMA,
        "model_kind":"ANALYTICAL_TOY_COMPARE__NOT_A_PHYSICAL_EXPERIMENT",
        "source_DOIs":{"ABL_1964":DOI_ABL,"Deutsch_1991":DOI_DEUTSCH,"Ji_Lloyd_Wilde_2026":DOI_JLW},
        "Ji_Lloyd_Wilde_scope":"Hypothesized noisy POSTSELECTED CTC channel capacities; not computed or inferred from this Deutsch SWAP case",
        "two_boundary_ABL":abl,
        "genuine_unitary_Deutsch_SWAP_fixed_point":ctc,
        **hypotheses(),
        "physical_experiments_performed":0,
        "retrocausality_physically_proven":False,
        "earlier_closed_010_and_011C_unchanged":True
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    record=result()
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf-8") as f:
        json.dump(record,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n")
    print("JANUS_011D_RESULT "+json.dumps({
        "ABL_complete_unconditional_delta":record["two_boundary_ABL"]["unconditional_early_delta_A0"],
        "ABL_postselected_delta":record["two_boundary_ABL"]["conditional_postselection_delta_A0"],
        "DCTC_noiseless_internal_capacity_bits":record["genuine_unitary_Deutsch_SWAP_fixed_point"][0]["model_internal_binary_Shannon_capacity_bits_per_use"],
        "DCTC_noise_10pct_internal_capacity_bits":record["genuine_unitary_Deutsch_SWAP_fixed_point"][1]["model_internal_binary_Shannon_capacity_bits_per_use"],
        "DCTC_full_noise_internal_capacity_bits":record["genuine_unitary_Deutsch_SWAP_fixed_point"][-1]["model_internal_binary_Shannon_capacity_bits_per_use"],
        "ordinary_forward_early_delta":record["genuine_unitary_Deutsch_SWAP_fixed_point"][0]["ordinary_open_loop_early_P_L1_delta"],
        "physical_trials":0,"proven_retrocausality":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
