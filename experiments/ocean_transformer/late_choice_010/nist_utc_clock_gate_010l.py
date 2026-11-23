#!/usr/bin/env python3
"""JANUS-NIST-010L: independent hardware UTC-clock reference admission gate.

This does NOT analyze photon outcomes and does NOT invent UTC labels.
Only real externally matched UTC PPS seconds could define a candidate
relative clock epoch. Even candidate numeric offsets are NOT "certified":
the instrument provenance, cable delays and independent custody must be
verified by human lab reviewer and cryptographic evidence before physics use.

All NIST historical and 010F/010G findings stay unchanged.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re

SCHEMA="janus.nist010l.utc_pps_clock_admission.v1"
PERIOD_NS=Fraction(5,64)  # exactly 78.125 ps per tick
SHA_RE=re.compile(r"^[0-9a-f]{64}$")

OFFICIAL={
    "NIST_2015_original_data_description":"https://s3.amazonaws.com/nist-belltestdata/belldata/File_Folder_Descriptions.pdf",
    "NIST_2015_original_processing":"https://s3.amazonaws.com/nist-belltestdata/belldata/code/analysis/DataProcessingDescription.pdf",
    "NIST_2015_published_paper":"https://pmc.ncbi.nlm.nih.gov/articles/PMC5815856/",
    "NIST_time_metrology_guidance":"https://www.nist.gov/publications/evaluating-frequency-and-time-uncertainty-gps-disciplined-oscillators-and-clocks",
    "NIST_GPS_satellite_archive":"https://www.nist.gov/pml/time-and-frequency-division/services/gps-data-archive"
}

def external_inventory():
    return {
        "schema":SCHEMA,
        "experiment":"NIST_2015_Sh alm_Bell".replace(" ",""),
        "source_type":"ACTUAL_NIST_ORIGINAL_BELL_RAW_RUN3_TIMING_FAULT_CONTROL",
        "source_zip_sha256":{
          "alice":"d581080c9fa6853a1bfb8ce511782563f433512f3ce7efb612202a5179c5ee6c",
          "bob":"f42204b41289c26ef779d39957062604c8d4008a4892724b7f2078afd7ddd5d4"},
        "local_PPS_count":{"alice":417,"bob":417},
        "has_externally_verified_matching_UTC_second_indices":False,
        "utc_pps_pairs":[],
        "hardware_cable_delay_uncertainty_calibration":None,
        "clock_anchor_external_custodian_signature_verification":None,
        "documented_Bell_spacelike_timing_margin_for_five_pulses_ns":38.3,
        "documented_published_margin_uncertainty_ns":3.7
    }

def exact_frac(value):
    if isinstance(value,bool) or type(value) not in (int,str):
        raise ValueError("TICK_MUST_BE_INT_OR_CANONICAL_NUMBER_STRING")
    if type(value) is str:
        if not re.fullmatch(r"[0-9]+",value):raise ValueError("NONCANONICAL_TICK_VALUE")
        value=int(value)
    if value<0:raise ValueError("NEGATIVE_LOCAL_COUNTER_TICK")
    return value

def analyze_utc_pairs(pairs):
    if not isinstance(pairs,list):raise ValueError("EXPECTED_UTC_PPS_PAIRS_ARRAY")
    if not pairs:return None
    if len(pairs)<3:raise ValueError("TOO_FEW_EXTERNALLY_PAIRED_PPS_EVENTS")
    previous_utc=None; prev_a=None; prev_b=None
    offsets=[]
    for p in pairs:
        if set(p)!={"utc_second","alice_tick","bob_tick"}:raise ValueError("MALFORMED_COMMON_UTC_PPS_ENTRY")
        utc=exact_frac(p["utc_second"])
        a=exact_frac(p["alice_tick"]); b=exact_frac(p["bob_tick"])
        if previous_utc is not None and (utc<=previous_utc or a<=prev_a or b<=prev_b):
            raise ValueError("NONMONOTONIC_UTC_OR_LOCAL_PPS")
        if previous_utc is not None and utc-previous_utc!=1:
            raise ValueError("GAP_IN_UTC_SECOND_LABELS_REQUIRE_EXPLICIT_MISSINGNESS")
        offsets.append(a-b)
        previous_utc=utc;prev_a=a;prev_b=b
    delta_ticks_min=min(offsets);delta_ticks_max=max(offsets)
    sorted_d=sorted(offsets); k=len(sorted_d)
    if k%2:med=Fraction(sorted_d[k//2],1)
    else:med=Fraction(sorted_d[k//2-1]+sorted_d[k//2],2)
    def to_str(f):return f"{f.numerator}/{f.denominator}" if f.denominator!=1 else str(f.numerator)
    return {
      "n_common_utc_pps_pairs":len(offsets),
      "candidate_counter_A_minus_B_epoch_tick_median":to_str(med),
      "candidate_counter_A_minus_B_epoch_ns_exact":to_str(med*PERIOD_NS),
      "range_of_candidate_offsets_ticks":delta_ticks_max-delta_ticks_min,
      "range_of_candidate_offsets_ns_exact":to_str((delta_ticks_max-delta_ticks_min)*PERIOD_NS),
      "source":"Only external matching UTC-second PPS labels, never any photon/detector coincidence",
      "absolute_physical_offset_after_cable_delay":"UNDETERMINED",
      "uncertainty_intervals_and_instrument_latency":"NOT_INFERRED_FROM_PPS_COUNT",
      "numerical_candidate_is_not_certificate":True
    }

def gate(record):
    if record.get("schema")!=SCHEMA:raise ValueError("UNKNOWN_REFERENCE_SCHEMA")
    sha=record.get("source_zip_sha256")
    if not isinstance(sha,dict) or set(sha)!={"alice","bob"} or not all(SHA_RE.fullmatch(x) for x in sha.values()):
        raise ValueError("MISSING_OR_INVALID_NIST_ORIGINAL_SOURCE_SHA256")
    actual_labels=record.get("has_externally_verified_matching_UTC_second_indices")
    if type(actual_labels) is not bool:raise ValueError("INDEPENDENT_UTC_LABEL_FLAG_INVALID")
    pairs=record.get("utc_pps_pairs")
    computed=analyze_utc_pairs(pairs)
    if actual_labels and not pairs:raise ValueError("CLAIMED_VERIFIED_UTC_LABELS_WITHOUT_EVIDENCE")
    if pairs and not actual_labels:raise ValueError("SELF_PROVIDED_COMMON_UTC_LABELS_UNVERIFIED")
    # Note a self-asserted boolean is NOT provenance certification.
    return {
       "schema":"janus.nist010l.utc_clock_gate_result.v1",
       "input_record_sha256":hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest(),
       "paper_and_metrology_sources":OFFICIAL,
       "source_type":record.get("source_type"),
       "individual_NIST_raw_archives_sha256":sha,
       "GPS_channel_5_pulses_reported":record.get("local_PPS_count"),
       "raw_PPS_input_labels_exist":bool(pairs),
       "candidate_from_utc_labels":computed,
       "independent_external_provenance_cryptographically_verified":False,
       "hardware_delay_and_uncertainty_independently_verified":False,
       "NIST_2015_five_pulse_timing_margin_ns_published":38.3,
       "published_margin_uncertainty_ns":3.7,
       "do_not_subtract_PPS_jitter_from_published_Bell_margin":"Different experimental quantities; need actual hardware-specific uncertainty budget",
       "absolute_A_B_clock_offset_certified":False,
       "physical_timing_validated_for_010":False,
       "eligible_for_future_to_past_inference":False,
       "status":"BLOCKED_NO_INDEPENDENT_UTC_PPS_PAIRING" if not pairs else "NUMERIC_UTC_PPS_CANDIDATE_EXTERNAL_CUSTODY_AND_LATENCY_VERIFICATION_PENDING",
       "next_gate":"Acquire external common UTC labels / original NIST 2015 source + instrument path delay calibration and independent custody audit; do not match photons to choose time offset."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",help="Path to external UTC PPS pairing evidence; default is verified 010F inventory without UTC labels")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    manifest=json.loads(Path(a.manifest).read_text()) if a.manifest else external_inventory()
    result=gate(manifest)
    dst=Path(a.output);dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010L_RESULT "+json.dumps({"status":result["status"],
         "absolute_A_B_clock_offset_certified":False,
         "utc_pair_count":result["candidate_from_utc_labels"]["n_common_utc_pps_pairs"] if result["candidate_from_utc_labels"] else 0},sort_keys=True),flush=True)

if __name__=="__main__":main()
