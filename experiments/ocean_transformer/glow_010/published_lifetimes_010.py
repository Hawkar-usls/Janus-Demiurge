#!/usr/bin/env python3
"""GLOW-010: calculate constraints from REAL PUBLISHED EXPERIMENTAL FITS.

Lifetimes and goodness-of-fit below are TRANSCRIBED PUBLISHED VALUES from
Edinburgh Instruments AN_P28 (2017), not raw measurement series and not an
independent refit by JANUS. Original laboratory fitted 4 exponentials.
DO NOT compare fit errors of mono/bi/power-law without genuine time/intensity
rows and experiment-specific fitting amplitudes/background.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import statistics

URL="https://edin.b-cdn.net/wp-content/uploads/2023/03/Luminescence-Phosphors_App28.pdf"
PROVENANCE="Edinburgh Instruments, G. Arnaoutakis, AN_P28 (12 June 2017), Table 1, Figure 2"
SOURCE_LICENSE_NOTE="Copyright Edinburgh Instruments; numeric experimental fit summary attributed, no raw plot reproduction"
# λ_ex [nm], τ1..4 [s], χ² as published, <τ> [s]
ROWS=[
 [300,1.29,29.27,221.10,1955.00,1.16,1776.99],
 [310,0.94,26.66,172.60,1089.00,1.53,849.53],
 [320,5.32,48.04,221.00,1137.00,1.66,803.19],
 [330,10.47,57.52,240.90,1170.00,1.53,773.17],
 [340,9.75,54.38,229.30,1115.00,1.88,719.85],
 [350,11.58,59.84,243.60,1167.00,1.66,757.25],
]
DEFAULT_TAU_S=900.0

def compute():
    rows=[{
        "excitation_nm":r[0],"tau_fast_1_s":r[1],"tau_fast_2_s":r[2],
        "tau_mid_3_s":r[3],"tau_slow_4_s":r[4],
        "reported_chi_squared_4exp":r[5],"reported_average_lifetime_s":r[6],
        "slow_component_exponential_survival_at_600s":round(math.exp(-600/r[4]),8),
        "slow_component_exponential_survival_at_1800s":round(math.exp(-1800/r[4]),8),
        "abs_difference_in_reported_average_vs_prior_900s":round(abs(r[6]-DEFAULT_TAU_S),8),
    } for r in ROWS]
    ave=[r[6] for r in ROWS]
    tau4=[r[4] for r in ROWS]
    return {
        "schema":"janus.ocean.glow010.real_published_fit_constraint.v1",
        "experiment":"JANUS-OCEAN-GLOW-010",
        "status":"REAL_PUBLISHED_FOUR_EXPONENTIAL_FIT_PARAMETERS_CALCULATED__NO_RAW_CURVE_REFIT",
        "published_reference":PROVENANCE,
        "source_url":URL,
        "source_license_note":SOURCE_LICENSE_NOTE,
        "sample":"Micro-crystalline SrAl2O4:Eu2+,Dy3+ powder, Glotech International; NOT a SUNLU PLA Glow filament sample",
        "conditions":{
            "pump_duration_s":300,"pump_wavelengths_nm":[300,310,320,330,340,350],
            "measurement_emission_nm":520,"measurement_duration_s":3600,"instrument":"FLS1000 PMT-900",
            "published_time_resolution_seconds":1,
        },
        "published_rows":rows,
        "n_published_excitation_conditions":len(rows),
        "slow_component_tau_range_s":[min(tau4),max(tau4)],
        "reported_mean_lifetime_range_s":[min(ave),max(ave)],
        "median_reported_mean_lifetime_s":round(statistics.median(ave),6),
        "mean_reported_mean_lifetime_s":round(statistics.mean(ave),6),
        "hypothesized_prior_single_tau_s":DEFAULT_TAU_S,
        "prior_900s_mae_vs_published_condition_means_s":round(statistics.mean(abs(x-DEFAULT_TAU_S) for x in ave),6),
        "prior_900s_mape_vs_published_condition_means_percent":round(
           100*statistics.mean(abs(x-DEFAULT_TAU_S)/x for x in ave),6),
        "prior_900s_single_component_survival_at_600s":round(math.exp(-600/DEFAULT_TAU_S),8),
        "literature_four_exponential_fit_chi_squared_range":[min(r[5] for r in ROWS),max(r[5] for r in ROWS)],
        "reported_three_exponential_fit_chi_squared_greater_than":3,
        "published_4exp_had_better_fit_than_3exp_by_reported_chi_squared":True,
        "monoexp_vs_biexp_vs_powerlaw_out_of_sample_MAE":None,
        "monoexp_vs_biexp_vs_powerlaw_model_winner":None,
        "reason_model_comparison_pending":"Fitted lifetimes alone do not contain true per-second time/intensity observations, optical background, or model amplitudes. Cannot independently fit or compare three time-domain curve models yet.",
        "raw_measurement_pairs_available_here":False,
        "sunlu_composite_emission_measured":False,
        "no_retrocausal_conclusion":True,
        "notes":[
          "Source authors published 4-exponential lifetimes for six 300-350nm excitation conditions.",
          "The quoted 900s from GLOW-009C was an illustrative single tau, never independently measured.",
          "Calculated single-channel decay factors are ONLY for the slowest exponential component, not total emission without unknown component amplitudes.",
          "Time constants from microcrystalline powder must not be transposed to PLA composite without material-specific calibration.",
          "Published fitted mean lifetime is NOT a raw afterglow intensity time-series and cannot supply an actual chronological train/test prediction score.",
        ]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    a=p.parse_args()
    result=compute()
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:f.write(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in ("status","n_published_excitation_conditions",
         "slow_component_tau_range_s","prior_900s_mae_vs_published_condition_means_s",
         "monoexp_vs_biexp_vs_powerlaw_model_winner")},sort_keys=True))

if __name__=="__main__":
    main()
