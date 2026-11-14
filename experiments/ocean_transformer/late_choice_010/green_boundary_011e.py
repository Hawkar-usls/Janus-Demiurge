#!/usr/bin/env python3
"""JANUS-011E: retarded vs advanced classical wave Green functions, no CTC claim.

For Box=(1/c^2)d_tt - Laplacian in 3+1D, at r>0:
 G_ret=delta(t-r/c)/(4*pi*r), G_adv=delta(t+r/c)/(4*pi*r).
Both solve Box G=delta(t)delta_3(x) distributionally. A convex mixture
also solves the SAME wave PDE; boundary conditions, not the PDE, choose it.

The numerical envelope Y=4*pi*r*phi is evaluated by exact Fraction samples;
it is NOT a measured probability, electromagnetic energy, or an early
physical signal. The offline algorithm already has future model choice C.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

SCHEMA="janus.retro011e.wave_boundary_green_falsification.v1"
WAVE_LAW="(c^-2 d_t^2 - Laplacian) phi = source in flat 3+1 dimensions"
T_SOURCE=16
DISTANCE_OVER_C=5
EARLY_T=11
LATE_RET_T=21
LAST_T=30
FROZEN_FRACTIONS={"retarded":F(0),"symmetric":F(1,2),"advanced":F(1)}
RAW_PULSE={0:F(1),1:F(1,2),2:F(1,4)}
TIMESTAMP_SHIFT_FALSE_PRECURSOR=-10
BOX_IDENTITY="Box G_ret = Box G_adv = delta(t)delta_3(x)"
BIBLIO={
    "Wheeler_Feynman_1945":"10.1103/RevModPhys.17.157",
    "Wheeler_Feynman_1949":"10.1103/RevModPhys.21.425",
    "Leifer_Pusey_2017":"10.1098/rspa.2016.0607",
}

def fstr(x:F)->str:
    return str(x.numerator) if x.denominator==1 else f"{x.numerator}/{x.denominator}"

def cbit(c:int):
    if type(c) is not int or c not in (0,1):
        raise ValueError("SOURCE_CHOICE_MUST_BE_0_OR_1")
    return c

def src_at(t:int,c:int)->F:
    cbit(c)
    if type(t) is not int:raise ValueError("TIME_MUST_BE_INTEGER")
    return F(c)*RAW_PULSE.get(t-T_SOURCE,F(0))

def ret_at(t:int,c:int)->F:
    return src_at(t-DISTANCE_OVER_C,c)

def adv_at(t:int,c:int)->F:
    return src_at(t+DISTANCE_OVER_C,c)

def field_at(t:int,c:int,lam:F)->F:
    if not isinstance(lam,F) or not F(0)<=lam<=F(1):
        raise ValueError("BOUNDARY_FRACTION_NOT_0_TO_1")
    return (1-lam)*ret_at(t,c)+lam*adv_at(t,c)

def avg_at(t:int,c:int,centered:bool)->F:
    # Five time samples. Centered output at t is computed with samples
    # t+1,t+2 -- FUTURE DATA. Trailing filter is online causal.
    offsets=range(-2,3) if centered else range(-4,1)
    return sum((src_at(t+k,c) for k in offsets),F(0))/5

def causal_initial_record():
    # An example legitimate early distribution generated from a variable
    # U independent of C. Never falsely claim actual WORM custody.
    return {
        "early_witness_is_real_hardware":False,
        "source_clock_and_later_QRNG_physically_observed":False,
        "precommitted_A_distribution_by_do_C":{
            "0":{"P(A1)":"1/2","P(A0)":"1/2"},
            "1":{"P(A1)":"1/2","P(A0)":"1/2"}},
        "ordinary_forward_interventional_delta":0,
        "requires_future_source_bit_to_compute_advanced_early_trace":True,
        "offline_source_bit_read_after_t_source_is_not_early_witness":True
    }

def all_model_results():
    models=[]
    for name,lam in FROZEN_FRACTIONS.items():
        by_c=[]
        for c in (0,1):
            trace=[field_at(t,c,lam) for t in range(LAST_T+1)]
            source=[src_at(t,c) for t in range(LAST_T+1)]
            by_c.append({
                "do_C":c,
                "source_nonzero_steps":[t for t,v in enumerate(source) if v],
                "receiver_nonzero_steps":[t for t,v in enumerate(trace) if v],
                "receiver_trace_fraction_strings":[fstr(v) for v in trace],
                "receiver_at_early_t11":fstr(trace[EARLY_T]),
                "receiver_at_late_t21":fstr(trace[LATE_RET_T]),
                "sum_of_all_discrete_receiver_amplitudes_not_an_energy":fstr(sum(trace,F(0)))
            })
        delta=field_at(EARLY_T,1,lam)-field_at(EARLY_T,0,lam)
        models.append({
            "boundary":name,
            "advanced_weight_lambda":fstr(lam),
            "same_differential_wave_operator":True,
            "boundary_law_independently_deduced_from_wave_equation":False,
            "full_unselected_early_model_amplitude_delta":fstr(delta),
            "full_unselected_late_model_amplitude_delta":fstr(field_at(LATE_RET_T,1,lam)-field_at(LATE_RET_T,0,lam)),
            "traces":by_c,
            "physically_precommitted_receiver_observed":False
        })
    return models

def false_controls():
    c=1
    sym=FROZEN_FRACTIONS["symmetric"]
    # Adding exactly half(ret-adv) to symmetric gives retarded. This
    # counterterm is ASSUMED, not physically derived from absorber response.
    full=[field_at(t,c,sym) + F(1,2)*(ret_at(t,c)-adv_at(t,c))
          for t in range(LAST_T+1)]
    ret=[ret_at(t,c) for t in range(LAST_T+1)]
    assert full==ret
    centered=[avg_at(t,c,True) for t in range(LAST_T+1)]
    trailing=[avg_at(t,c,False) for t in range(LAST_T+1)]
    # If physical t_ret is recorded with a mistaken negative 10-step
    # common timestamp calibration shift, t_phys=21 is displayed as 11.
    displayed_t_ret=LATE_RET_T+TIMESTAMP_SHIFT_FALSE_PRECURSOR
    return {
       "absorber_compensator_ALGEBRA_ONLY":{
          "field":"(G_ret+G_adv)/2 + (G_ret-G_adv)/2 = G_ret",
          "advanced_past_precursor_after_compensator":fstr(full[EARLY_T]),
          "equals_retarded_trace_all_steps":True,
          "absorber_material_response_or_boundary_derived_from_theory":False,
          "physical_absorber_response_measured":False
       },
       "noncausal_digital_filter_artifact":{
          "window_samples":5,
          "centered_lookahead_samples":2,
          "centered_nonzero_before_source":[t for t,v in enumerate(centered) if v and t<T_SOURCE],
          "trailing_nonzero_before_source":[t for t,v in enumerate(trailing) if v and t<T_SOURCE],
          "centered_source_pre_event_t14_amplitude":fstr(centered[14]),
          "trailing_source_pre_event_t14_amplitude":fstr(trailing[14]),
          "reading_future_raw_samples_required_for_centered_filter":True,
          "real_physical_backwards_propagation_demonstrated":False
       },
       "instrument_timestamp_miscalibration_artifact":{
          "true_retarded_arrival_t":LATE_RET_T,
          "erroneous_recorded_timestamp_shift":TIMESTAMP_SHIFT_FALSE_PRECURSOR,
          "apparent_displayed_arrival_t":displayed_t_ret,
          "predates_source_on_wrong_clock":displayed_t_ret<T_SOURCE,
          "ordinary_retarded_physical_timeline_unchanged":True,
          "independent_NIST_style_clock_custody_needed":True
       }
    }

def theoretical_source_equivalence():
    return {
      "wave_operator":WAVE_LAW,
      "fundamental_solutions":[
        {"label":"G_ret","symbolic":"delta(t-r/c)/(4*pi*r)","characteristic":"source signal received at source_time+r/c"},
        {"label":"G_adv","symbolic":"delta(t+r/c)/(4*pi*r)","characteristic":"model precursor at source_time-r/c"}
      ],
      "distributional_proof_from_standard_field_theory":BOX_IDENTITY,
      "homogeneous_difference":"Box(G_adv-G_ret)=0 distributionally, since both have identical delta sources",
      "affine_family":"G_lambda=(1-lambda)*G_ret+lambda*G_adv satisfies SAME Box G=delta source for EVERY lambda",
      "wave_law_selects_advanced_weight_without_boundary":False,
      "actual_boundary_physics_has_been_derived":False,
      "solves_full_Wheeler_Feynman_absorber_interaction":False,
      "theoretical_citation_required":"doi:10.1103/RevModPhys.17.157 ; doi:10.1103/RevModPhys.21.425",
      "verification_scope":"This program evaluates the exact known Green-convolution waveforms, but DOES NOT numerically prove the distributional field-equation identity.",
      "source_classical_massless_wave_not_quantum_CTC":True
    }

def evaluate():
    data={
      "schema":SCHEMA,
      "status":"WAVE_EQUATION_ADVANCED_RETARDED_BOUNDARY_UNDERDETERMINATION__NO_PHYSICAL_RETROCHANNEL",
      "protocol_frozen_before_computation":True,
      "original_protocol_path":"experiments/ocean_transformer/late_choice_010/PROTOCOL_011E_WAVE_BOUNDARY_FROZEN.md",
      "quantitative_model_units":"NORMALIZED_SCALAR_FIELD_AMPLITUDE, not probability or physical energy",
      "frozen_variables":{
        "source_choice_time":T_SOURCE,
        "receiver_distance_over_c":DISTANCE_OVER_C,
        "early_readout_t":EARLY_T,
        "late_retarded_t":LATE_RET_T,
        "timeline_range":[0,LAST_T],
        "late_source_pulse_by_delay":{str(k):fstr(v) for k,v in RAW_PULSE.items()},
        "boundary_fractions":{k:fstr(v) for k,v in FROZEN_FRACTIONS.items()}
      },
      "physical_wave_equation_and_boundary":theoretical_source_equivalence(),
      "independent_complete_two_choice_model_traces":all_model_results(),
      "false_positive_controls":false_controls(),
      "causal_early_witness_control":causal_initial_record(),
      "scientific_admission":{
        "independent_source_physics_selected_lambda":False,
        "advanced_future_boundary_assumed_for_lambda_positive":True,
        "pre_event_modeled_response_without_future_access":False,
        "actual_late_physically_randomized_QRNG_choices":0,
        "actual_independently_authenticated_early_field_records":0,
        "physical_trials_completed":0,
        "physical_retrocausal_signal_measured":False,
        "quantum_entanglement_or_Deutsch_CTC_modeled":False,
        "no_postselection_and_all_time_samples_included":True,
        "new_unconditional_physical_law_prediction_derived_without_boundary":False,
        "final_conclusion":"Wave PDE permits both solutions, but cannot select a physically measurable advanced response without extra future/radiation/absorber boundary. Thus independent-law JANUS-011E physical derivation gate FAILS, while mathematical consistency PASS."
      },
      "references":BIBLIO,
      "sealed_JANUS_010_and_all_previous_records_unmodified":True,
      "NAS_QPU_external_laboratory_untouched":True
    }
    return data

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    record=evaluate()
    with dst.open("x",encoding="utf-8") as f:
        json.dump(record,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n")
    print("JANUS_011E_RESULT "+json.dumps({
        "retarded_pre_event_field_delta":record["independent_complete_two_choice_model_traces"][0]["full_unselected_early_model_amplitude_delta"],
        "symmetric_pre_event_field_delta":record["independent_complete_two_choice_model_traces"][1]["full_unselected_early_model_amplitude_delta"],
        "advanced_pre_event_field_delta":record["independent_complete_two_choice_model_traces"][2]["full_unselected_early_model_amplitude_delta"],
        "centered_filter_false_precursor_at_t14":record["false_positive_controls"]["noncausal_digital_filter_artifact"]["centered_source_pre_event_t14_amplitude"],
        "absorb_cancellation_pre_event_delta":record["false_positive_controls"]["absorber_compensator_ALGEBRA_ONLY"]["advanced_past_precursor_after_compensator"],
        "physical_boundary_derived":False,"real_physical_trials":0,"retrocausality_proven":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    main()
