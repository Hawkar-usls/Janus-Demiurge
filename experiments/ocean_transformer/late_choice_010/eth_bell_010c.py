#!/usr/bin/env python3
"""JANUS 010C: independent audit of ETH Zurich 2023 real superconducting Bell outcomes.

Original experiment: Storz et al., Nature 617, 265 (2023).
This is a RETROSPECTIVE ANALYSIS of four publicly recorded trial columns,
not an early-outcome/physically-late-choice experiment. Does not measure or
claim retrocausality. No original data redistributed.

Uses only Python standard library and actual source checksum, with exact
pre-specified all-row inclusion. No manual physics parameters or heuristics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import urllib.request
import zipfile
from pathlib import Path

SRC="https://www.research-collection.ethz.ch/server/api/core/bitstreams/88466bab-6aba-46e8-bd18-9a62c2c45ea5/content"
DOI="10.3929/ethz-b-000624026"
PAPER="10.1038/s41586-023-05885-0"
EXPECTED_MD5="aa308b354b78d4ba4d8ef5a5457dae1a"
EXPECTED_N=1048576
ZIP_LIMIT=4000000
TEXT_LIMIT=45000000


def source():
    req=urllib.request.Request(SRC,headers={"User-Agent":"JANUS-010C/1.0 public source integrity audit"})
    with urllib.request.urlopen(req,timeout=50) as h:
        blob=h.read(ZIP_LIMIT+1)
    if len(blob)>ZIP_LIMIT:raise ValueError("ZIP_TOO_BIG")
    if hashlib.md5(blob).hexdigest()!=EXPECTED_MD5:
        raise ValueError("ORIGINAL_ETH_SOURCE_MD5_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=[n for n in z.namelist() if n.endswith("/main_dataset_all_events.txt") or n=="main_dataset_all_events.txt"]
        if len(names)!=1:raise ValueError("MISSING_UNIQUE_ETH_MAIN_DATASET")
        info=z.getinfo(names[0])
        if info.file_size>TEXT_LIMIT:raise ValueError("DECOMPRESSION_LIMIT")
        with z.open(info,"r") as infile:
            data=infile.read(TEXT_LIMIT+1)
        if len(data)>TEXT_LIMIT:raise ValueError("DECOMPRESSION_LIMIT")
    return blob,data


def audit_rows(data):
    counts={(a,b):{(A,B):0 for A in (-1,1) for B in (-1,1)}
            for a in (0,1) for b in (0,1)}
    n=0
    for index,row in enumerate(csv.reader(io.StringIO(data.decode("utf-8-sig")))):
        if index<2:continue  # original repository contains exactly two headers
        if not row:continue
        if len(row)!=4:raise ValueError("NON_FOUR_COLUMN_ROW_"+str(index+1))
        try:
            a,A,b,B=(int(s.strip()) for s in row)
        except ValueError:
            raise ValueError("NON_INTEGER_ROW_"+str(index+1)) from None
        if a not in (0,1) or b not in (0,1) or A not in (-1,1) or B not in (-1,1):
            raise ValueError("INVALID_SETTING_OR_OUTCOME_"+str(index+1))
        counts[(a,b)][(A,B)]+=1
        n+=1
    if n!=EXPECTED_N:raise ValueError("ETH_TRIAL_COUNT_CHANGED_"+str(n))
    return counts,n


def two_sided_normal_p(z):
    return math.erfc(abs(z)/math.sqrt(2))


def marginals(counts):
    """Four local-by-remote two-proportion tests, with Holm familywise correction.
    Uses large-N asymptotic score z, not tiny-sample Fisher; reports n and null.
    """
    checks=[]
    for wing in ("Alice","Bob"):
        for own_setting in (0,1):
            sampled=[]
            for remote in (0,1):
                subset=[]
                for (a,b),d in counts.items():
                    if (a if wing=="Alice" else b)!=own_setting:
                        continue
                    if (b if wing=="Alice" else a)!=remote:
                        continue
                    subset.extend((local,n) for (A,B),n in d.items() for local in [A if wing=="Alice" else B])
                trials=sum(n for _,n in subset)
                successes=sum(n for local,n in subset if local==1)
                sampled.append((successes,trials))
            (k0,n0),(k1,n1)=sampled
            if min(n0,n1)<=0:raise ValueError("UNTESTABLE_MARGINAL")
            p=(k0+k1)/(n0+n1)
            se=math.sqrt(p*(1-p)*(1/n0+1/n1))
            if se==0:raise ValueError("ZERO_VARIANCE_MARGINAL")
            delta=k1/n1-k0/n0
            z=delta/se
            checks.append({"wing":wing,"own_setting":own_setting,
                           "remote0":{"positive_outcomes":k0,"n":n0},
                           "remote1":{"positive_outcomes":k1,"n":n1},
                           "delta_p_plus_remote1_minus0":delta,
                           "z_score":z,"p_two_sided_normal":two_sided_normal_p(z)})
    order=sorted(range(len(checks)),key=lambda i:checks[i]["p_two_sided_normal"])
    prev=0.0
    for j,i in enumerate(order):
        adjusted=max(prev,min(1.0,(len(checks)-j)*checks[i]["p_two_sided_normal"]))
        checks[i]["p_holm_familywise"]=adjusted
        prev=adjusted
    return checks


def summarize(counts,n):
    cell_n={}
    E={}
    for a in (0,1):
        for b in (0,1):
            d=counts[(a,b)]
            m=sum(d.values())
            if not m:raise ValueError("EMPTY_BELL_SETTING_CELL")
            name=str(a)+str(b)
            cell_n[name]=m
            E[name]=sum(A*B*num for (A,B),num in d.items())/m
    correlators=[E[name] for name in ("00","01","10","11")]
    # Conventional CHSH orientations, abs; no choosing outcome-dependent subgroup.
    patterns=((1,1,1,-1),(1,1,-1,1),(1,-1,1,1),(-1,1,1,1))
    orientations=[abs(sum(s*e for s,e in zip(pat,correlators))) for pat in patterns]
    best=max(orientations)
    # With each individual binary product ±1, the independent-cell plug-in SE.
    chsh_se=math.sqrt(sum((1-E[k]**2)/cell_n[k] for k in ("00","01","10","11")))
    return {"n_trials":n,"CHSH_S_max_four_orientations":best,
            "CHSH_orientations_abs":orientations,
            "CHSH_E":E,"CHSH_setting_cell_counts":cell_n,
            "CHSH_gaussian_plug_in_standard_error":chsh_se,
            "CHSH_local_hidden_variable_bound":2.0,
            "marginal_no_signalling_tests":marginals(counts),
            "setting_outcome_counts":{str(a)+str(b):{str(A)+","+str(B):n
                for (A,B),n in d.items()} for (a,b),d in counts.items()}}


def run(destination):
    blob,data=source()
    counts,n=audit_rows(data)
    analysis=summarize(counts,n)
    record={"schema":"janus.open010c.eth2023_archival_physical_replay.v1",
            "source_paper_DOI":PAPER,"source_archive_DOI":DOI,
            "original_archive_url":SRC,
            "original_MD5_verified":EXPECTED_MD5,
            "raw_archive_sha256":hashlib.sha256(blob).hexdigest(),
            "dataset_content_sha256":hashlib.sha256(data).hexdigest(),
            "license":"ETH Research Collection CC BY 4.0; only aggregate counts distributed",
            "source_kind":"REAL_HISTORICAL_SUPERCONDUCTING_QUBIT_BELL_TEST",
            "all_rows_included":True,
            "manual_postselection":False,
            "physical_qrng_recorded_in_published_4col_file":False,
            "per_event_physical_timestamp_in_published_4col_file":False,
            "independent_late_setting_after_earlier_A_verified":False,
            "results":analysis,
            "causal_warning":"Bell violation does not demonstrate retrocausal signalling or causation by physically later choice. Source has only four columns and no timing metadata.",
            "retrocausality_proven":False}
    out=Path(destination)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("x",encoding="utf8") as h:
        json.dump(record,h,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
        h.write("\n")
        h.flush()
        os.fsync(h.fileno())
    print("JANUS_ETH010C "+json.dumps({"source_sha256":record["raw_archive_sha256"],
           "n":n,"CHSH_S":analysis["CHSH_S_max_four_orientations"],
           "CHSH_SE":analysis["CHSH_gaussian_plug_in_standard_error"],
           "marginal_tests":analysis["marginal_no_signalling_tests"],
           "retrocausality_proven":False},sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    run(p.parse_args().output)
