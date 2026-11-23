#!/usr/bin/env python3
"""JANUS-010G: can GPS 1PPS interval jitter alone identify a shared second index?

No photon data or arbitrary outcome matching. Candidate lag is *learned on
first half* of archived NIST 00_44/run3 PPS intervals and evaluated on held-
out second half. Circular shifts provide an exploratory time-series null;
stationarity/independence are unverified, hence a candidate is NOT an
externally certified UTC alignment. Known-fault run; no retrocausal claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import zipfile
import nist_full_clock_010f as raw

# These are committed only AFTER the separately SHA-archived completed 010F
# source verification; changes to the original bytes refuse scoring.
SOURCE_SHA256={
  "alice":"d581080c9fa6853a1bfb8ce511782563f433512f3ce7efb612202a5179c5ee6c",
  "bob":"f42204b41289c26ef779d39957062604c8d4008a4892724b7f2078afd7ddd5d4"
}
EXPECTED_PPS=417
LAG_MIN=-120
LAG_MAX=120
TRAIN_END=208
ALPHA_EXPLORATORY=0.01


def extract_pps(zip_path):
    """Read every original 24byte record, keep ONLY public GPS channel5 tags."""
    pps=[]
    with zipfile.ZipFile(zip_path) as z:
        entries=[x for x in z.infolist() if not x.is_dir()]
        if len(entries)!=1:raise ValueError("ZIP_SOURCE_MEMBER_AMBIGUOUS")
        with z.open(entries[0]) as f:
            while True:
                block=f.read(raw.REC.size*100000)
                if not block:break
                if len(block)%raw.REC.size:raise ValueError("UNALIGNED_RAW_EVENT_CHUNK")
                for channel,tick,_ in raw.REC.iter_unpack(block):
                    if channel==5:pps.append(tick)
    if len(pps)!=EXPECTED_PPS:raise ValueError("EXPECTED_417_GPS_PPS_NOT_FOUND")
    intervals=[b-a for a,b in zip(pps[:-1],pps[1:])]
    if any(k<=0 for k in intervals):raise ValueError("NONMONOTONIC_PPS")
    if any(k < .75*raw.SECOND_TICKS or k > 1.25*raw.SECOND_TICKS for k in intervals):
        raise ValueError("PPS_INTERVAL_MISSING_OR_DUPLICATED")
    return pps,intervals


def pearson(x,y):
    if len(x)!=len(y) or len(x)<3:raise ValueError("NOT_ENOUGH_PAIRWISE_PPS_PERIODS")
    u=statistics.mean(x);v=statistics.mean(y)
    xx=sum((a-u)**2 for a in x)
    yy=sum((b-v)**2 for b in y)
    if xx==0 or yy==0:return 0.0
    return sum((a-u)*(b-v) for a,b in zip(x,y))/math.sqrt(xx*yy)


def paired_lag(a,b,lag,start,end):
    x,y=[],[]
    for i in range(start,end):
        j=i+lag
        if 0<=j<len(b):
            x.append(a[i]);y.append(b[j])
    return x,y


def evaluate(a,b):
    """Predefined heldout split: 208 training + 208 validation GPS gaps."""
    if len(a)!=416 or len(b)!=416:raise ValueError("EXPECTED_416_PPS_GAPS")
    candidates=[]
    for lag in range(LAG_MIN,LAG_MAX+1):
        x,y=paired_lag(a,b,lag,0,TRAIN_END)
        if len(x)<80:continue
        r=pearson(x,y)
        candidates.append({"lag_B_index_minus_A_index":lag,
                           "train_n":len(x),"train_r":r})
    if not candidates:raise ValueError("NO_LAG_CAN_BE_TESTED")
    # Deterministic MLE ranking: Pearson |r| for centered Gaussian waveform.
    # Ties resolved by smaller |lag| then increasing signed lag.
    chosen=sorted(candidates,key=lambda c:(-abs(c["train_r"]),
                     abs(c["lag_B_index_minus_A_index"]),
                     c["lag_B_index_minus_A_index"]))[0]
    lag=chosen["lag_B_index_minus_A_index"]
    xx,yy=paired_lag(a,b,lag,TRAIN_END,len(a))
    if len(xx)<80:raise ValueError("HOLDOUT_OVERLAP_TOO_SMALL")
    r=pearson(xx,yy)
    circular=[pearson(xx,yy[k:]+yy[:k]) for k in range(1,len(yy))]
    # Exact enumeration of available nonzero circular shifts, no hand-optimized window.
    # Valid only if the alignment-null is stationary under circular rotation.
    p=(1+sum(abs(v)>=abs(r)-1e-12 for v in circular))/len(yy)
    sign_consistent=(chosen["train_r"]*r>0)
    candidate_passes=(p<=ALPHA_EXPLORATORY and sign_consistent)
    return {
      "test":"PPS gap waveform Pearson correlation and heldout circular-shift control",
      "clock_source":"ONLY channel 5 GPS 1PPS intervals from originally published NIST files",
      "fixed_lag_range":[LAG_MIN,LAG_MAX],
      "train_A_interval_indices":[0,TRAIN_END-1],
      "validation_A_interval_indices":[TRAIN_END,len(a)-1],
      "candidate_B_index_minus_A_index":lag,
      "train_pearson_r":chosen["train_r"],
      "training_pairs":chosen["train_n"],
      "validation_pearson_r":r,
      "validation_pairs":len(xx),
      "validation_circular_shift_p_two_sided":p,
      "validation_sign_consistent":sign_consistent,
      "exploratory_alpha":ALPHA_EXPLORATORY,
      "relative_pps_sequence_candidate_detected":candidate_passes,
      "numerically_computed_lag_is_not_an_absolute_clock_offset":True,
      "certified_UTC_second_index_mapping_established":False,
      "independent_physical_clock_offset_established":False,
      "causal_inference_eligible":False,
      "reasons":[
         "Training-selected lag has validation separate from fitting, but archive is retrospective and noise stationarity/circular shift exchangeability are unverified",
         "GPS interval patterns may be independent between stations; even an apparent match needs instrument provenance to establish shared pulse origin",
         "Absolute calibrated detector path latency and UTC second labels are not supplied by the 24byte event records",
         "The NIST 00_44/run3 setup has a known timing correction error."
      ]
    }


def run(destination):
    spec=raw.PAIRS["00_44_run3_known_timing_fault"]
    data={}
    with tempfile.TemporaryDirectory(prefix="janus-nist-010g-") as root:
        for wing in ("alice","bob"):
            name=spec[wing]
            uri=f"{raw.BASE}/{wing}/{spec['day']}/{name}"
            zip_path=Path(root)/name
            size,sha=raw.download_to(uri,zip_path,spec["max_bytes_per_zip"])
            if sha!=SOURCE_SHA256[wing]:raise ValueError("NIST010F_SOURCE_HASH_CHANGED")
            pps,intervals=extract_pps(zip_path)
            data[wing]={"original_zip_sha256":sha,"zip_bytes":size,
                  "n_pps":len(pps),"n_periods":len(intervals),
                  "first_tick":pps[0],"last_tick":pps[-1],
                  "interval_median_ns":statistics.median(intervals)*raw.TICK_PS*1e-3,
                  "PPS_interval_raw_digest_sha256":hashlib.sha256(
                     json.dumps(intervals,separators=(",",":")).encode()).hexdigest()}
            data[wing]["intervals"]=intervals
            zip_path.unlink()
            print("NIST_010G_SOURCE "+json.dumps({k:v for k,v in data[wing].items() if k!="intervals"}|{"wing":wing},sort_keys=True),flush=True)
    score=evaluate(data["alice"]["intervals"],data["bob"]["intervals"])
    for wing in ("alice","bob"):del data[wing]["intervals"]
    obj={"schema":"janus.nist010g.independent_gps_lag_test.v1",
      "data_kind":"REAL_HISTORICAL_NIST_2015_FULL_RUN3_PPS_NOT_PHOTON_PAIRS",
      "source":"00_44/run3 known timing-fault instrument negative control",
      "data":data,"lag_test":score,
      "retrocausality_proven":False,
      "source_original_run_class":"KNOWN_INCORRECT_TIMING",
      "new_physical_late_choice_performed":False}
    out=Path(destination)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf8") as f:
        json.dump(obj,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("NIST_010G_RESULT "+json.dumps(score,sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    run(p.parse_args().output)
