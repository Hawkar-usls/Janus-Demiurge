#!/usr/bin/env python3
"""JANUS NIST-010F: complete original raw acquisition, GPS-only clock-rate audit.

NO detector-coincidence fitting, no adjustable cross-wing time alignment.
The selected NIST full experimental run 00_44/run3 is an official *known
timing-fault control*, not a source for new Bell or retrocausal discovery.
Runs are fully downloaded from original NIST S3 and parsed incrementally;
only source hashes, global counts and GPS summaries are retained.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import struct
import tempfile
import urllib.request
import zipfile

TICK_PS = 78.125
SECOND_TICKS = 12_800_000_000
REC = struct.Struct("<QQQ")
KNOWN = {0:"detector_click",2:"rng_output_0",4:"rng_output_1",5:"gps_pps",6:"sync"}
BASE = "https://s3.amazonaws.com/nist-belltestdata/belldata/rawdata_from_servers"
PAIRS = {
    "00_44_run3_known_timing_fault": {
      "day":"2015_09_18",
      "alice":"00_44_CH_pockel_100kHz.run3.alice.dat.zip",
      "bob":"00_43_CH_pockel_100kHz.run3.bob.dat.zip",
      "instrument_note":"The official NIST source describes improperly corrected timing; use solely as an instrument/analysis negative control.",
      "max_bytes_per_zip":450_000_000,
      "max_uncompressed_bytes_per_station":8_000_000_000
    }
}

def download_to(url,dest,limit):
    req=urllib.request.Request(url,headers={"User-Agent":"JANUS-010F/1.0 NIST Bell raw data reproducibility"})
    d=hashlib.sha256()
    total=0
    with urllib.request.urlopen(req,timeout=180) as h, dest.open("xb") as f:
        announced=h.headers.get("Content-Length")
        if announced is not None and int(announced)>limit:
            raise ValueError("ZIP_CONTENT_LENGTH_EXCEEDS_LIMIT")
        while True:
            chunk=h.read(4*1024*1024)
            if not chunk:break
            total+=len(chunk)
            if total>limit:raise ValueError("ZIP_STREAM_OVER_LIMIT")
            d.update(chunk)
            f.write(chunk)
        f.flush();os.fsync(f.fileno())
    return total,d.hexdigest()

def summarize_raw(zip_path,raw_cap):
    counts=collections.Counter()
    first={}
    last={}
    pps=[]
    max_trans=0
    prev_tick=None
    inversions=0
    total=0
    digest=hashlib.sha256()
    with zipfile.ZipFile(zip_path) as z:
        entries=[e for e in z.infolist() if not e.is_dir()]
        if len(entries)!=1 or not entries[0].filename.endswith(".dat"):
            raise ValueError("ZIP_DOES_NOT_CONTAIN_EXACTLY_ONE_RAW_DAT")
        info=entries[0]
        if info.file_size>raw_cap:raise ValueError("RAW_DECOMPRESSED_FILE_SIZE_OVER_CAP")
        if info.file_size % REC.size:raise ValueError("RAW_ARCHIVE_SIZE_NOT_24_BYTE_ALIGNED")
        with z.open(info) as f:
            while True:
                chunk=f.read(REC.size*100_000)
                if not chunk:break
                if len(chunk)%REC.size:raise ValueError("RAW_STREAM_RECORD_ALIGNMENT_FAILED")
                total+=len(chunk)
                if total>raw_cap:raise ValueError("DECOMPRESSION_STREAM_OVER_CAP")
                digest.update(chunk)
                for ch,t,transfer in REC.iter_unpack(chunk):
                    counts[ch]+=1
                    if ch not in first:first[ch]=t
                    last[ch]=t
                    max_trans=max(max_trans,transfer)
                    if prev_tick is not None and t<prev_tick:inversions+=1
                    prev_tick=t
                    if ch==5:
                        pps.append(t)
                        if len(pps)>100_000:raise ValueError("TOO_MANY_GPS_PPS")
                    if ch>255:raise ValueError("IMPLAUSIBLE_CHANNEL_CODE_ENDIAN_OR_CORRUPT")
    if total!=info.file_size:raise ValueError("READ_SIZE_DIFFERS_FROM_ZIP_METADATA")
    if not total:raise ValueError("EMPTY_RAW_SOURCE")
    if len(pps)<3:phase=None;period=None
    else:
        gaps=[b-a for a,b in zip(pps,pps[1:])]
        if any(x<=0 for x in gaps):raise ValueError("PPS_REORDERING_OR_DUPLICATES")
        period=statistics.median(gaps)
        phase={
          "first_pps_tick":pps[0],
          "last_pps_tick":pps[-1],
          "n_pps":len(pps),
          "n_periods":len(gaps),
          "median_period_ticks":period,
          "median_period_ns":period*TICK_PS*1e-3,
          "median_period_minus_1s_ns":(period-SECOND_TICKS)*TICK_PS*1e-3,
          "median_abs_dev_period_ns":statistics.median([abs(g-period) for g in gaps])*TICK_PS*1e-3,
          "min_period_ns":min(gaps)*TICK_PS*1e-3,
          "max_period_ns":max(gaps)*TICK_PS*1e-3,
          "period_outlier_count_outside_0_75_to_1_25_s":sum(
               g < SECOND_TICKS*.75 or g>SECOND_TICKS*1.25 for g in gaps),
          "local_pps_median_period_source":"PPS only; detector event times not used"
        }
        if phase["period_outlier_count_outside_0_75_to_1_25_s"]>0:
            phase["rate_estimate_valid"]=False
        else:phase["rate_estimate_valid"]=True
    return {
        "n_original_raw_events":total//REC.size,
        "original_raw_file_bytes":total,
        "original_raw_sha256":digest.hexdigest(),
        "counts_by_channel":{str(ch):int(v) for ch,v in sorted(counts.items())},
        "mapped_physical_channels":{str(ch):counts[ch] for ch in KNOWN},
        "unclassified_codes":{str(ch):v for ch,v in sorted(counts.items()) if ch not in KNOWN},
        "first_local_ticks":{str(ch):t for ch,t in sorted(first.items())},
        "last_local_ticks":{str(ch):t for ch,t in sorted(last.items())},
        "globally_descending_timetag_pairs":inversions,
        "max_data_transfer_counter":max_trans,
        "gps_phase_rate_diagnostics":phase,
        "partial_gps_info_if_too_few":len(pps) if len(pps)<3 else None,
        "filename_inside_zip":info.filename
    }

def clock_audit(a,b):
    pa=a["gps_phase_rate_diagnostics"]
    pb=b["gps_phase_rate_diagnostics"]
    result={
      "clock_source":"Only local GPS PPS tag intervals, no detector coincidences",
      "shared_10MHz_reference":"Recorded in NIST source documentation",
      "original_raw_epoch_match":False,
      "identifiable_absolute_A_minus_B_clock_offset_ticks":False,
      "why_offset_not_identifiable":"PPS events record unnumbered whole-second boundaries; without an externally authenticated common UTC second label, pairing PPS index i from Alice to PPS index j from Bob has unknown integer shift. Source start filenames have only minute resolution.",
      "do_not_estimate_offset_by_searching_photon_coincidences":True,
      "cross_station_signal_or_retrocausality_test_eligible":False,
      "raw_filename_first_pps_mod_UTC_second":"Unknown because source files contain no absolute UTC-second labels"
    }
    if pa and pb and pa["rate_estimate_valid"] and pb["rate_estimate_valid"]:
       result["alice_period_ns"]=pa["median_period_ns"]
       result["bob_period_ns"]=pb["median_period_ns"]
       result["alice_minus_bob_median_period_ns"]=pa["median_period_ns"]-pb["median_period_ns"]
       result["fractional_frequency_difference_ppm"]=(pa["median_period_ticks"]-pb["median_period_ticks"])/SECOND_TICKS*1e6
       result["relative_clock_rate_eligible_for_diagnostic"]=True
    else:
       result["relative_clock_rate_eligible_for_diagnostic"]=False
       result["reason"]="Insufficient reliable PPS periods on one or both sources"
    return result

def run(which,out):
    spec=PAIRS[which]
    row={"schema":"janus.nist010f.original_full_run_gps_clock_audit.v1",
        "status":"IN_PROGRESS",
        "source_type":"ACTUAL_FULL_NIST_2015_EXPERIMENTAL_RAW_FILES_NOT_FIND_SYNC",
        "selected_run":which,
        "source_instrument_warning":spec["instrument_note"],
        "NIST_official_source_index":"https://www.nist.gov/pml/applied-physics-division/bell-test-research-software-and-data/repository-bell-test-research-3",
        "NIST_official_format_document":"https://s3.amazonaws.com/nist-belltestdata/belldata/File_Folder_Descriptions.pdf",
        "raw_channel_tick_ps":TICK_PS,
        "counts_includes_all_raw_records":True,
        "timestamp_matching_or_postselection":False,
        "clock_offset_fitted_using_detector_correlations":False,
        "retrocausality_proven":False,"wings":{}}
    with tempfile.TemporaryDirectory(prefix="janus-010f-nist-") as root:
        for wing in ("alice","bob"):
            name=spec[wing]
            url=f"{BASE}/{wing}/{spec['day']}/{name}"
            path=Path(root)/name
            nbytes,zip_sha=download_to(url,path,spec["max_bytes_per_zip"])
            print("NIST_010F_DOWNLOADED "+json.dumps({"wing":wing,"source":url,
                "zip_bytes":nbytes,"source_zip_sha256":zip_sha}),flush=True)
            s=summarize_raw(path,spec["max_uncompressed_bytes_per_station"])
            row["wings"][wing]={"source_url":url,"zip_bytes":nbytes,
                "source_zip_sha256":zip_sha,"event_summary":s}
            print("NIST_010F_WING "+json.dumps({"wing":wing,"events":s["n_original_raw_events"],
                "channels":s["counts_by_channel"],"gps":s["gps_phase_rate_diagnostics"],
                "raw_sha256":s["original_raw_sha256"]},sort_keys=True),flush=True)
            path.unlink()
    row["clock_alignment"]=clock_audit(row["wings"]["alice"]["event_summary"],
                                       row["wings"]["bob"]["event_summary"])
    row["status"]="FULL_ORIGINAL_SOURCES_PROCESSED__ABSOLUTE_CLOCK_EPOCH_UNIDENTIFIED"
    row["physical_limits"]=[
        "00_44/run3 is a NIST-documented improperly corrected timing experimental run; must not be mistaken for final loophole-free proof run.",
        "Original detector settings are in raw hardware timestamps; choice generation instant and actual physical actuation latency are not independently notarized.",
        "Unlabelled PPS across distinct acquisition start epochs only supports independent frequency comparison; it does not establish an absolute cross-wing offset modulo integer seconds.",
        "No detector-matched pair table or Bell/retrocausal statistic computed.",
        "Unknown NIST channel codes remain unclassified, not inferred detector events."
    ]
    p=Path(out)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("x",encoding="utf8") as f:
        json.dump(row,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010F_RESULT "+json.dumps({
        "run":which,
        "alice_events":row["wings"]["alice"]["event_summary"]["n_original_raw_events"],
        "bob_events":row["wings"]["bob"]["event_summary"]["n_original_raw_events"],
        "clock":row["clock_alignment"],"status":row["status"]
    },sort_keys=True),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--run",choices=list(PAIRS),default="00_44_run3_known_timing_fault")
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    run(args.run,args.output)
