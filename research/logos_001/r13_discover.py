"""JANUS-LOGOS-001 R1.3: frozen R1.2 analytic discoverer against NEW rows.

No data-source or holdout imports here. Same unchanged R1.2 model selection,
applied to six frozen R1.3 cases. No post-hoc tuning.
"""
import argparse, hashlib, json
from pathlib import Path
import r12_discover

NAMES=("HAHN1","THURBER","BENNETT5")
IDS=NAMES+tuple(x+"_SHUFFLED_VALIDATION" for x in NAMES)

def discover(obj):
    if not isinstance(obj,dict) or set(obj)!={"experiment","phase","source","cases"}:
        raise ValueError("Unexpected dataset envelope / possible test leakage")
    if (obj["experiment"],obj["phase"],obj["source"])!=(
        "JANUS-LOGOS-001","R1.3","NIST_STRD_NEW_REAL_INSTRUMENT_OBSERVATIONS"):
        raise ValueError("Wrong research protocol")
    if [r.get("id") for r in obj["cases"]]!=list(IDS):
        raise ValueError("Missing or reordered dataset")
    canonical=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    # Reuse unchanged R1.2 case-level learner, including all frozen grid choices.
    out=[r12_discover.case_discovery(row) for row in obj["cases"]]
    return {"experiment":"JANUS-LOGOS-001","phase":"R1.3",
            "algorithm":"FROZEN_R12_TRAIN_CV_VALIDATION_SELECTION",
            "source_sha256":hashlib.sha256(canonical).hexdigest(),
            "input_access":"TRAIN_VALIDATION_ONLY_NO_HOLDOUT",
            "cases":out,
            "scientific_status":"PROPOSALS_PENDING_INDEPENDENT_WITNESS"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    r=discover(json.loads(Path(a.input).read_text(encoding="utf-8")))
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({v["id"]:v["decision"] for v in r["cases"]},sort_keys=True))
if __name__=="__main__":main()
