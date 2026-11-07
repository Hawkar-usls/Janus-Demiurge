#!/usr/bin/env python3
"""JANUS R6: independently audit Qu et al 2026 *public aggregate* data.

Data: 16 setting-specific probability/errorbar CSVs in Dryad
DOI 10.5061/dryad.8kprr4z24. This code never executes downloaded code,
never postselects based on outcomes, never equates indefinite causal order
with future-to-past signalling, and never treats probability tables as raw
time-tagged photon records.

The *published* inequality is 1.8090±0.0024 against bound 1.75.
That statistic is a reference reported by authors, not falsely claimed to
have been independently computed from CSV before the mapping of outcomes to
the three inequality terms is separately reproduced.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile

EXPECTED={f"Fig4_input_setting{i:04b}_vs_probability.csv":f"{i:04b}"
          for i in range(16)}
DATASET_DOI="10.5061/dryad.8kprr4z24"
DATASET_API="https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.8kprr4z24/download"
MAX_UNCOMPRESSED=2_000_000


def require(condition,message):
    if not condition:
        raise ValueError(message)


def read_aggregate_csv(data):
    try:
        text=data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("BAD_UTF8_CSV") from exc
    lines=list(csv.reader(io.StringIO(text)))
    lines=[r for r in lines if r and any(v.strip() for v in r)]
    require(lines, "EMPTY_CSV")
    header=[s.strip().lower() for s in lines[0][:3]]
    if header in (["outcome","probability","errorbar"],
                  ["outcome","probability","error"]):
        lines=lines[1:]
    require(len(lines)>=8 and len(lines)<=64,"UNEXPECTED_OUTCOME_COUNT")
    outcome=set()
    probs=[]
    errors=[]
    for row in lines:
        require(len(row)==3,"UNEXPECTED_DATA_COLUMNS")
        state=row[0].strip()
        require(state and state not in outcome, "EMPTY_OR_DUPLICATE_OUTCOME")
        outcome.add(state)
        try:
            p=float(row[1].strip())
            e=float(row[2].strip())
        except ValueError as exc:
            raise ValueError("NON_NUMERIC_PROBABILITY") from exc
        require(math.isfinite(p) and math.isfinite(e) and
                0 <= p <= 1 and e >= 0,"INVALID_PROBABILITY_OR_ERRORBAR")
        probs.append(p)
        errors.append(e)
    total=sum(probs)
    # CSV reports rounded experimental probabilities; do not silently
    # renormalize the files to manufacture a stronger inequality result.
    require(abs(total-1)<=.03,"PROBABILITY_NORMALIZATION_OUTSIDE_TOLERANCE")
    return {
        "outcomes":len(outcome),"sum_probability":total,
        "max_errorbar":max(errors),"min_probability":min(probs),
        "max_probability":max(probs),
        "data_fields":["outcome","probability","errorbar"]
    }


def inspect_zip(path):
    raw=Path(path).read_bytes()
    require(len(raw)<=4_000_000 and zipfile.is_zipfile(io.BytesIO(raw)),
            "DATA_ARCHIVE_NOT_SMALL_ZIP")
    found={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        entries=z.infolist()
        require(len(entries)<=50 and
                sum(m.file_size for m in entries)<=MAX_UNCOMPRESSED,
                "DATA_ARCHIVE_RESOURCE_CAP")
        for i in entries:
            if i.is_dir():
                continue
            name=Path(i.filename).name
            if name in EXPECTED:
                require(name not in found,"DUPLICATE_SETTING_CSV")
                data=z.read(i)
                found[name]={
                    "setting":EXPECTED[name],
                    "sha256":hashlib.sha256(data).hexdigest(),
                    **read_aggregate_csv(data)
                }
    require(set(found)==set(EXPECTED),"MISSING_ONE_OR_MORE_16_SETTINGS")
    totals={name:info["sum_probability"] for name,info in found.items()}
    return {
        "schema":"janus.public_ico_qu_dryad16_aggregate_audit.r6",
        "source_dataset_doi":DATASET_DOI,
        "public_dataset_api":DATASET_API,
        "archive_sha256":hashlib.sha256(raw).hexdigest(),
        "expected_settings":16,
        "settings_verified":len(found),
        "per_setting":found,
        "sum_probability_min":min(totals.values()),
        "sum_probability_max":max(totals.values()),
        "no_events_dropped_or_renormalized_by_this_audit":True,
        "original_data_are_aggregated_fig4_conditional_probabilities":True,
        "original_trial_level_detector_time_tags_in_these_16_csv":False,
        "published_inequality_reference":{
            "paper":"Qu et al., Science Advances 12, 2026",
            "doi":"10.1126/sciadv.aee9271",
            "reported_value":1.8090,
            "reported_standard_error":.0024,
            "fixed_order_bound":1.75,
            "reported_excess":round(1.8090-1.75,6),
            "naive_z_using_reported_standard_error":(1.8090-1.75)/.0024,
            "authors_term_values":[.4846,.4895,.8348],
            "rounded_sum_of_published_terms":round(.4846+.4895+.8348,6),
            "raw_csv_to_inequality_term_mapping_reproduced":False,
            "statistical_covariance_from_raw_photon_shots_available":False
        },
        "full_physical_time_order_independently_testable_from_tables":False,
        "open_data_inequality_violation_is_not_operational_message_to_past":True,
        "actual_retrocausal_signal_detected":False,
        "physical_retrocausality_proven":False,
        "promotion_to_production":False,
        "verdict":"AGGREGATE_DATA_COMPLETENESS_AND_NORMALIZATION_AUDIT__NOT_PHYSICAL_RETROCAUSAL_PROOF"
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--zip",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    result=inspect_zip(args.zip)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({"settings_verified":result["settings_verified"],
      "min_probability_sum":result["sum_probability_min"],
      "max_probability_sum":result["sum_probability_max"],
      "raw_time_tags_available":False,
      "physical_retrocausality_proven":False}))


if __name__=="__main__":
    main()
