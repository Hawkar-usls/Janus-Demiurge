"""JANUS Demiurge LOGOS R1.2 read-only research proposal adapter.

The bounded scientific candidate model is separate from the production model
selector. Evidence is independently checked in Meta Registry on heldout data.
"""
import argparse
import json
from pathlib import Path
from r12_discover import run

ROLE="DEMIURGE_LOGOS_R12_ANALYTIC_EQUATION_PROPOSAL"
PRODUCTION_MODEL_PROMOTION_ALLOWED=False
SOURCE_SHA="97094ba3ef7461ff1b0eb44541d4a926260c239b"

def propose_laws_from_observations(training_validation_only):
    candidate=run(training_validation_only)
    if candidate["input_access"]!="TRAIN_VALIDATION_ONLY_NO_HOLDOUT":
        raise ValueError("Research evidence contract violated")
    return candidate

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    data=json.loads(Path(a.input).read_text(encoding="utf-8"))
    candidate=propose_laws_from_observations(data)
    Path(a.out).write_text(json.dumps(candidate,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"role":ROLE,"source_blob_sha":SOURCE_SHA,
        "production_model_promotion_allowed":PRODUCTION_MODEL_PROMOTION_ALLOWED,
        "next_gate":"INDEPENDENT_HOLDOUT_WITH_PREDECLARED_BASELINES",
        "decisions":{c["id"]:c["decision"] for c in candidate["cases"]}}))
if __name__=="__main__":main()
