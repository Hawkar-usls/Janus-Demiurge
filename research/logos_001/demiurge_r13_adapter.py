"""Demiurge experimental law hypothesis API: JANUS-LOGOS-001 R1.3.

Only TRAIN/VALIDATION. This wrapper cannot see new observed TEST
or change active Demiurge models or runtime authorization.
"""
import argparse
import json
from pathlib import Path
from r13_discover import discover

ADAPTER="JANUS_DEMIURGE_LOGOS_R13_RESEARCH_ONLY"
SOURCE_SHA="b16f367b477b12cae1b582cbcdcff9d29f537df4"
PRODUCTION_MODEL_PROMOTION_ALLOWED=False

def propose_scientific_equations(train_validation_json):
    result=discover(train_validation_json)
    if result["input_access"]!="TRAIN_VALIDATION_ONLY_NO_HOLDOUT":
        raise ValueError("Wrong experimental data authority")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    d=json.loads(Path(a.input).read_text(encoding="utf-8"))
    result=propose_scientific_equations(d)
    Path(a.out).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"adapter":ADAPTER,"source_sha":SOURCE_SHA,
        "production_model_promotion_allowed":PRODUCTION_MODEL_PROMOTION_ALLOWED,
        "candidate_decisions":{case["id"]:case["decision"] for case in result["cases"]},
        "next":"SEPARATE_SCIENTIFIC_STRONG_BASELINE_WITNESS"}))

if __name__=="__main__":main()
