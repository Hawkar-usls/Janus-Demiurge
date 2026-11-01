"""Demiurge R1.1 read-only scientific proposal adapter; deliberately no model promotion.

Source-bound to Meta Registry JANUS-LOGOS-001-R11; only real observed
training and validation records may enter the proposer. TEST and oracle
holdout remain in a separate GitHub worker and codebase.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from r11_discover import run

ROLE="JANUS_DEMIURGE_R11_REAL_MEASUREMENT_RESEARCH_ONLY"
MODEL_PROMOTION_ALLOWED=False

def propose_calibration_laws(observed_training_and_validation):
    candidate=run(observed_training_and_validation)
    if candidate["generator"]!="REAL_NIST_STRD_TRAIN_VALIDATION_ONLY":
        raise ValueError("Research provenance mismatch")
    return candidate

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    candidate=propose_calibration_laws(json.loads(Path(a.input).read_text(encoding="utf-8")))
    Path(a.out).write_text(json.dumps(candidate,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"role":ROLE,"model_promotion_allowed":MODEL_PROMOTION_ALLOWED,
                      "candidate_decisions":{d["id"]:d["decision"] for d in candidate["cases"]},
                      "next_gate":"INDEPENDENT_HOLDOUT_WITNESS"}))
if __name__=="__main__":main()
