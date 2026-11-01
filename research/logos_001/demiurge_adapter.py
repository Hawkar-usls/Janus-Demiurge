"""JANUS Demiurge research-only adapter to bounded LOGOS-001 R1.

Imports *only* the pinned local scientific proposal module. Caller must supply
TRAIN and VALIDATION; no TEST observations can be passed into this API.
This is not a production model or automatic self-modification channel.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from r1_discover import discover, PROTOCOL

ADAPTER_NAME="JANUS_DEMIURGE_LOGOS_R1_EXPERIMENTAL"
AUTHORITY="RESEARCH_PROPOSAL_ONLY_NO_PROOF_NO_DEPLOY_NO_MODEL_PROMOTION"

def propose_symbolic_laws(training_validation_data: dict) -> dict:
    """Return typed equation hypotheses; the independent witness must score them."""
    result=discover(training_validation_data)
    if result["protocol"]!=PROTOCOL or result["data_access"]!="TRAIN_AND_VALIDATION_ONLY__NO_TEST":
        raise RuntimeError("LOGOS R1 authority boundary violated")
    return result

def main():
    parser=argparse.ArgumentParser(description=ADAPTER_NAME)
    parser.add_argument("--input",required=True,help="TRAIN+VALIDATION JSON only")
    parser.add_argument("--out",required=True,help="Candidate JSON, NOT a verified discovery")
    args=parser.parse_args()
    data=json.loads(Path(args.input).read_text(encoding="utf-8"))
    candidate=propose_symbolic_laws(data)
    Path(args.out).write_text(json.dumps(candidate,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"adapter":ADAPTER_NAME,"authority":AUTHORITY,
                      "proposed":sum(x["decision"]=="PROPOSE" for x in candidate["cases"]),
                      "pending":"INDEPENDENT_HOLDOUT_VERIFICATION"}))

if __name__=="__main__":main()
