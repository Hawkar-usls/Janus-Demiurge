#!/usr/bin/env python3
"""JANUS-010N: fresh cross-lab source prospective-in-code archival replay.

Frozen hypothesis and April->June split in original SHA
ee8ff5fdd4ae9844cf4e4fc94c52c07cdabd64c6 before inspecting either ZIP.
Archive April inspected for file format; June untouched until this code and
unit tests committed. Historical 2016 events are NOT prospective physics.

SOURCE SELECTION WARNING: author *_pairs.csv has ONLY VALID matched atom
events; pair selection was by original +/-100 ms PC clocks and apparatus
exclusion flags. All raw attempt rows are inventoried, but paired events
cannot be called the unconditional all-trials sample. All scores and p values
therefore exploratory and physically retrocausal inference PROHIBITED.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import urllib.request
import zipfile

ZENODO="https://zenodo.org/records/22936124/files/"
SOURCES={
 "april":{"filename":"Bell_2016-04-15.zip",
          "md5":"53544819317d4dcfbe5c63e039a8aa38"},
 "june":{"filename":"Bell_2016-06-14.zip",
         "md5":"030ce1a0c6c6cc7f1107e1cd608cce77"}
}
SIZE_CAP=2_000_000
DECOMPRESS_CAP=60_000_000
FAMILY_ALPHA=0.001
SAMPLE_EFFECT_RELEVANCE=0.01

def acquire(role):
    spec=SOURCES[role]
    url=ZENODO+spec["filename"]+"?download=1"
    request=urllib.request.Request(url,headers={"User-Agent":"JANUS-010N source-frozen atomic Bell audit"})
    with urllib.request.urlopen(request,timeout=60) as r:
        raw=r.read(SIZE_CAP+1)
    if len(raw)>SIZE_CAP:raise ValueError("SOURCE_ZIP_EXCEEDS_CAP")
    if hashlib.md5(raw).hexdigest()!=spec["md5"]:raise ValueError("ZENODO_PINNED_MD5_MISMATCH")
    return {"url":url,"md5":spec["md5"],"sha256":hashlib.sha256(raw).hexdigest(),
            "zip_bytes":len(raw)},raw

def parse_binary(s,label):
    if s.strip() not in ("0","1"):raise ValueError("INVALID_OR_MISSING_"+label)
    return int(s.strip())

def lab_rows(data,wing):
    lines=list(csv.reader(io.StringIO(data.decode("utf-8-sig")),delimiter=";"))
    if not lines or "setting" not in lines[0][1].lower() or "result" not in lines[0][2].lower():
        raise ValueError("LAB_HEADER_UNKNOWN")
    result=[]
    for i,row in enumerate(lines[1:]):
        if not row or not any(x.strip() for x in row):
            raise ValueError("EMPTY_ATTEMPT_RECORD")
        if len(row)<6:raise ValueError("LAB_FIELDS_TOO_SHORT")
        info={"row_index":i,"raw_fields_count":len(row)}
        info["event_utc_ms"]=int(row[0].strip())
        info["setting"]=parse_binary(row[1],"LAB_SETTING")
        info["result"]=parse_binary(row[2],"LAB_RESULT")
        info["local_tick"]=int(row[3].strip())
        if wing==1:
            info["herald_state"]=row[4].strip()
            info["excluded_flag"]=row[5].strip().lower()
            info["reason"]=";".join(row[6:]).strip()
        else:
            info["excluded_flag"]=row[4].strip().lower()
            info["reason"]=";".join(row[5:]).strip()
        if info["excluded_flag"] not in ("yes","no"):
            raise ValueError("UNKNOWN_AUTHOR_EXCLUSION_FLAG")
        result.append(info)
    if not result:raise ValueError("EMPTY_ORIGINAL_LAB_FILE")
    return result

def author_pairs(data,first,second):
    lines=list(csv.reader(io.StringIO(data.decode("utf-8-sig")),delimiter="\t"))
    if not lines or len(lines[0])!=8:
        raise ValueError("PAIRS_SOURCE_HEADER_UNKNOWN")
    records=[]
    used_first=set();used_second=set()
    for row in lines[1:]:
        if not row or not any(x.strip() for x in row):
            raise ValueError("EMPTY_PAIR_RECORD")
        if len(row)!=8:raise ValueError("PAIR_ROW_NOT_8_FIELDS")
        try:i=int(row[6]);j=int(row[7]);utc=int(row[0])
        except ValueError:raise ValueError("PAIR_INDEX_PARSE_FAILED") from None
        if i<0 or i>=len(first) or j<0 or j>=len(second):
            raise ValueError("PAIR_INDEX_OUT_OF_ORIGINAL_LAB_RANGE")
        if i in used_first or j in used_second:raise ValueError("DUPLICATE_ORIGINAL_LAB_PAIR")
        used_first.add(i);used_second.add(j)
        a=first[i];b=second[j]
        if a["excluded_flag"]!="no" or b["excluded_flag"]!="no":
            raise ValueError("AUTHOR_PAIR_MARKED_EXCLUDED")
        if a["event_utc_ms"]!=utc or abs(a["event_utc_ms"]-b["event_utc_ms"])>100:
            raise ValueError("AUTHOR_PAIR_TIME_OUTSIDE_PREDECLARED_100MS")
        if tuple(parse_binary(row[k],"PAIRS") for k in (2,3,4,5))!=(
           a["setting"],a["result"],b["setting"],b["result"]):
            raise ValueError("PAIR_OUTCOME_SETTING_DIFFERS_FROM_ORIGINAL_RAW")
        if row[1].strip()!=a["herald_state"]:
            raise ValueError("PAIR_HERALD_STATE_DIFFERS_FROM_LAB")
        records.append((a["setting"],a["result"],b["setting"],b["result"]))
    if not records:raise ValueError("NO_ORIGINAL_VALID_PAIR_ROWS")
    return records

def extract_zip(blob):
    raw_all=[];all_attempts={"Alice":0,"Bob":0}
    excluded={"Alice":0,"Bob":0}
    groups={}
    entry_hashes={}
    total=0
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.infolist():
            if member.is_dir():continue
            if member.filename.startswith("/") or ".." in Path(member.filename).parts:
                raise ValueError("UNSAFE_ORIGINAL_ZIP_PATH")
            total+=member.file_size
            if total>DECOMPRESS_CAP:raise ValueError("SOURCE_DECOMPRESSED_SIZE_CAP")
            filename=Path(member.filename).name
            payload=z.read(member)
            entry_hashes[filename]=hashlib.sha256(payload).hexdigest()
            if filename.lower()=="readme.txt":continue
            suffix=None
            for ending in ("_lab_1.csv","_lab_2.csv","_pairs.csv"):
                if filename.endswith(ending):
                    suffix=ending;break
            if suffix is None:raise ValueError("UNKNOWN_ORIGINAL_ARCHIVE_ENTRY")
            group=filename[:-len(suffix)]
            content=groups.setdefault(group,{})
            if suffix in content:raise ValueError("DUPLICATE_GROUP_FILE")
            content[suffix]=payload
    if not groups:raise ValueError("NO_EXPERIMENT_GROUPS")
    per_group=[]
    for name,g in sorted(groups.items()):
        if set(g)!={"_lab_1.csv","_lab_2.csv","_pairs.csv"}:
            raise ValueError("INCOMPLETE_EVENT_READY_SOURCE_TRIPLET")
        a=lab_rows(g["_lab_1.csv"],1);b=lab_rows(g["_lab_2.csv"],2)
        matched=author_pairs(g["_pairs.csv"],a,b)
        raw_all.extend(matched)
        for wing,arr in (("Alice",a),("Bob",b)):
            all_attempts[wing]+=len(arr)
            excluded[wing]+=sum(x["excluded_flag"]=="yes" for x in arr)
        per_group.append({"source_group":name,"Alice_original_attempts":len(a),
              "Bob_original_attempts":len(b),"author_valid_pairs":len(matched),
              "Alice_excluded_attempts":sum(x["excluded_flag"]=="yes" for x in a),
              "Bob_excluded_attempts":sum(x["excluded_flag"]=="yes" for x in b)})
    return {"all_attempts":all_attempts,"author_excluded":excluded,
            "source_groups":per_group,"entry_sha256":entry_hashes,
            "author_valid_pairs":len(raw_all),
            "unmatched_or_excluded_events_cannot_be_reconstructed_as_joint_trials":True},raw_all

def empty():
    return {w:{str(a):{str(b):{"n":0,"k":0} for b in (0,1)} for a in (0,1)} for w in ("Alice","Bob")}

def tables(records):
    base=empty();selected=empty()
    for a,A,b,B in records:
        for name,own,remote,positive,other in (
           ("Alice",a,b,A,B),("Bob",b,a,B,A)):
            x=base[name][str(own)][str(remote)]
            x["n"]+=1;x["k"]+=positive
            if other==1:
                y=selected[name][str(own)][str(remote)]
                y["n"]+=1;y["k"]+=positive
    return base,selected

def beta(k,n):
    return (k+.5)/(n+1)

def ll(k,n,p):
    if n<0 or k<0 or k>n:raise ValueError("INVALID_COUNT")
    return k*math.log(p)+(n-k)*math.log1p(-p)

def comparison(cal,test):
    out={}
    for wing in ("Alice","Bob"):
        l0=l1=0.0;nt=0
        for own in (0,1):
            c=[cal[wing][str(own)][str(r)] for r in (0,1)]
            n=sum(z["n"] for z in c);k=sum(z["k"] for z in c)
            if not n or any(z["n"]==0 for z in c):
                raise ValueError("CALIBRATION_EMPTY_SETTING_CELL")
            pred0=beta(k,n)
            for remote in (0,1):
                row=test[wing][str(own)][str(remote)]
                if not row["n"]:raise ValueError("VALIDATION_EMPTY_SETTING_CELL")
                pred1=beta(c[remote]["k"],c[remote]["n"])
                l0+=ll(row["k"],row["n"],pred0)
                l1+=ll(row["k"],row["n"],pred1)
                nt+=row["n"]
        out[wing]={"n_author_valid_heldout_pairs":nt,
           "M0_out_of_run_log_likelihood":l0,
           "Mjanus_out_of_run_log_likelihood":l1,
           "Mjanus_minus_M0_bits_per_pair":(l1-l0)/(nt*math.log(2)),
           "purely_descriptive_selected_trial_predictive_comparison":True}
    return out

def contrast(table,wing,own):
    x=table[wing][str(own)]["0"];y=table[wing][str(own)]["1"]
    n0=x["n"];n1=y["n"]
    if min(n0,n1)==0:return None
    delta=y["k"]/n1-x["k"]/n0
    p=(x["k"]+y["k"])/(n0+n1)
    se=math.sqrt(p*(1-p)*(1/n0+1/n1))
    z=delta/se if se else (0 if delta==0 else float("inf"))
    return {"wing":wing,"own_setting":own,"remote0_n":n0,"remote1_n":n1,
      "delta_Pplus_remote1_minus0":delta,
      "two_sided_binomial_normal_p_descriptive":math.erfc(abs(z)/math.sqrt(2)),
      "author_selected_valid_pairs_only":True}

def holm(items):
    eligible=[x for x in items if x is not None]
    if len(eligible)!=4:
        raise ValueError("REQUIRE_FOUR_FIXED_COMPARISONS")
    ordered=sorted(eligible,key=lambda x:x["two_sided_binomial_normal_p_descriptive"])
    prev=0.
    for rank,x in enumerate(ordered):
        prev=max(prev,min(1.,(4-rank)*x["two_sided_binomial_normal_p_descriptive"]))
        x["holm_p_descriptive"]=prev
        x["not_primary_unconditional_physical_test"]=True
    return items

def run(output):
    reports={}
    outcomes={}
    for role in ("april","june"):
        original,blob=acquire(role)
        inventory,rows=extract_zip(blob)
        reports[role]={"original_archive":original,
                "source_inventory":inventory,
                "physical_herald_trials_are_NOT_complete_joint_source_table":True}
        outcomes[role]=rows
        print("JANUS_010N_SOURCE "+json.dumps({"role":role,
          "original_source_sha256":original["sha256"],
          "author_valid_pairs":len(rows),
          "all_attempts":inventory["all_attempts"],
          "author_excluded":inventory["author_excluded"]},sort_keys=True),flush=True)
    cal,_=tables(outcomes["april"])
    test,post=tables(outcomes["june"])
    scores=comparison(cal,test)
    contrasts=holm([contrast(test,wing,own) for wing in ("Alice","Bob") for own in (0,1)])
    for x in contrasts:
        other=contrast(post,x["wing"],x["own_setting"])
        x["opposite_outcome_plus_postselection_control"]={
            "selected_n":sum(post[x["wing"]][str(x["own_setting"])][str(r)]["n"] for r in (0,1)),
            "delta_selected":other["delta_Pplus_remote1_minus0"] if other is not None else None,
            "excluded_from_primary_and_training":True}
    rec={
      "schema":"janus.physical010n.rosenfeld_atomic_bell_source_validation.v1",
      "predata_frozen_commit":"ee8ff5fdd4ae9844cf4e4fc94c52c07cdabd64c6",
      "independent_atomic_laboratory":True,
      "source_2016_historical_not_prospective":True,
      "original_source_DOI":"10.5281/zenodo.22936124",
      "source_paper_DOI":"10.1103/PhysRevLett.119.010402",
      "original_archives":reports,
      "validation_out_of_run":True,
      "entire_June_valid_pair_file_used_for_descriptive_scoring":True,
      "original_full_all_attempts_included_in_source_inventory":True,
      "original_author_100ms_matching_and_hardware_maintenance_exclusions":True,
      "predeclared_all_heralded_trials_joint_table_available":False,
      "PRIMARY_UNCONDITIONAL_CAUSAL_TEST_STATUS":"INELIGIBLE_PRIMARY_DATA_ONLY",
      "M0_vs_Mjanus_descriptive_valid_pair_prediction":scores,
      "four_fixed_descriptive_author_valid_pair_marginals":contrasts,
      "postselection_results_are_exploratory_only":True,
      "no_source_derived_absolute_clock_offset":True,
      "true_timelike_independent_late_choice_after_committed_A":False,
      "no_physical_retrocausal_channel_proven":True,
      "science_status":"NEW_INDEPENDENT_LAB_HISTORICAL_RECORDS_SCORE_ONLY_NOT_CAUSAL_ADMISSION"
    }
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(rec,f,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("JANUS_010N_RESULT "+json.dumps({
      "source_lab":"LMU Munich 2016 atoms",
      "validation_N_author_valid_pairs":len(outcomes["june"]),
      "prediction_bits":{w:round(x["Mjanus_minus_M0_bits_per_pair"],12) for w,x in scores.items()},
      "contrasts":[{"wing":x["wing"],"setting":x["own_setting"],
             "delta":x["delta_Pplus_remote1_minus0"],"holm":x["holm_p_descriptive"],
             "after_selection":x["opposite_outcome_plus_postselection_control"]["delta_selected"]} for x in contrasts],
      "primary_status":"INELIGIBLE_PRIMARY_DATA_ONLY",
      "retrocausality":False},sort_keys=True),flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    run(parser.parse_args().output)
