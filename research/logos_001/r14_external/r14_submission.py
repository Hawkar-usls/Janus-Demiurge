"""Frozen external-evaluator submission for JANUS-LOGOS-001 R1.4.

An independent evaluator supplies TRAIN+VALIDATION labels plus TEST x only.
TEST y MUST NOT appear in input; no network/filesystem access required.
This is a predictor, not an attestation, and does not score itself.

Requires repository's frozen research/logos_001/r12_discover.py on sys.path.
"""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from r12_discover import case_discovery, features

FROZEN_R12_GIT_BLOB_SHA="97094ba3ef7461ff1b0eb44541d4a926260c239b"
PROTOCOL="JANUS_LOGOS_R14_EXTERNAL_SEALED_v1"
REQUIRED={"domain_id","train","validation","test_x"}

def validate_domain_input(data):
    if type(data)!=dict or set(data)!=REQUIRED:
        raise ValueError("Only domain_id/train/validation/test_x permitted; TEST y is forbidden")
    name=data["domain_id"]
    if type(name)!=str or not re.fullmatch(r"[a-zA-Z0-9_-]{3,64}",name):
        raise ValueError("Invalid anonymized domain identifier")
    for k in ("train","validation"):
        rows=data[k]
        if type(rows)!=list or len(rows)<7:raise ValueError("Missing calibration measurements")
        for row in rows:
            if type(row)!=list or len(row)!=2:raise ValueError("Malformed measured pair")
            x,y=row
            if type(x) not in (int,float) or type(y) not in (int,float):
                raise ValueError("Measured values must be numbers")
            if not math.isfinite(x) or not math.isfinite(y) or x<0 or x>1 or abs(y)>10000:
                raise ValueError("Nonfinite or out of declared physical range")
    test=data["test_x"]
    if type(test)!=list or len(test)<10 or len(test)>100000:
        raise ValueError("Sealed TEST must contain >=10 inputs")
    for x in test:
        if type(x) not in (float,int) or not math.isfinite(x) or not (0<=x<=1):
            raise ValueError("TEST input outside declared range")
    groups=[{float(r[0]) for r in data[p]} for p in ("train","validation")]
    test_unique=set(float(x) for x in test)
    if len(groups[0])<9 or len(groups[1])<3 or len(test_unique)<10:
        raise ValueError("Not enough independent x groups")
    if groups[0]&groups[1] or groups[0]&test_unique or groups[1]&test_unique:
        raise ValueError("TRAIN, VALIDATION and TEST input groups not disjoint")
    return name

def produce_predictions(data):
    ident=validate_domain_input(data)
    # Crucial separation: learner receives only labeled training+validation.
    proposal=case_discovery({"id":ident,"train":data["train"],"validation":data["validation"]})
    result={
        "protocol":PROTOCOL,
        "domain_id":ident,
        "frozen_learner_blob_sha":FROZEN_R12_GIT_BLOB_SHA,
        "decision":proposal["decision"],
        "n_test":len(data["test_x"]),
        "production_model_promotion_allowed":False,
        "scientific_claim":"UNSCORED_EXTERNAL_HOLDOUT",
    }
    if proposal["decision"]=="ABSTAIN":
        result["predictions"]=None
        result["reason"]=proposal["reason"]
    else:
        model=proposal["model"]
        terms=model["template"]
        coeff=model["coefficients"]
        ys=[]
        for x in data["test_x"]:
            prediction=math.fsum(float(c)*float(v) for c,v in
                                 zip(coeff,features(terms,float(x))))
            if not math.isfinite(prediction):raise ValueError("Nonfinite external prediction")
            ys.append(prediction)
        result["model"]=model
        result["predictions"]=ys
    return result

def main():
    p=argparse.ArgumentParser(description="No TEST y, no live model promotion")
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    request=json.loads(Path(a.input).read_text(encoding="utf-8"))
    response=produce_predictions(request)
    Path(a.out).write_text(json.dumps(response,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"protocol":PROTOCOL,"domain_id":response["domain_id"],
                      "decision":response["decision"],
                      "test_predictions":response["n_test"],
                      "external_ground_truth_received":False,
                      "model_promotion":False},sort_keys=True))
if __name__=="__main__":main()
