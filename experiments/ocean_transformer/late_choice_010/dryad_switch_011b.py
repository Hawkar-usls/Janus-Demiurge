#!/usr/bin/env python3
"""JANUS-011B: independently replay original Qu et al. 2026 Dryad Tables.

Source DOI 10.5061/dryad.8kprr4z24; source version 448155.
Original complete version ZIP SHA256 was recorded BEFORE this calculation.
Paper Sci Adv 2026 Qu et al DOI 10.1126/sciadv.aee9271, Eq (4).

Data outcomes are a1,a2,b,c (four binary digits in that order);
inputs are x1,x2,y,z. Entire 16*16 tables mandatory.
No trial timestamps or precommitted early A: this is not a retrochannel test.

Dependency-free stdlib; no original raw CSV rows redistributed in report.
"""
from __future__ import annotations
import argparse
import csv
from decimal import Decimal,InvalidOperation,getcontext
import hashlib
import io
import json
import math
from pathlib import Path
import re
from urllib.request import Request,urlopen
import zipfile

getcontext().prec=34
VERSION=448155
VERSION_URL=f"https://datadryad.org/api/v2/versions/{VERSION}/download"
FILES_API=f"https://datadryad.org/api/v2/versions/{VERSION}/files"
VERSION_ZIP_SHA256="5cf46d27052bcae65ca2f4c58ef5e373a4410c3c4d52c1cfc785b3e169c9054c"
ARCHIVE_LIMIT=120000
SINGLE_CSV_LIMIT=10000
EXPECTED_NAMES={f"Fig4_input_setting{i:04b}_vs_probability.csv" for i in range(16)}
PAPER_VALUES={"T1":.4846,"T2":.4895,"T3":.8348,"S":1.8090,"S_reported_sigma":.0024,"bound":1.75}
ZERO=Decimal("0")
ONE=Decimal("1")
HALF=Decimal("0.5")
EIGHT=Decimal("8")
FOUR=Decimal("4")

def get_public(url,cap):
    if not url.startswith("https://datadryad.org/api/v2/"):
        raise ValueError("SOURCE_NOT_OFFICIAL_DRYAD_API")
    with urlopen(Request(url,headers={"User-Agent":"JANUS-011B/1.0 reproducible scientific data audit"}),timeout=40) as response:
        data=response.read(cap+1)
    if len(data)>cap:raise ValueError("PUBLIC_SOURCE_EXCEEDS_CAP")
    return data

def official_manifest():
    raw=get_public(FILES_API,50000)
    doc=json.loads(raw)
    rows=doc.get("_embedded",{}).get("stash:files",[])
    if len(rows)!=17 or doc.get("total")!=17:
        raise ValueError("DRYAD_VERSION_HAS_NOT_EXACTLY_17_FILES")
    manifest={}
    for item in rows:
        path=item["path"]
        if path in manifest:raise ValueError("DUPLICATE_ORIGINAL_DRYAD_FILE")
        digest=item.get("digest")
        if item.get("digestType")!="sha-256" or not re.fullmatch("[a-f0-9]{64}",digest or ""):
            raise ValueError("NO_VALID_ORIGINAL_SOURCE_SHA256")
        manifest[path]={"sha256":digest,"size":item["size"],"mimeType":item.get("mimeType")}
    if set(manifest)!=(EXPECTED_NAMES|{"README.md"}):
        raise ValueError("UNEXPECTED_DRYAD_SOURCE_FILES")
    return manifest,hashlib.sha256(raw).hexdigest()

def decode_csv(blob,setting):
    txt=blob.decode("utf-8-sig")
    table={}
    r=csv.reader(io.StringIO(txt))
    for index,row in enumerate(r):
        if not row:continue
        cells=[s.strip().strip('"') for s in row]
        if index==0 and [s.lower() for s in cells] in (
            ["outcome","probability","errorbar"],
            ["outcome","probability","error bar"],
            ["outcome","probability","uncertainty"]
        ):continue
        if len(cells)!=3:raise ValueError("ORIGINAL_CSV_COLUMN_COUNT_NOT_THREE")
        out,p,sigma=cells
        if not re.fullmatch("[01]{4}",out):raise ValueError("UNKNOWN_OUTCOME_ENCODING_NO_MANUAL_REMAP")
        if out in table:raise ValueError("DUPLICATE_OUTCOME")
        try:
            v=Decimal(p);e=Decimal(sigma)
        except InvalidOperation:raise ValueError("INVALID_DECIMAL_ENTRY") from None
        if not v.is_finite() or not e.is_finite() or not ZERO<=v<=ONE or e<ZERO:
            raise ValueError("INVALID_PROBABILITY_OR_ERRORBAR")
        table[out]=(v,e)
    if set(table)!={f"{j:04b}" for j in range(16)}:raise ValueError("MISSING_OUTCOME_IN_SETTING")
    normalized=sum((p for p,_ in table.values()),ZERO)
    if abs(normalized-ONE)>Decimal(".01"):raise ValueError("SOURCE_NOT_NORMALIZED")
    return table,{
        "setting":setting,"row_count":len(table),
        "original_probability_sum":str(normalized),
        "rounding_difference_from_one":str(normalized-ONE),
        "source_retained_without_renormalization":True
    }

def original_tables():
    manifest,meta_sha=official_manifest()
    zipbytes=get_public(VERSION_URL,ARCHIVE_LIMIT)
    original_zip_sha=hashlib.sha256(zipbytes).hexdigest()
    if original_zip_sha!=VERSION_ZIP_SHA256:raise ValueError("DROPPED_OR_CHANGED_ORIGINAL_ZIP_VERSION")
    files={}
    with zipfile.ZipFile(io.BytesIO(zipbytes)) as z:
        infos=z.infolist()
        if len(infos)!=17:raise ValueError("ZIP_ENTRY_COUNT_CHANGED")
        for inf in infos:
            name=inf.filename
            if name not in manifest or name in files or inf.is_dir():raise ValueError("BAD_OR_DUPLICATE_ORIGINAL_ZIP_MEMBER")
            if inf.file_size>SINGLE_CSV_LIMIT:raise ValueError("UNEXPECTED_ORIGINAL_CSV_FILE_SIZE")
            content=z.read(inf)
            if len(content)!=manifest[name]["size"] or hashlib.sha256(content).hexdigest()!=manifest[name]["sha256"]:
                raise ValueError("FILE_NOT_MATCHING_DRYAD_PUBLISHED_SHA256")
            files[name]=content
    if set(files)!=set(manifest):raise ValueError("ZIP_FILE_SET_CHANGED")
    tables={}
    diagnostics=[]
    for key in sorted(EXPECTED_NAMES):
        m=re.fullmatch(r"Fig4_input_setting([01]{4})_vs_probability\.csv",key)
        setting=m.group(1)
        tables[setting],diag=decode_csv(files[key],setting)
        diagnostics.append(diag)
    return tables,{"source_Dryad_DOI":"10.5061/dryad.8kprr4z24",
        "paper_DOI":"10.1126/sciadv.aee9271",
        "source_version_id":VERSION,
        "version_original_zip_sha256":original_zip_sha,
        "Dryad_files_API_sha256":meta_sha,
        "files_sha256":{k:v["sha256"] for k,v in sorted(manifest.items())},
        "archive_bytes":len(zipbytes),
        "N_settings":len(tables),
        "N_outcome_rows":sum(len(x) for x in tables.values()),
        "normalization_by_setting":diagnostics,
        "all_original_conditional_probabilities_included":True,
        "original_probabilities_not_renormalized":True
    }

def eq4_weights():
    """Article Eq4: weights indexed by binary x1 x2 y z, a1 a2 b c."""
    out={}
    for settings in (f"{i:04b}" for i in range(16)):
        x1,x2,y,z=map(int,settings)
        for outcome in (f"{i:04b}" for i in range(16)):
            a1,a2,b,c=map(int,outcome)
            coeff=[ZERO,ZERO,ZERO]
            if y==0:
                if b==0 and a2==x1:coeff[0]=ONE/EIGHT
                if b==1 and a1==x2:coeff[1]=ONE/EIGHT
            if x1==0 and x2==0 and (b^c)==(y*z):
                coeff[2]=ONE/FOUR
            out[(settings,outcome)]=coeff
    return out

def inequality(tables):
    if set(tables)!={f"{i:04b}" for i in range(16)}:raise ValueError("REQUIRE_ALL_16_SETTINGS")
    weights=eq4_weights()
    terms=[ZERO,ZERO,ZERO]
    # Marginal errorbars are correlated; this diagonal-only propagation is
    # an *unlicensed* planning quantity, NOT independent physical SD.
    diag_independent_var=[0.,0.,0.]
    total_diag_var=0.
    n=0
    for (setting,outcome),weights_row in sorted(weights.items()):
        if setting not in tables or outcome not in tables[setting]:
            raise ValueError("MISSING_ORIGINAL_ROW")
        p,errorbar=tables[setting][outcome]
        n+=1
        coeff=sum(weights_row,ZERO)
        total_diag_var+=(float(coeff)*float(errorbar))**2
        for j,weight in enumerate(weights_row):
            terms[j]+=weight*p
            diag_independent_var[j]+=(float(weight)*float(errorbar))**2
    if n!=256:raise ValueError("INCOMPLETE_16X16_SOURCE_GRID")
    S=sum(terms,ZERO)
    return {
      "full_source_outcome_rows_used":n,
      "term1":float(terms[0]),"term2":float(terms[1]),"term3":float(terms[2]),
      "S":float(S),
      "causal_definite_order_bound":1.75,
      "observed_S_minus_bound":float(S-Decimal("1.75")),
      "descriptive_diagonal_only_terms_sigma":[math.sqrt(v) for v in diag_independent_var],
      "descriptive_diagonal_only_S_sigma":math.sqrt(total_diag_var),
      "diagonal_only_sigma_NOT_authoritative":True,
      "why_not":"The published per-outcome SD values inherit within-run count, normalization and cross-setting covariance. The original joint count covariance is not in the 16 CSV tables; no independent sigma or p-value can be obtained by assuming them independent.",
      "authors_reported_rounded_S":1.8090,
      "authors_reported_S_sd":.0024,
      "authors_reported_claim_24_SD":True,
      "claimed_24_SD_independently_reproduced":False,
      "compare_to_published_T1_T2_T3":{
          "published":[.4846,.4895,.8348],
          "independent_difference":[float(terms[j])-v for j,v in enumerate((.4846,.4895,.8348))]},
      "causal_inequality_violation_conditional_on_source_sampling_assumptions":float(S)>1.75,
      "retrocause_signal_from_early_records":False
    }

def analytical_models():
    # All outcomes, not selected. A deterministic normalized nonlinear pure
    # state map can distinguish different ensembles of *same* rho=I/2.
    z_ensemble_unphysical=.5
    x_ensemble_unphysical=4./5.
    # K_success diag(1,.5), K_failure diag(0,sqrt(.75)).
    # Normalized success-only Z ensemble P0=2/3; X P0=4/5.
    success_Z=.75
    success_X=.625
    physical_all_Z=success_Z*(2./3.)+(1.-success_Z)*0.
    physical_all_X=success_X*(4./5.)+(1.-success_X)*0.
    return {
      "nonlinear_pure_state_map":{
         "K":"diag(1,1/2), deterministic map psi->Kpsi/||Kpsi|| applied to EACH remotely prepared pure state",
         "same_input_reduced_rho":"I/2 for Z and X remote ensemble decompositions",
         "Z_ensemble_P0_after_assumed_deterministic_map":z_ensemble_unphysical,
         "X_ensemble_P0_after_assumed_deterministic_map":x_ensemble_unphysical,
         "assumed_potential_operational_delta":x_ensemble_unphysical-z_ensemble_unphysical,
         "physical_process_observed":False,
         "density_operator_channel_well_defined":False,
         "why":"Different outputs from two decompositions of I/2; standard deterministic CPTP maps must not depend on decomposition."
      },
      "standard_quantum_filter_all_outcomes":{
         "K_success":"diag(1,1/2)",
         "K_failure":"diag(0,sqrt(3)/2)",
         "K0dagK0_plus_K1dagK1_equals_I":True,
         "success_fraction_Z":success_Z,
         "success_fraction_X":success_X,
         "Z_unconditional_P0":physical_all_Z,
         "X_unconditional_P0":physical_all_X,
         "unconditional_signal_delta":physical_all_X-physical_all_Z,
         "after_success_only_Z_P0":2./3.,
         "after_success_only_X_P0":4./5.,
         "filtered_success_only_is_not_early_signalling":True
      },
      "coherent_quantum_switch":{
         "example_order_operations":"XZ and ZX anti-commute; coherent control stores relative phase",
         "ideal_control_minus_probability":1.,
         "incoherent_mixture_control_minus_probability":.5,
         "all_outcomes_included":True,
         "difference_is_control_output_interference_not_retrocausal_A":True,
         "earlier_already_fixed_A_can_be_rewritten":False
      },
      "Ji_Lloyd_Wilde_2026":{
         "DOI":"10.1103/znyd-npk5",
         "published_2026_06_11":True,
         "original_theory":"Information-theoretic capacities of noisy postselected CTC channel under modeled assumptions",
         "experimental_noisy_CTC_parameters_in_Dryad":False,
         "capacity_numeric_value_computed":False,
         "capacity_theorems_applicable_as_physical_claim_without_CTC":False
      }
    }

def run(path):
    tbl,prov=original_tables()
    results=inequality(tbl)
    theory=analytical_models()
    record={
      "schema":"janus.011b.dryad_qu2026_independent_reanalysis.v1",
      "pre_data_frozen_commit":"979bbc30649ad6f4fb8e2c3e81c34c2688cf03ca",
      "data":prov,"experimental_causal_inequality":results,
      "theory_math_controls":theory,
      "physical_temporal_causality_admission":{
         "has_external_precommitted_early_A_shots":False,
         "has_independent_later_free_C_after_recorded_A":False,
         "has_trial_level_trusted_clock_and_cable_delays":False,
         "raw_all_emitted_photon_trials_in_Dryad":False,
         "paper_fair_sampling_assumption_required":True,
         "indefinite_causal_order_and_retrosignal_are_distinct":True,
         "status":"EARLY_RECORD_CAUSAL_TEST_INELIGIBLE",
         "physical_retrocausality_proven":False
      },
      "summary":"All original 16x16 reported aggregate probabilities reconstructed. No original raw photon counts, independent time-ordered earlier readout or fully specified covariance; no physical backward-time signal."
    }
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("x",encoding="utf8") as f:
        json.dump(record,f,indent=2,ensure_ascii=False,sort_keys=True,allow_nan=False)
        f.write("\n")
    print("JANUS_011B_RESULT "+json.dumps({
        "original_zip_sha256":prov["version_original_zip_sha256"],
        "complete_16x16_rows":prov["N_outcome_rows"],
        "normalizations":[x["original_probability_sum"] for x in prov["normalization_by_setting"]],
        "T1":results["term1"],"T2":results["term2"],"T3":results["term3"],
        "S":results["S"],"excess":results["observed_S_minus_bound"],
        "diagonal_only_unverified_sd":results["descriptive_diagonal_only_S_sigma"],
        "nonlinear_toy_delta":theory["nonlinear_pure_state_map"]["assumed_potential_operational_delta"],
        "CPTP_all_outcomes_delta":theory["standard_quantum_filter_all_outcomes"]["unconditional_signal_delta"],
        "switch_control_minus_probability":theory["coherent_quantum_switch"]["ideal_control_minus_probability"],
        "physical_early_record_status":"EARLY_RECORD_CAUSAL_TEST_INELIGIBLE",
        "retrocausality":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",required=True)
    run(ap.parse_args().output)
