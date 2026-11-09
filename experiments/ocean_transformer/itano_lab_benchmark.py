#!/usr/bin/env python3
"""External laboratory benchmark: Itano et al. (1990), Phys Rev A 41, 2295.

These 14 numbers are transcribed from Table I of a published experiment,
NOT simulated data, NOT raw individual ion shots and NOT a blinded future test.

Compares the previously frozen ideal Ocean qubit model against two measured
transition directions, and an author-supplied full apparatus prediction.
The full prediction is an external comparator, not an Ocean model trained
or reconstructed from the observations.

No fit, clamping, sample selection, provider calls or model promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

import zeno_temporal_001 as ideal

SCHEMA="janus.ocean.itano1990_external_lab_benchmark.v1"
INPUT_SCHEMA="janus.ocean.lab_zeno_itano1990.table1.v1"
EXPECTED_N=(1,2,4,8,16,32,64)
EXPECTED_DOI="10.1103/PhysRevA.41.2295"
# Lock the published observations to prevent test-time cherry-picking.
LOCKED_OBSERVATIONS={
    "observed_forward_1_to_2":(.995,.500,.335,.194,.103,.013,-.006),
    "observed_reverse_2_to_1":(.998,.496,.363,.209,.106,.061,.075),
    "published_forward_prediction":(.995,.497,.351,.201,.095,.034,.006),
    "published_reverse_prediction":(.999,.501,.365,.217,.118,.073,.080),
}


def load_locked_table(path: str) -> tuple[dict,str]:
    raw=Path(path).read_bytes()
    if len(raw)>16000:
        raise ValueError("TABLE_OVERSIZE")
    try:
        table=json.loads(raw)
    except (ValueError,UnicodeError):
        raise ValueError("TABLE_MALFORMED") from None
    if not isinstance(table,dict):
        raise ValueError("TABLE_NOT_OBJECT")
    if (table.get("schema")!=INPUT_SCHEMA or table.get("doi")!=EXPECTED_DOI
        or tuple(table.get("n_pulses",[]))!=EXPECTED_N
        or table.get("data_type")!="PUBLICATION_TABLE_TRANSCRIPTION_NOT_ORIGINAL_RAW_SHOTS"):
        raise ValueError("TABLE_PROVENANCE_INVALID")
    for key, reference in LOCKED_OBSERVATIONS.items():
        supplied=table.get(key)
        if (not isinstance(supplied,list) or len(supplied)!=len(reference)
                or any(type(v) not in (int,float) or not math.isfinite(v) for v in supplied)):
            raise ValueError("INVALID_PUBLISHED_MEASUREMENT")
        if tuple(supplied)!=reference:
            raise ValueError("LOCKED_TABLE_CHANGED_"+key)
    if table.get("published_uncertainty_approx")!=.02:
        raise ValueError("UNCERTAINTY_MISMATCH")
    if table["observed_forward_1_to_2"][-1]!=-.006:
        raise ValueError("NEGATIVE_OBSERVATION_MUST_REMAIN_UNCLIPPED")
    return table,hashlib.sha256(raw).hexdigest()


def score(observed: Iterable[float], reference: Iterable[float]) -> dict:
    o=tuple(observed)
    r=tuple(reference)
    if not o or len(o)!=len(r):
        raise ValueError("BAD_PAIR_COUNT")
    residuals=[a-b for a,b in zip(o,r)]
    return {
        "n":len(o),
        "mae":sum(abs(x) for x in residuals)/len(o),
        "rmse":math.sqrt(sum(x*x for x in residuals)/len(o)),
        "mean_residual":sum(residuals)/len(o),
        "max_absolute_residual":max(abs(x) for x in residuals),
    }


def assess(path: str) -> dict:
    table,source_sha=load_locked_table(path)
    n=table["n_pulses"]
    ideal_transitions=[
        1.0 - ideal.probabilities(math.pi,count)["unconditional_final_p0"]
        for count in n
    ]
    analytic_transitions=[.5*(1-math.cos(math.pi/count)**count) for count in n]
    if any(abs(a-b)>1e-12 for a,b in zip(ideal_transitions,analytic_transitions)):
        raise ArithmeticError("OCEAN_MODEL_NOT_MATCHING_PREDECLARED_ANALYTIC_BASELINE")
    metric={}
    rows=[]
    for label,observed_key,paper_key in (
        ("level_1_to_2","observed_forward_1_to_2","published_forward_prediction"),
        ("level_2_to_1","observed_reverse_2_to_1","published_reverse_prediction"),
    ):
        obs=table[observed_key]
        paper=table[paper_key]
        metric[label]={
            "observed_vs_frozen_ideal":score(obs,ideal_transitions),
            "observed_vs_original_paper_apparatus_prediction":score(obs,paper)
        }
        rows.extend({
            "direction":label,"n_measurement_pulses":count,
            "published_observed_transition_estimate":actual,
            "frozen_ideal_cpu_transition":reference,
            "original_paper_apparatus_prediction":apparatus,
            "observed_minus_ideal":actual-reference,
            "observed_minus_paper":actual-apparatus
        } for count,actual,reference,apparatus in zip(n,obs,ideal_transitions,paper))
    r={
        "schema":SCHEMA,
        "status":"PUBLISHED_LAB_OBSERVATIONS_COMPARED_WITH_FROZEN_CPU_BASELINE",
        "experiment_id":"JANUS-ZENO-TEMPORAL-003",
        "source":{"doi":EXPECTED_DOI,"source_table":"Itano et al. 1990 Table I",
                  "source_table_sha256":source_sha,
                  "observed_values_count":2*len(n),
                  "source_type":"REPORTED_LAB_ESTIMATES_NOT_RAW_SHOTS",
                  "approximate_observation_uncertainty":.02},
        "model":{"name":"JANUS-ZENO-TEMPORAL-001 IDEAL NONSELECTIVE QUBIT",
                 "total_rotation_rad":math.pi,"fitted_using_published_observations":False,
                 "observables":"P_transition = 1 - P_initial_final",
                 "formula":"(1 - cos(pi/n)^n)/2",
                 "N_from_paper_preserved":n},
        "competing_reference":{
            "name":"ORIGINAL_PAPER_FULL_APPARATUS_PREDICTION",
            "published_by_original_experimenters":True,
            "fitted_as_new_janus_model":False,
            "includes":"Finite optical measurement pulse duration and optical pumping",
        },
        "individual_rows":rows,
        "metrics":metric,
        "interpretation":{
            "quantum_zeno_trend_supported_by_laboratory_measurements":True,
            "ideal_model_matches_every_observation_within_0_02":False,
            "paper_apparatus_model_has_smaller_rmse_both_directions":all(
                metric[d]["observed_vs_original_paper_apparatus_prediction"]["rmse"]
                < metric[d]["observed_vs_frozen_ideal"]["rmse"] for d in metric),
            "observed_minus_0_006_preserved":table["observed_forward_1_to_2"][-1]==-.006,
            "negative_observation_is_noisy_estimate_not_negative_probability":True,
            "uncertainty_interpreted_as_independent_identical_sigma":False,
            "formal_pvalue_computed":False,
            "data_pretended_independent_blind_hidden_set":False,
            "physical_retrocausality_established":False,
            "production_model_promoted":False,
        },
        "scope":{
            "physical_measurements_performed_by_janus":False,
            "lab_measurement_values_from_published_paper":True,
            "real_external_lab_measurements_used":True,
            "provider_wolfram_queries":0,
            "network_queries_during_benchmark":0
        }
    }
    return r


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default=str(Path(__file__).parent/"data/itano1990_pra_table1.json"))
    p.add_argument("--output",required=True)
    args=p.parse_args()
    report=assess(args.input)
    dst=Path(args.output)
    if dst.exists():
        raise ValueError("IMMUTABLE_EVIDENCE_OVERWRITE_REFUSED")
    dst.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(report,indent=2,sort_keys=True)+"\n"
    dst.write_text(encoded,encoding="utf-8")
    print(json.dumps({"status":report["status"],
                      "observations":report["source"]["observed_values_count"],
                      "metrics":report["metrics"],"lab_new_hardware":False,
                      "retrosignal_proven":False},sort_keys=True))


if __name__=="__main__":
    main()
