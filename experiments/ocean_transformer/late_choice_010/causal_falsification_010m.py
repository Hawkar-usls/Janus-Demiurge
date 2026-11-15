#!/usr/bin/env python3
"""JANUS-PHYSICAL-010M: falsifiable three-model retrospective ETH Bell check.

Models:
M0 (no signalling): local binary outcome depends only on its OWN setting.
Mpost: illustrates outcome-conditioning collider/selection, NEVER primary.
Mjanus: local outcome may additionally depend on REMOTE setting. Free later
choice is NOT verified in 2023 ETH data; Mjanus is only a statistical proxy.

Train/heldout: first 2^19 chronological rows, last 2^19 rows, frozen here
before this 010M replay. NOTE: ETH records have already been studied by
JANUS-010C, so this is NOT fresh independent blinded physical validation.
No temporal/casual conclusions; source has NO event timestamps.
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

SRC=("https://www.research-collection.ethz.ch/server/api/core/bitstreams/"
     "88466bab-6aba-46e8-bd18-9a62c2c45ea5/content")
DOI="10.3929/ethz-b-000624026"
PAPER="10.1038/s41586-023-05885-0"
ZIP_SHA256="2d39d1b6898480d3de0134e2d55ac3faee87af32c8db5bc6fdf6fa6997296909"
ZIP_MD5="aa308b354b78d4ba4d8ef5a5457dae1a"
EXPECTED_N=1_048_576
HALF_N=524_288
BLOCK_SIZE=4096
ALPHA_FAMILY=0.001
HYPOTHESIS_DELTA=0.01
ZIP_CAP=4_000_000
TEXT_CAP=45_000_000
WINGS=("Alice","Bob")
OWN=(0,1)
REMOTE=(0,1)

def get_original():
    req=urllib.request.Request(SRC,headers={"User-Agent":"JANUS-010M real-data causal-models preread"})
    with urllib.request.urlopen(req,timeout=60) as f:
        blob=f.read(ZIP_CAP+1)
    if len(blob)>ZIP_CAP:raise ValueError("ETH_SOURCE_TOO_LARGE")
    if hashlib.md5(blob).hexdigest()!=ZIP_MD5 or hashlib.sha256(blob).hexdigest()!=ZIP_SHA256:
        raise ValueError("ETH_SOURCE_HASH_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        entries=[x for x in z.infolist()
                 if x.filename.endswith("/main_dataset_all_events.txt")
                 or x.filename=="main_dataset_all_events.txt"]
        if len(entries)!=1:raise ValueError("ETH_MAIN_FILE_NOT_UNIQUE")
        if entries[0].file_size>TEXT_CAP:raise ValueError("SOURCE_UNCOMPRESSED_CAP")
        with z.open(entries[0]) as f: raw=f.read(TEXT_CAP+1)
        if len(raw)>TEXT_CAP:raise ValueError("SOURCE_UNCOMPRESSED_CAP")
    return blob,raw

def empty():
    return {w:{str(o):{str(r):{"n":0,"plus":0} for r in REMOTE} for o in OWN} for w in WINGS}

def add(table,w,o,r,positive):
    c=table[w][str(o)][str(r)]
    c["n"]+=1
    c["plus"]+=int(positive)

def parse(raw,expected_n=EXPECTED_N,block_size=BLOCK_SIZE):
    if type(expected_n) is not int or expected_n<=0 or expected_n%2:
        raise ValueError("EXPECTED_N_MUST_BE_POSITIVE_EVEN")
    half=expected_n//2
    if not (block_size>0 and half%block_size==0):
        raise ValueError("UNEVEN_FIXED_VALIDATION_BLOCKS")
    train=empty(); validation=empty(); post=empty()
    blocks=[empty() for _ in range(half//block_size)]
    trial=0
    for row_number,line in enumerate(csv.reader(io.StringIO(raw.decode("utf-8-sig"))),1):
        if row_number<=2:continue
        if not line:continue
        if len(line)!=4:raise ValueError("EXPECTED_EXACTLY_FOUR_COLS")
        try:a,A,b,B=[int(x.strip()) for x in line]
        except ValueError:raise ValueError("NON_INTEGER_ROW") from None
        if a not in OWN or b not in REMOTE or A not in (-1,1) or B not in (-1,1):
            raise ValueError("INVALID_QUBIT_SETTING_OR_OUTCOME")
        if trial>=expected_n:raise ValueError("MORE_ROWS_THAN_EXPECTED")
        t=train if trial<half else validation
        add(t,"Alice",a,b,A==1)
        add(t,"Bob",b,a,B==1)
        if trial>=half:
            idx=(trial-half)//block_size
            add(blocks[idx],"Alice",a,b,A==1)
            add(blocks[idx],"Bob",b,a,B==1)
            # Late-outcome-based selection is shown only as a FALSE POSITIVE control.
            if B==1:add(post,"Alice",a,b,A==1)
            if A==1:add(post,"Bob",b,a,B==1)
        trial+=1
    if trial!=expected_n:raise ValueError("ETH_TRIAL_COUNT_MISMATCH")
    return train,validation,post,blocks,trial

def sample(table,w,o,r):
    return table[w][str(o)][str(r)]

def delta(table,w,o):
    z=sample(table,w,o,0);y=sample(table,w,o,1)
    if z["n"]==0 or y["n"]==0:raise ValueError("EMPTY_REMOTE_SETTING_CELL")
    return y["plus"]/y["n"]-z["plus"]/z["n"]

def score_test(table,w,o):
    a=sample(table,w,o,0);b=sample(table,w,o,1)
    n0=a["n"];n1=b["n"]
    if not n0 or not n1:raise ValueError("EMPTY_CELL_FOR_TEST")
    k0=a["plus"];k1=b["plus"]
    p=(k0+k1)/(n0+n1)
    d=k1/n1-k0/n0
    se=math.sqrt(p*(1-p)*(1/n0+1/n1))
    if se==0:
        z=0.0 if d==0 else float("inf")
    else:z=d/se
    return {"wing":w,"own_setting":o,
            "remote0":{"n":n0,"positive":k0},
            "remote1":{"n":n1,"positive":k1},
            "delta_plus_remote1_minus0":d,
            "score_z_asymptotic":z if math.isfinite(z) else "infinity",
            "iid_approx_two_sided_p":math.erfc(abs(z)/math.sqrt(2)),
            "assumptions":"Large-n independent-trial score approximation; serial memory, drift and RNG independence cannot be certified from 4 columns"}

def holm(checks):
    order=sorted(range(len(checks)),key=lambda i:checks[i]["iid_approx_two_sided_p"])
    previous=0.0
    for rank,i in enumerate(order):
        previous=max(previous,min(1.0,(len(checks)-rank)*checks[i]["iid_approx_two_sided_p"]))
        checks[i]["p_holm_4_tests"]=previous
        checks[i]["passes_familywise_alpha_0_001"]=previous<ALPHA_FAMILY
    return checks

def block_control(blocks,w,o):
    xs=[]
    for b in blocks:
        try:xs.append(delta(b,w,o))
        except ValueError:continue
    if len(xs)<10:return {"n_blocks":len(xs),"insufficient_blocks":True}
    mean=sum(xs)/len(xs)
    sd=math.sqrt(sum((x-mean)**2 for x in xs)/(len(xs)-1))
    z=mean/(sd/math.sqrt(len(xs))) if sd else (0.0 if mean==0 else float("inf"))
    return {"n_blocks":len(xs),"mean_block_delta":mean,
            "block_sd":sd,
            "block_z_normal_descriptive":z if math.isfinite(z) else "infinity",
            "block_normal_p_heuristic":math.erfc(abs(z)/math.sqrt(2)),
            "limitations":"Nonoverlapping 4096-event blocks, no proof of independent blocks; normal approximation descriptive, not confirmatory"}

def loglik(cell,p):
    if p<=0 or p>=1:raise ValueError("PREDICTION_MUST_BE_INTERIOR")
    return cell["plus"]*math.log(p)+(cell["n"]-cell["plus"])*math.log1p(-p)

def beta_smooth(k,n):
    return (k+.5)/(n+1)

def predict(train,validation):
    result={}
    for w in WINGS:
        base_ll=0.0;janus_ll=0.0;n=0
        for o in OWN:
            train_cells=[sample(train,w,o,r) for r in REMOTE]
            k_total=sum(c["plus"] for c in train_cells)
            n_total=sum(c["n"] for c in train_cells)
            if any(c["n"]==0 for c in train_cells):raise ValueError("TRAINING_SETTING_EMPTY")
            p0=beta_smooth(k_total,n_total)
            for r in REMOTE:
                c=sample(validation,w,o,r)
                if not c["n"]:raise ValueError("HOLDOUT_SETTING_EMPTY")
                base_ll+=loglik(c,p0)
                p1=beta_smooth(train_cells[r]["plus"],train_cells[r]["n"])
                janus_ll+=loglik(c,p1)
                n+=c["n"]
        result[w]={"heldout_n":n,
                   "M0_no_signalling_log_likelihood":base_ll,
                   "Mjanus_remote_conditional_log_likelihood":janus_ll,
                   "Mjanus_minus_M0_log_likelihood":janus_ll-base_ll,
                   "Mjanus_minus_M0_bits_per_event":(janus_ll-base_ll)/(n*math.log(2)),
                   "predictive_improvement_is_proof_of_retrocausality":False}
    return result

def physics_proof():
    return {
      "M0_no_signalling":
        "For any bipartite density matrix rho_AB and trace-preserving local CPTP map E_C on B, Tr_B[(I tensor E_C)(rho_AB)] = Tr_B[rho_AB]. Hence Alice's unconditional outcome distribution for each fixed Alice setting a is independent of C, assuming no communication and ordinary quantum operations.",
      "Mpost_collider":
        "Take A and C as independent fair bits and define B=A XOR C. Then P(A=1|C=0)=P(A=1|C=1)=1/2, yet conditioning on B=0 forces A=C and creates perfect predictive association without retro-signalling. This is a synthetic causal counterexample, not a quantum historical measurement.",
      "Mjanus_proxy":
        "A descriptive model permits P(A=+1|a,b=1) != P(A=+1|a,b=0). For true retrocausality, b must be a genuinely late independent physical intervention relative to a committed A. The ETH Bell source does not establish such timing, so descriptive preference or a low p-value is not physical evidence.",
      "null":"Four local own-setting-stratified no-signalling contrasts: Alice for a=0,1 and Bob for b=0,1.",
      "family_alpha":ALPHA_FAMILY,
      "Holm_correction":"Across four two-sided score approximations, no optional selection of the winning contrast.",
      "JANUS_predeclared_exploratory_effect_abs_delta":HYPOTHESIS_DELTA,
      "source_prior_exposure_warning":"Prior JANUS-010C already examined all ETH outcomes; the 010M chronological split is a reproducibility control, NOT truly never-seen/independent blind data."
    }

def run(output):
    blob,raw=get_original()
    train,validation,post,blocks,n=parse(raw)
    tests=holm([score_test(validation,w,o) for w in WINGS for o in OWN])
    for check in tests:
        check["block_control"]=block_control(blocks,check["wing"],check["own_setting"])
        w,o=check["wing"],check["own_setting"]
        try:
            check["postselection_only_false_signal_diagnostic"]={
              "select_remote_outcome_plus":True,
              "selected_n":sum(sample(post,w,o,r)["n"] for r in REMOTE),
              "delta_conditioned_on_other_wing_outcome":delta(post,w,o),
              "used_in_primary":False
            }
        except ValueError:
            check["postselection_only_false_signal_diagnostic"]={"insufficient_selected_cells":True,"used_in_primary":False}
    predictions=predict(train,validation)
    record={
      "schema":"janus.physical010m.independent_causal_falsification_archival_v1",
      "original_archive_url":SRC,"original_data_doi":DOI,"paper_doi":PAPER,
      "original_zip_sha256_verified":ZIP_SHA256,
      "original_zip_md5_verified":ZIP_MD5,
      "uncompressed_original_content_sha256":hashlib.sha256(raw).hexdigest(),
      "actual_N":n,"first_half_training_N":HALF_N,"second_half_validation_N":HALF_N,
      "all_physical_trials_included":True,"all_validation_trials_used_primary":True,
      "validation_block_size":BLOCK_SIZE,
      "historical_data_already_analyzed_by_010C":True,
      "new_independent_blinded_physical_measurements":False,
      "physical_choice_generated_after_early_A_established":False,
      "per_event_source_timestamps_present":False,
      "hypotheses_and_mathematical_proofs":physics_proof(),
      "models":{
         "M0":"Jeffreys-smoothed Bernoulli probability per own setting only; fit on first half",
         "Mpost":"Descriptive selection on OTHER wing's positive outcome; explicitly excluded from primary and prediction",
         "Mjanus":"Jeffreys-smoothed Bernoulli probability per own AND remote setting; fit on first half, tested on second half; physically late choice NOT demonstrated"
      },
      "M0_vs_Mjanus_pure_outcome_prediction":predictions,
      "four_validation_no_signalling_tests":tests,
      "any_asymptotic_familywise_rejection":any(t["passes_familywise_alpha_0_001"] for t in tests),
      "assumptions_and_limitations":[
         "Published experiment is spacelike Bell settings and outcomes, not timelike late-free-choice intervention.",
         "The chronological half-split cannot undo previous exposure of ETH data to JANUS-010C.",
         "Trial-level score tests use iid large-sample asymptotics; block checks do not cure all serial dependence or RNG confounding.",
         "Conditioning on remote outcomes is collider/postselection and cannot be interpreted as signalling.",
         "Predictive superiority on heldout archival outcomes is association only, not a cause across time.",
         "This protocol did NOT execute a prospective signed early-A witness or any independent lab hardware."
      ],
      "physics_retrocausality_proven":False,
      "eligible_to_claim_physical_retrocausality":False,
      "status":"ARCHIVAL_REAL_PHYSICS_FALSIFICATION_DIAGNOSTIC_ONLY"
    }
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(record,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        f.write("\n");f.flush();os.fsync(f.fileno())
    print("JANUS_010M_RESULT "+json.dumps({
        "n":n,"M0_vs_Mjanus":{w:round(x["Mjanus_minus_M0_bits_per_event"],12) for w,x in predictions.items()},
        "local_tests":[{"wing":t["wing"],"own_setting":t["own_setting"],"delta":t["delta_plus_remote1_minus0"],"p_holm":t["p_holm_4_tests"],"selected_delta":t["postselection_only_false_signal_diagnostic"].get("delta_conditioned_on_other_wing_outcome")} for t in tests],
        "retrocausality_proven":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    run(p.parse_args().output)
