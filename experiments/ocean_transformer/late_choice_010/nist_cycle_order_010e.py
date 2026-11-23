#!/usr/bin/env python3
"""JANUS-010E: within-station NIST timing audit on real 2015 calibrator files.

Every half-open sync-to-next-sync cycle is counted. No cross-wing offset fit,
no postselection for an inferential p-value, and NO attempt to interpret an
electrical RNG output tag as the timestamp of a later freely generated choice.
This is a retrospective raw hardware-causality *diagnostic* only.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import statistics
import nist_sync_010d as n


def sync_cycle_audit(data):
    """One-pass all-cycle accounting between consecutive physical channel-6 tags."""
    counts=collections.Counter()
    classification=collections.Counter()
    diffs_ns=[]
    rng_delays_ns=[]
    detector_delays_ns=[]
    unknown=collections.Counter()
    prev_known=None
    state=None
    before_sync=0
    last_tail=0

    def close_cycle(c):
        counts["completed_cycles"]+=1
        d=c["detectors"]
        q=c["rng"]
        if not d:classification["zero_detectors"]+=1
        else:classification["at_least_one_detector"]+=1
        if not q:classification["zero_rng_pulses"]+=1
        else:classification["at_least_one_rng_pulse"]+=1
        if len(q)==1 and not d:classification["one_rng_no_detector"]+=1
        if len(q)==1 and d:classification["one_rng_with_detector"]+=1
        if len(q)>1:classification["multiple_rng_pulses"]+=1
        if len(q)==1:
            classification["setting_code_"+str(q[0][0])]+=1
        if q and d:
            delta_ticks=q[0][1]-d[0]
            delta_ns=delta_ticks*n.TICK_PS*0.001
            diffs_ns.append(delta_ns)
            rng_delays_ns.append((q[0][1]-c["start"])*n.TICK_PS*0.001)
            detector_delays_ns.append((d[0]-c["start"])*n.TICK_PS*0.001)
            if delta_ticks<0:classification["earliest_rng_before_earliest_detector"]+=1
            elif delta_ticks>0:classification["earliest_detector_before_earliest_rng"]+=1
            else:classification["equal_earliest_tags"]+=1
            if len(q)!=1:classification["multi_rng_with_detector"]+=1

    for channel,tick,transfer in n.REC.iter_unpack(data):
        counts["total_raw_records"]+=1
        if channel not in n.CHANNELS:
            if channel>255:raise ValueError("INVALID_UNDOCUMENTED_CODE")
            unknown[channel]+=1
            continue
        if prev_known is not None and tick<prev_known:
            raise ValueError("NONMONOTONIC_KNOWN_PHYSICAL_EVENTS")
        prev_known=tick
        if channel==6:
            if state is not None:
                close_cycle(state)
            state={"start":tick,"rng":[],"detectors":[]}
            counts["sync_pulses"]+=1
            continue
        if state is None:
            before_sync+=1
            continue
        if channel==0:state["detectors"].append(tick)
        elif channel in (2,4):state["rng"].append((channel,tick))
        elif channel==5:counts["GPS_PPS_within_cycles"]+=1

    if state is not None:
        last_tail=len(state["rng"])+len(state["detectors"])
    counts["physical_event_records_before_first_sync"]=before_sync
    counts["incomplete_last_cycle_event_records_not_scored"]=last_tail
    def descriptor(x):
        return {"n":len(x),"median_ns":statistics.median(x) if x else None,
                "min_ns":min(x) if x else None,"max_ns":max(x) if x else None}
    return {
      "counts":dict(sorted(counts.items())),
      "all_completed_cycle_classes":dict(sorted(classification.items())),
      "unclassified_raw_channel_codes":{str(k):v for k,v in sorted(unknown.items())},
      "rng_minus_detector_first_event_ns":descriptor(diffs_ns),
      "rng_tag_minus_cycle_sync_ns":descriptor(rng_delays_ns),
      "detector_tag_minus_cycle_sync_ns":descriptor(detector_delays_ns),
      "interpretation":"Negative RNG-minus-detector means registered RNG-output pulse precedes detector click IN THAT SINGLE-STATION SYNC CYCLE. It is not the independent physical generation time of an intervention and does not imply transmission into the past.",
      "every_complete_cycle_included":True,
      "no_cross_station_clock_subtraction":True,
      "no_quantum_retrocausal_inference":True
    }


def run(path):
    result=[]
    for run_name,wing,filename in n.SAMPLES:
        if run_name!="2015-09-18-00_03":continue
        uri,blob,data,native=n.fetch(run_name,wing,filename)
        audit=sync_cycle_audit(data)
        result.append({"run":run_name,"wing":wing,
            "s3_url":uri,"zip_sha256":hashlib.sha256(blob).hexdigest(),
            "raw_sha256":hashlib.sha256(data).hexdigest(),
            "timing_audit":audit})
        print("NIST_010E_STATION "+json.dumps({
            "wing":wing,"raw_sha256":hashlib.sha256(data).hexdigest(),
            "timing_audit":audit},sort_keys=True),flush=True)
    if len(result)!=2:raise ValueError("MISSING_STATION_SOURCE")
    out={"schema":"janus.open010e.nist_single_station_cycle_timing.v1",
       "source":"REAL_NIST_2015_FIND_SYNC_CALIBRATION_DATA",
       "time_tick_ps":n.TICK_PS,
       "cycle_definition":"Half-open hardware sync-to-next-sync window, no adjustable acceptance gate",
       "original_NIST_reference":n.SOURCE_DOC,
       "no_posthoc_event_window":True,
       "samples":result,
       "cross_station_clock_offset_verified":False,
       "real_late_independent_physical_choice_verified":False,
       "retrospective_not_prospective":True,
       "retrocausality_proven":False}
    dest=Path(path)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(out,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",required=True)
    run(p.parse_args().output)
