#!/usr/bin/env python3
"""JANUS-010A: independently derived read-only replay of a REAL Bell experiment.

Source is TU Delft 2015 Hensen et al. spin entanglement data (not a simulated
quantum result). Exact original archive bytes validated by its published MD5.
This is a retrospective calibration of a no-signalling statistic, NOT an
experiment in which Bob's choice occurs after Alice's recorded outcome.

Expected 4,746 recorded rows; strict 245 trials as in the authors' specified
event-ready heralding windows. Do not retune windows after inspecting results.
No source data are redistributed in GitHub artifacts.
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

DATA_URL="https://data.4tu.nl/file/e8cf2991-3153-48ad-b67d-dfd7d7d97fd3/289c4850-6ed5-45a3-8b19-de8671f873a8"
ARCHIVE_MD5="342f29f8288c46575818acd2acebd535"
DATA_DOI="10.4121/uuid:6e19e9b2-4a2d-40b5-8dd3-a660bf3c0a31"
PAPER_DOI="10.1038/nature15759"
HERALD_C1_START_BY_CHANNEL=(5426350,5425700)
HERALD_WINDOW_WIDTH=52450
HERALD_C2_OFFSET=250000
A_B_READOUT_START=10620
READOUT_LENGTH=3700
INVALID_PAST=250
MAX_ARCHIVE_BYTES=800000
EXPECTED_RAW_ROWS=4746
EXPECTED_BELL_TRIALS=245


def sha256(x): return hashlib.sha256(x).hexdigest()


def canonical(obj):
    return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf8")


def fetch_archive():
    req=urllib.request.Request(DATA_URL,headers={"User-Agent":"JANUS-010A public academic data integrity check; research reproduction"})
    with urllib.request.urlopen(req,timeout=45) as h:
        raw=h.read(MAX_ARCHIVE_BYTES+1)
    if len(raw)>MAX_ARCHIVE_BYTES:
        raise ValueError("REFUSE_UNBOUNDED_ARCHIVE")
    if hashlib.md5(raw).hexdigest()!=ARCHIVE_MD5:
        raise ValueError("OFFICIAL_ARCHIVE_CHECKSUM_MISMATCH")
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError("OFFICIAL_ARCHIVE_IS_NOT_ZIP")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        matches=[name for name in z.namelist() if name.split("/")[-1]=="bell_open_data.txt"]
        if len(matches)!=1:
            raise ValueError("AUTHOR_DATA_FILE_NOT_UNIQUE")
        info=z.getinfo(matches[0])
        if info.file_size>5_000_000:
            raise ValueError("UNCOMPRESSED_FILE_TOO_BIG")
        text=z.read(matches[0]).decode("utf-8-sig")
    return raw,text


def parse_rows(raw_csv):
    out=[]
    for line_idx,row in enumerate(csv.reader(io.StringIO(raw_csv)),1):
        if not row:continue
        if len(row)!=17:
            raise ValueError(f"AUTHOR_ROW_{line_idx}_HAS_NOT_17_COLS")
        try:
            numbers=tuple(int(v.strip()) for v in row[1:])
        except ValueError:
            raise ValueError(f"AUTHOR_ROW_{line_idx}_NON_INTEGER_FIELDS") from None
        out.append((row[0].strip(),)+numbers)
    if len(out)!=EXPECTED_RAW_ROWS:
        raise ValueError(f"UNEXPECTED_AUTHOR_ROW_COUNT_{len(out)}")
    return out


def strict_predefined_herald(row):
    """Strict event-ready filter from published time windows, not fitted.

    Columns are 1-based relative to full CSV, with timestamp at column 0.
    This inclusion definition is a *historical calibration* only.
    """
    t1,ch1,t2,ch2=row[3],row[4],row[5],row[6]
    if ch1 not in (0,1) or ch2 not in (0,1):
        raise ValueError("INVALID_HERALD_CHANNEL")
    def in_window(t,ch,offset):
        start=HERALD_C1_START_BY_CHANNEL[ch]+offset
        return start<=t<start+HERALD_WINDOW_WIDTH
    if not (in_window(t1,ch1,0) and in_window(t2,ch2,HERALD_C2_OFFSET) and ch1!=ch2):
        return False
    ex_a,ex_b,inv_a,inv_b=row[13],row[14],row[15],row[16]
    return (ex_a==0 and ex_b==0 and
            (inv_a==0 or inv_a>INVALID_PAST) and
            (inv_b==0 or inv_b>INVALID_PAST))


def spin_outcome(time):
    if type(time) is not int:raise ValueError("NONINTEGER_DETECTOR_TIME")
    return 1 if A_B_READOUT_START<time<=A_B_READOUT_START+READOUT_LENGTH else -1


def select_events(rows):
    all_events=[]
    selected=[]
    for i,row in enumerate(rows):
        a,b=row[7],row[8]
        if a not in (0,1) or b not in (0,1):
            raise ValueError("INVALID_PHYSICAL_SETTING")
        e={"record_number":i,"setting_alice":a,"setting_bob":b,
           "outcome_alice":spin_outcome(row[11]),"outcome_bob":spin_outcome(row[12])}
        all_events.append(e)
        if strict_predefined_herald(row):
            selected.append(e)
    if len(selected)!=EXPECTED_BELL_TRIALS:
        raise ValueError(f"AUTHOR_BELL_SELECTION_COUNT_CHANGED_{len(selected)}")
    return all_events,selected


def log_choose(n,k):
    if k<0 or k>n:return float("-inf")
    return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)


def two_sided_fisher(tab):
    if len(tab)!=2 or any(len(x)!=2 or any(type(v) is not int or v<0 for v in x) for x in tab):
        raise ValueError("REQUIRE_NONNEGATIVE_INTEGER_2_BY_2")
    n0,n1=sum(tab[0]),sum(tab[1])
    if min(n0,n1)==0:raise ValueError("NO_SETTING_VARIATION")
    total=n0+n1
    positive=tab[0][1]+tab[1][1]
    xmin=max(0,positive-n1)
    xmax=min(positive,n0)
    obs=tab[0][1]
    norm=log_choose(total,n0)
    logs=[log_choose(positive,x)+log_choose(total-positive,n0-x)-norm for x in range(xmin,xmax+1)]
    observed_lp=logs[obs-xmin]
    center=max(logs)
    denominator=sum(math.exp(x-center) for x in logs)
    numerator=sum(math.exp(x-center) for x in logs if x<=observed_lp+1e-10)
    return min(1.0,numerator/denominator)


def correlations_and_signalling(rows):
    cells={(a,b):[] for a in (0,1) for b in (0,1)}
    for row in rows:
        cells[(row["setting_alice"],row["setting_bob"])].append(row)
    if min(len(x) for x in cells.values())==0:
        raise ValueError("EMPTY_CHSH_CELL")
    E={}
    counts={}
    for k,subset in cells.items():
        E[str(k[0])+str(k[1])]=sum(r["outcome_alice"]*r["outcome_bob"] for r in subset)/len(subset)
        counts[str(k[0])+str(k[1])]=len(subset)
    es=[E[t] for t in ("00","01","10","11")]
    signs=[(1,1,1,-1),(1,1,-1,1),(1,-1,1,1),(-1,1,1,1)]
    s=max(abs(sum(x*y for x,y in zip(es,pattern))) for pattern in signs)

    marginal=[]
    # These are four exploratory physical-data *calibration* checks, NOT
    # late-after-A settings; pre-specified familywise Holm adjustment.
    for observer in ("Alice","Bob"):
        for local in (0,1):
            tab=[[0,0],[0,0]]
            for row in rows:
                if observer=="Alice":
                    if row["setting_alice"]!=local:continue
                    remote_setting=row["setting_bob"]
                    result=row["outcome_alice"]
                else:
                    if row["setting_bob"]!=local:continue
                    remote_setting=row["setting_alice"]
                    result=row["outcome_bob"]
                tab[remote_setting][int(result==1)]+=1
            p=two_sided_fisher(tab)
            marginal.append({
                "observer":observer,"local_setting":local,
                "remote_setting_by_local_spin_minus_plus":tab,
                "p_two_sided_fisher":p,
                "difference_P_plus_remote1_minus0":tab[1][1]/sum(tab[1])-tab[0][1]/sum(tab[0])
            })
    # Holm family-wise correction, no p-value shopping across four checks.
    order=sorted(range(len(marginal)),key=lambda i:marginal[i]["p_two_sided_fisher"])
    previous=0.0
    for rank,i in enumerate(order):
        corrected=max(previous,min(1.0,(len(order)-rank)*marginal[i]["p_two_sided_fisher"]))
        marginal[i]["p_holm_familywise"]=corrected
        previous=corrected
    return {"CHSH_S":s,"CHSH_cell_counts":counts,"CHSH_E_correlators":E,
            "marginal_no_signalling_exploratory":marginal}


def run(output):
    raw,content=fetch_archive()
    rows=parse_rows(content)
    _,strict=select_events(rows)
    calibrated=correlations_and_signalling(strict)
    result={
        "schema":"janus.research.open010a.delft2015_real_bell_replay.v1",
        "status":"REAL_HISTORICAL_PHYSICAL_DATA_REPLAY_NOT_RETROCAUSAL_MEASUREMENT",
        "raw_source":"TU Delft 4TU.ResearchData: Hensen et al. 2015",
        "source_url":DATA_URL,
        "doi":DATA_DOI,
        "paper_doi":PAPER_DOI,
        "licensing":"4TU General Terms of Use; source ZIP not copied into artifact",
        "actual_archive_bytes":len(raw),
        "actual_archive_md5":hashlib.md5(raw).hexdigest(),
        "actual_archive_sha256":sha256(raw),
        "original_events_read":len(rows),
        "author_defined_event_ready_trials":len(strict),
        "strict_gate":"Published Bell-trial time windows and event veto fixed before reading data",
        "historical_public_data_not_newly_measured":True,
        "bob_setting_generated_after_alice_outcome_verified":False,
        "physical_outcomes":True,
        "predefined_statistical_calibration":calibrated,
        "external_independent_blinded_precommit":False,
        "retrocausal_signal_observed":False,
        "retrocausality_proven":False,
        "note":"This is a real past Bell measurement, not the future late-setting 010 experiment. Bell violation and cross-wing no-signalling are distinct from retrocausality."
    }
    destination=Path(output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf8") as out:
        out.write(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n")
        out.flush()
        os.fsync(out.fileno())
    print("JANUS_REAL_BELL_010A "+json.dumps({
        "source_sha256":result["actual_archive_sha256"],
        "n_raw":len(rows),"n_strict":len(strict),
        "S_CHSH":calibrated["CHSH_S"],
        "no_signalling_tests":calibrated["marginal_no_signalling_exploratory"],
        "retrocausality_proven":False},sort_keys=True),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    args=p.parse_args()
    run(args.output)
