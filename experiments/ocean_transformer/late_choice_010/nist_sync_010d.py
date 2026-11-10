#!/usr/bin/env python3
"""JANUS-010D: bounded replay of NIST 2015 raw clock-calibration timetags.

Data: official NIST S3 belltestdata rawdata_from_servers *find_sync* files,
NOT the Bell trials themselves. Only aggregates are saved, never source bytes.

The official documentation says each event is (channel:uint64, tick:uint64,
transfer:uint64) with tick period 78.125 ps. Byte order is assumed little-
endian based on common acquisition hardware; reject implausible channel codes
rather than silently treating endian assumptions as verified physics.

Clock starts differ between wings: raw cross-station timestamp subtraction
IS INVALID without independent offset/drift calibration and uncertainty.
No causal, retrocausal or quantum Bell outcome inferred from these files.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import struct
import urllib.request
import zipfile

BASE="https://s3.amazonaws.com/nist-belltestdata/belldata/rawdata_from_servers"
SAMPLES=(
    ("2015-09-18-18_32","alice","18_32_find_sync.T1.dat.zip"),
    ("2015-09-18-18_32","bob","18_32_find_sync.T2.dat.zip"),
    ("2015-09-18-00_03","alice","00_03_find_sync.T1.dat.zip"),
    ("2015-09-18-00_03","bob","00_03_find_sync.T2.dat.zip"),
)
CHANNELS={0:"detector_click",2:"QRNG_zero_setting_output",
          4:"QRNG_one_setting_output",5:"GPS_PPS",6:"pockels_sync"}
TICK_PS=78.125
GPS_HZ=1
REC=struct.Struct("<QQQ")
MAX_ZIP_BYTES=8_000_000
MAX_UNZIP_BYTES=90_000_000
SOURCE_DOC="https://s3.amazonaws.com/nist-belltestdata/belldata/File_Folder_Descriptions.pdf"


def fetch(run,wing,filename):
    uri=f"{BASE}/{wing}/2015_09_18/{filename}"
    request=urllib.request.Request(uri,headers={"User-Agent":"JANUS-010D NIST-open-research-timetag-audit"})
    with urllib.request.urlopen(request,timeout=50) as h:
        raw=h.read(MAX_ZIP_BYTES+1)
    if len(raw)>MAX_ZIP_BYTES:raise ValueError("REFUSE_ARCHIVE_OVER_CAP")
    if not zipfile.is_zipfile(io.BytesIO(raw)):raise ValueError("NOT_A_ZIP")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=[x for x in z.infolist() if not x.is_dir()]
        if len(entries)!=1:raise ValueError("NOT_EXACTLY_ONE_SOURCE_FILE")
        info=entries[0]
        if info.file_size>MAX_UNZIP_BYTES:raise ValueError("DECOMPRESSION_CAP_EXCEEDED")
        if not info.filename.endswith(".dat"):
            raise ValueError("UNEXPECTED_RAW_FILENAME_SUFFIX")
        with z.open(info) as f:
            data=f.read(MAX_UNZIP_BYTES+1)
        if len(data)>MAX_UNZIP_BYTES:raise ValueError("DECOMPRESSION_CAP_EXCEEDED")
    if len(data)%REC.size:raise ValueError("UNALIGNED_24_BYTE_EVENT_RECORD")
    return uri,raw,data,info.filename


def parse_events(raw):
    if len(raw)%REC.size:raise ValueError("UNALIGNED_24_BYTE_EVENT_RECORD")
    counts=collections.Counter()
    first={}
    last={}
    transfer_min=None
    transfer_max=None
    prev_tick=None
    inversions=0
    gps_ticks=[]
    sample=[]
    n=0
    for channel,tick,transfer in REC.iter_unpack(raw):
        if channel not in CHANNELS:
            raise ValueError(f"UNKNOWN_CHANNEL_{channel}_CHECK_ENDIAN_OR_FORMAT")
        n+=1
        counts[channel]+=1
        if channel not in first:first[channel]=tick
        last[channel]=tick
        if prev_tick is not None and tick<prev_tick:inversions+=1
        prev_tick=tick
        transfer_min=transfer if transfer_min is None else min(transfer_min,transfer)
        transfer_max=transfer if transfer_max is None else max(transfer_max,transfer)
        if channel==5:
            if len(gps_ticks)>100000:
                raise ValueError("TOO_MANY_PPS_FOR_BOUNDED_AUDIT")
            gps_ticks.append(tick)
        if len(sample)<6:
            sample.append({"channel":channel,"timetag_ticks":tick,"transfer":transfer})
    diffs=[a-b for b,a in zip(gps_ticks[:-1],gps_ticks[1:])]
    if any(x<=0 for x in diffs):
        raise ValueError("NONINCREASING_GPS_PPS_ON_LOCAL_STATION")
    intervals=[d*TICK_PS*1e-3 for d in diffs]  # 1 ps = 1e-3 ns
    return {
      "n_raw_events":n,
      "per_channel":{str(ch):{"name":CHANNELS[ch],"count":counts[ch],
                             "first_tick":first.get(ch),"last_tick":last.get(ch)}
                     for ch in CHANNELS},
      "unknown_channel_count":0,
      "globally_descending_timetag_pairs":inversions,
      "transfer_counter_min":transfer_min,"transfer_counter_max":transfer_max,
      "GPS_PPS_count":len(gps_ticks),
      "GPS_PPS_interval_count":len(intervals),
      "GPS_PPS_interval_median_ns":statistics.median(intervals) if intervals else None,
      "GPS_PPS_interval_min_ns":min(intervals) if intervals else None,
      "GPS_PPS_interval_max_ns":max(intervals) if intervals else None,
      "GPS_nominal_one_second_ns":1_000_000_000,
      "sample_for_parser_inspection":sample
    }


def run(dest):
    rows=[]
    for run_name,wing,filename in SAMPLES:
        uri,zipped,raw,native=fetch(run_name,wing,filename)
        stats=parse_events(raw)
        row={"run_name":run_name,"wing":wing,"official_s3_uri":uri,
             "original_zip_bytes":len(zipped),
             "source_zip_sha256":hashlib.sha256(zipped).hexdigest(),
             "uncompressed_file_name":native,
             "uncompressed_bytes":len(raw),
             "raw_event_data_sha256":hashlib.sha256(raw).hexdigest(),
             "stats":stats}
        rows.append(row)
        print("NIST_010D_STATION "+json.dumps({"run_name":run_name,"wing":wing,
                  "zip_sha256":row["source_zip_sha256"],"stats":stats},sort_keys=True),flush=True)
    out={"schema":"janus.open010d.nist_raw_sync_timetag_calibration.v1",
         "data_origin":"NIST official 2015 Shalm et al. Bell test rawdata",
         "official_docs":SOURCE_DOC,
         "physical_source":"REAL_NIST_CALIBRATION_DATA_NOT_BELL_TRIALS",
         "physical_record_encoding":"24 bytes per event: uint64 channel, uint64 timetag, uint64 transfer index; little endian assumed",
         "picosecond_per_timetag":TICK_PS,
         "channel_mapping":CHANNELS,
         "official_reference":"Two stations locked to common 10 MHz frequency; different raw clock start epochs, GPS PPS jitter ~10 ns with possible 100 ns jumps",
         "paired_station_acquisition":"Same approximate local training run labels, NOT established physical event-by-event cross-station alignment",
         "clock_shift_fit_performed":False,
         "absolute_timestamp_cross_wing_comparison_performed":False,
         "setting_after_A_causality_established":False,
         "quantum_no_signalling_hypothesis_test_performed":False,
         "retrocausality_proven":False,
         "sources":rows,
         "limitations":[
           "Clock-calibration find_sync files have no guaranteed usable Bell trials",
           "Nominal 78.125 ps resolution is not clock accuracy or detector latency",
           "Raw source endian assumed little-endian until independently corroborated",
           "PPS channel may be absent in very short runs; null is not inferred accuracy",
           "No independently signed physical early log or true late free-choice intervention",
           "Do not select apparent timestamp coincidences after inspecting outcome"
         ]}
    output=Path(dest)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf8") as f:
        json.dump(out,f,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)
        f.write("\n")
        f.flush();os.fsync(f.fileno())
    print("NIST_010D_COMPLETE "+json.dumps({"sources":len(rows),"events":sum(x["stats"]["n_raw_events"] for x in rows),"retrocausality_proven":False}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)
