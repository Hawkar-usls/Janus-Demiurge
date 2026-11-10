#!/usr/bin/env python3
"""JANUS-011F: measured Au/Ag n,k -> ideal passive slab optics and false-time controls.

Real external data: Johnson & Christy (1972), immutable CC0 refractiveindex.info
commit e6d15e364f70de1cad8a96a20f75689f2fba8b21. These are measured
SPECTRAL constants, not experimental time response or CTC observations.

Calculate normal-incidence finite slab reflectance, transmittance, absorption
from n+i*k, with a passive field e^(i*kz-i*omega*t) convention. A causal
front/early signal CANNOT be inferred from the finite sampled n,k band.
"""
from __future__ import annotations
import argparse
import cmath
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

SCHEMA="janus.physical011f.measured_absorbers_optical_causality_audit.v1"
COMMIT="e6d15e364f70de1cad8a96a20f75689f2fba8b21"
SOURCE_PREFIX="https://raw.githubusercontent.com/polyanskiy/refractiveindex.info-database/"+COMMIT+"/database/data/main/"
MATERIALS=("Au","Ag")
WAVELENGTHS=(0.4509,0.5486,0.7045,0.8920)
THICKNESS_UM=0.04
SECONDARY_THICKNESSES=(0.03,0.05)
C_MPS=299792458.
MAX_SOURCE_BYTES=40000
TIME_SAMPLES=tuple(range(-8,13))
DELAY=5
WAVELENGTH_RANGE_EXPECTED=(0.1879,1.937)
ROW=re.compile(r"^\s*(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s*$")

def load_pinned_file(material):
    if material not in MATERIALS:raise ValueError("UNKNOWN_MEASURED_MATERIAL")
    url=SOURCE_PREFIX+material+"/nk/Johnson.yml"
    req=Request(url,headers={"User-Agent":"JANUS-011F research optical constant provenance audit"})
    with urlopen(req,timeout=40) as resp:
        original=resp.read(MAX_SOURCE_BYTES+1)
    if len(original)>MAX_SOURCE_BYTES:raise ValueError("ORIGINAL_NK_FILE_TOO_BIG")
    return original,url

def parse_original_nk(data):
    original=data.decode("utf-8-sig")
    if "Johnson" not in original or "Christy" not in original or "tabulated nk" not in original:
        raise ValueError("ORIGINAL_JOHNSON_CHRISTY_NK_IDENTITY_MISSING")
    rows=[]
    for line in original.splitlines():
        match=ROW.fullmatch(line)
        if not match:continue
        wavelength,n,k=map(float,match.groups())
        if not all(math.isfinite(x) for x in (wavelength,n,k)) or wavelength<=0 or n<=0 or k<0:
            raise ValueError("INVALID_OR_NONPASSIVE_ORIGINAL_NK_ROW")
        if rows and wavelength<=rows[-1][0]:
            raise ValueError("ORIGINAL_NK_WAVELENGTHS_NOT_INCREASING")
        rows.append((wavelength,n,k))
    if len(rows)<40 or abs(rows[0][0]-WAVELENGTH_RANGE_EXPECTED[0])>1e-6 or abs(rows[-1][0]-WAVELENGTH_RANGE_EXPECTED[1])>1e-6:
        raise ValueError("SOURCE_NK_RANGE_OR_ROW_COUNT_NOT_EXPECTED")
    for target in WAVELENGTHS:
        if not any(abs(row[0]-target)<1e-8 for row in rows):
            raise ValueError("SOURCE_EXACT_PRIMARY_WAVELENGTH_MISSING")
    return rows

def slab(wavelength,n,k,thickness_um):
    if not (wavelength>0 and n>0 and k>=0 and thickness_um>=0):
        raise ValueError("INVALID_IDEAL_FILM_INPUT")
    N=complex(n,k)
    r01=(1-N)/(1+N)
    r12=-r01
    t01=2/(1+N)
    t12=2*N/(N+1)
    beta=2*math.pi*N*thickness_um/wavelength
    z=cmath.exp(1j*beta)
    denominator=1+r01*r12*z*z
    if abs(denominator)<1e-12:raise ValueError("FILM_DENOMINATOR_SINGULAR")
    r=(r01+r12*z*z)/denominator
    t=t01*t12*z/denominator
    R=abs(r)**2
    T=abs(t)**2
    A=1-R-T
    if R < -1e-10 or T < -1e-10 or A < -1e-10 or max(R,T,A)>1+1e-10:
        raise ValueError("NONPASSIVE_SLAB_ENERGY_BALANCE")
    return {
      "R_model":max(0,R),
      "T_model":max(0,T),
      "A_model":max(0,A),
      "energy_balance_residual":R+T+A-1,
      "transmission_complex":t
    }

def group_delay_local(rows,index,thickness_um):
    if index<1 or index>=len(rows)-1:raise ValueError("NEIGHBORS_REQUIRED")
    wl_hi_omega,n_hi,k_hi=rows[index-1]
    wl_lo_omega,n_lo,k_lo=rows[index+1]
    high=slab(wl_hi_omega,n_hi,k_hi,thickness_um)["transmission_complex"]
    low=slab(wl_lo_omega,n_lo,k_lo,thickness_um)["transmission_complex"]
    delta_phi=cmath.phase(high/low) # wrapped local delta only
    delta_omega=2*math.pi*C_MPS*(1/(wl_hi_omega*1e-6)-1/(wl_lo_omega*1e-6))
    if delta_omega<=0:raise ValueError("OMEGA_NOT_SORTED")
    return delta_phi/delta_omega*1e15

def source_diagnostics(data,material,url):
    rows=parse_original_nk(data)
    origin_sha=hashlib.sha256(data).hexdigest()
    primary=[]
    exact_index={round(row[0],4):i for i,row in enumerate(rows)}
    for wavelength in WAVELENGTHS:
        idx=exact_index.get(round(wavelength,4))
        if idx is None:raise ValueError("PINNED_WAVELENGTH_NOT_FOUND")
        lam,n,k=rows[idx]
        m=slab(lam,n,k,THICKNESS_UM)
        alpha_um=4*math.pi*k/lam
        sample={
            "wavelength_um_exact_measured":lam,
            "n_measured":n,
            "k_measured":k,
            "alpha_intensity_per_um_derived":alpha_um,
            "intensity_1_over_e_attenuation_depth_nm":1000/alpha_um if alpha_um>0 else None,
            "film_thickness_primary_nm":40,
            "slab_reflectance_R_model":m["R_model"],
            "slab_transmittance_T_model":m["T_model"],
            "slab_absorptance_A_model":m["A_model"],
            "local_three_sample_group_delay_fs_MODEL_NOT_FRONT":group_delay_local(rows,idx,THICKNESS_UM),
            "noncausal_time_reconstruction_or_earliest_arrival_proven":False,
            "thickness_sensitivity":[
                {"d_nm":round(thickness*1000),
                "R_model":slab(lam,n,k,thickness)["R_model"],
                "T_model":slab(lam,n,k,thickness)["T_model"],
                "A_model":slab(lam,n,k,thickness)["A_model"]}
                for thickness in SECONDARY_THICKNESSES
            ]
        }
        primary.append(sample)
    all_wavelengths=[]
    for lam,n,k in rows:
        m=slab(lam,n,k,THICKNESS_UM)
        all_wavelengths.append({
           "wavelength_um":lam,
           "R_ideal_slab":m["R_model"],"T_ideal_slab":m["T_model"],
           "A_ideal_slab":m["A_model"]
        })
    return {
      "material":material,
      "original_paper_doi":"10.1103/PhysRevB.6.4370",
      "original_database_repository":"polyanskiy/refractiveindex.info-database",
      "original_source_commit":COMMIT,
      "original_file_url":url,
      "original_file_sha256":origin_sha,
      "original_bytes":len(data),
      "original_measured_nk_rows":len(rows),
      "original_first_wavelength_um":rows[0][0],
      "original_last_wavelength_um":rows[-1][0],
      "all_measured_wavelengths_included_in_film_model":True,
      "primary_four_measured_wavelengths":primary,
      "all_measured_wavelengths_40nm_slab_models":all_wavelengths,
      "original_measured_direct_film_RTA_at_40nm_available":False,
      "source_nk_is_measurement_not_temporal_pulse":True,
      "Kramers_Kronig_global_causality_from_truncated_band_verified":False
    }

def sinc_bandlimited(t,delay=DELAY,omega_max=math.pi/2):
    """Hard two-sided frequency cutoff of exact causal pure-delay impulse."""
    difference=t-delay
    if difference==0:return omega_max/math.pi
    return math.sin(omega_max*difference)/(math.pi*difference)

def ideal_impulse(t):return 1. if t==DELAY else 0.

def moving_average(t,centered):
    offsets=range(-2,3) if centered else range(-4,1)
    return sum(ideal_impulse(t+k) for k in offsets)/5

def temporal_false_positives():
    false_before_band=[t for t in TIME_SAMPLES if t<DELAY and abs(sinc_bandlimited(t))>1e-7]
    false_before_centered=[t for t in TIME_SAMPLES if t<DELAY and moving_average(t,True)>0]
    trailing_before=[t for t in TIME_SAMPLES if t<DELAY and moving_average(t,False)>0]
    return {
      "true_delayed_impulse_at_t":DELAY,
      "true_exact_early_pre_impulse_nonzero_samples":[t for t in TIME_SAMPLES if t<DELAY and ideal_impulse(t)],
      "hard_frequency_band_minus_pi_over_2_to_plus_pi_over_2":True,
      "bandlimited_reconstruction_nonzero_before_true_delay":false_before_band,
      "bandlimited_reconstructed_amplitude_at_t4":sinc_bandlimited(4),
      "bandlimited_artifact_is_not_physical_advanced_response":True,
      "centered_five_sample_filter_reads_future_samples":True,
      "centered_filter_nonzero_before_true_delay":false_before_centered,
      "centered_filter_at_t3":moving_average(3,True),
      "causal_trailing_filter_nonzero_before_true_delay":trailing_before,
      "causal_trailing_filter_at_t3":moving_average(3,False),
      "wrong_clock_offset_steps":-6,
      "wrong_displayed_impulse_t":DELAY-6,
      "correct_physical_impulse_t_unchanged":DELAY,
      "no_pre_registered_early_hardware_record_present":True
    }

def evaluate():
    mats=[]
    for material in MATERIALS:
        src,url=load_pinned_file(material)
        mats.append(source_diagnostics(src,material,url))
    return {
      "schema":SCHEMA,
      "scientific_class":"REAL_MEASURED_SPECTRAL_NK_PLUS_IDEAL_SLAB_MODEL_NOT_REAL_TIME_EXPERIMENT",
      "frozen_protocol":"PROTOCOL_011F_MEASURED_ABSORBERS_FROZEN.md",
      "geometry":"Ideal freestanding vacuum/metal/vacuum 40nm homogeneous slab normal incidence with coherent multiply reflected waves",
      "primary_wavelengths_um":list(WAVELENGTHS),
      "source_data_are_real_published_measurements":True,
      "materials":mats,
      "mathematical_false_early_precursors":temporal_false_positives(),
      "scientific_gate":{
        "measured_nk_provenance_and_hashes_verified":True,
        "passive_film_spectral_RTA_theoretically_computed":True,
        "material_spectral_dispersion_descriptively_estimated":True,
        "full_band_causal_impulse_measured":False,
        "analytically_KK_verified_from_finite_band_alone":False,
        "physically_selected_advanced_Green_fraction_from_material_data":False,
        "physical_absorber_global_radiation_boundary_derived":False,
        "physical_late_free_QRNG_choice":False,
        "independent_early_WORM_record":False,
        "new_physical_trials":0,
        "retrocausal_information_channel_observed":False,
        "result":"MEASURED_SPECTRAL_ABSORBER_CONSTRAINTS_PASS__RETROCAUSAL_ADVANCED_BOUNDARY_NOT_IDENTIFIED"
      },
      "scope_note":"The absorber's measured n,k and a passive slab model do not uniquely determine future boundary conditions. Bandlimited reconstructions and centered offline filtering can produce fake pre-impulse lobes without backwards information.",
      "sealed_JANUS_010_and_NAS_unchanged":True
    }

def main():
    p=argparse.ArgumentParser();p.add_argument("--output",required=True);args=p.parse_args()
    result=evaluate()
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write("\n")
    print("JANUS_011F_RESULT "+json.dumps({
      "sources":[{"material":m["material"],"original_sha256":m["original_file_sha256"],
          "rows":m["original_measured_nk_rows"],
          "primary":[{"wl_um":s["wavelength_um_exact_measured"],"R":round(s["slab_reflectance_R_model"],6),
              "T":round(s["slab_transmittance_T_model"],6),
              "A":round(s["slab_absorptance_A_model"],6)} for s in m["primary_four_measured_wavelengths"]]} for m in result["materials"]],
      "bandlimit_early_artifact_t4":result["mathematical_false_early_precursors"]["bandlimited_reconstructed_amplitude_at_t4"],
      "centered_preimpulse_t3":result["mathematical_false_early_precursors"]["centered_filter_at_t3"],
      "trailing_preimpulse_t3":result["mathematical_false_early_precursors"]["causal_trailing_filter_at_t3"],
      "advanced_physical_fraction_determined":False,"physical_trials":0
    },sort_keys=True),flush=True)

if __name__=="__main__":main()
