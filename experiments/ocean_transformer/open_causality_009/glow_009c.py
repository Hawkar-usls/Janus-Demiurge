#!/usr/bin/env python3
"""OPEN-GLOW-009C: illustrative SrAl2O4:Eu,Dy trapping/afterglow sensor model.

Never call this a measurement of SUNLU filament or a QPU. It intentionally
turns real/predicted NOAA broad-band GHI into a hypothetical 365 nm pump via
an UNMEASURED spectral fraction and assumed optical capture quantum yield.
Useful as a negative control for ordinary time-delayed memory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

SCHEMA="janus.ocean.open_glow_009c.v1"
H=6.62607015e-34
C=299792458.0
EPUMP=H*C/(365e-9)
EEMIT=H*C/(520e-9)
LAMBDA_PUMP_NM=365
LAMBDA_EMISSION_NM=520
SAMPLE_SIDE_M=.01
SAMPLE_THICK_M=.001
DENSITY_G_CM3=1.23
SR_ALUMINATE_MASS_FRACTION=.05
ABSORBED_FRACTION=.10
DELAYED_PHOTON_YIELD=.05
TAU_SECONDS=900.0
SOLAR_PUMP_FRACTION=.03


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def scenario():
    return {
      "name":"GLOW_009C_FIXED_UNCALIBRATED_SCENARIO",
      "identity":"SrAl2O4:Eu2+,Dy3+ assumed green 520nm; SUNLU SDS 2023 lists 5% strontium aluminate by mass but does not certify doping or active yield in every spool",
      "sample_dimensions_mm":[10,10,1],
      "sample_mass_g":round((10*10*1/1000)*DENSITY_G_CM3,6),
      "strontium_aluminate_mass_mg":round((10*10*1/1000)*DENSITY_G_CM3*SR_ALUMINATE_MASS_FRACTION*1000,6),
      "spectral_pump_nm":LAMBDA_PUMP_NM,
      "green_emission_nm":LAMBDA_EMISSION_NM,
      "assumed_absorbed_photon_fraction":ABSORBED_FRACTION,
      "assumed_absorbed_to_delayed_photon_yield":DELAYED_PHOTON_YIELD,
      "assumed_effective_decay_tau_s":TAU_SECONDS,
      "assumed_solar_GHI_365nm_equivalent_fraction":SOLAR_PUMP_FRACTION,
      "solar_fraction_is_not_a_physical_spectral_measurement":True,
      "spectrally_resolved_absorption_unknown":True,
      "real_glow_filament_luminous_flux_measured":False,
      "afterglow_lifetime_not_a_single_mechanistic_trap_state":True,
      "benchmark_365nm_pump_W":.001,
      "benchmark_pump_duration_s":300.0,
      "sources":[
        "https://sunlu.kyiv.ua/content/files/21_msds_sunlu_pla_grow_in_the_dark_filament-99280517.pdf",
        "https://www.edinst.com/resource/application-note-kinetics-of-persistent-luminescence-phosphors/",
        "https://doi.org/10.1016/j.jre.2021.07.014",
      ]
    }

def step(population,pump_W,seconds):
    """Exact solution to dN/dt=I_abs * phi/(hc/lambda)-N/tau."""
    if not (isinstance(population,(int,float)) and math.isfinite(population) and population>=0
       and isinstance(pump_W,(int,float)) and math.isfinite(pump_W) and pump_W>=0
       and isinstance(seconds,(int,float)) and math.isfinite(seconds) and seconds>0):
        raise ValueError("GLOW_INVALID_TRAP_STEP")
    r=pump_W*ABSORBED_FRACTION*DELAYED_PHOTON_YIELD/EPUMP
    decay=math.exp(-seconds/TAU_SECONDS)
    return population*decay + r*TAU_SECONDS*(1-decay)

def power_W(population):
    if population < 0 or not math.isfinite(population):raise ValueError("GLOW_INVALID_TRAP_POPULATION")
    return population/TAU_SECONDS*EEMIT

def benchtop():
    initial=step(0,.001,300)
    powers={str(sec):round(power_W(initial*math.exp(-sec/TAU_SECONDS))*1e6,8)
            for sec in (0,60,300,600,1800,3600)}
    return {
      "schema":SCHEMA,"experiment":"OPEN-GLOW-009C",
      "status":"ANALYTIC_SCENARIO_NOT_MEASURED",
      "hypothetical_365nm_pump_mW":1,
      "charge_duration_seconds":300,
      "trap_population_photon_equivalents":round(initial),
      "pump_photon_rate_per_s":round(.001/EPUMP),
      "afterglow_power_microwatt_at_seconds":powers,
      "sensor_readout_scenarios":{
         # photodiode output P_emit*capture*responsivity*transimpedance
         "1percent_collection_resp0p3AperW_gain100kohm_initial_mV":round(power_W(initial)*.01*.3*100000*1000,7),
         "10percent_collection_resp0p3AperW_gain100kohm_initial_mV":round(power_W(initial)*.1*.3*100000*1000,7),
      },
      "all_coefficients_except_fundamental_constants_are_hypotheses":True,
      "no_physical_glow_sensor_run":True,"retrocausality_proven":False,
    }

def sun_drive(hourly_ghi):
    """One day from zero trapped charge; hypothetical spectral conversion."""
    if len(hourly_ghi)!=24 or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in hourly_ghi):
        raise ValueError("GLOW_EXPECTS_24_NONNEGATIVE_GHI")
    n=0.
    output=[]
    for ghi in hourly_ghi:
        assumed_pump=ghi*(SAMPLE_SIDE_M**2)*SOLAR_PUMP_FRACTION
        n=step(n,assumed_pump,3600)
        output.append(round(power_W(n)*1e6,8))
    return output

def precommit(noaa_early):
    p=noaa_early.get("payload")
    if (not isinstance(p,dict) or noaa_early.get("sha256")!=digest(p) or
            p.get("lane")!="OPEN-LIGHT-009A" or len(p.get("predictions_w_m2",[]))!=24):
        raise ValueError("GLOW_NOAA_FORECAST_NOT_FROZEN")
    ghis=p["predictions_w_m2"]
    if any(x<0 for x in ghis):raise ValueError("GLOW_NEGATIVE_IRRADIANCE")
    output={
      "schema":SCHEMA,"experiment":"OPEN-GLOW-009C",
      "status":"HYPOTHETICAL_PHOSPHOR_FORECAST_PRECOMMIT",
      "noaa_009a_forecast_sha256":noaa_early["sha256"],
      "target_date":p["target_date_utc"],
      "scenario":scenario(),
      "expected_520nm_emission_microwatt":sun_drive(ghis),
      "actual_glow_measurements_available":False,
      "future_noaa_ghi_used":False,
      "future_photons_detected":False,
      "retrocausality_proven":False,
    }
    return {"payload":output,"sha256":digest(output)}

def assess(noaa_early, glow_early, noaa_observed):
    expect=precommit(noaa_early)
    if glow_early!=expect:raise ValueError("GLOW_HYPOTHETICAL_FORECAST_MUTATED")
    if (noaa_observed.get("date")!=expect["payload"]["target_date"] or
            len(noaa_observed.get("hourly_ghi",[]))!=24 or
            any(type(v) not in (int,float) or v<0 for v in noaa_observed["hourly_ghi"])):
        raise ValueError("GLOW_OBSERVED_SOLAR_INPUT_INVALID")
    measured_ghi=noaa_observed["hourly_ghi"]
    reference=sun_drive(measured_ghi)  # NOT physical afterglow measurement!
    prediction=expect["payload"]["expected_520nm_emission_microwatt"]
    mae=sum(abs(a-b) for a,b in zip(reference,prediction))/24
    return {
       "schema":SCHEMA,"experiment":"OPEN-GLOW-009C",
       "status":"SOLAR_FORECAST_PROPAGATED_THROUGH_HYPOTHETICAL_GLOW_MODEL",
       "earlier_glow_forecast_sha256":glow_early["sha256"],
       "observed_NOAA_ghi_sha256":noaa_observed["raw_sha256"],
       "synthetic_glow_derived_from_real_solar_ghi":True,
       "actual_glow_phosphor_measurements":0,
       "modeled_glow_mae_microwatt":round(mae,8),
       "hourly_virtual_green_emission_from_real_ghi":reference,
       "cannot_validate_the_phosphor_without_calibration":True,
       "retrocausality_proven":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("bench","prepare","assess"))
    ap.add_argument("--noaa-early")
    ap.add_argument("--glow-early")
    ap.add_argument("--noaa-observed")
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    if a.mode=="bench":result=benchtop()
    elif a.mode=="prepare":
        if not a.noaa_early:ap.error("No NOAA early precommit supplied")
        result=precommit(json.loads(Path(a.noaa_early).read_text()))
    else:
        if not(a.noaa_early and a.glow_early and a.noaa_observed):ap.error("Need NOAA early, glow early, observed NOAA")
        result=assess(json.loads(Path(a.noaa_early).read_text()),
                      json.loads(Path(a.glow_early).read_text()),
                      json.loads(Path(a.noaa_observed).read_text()))
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x") as f:f.write(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"sha256":digest(result),
                      "real_glow_measurements":0}))
if __name__=="__main__":main()
