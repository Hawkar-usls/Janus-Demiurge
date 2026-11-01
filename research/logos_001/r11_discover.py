"""JANUS-LOGOS-001 R1.1: bounded discovery on observed NIST measurements.

Input MUST contain only train and validation. No import of r11_data,
NIST reference equations, witness, TEST coordinates or TEST labels.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

BASIS=("x","x2","x3","sin_pi_x","cos_pi_x")
IDS=("PONTIUS","NORRIS","PONTIUS_SHUFFLED_VAL","NORRIS_SHUFFLED_VAL")

def f(name,x):
    if name=="x":return x
    if name=="x2":return x*x
    if name=="x3":return x*x*x
    if name=="sin_pi_x":return math.sin(math.pi*x)
    if name=="cos_pi_x":return math.cos(math.pi*x)
    raise ValueError("Unapproved term")

def solve(gram,rhs):
    n=len(rhs)
    a=[row[:]+[v] for row,v in zip(gram,rhs)]
    for j in range(n):
        k=max(range(j,n),key=lambda i:abs(a[i][j]))
        if abs(a[k][j])<1e-10:return None
        a[k],a[j]=a[j],a[k]
        s=a[j][j]
        a[j]=[v/s for v in a[j]]
        for i in range(n):
            if i!=j:
                w=a[i][j]
                a[i]=[p-w*q for p,q in zip(a[i],a[j])]
    return [a[i][-1] for i in range(n)]

def fit(train,basis):
    rows=[[1.0]+[f(t,x) for t in basis] for x,y in train]
    k=len(basis)+1
    a=[[sum(row[i]*row[j] for row in rows) for j in range(k)] for i in range(k)]
    b=[sum(row[i]*train[r][1] for r,row in enumerate(rows)) for i in range(k)]
    return solve(a,b)

def rmse(points,basis,coefficients):
    return math.sqrt(sum((y-coefficients[0]-sum(c*f(t,x) for t,c in zip(basis,coefficients[1:])))**2 for x,y in points)/len(points))

def parse_rows(rows):
    if not isinstance(rows,list) or len(rows)<7:raise ValueError("Insufficient data")
    out=[]
    for row in rows:
        if not isinstance(row,list) or len(row)!=2:raise ValueError("Malformed point")
        x,y=row
        if type(x) not in (int,float) or type(y) not in (int,float):raise ValueError("Non-numeric")
        if not math.isfinite(x) or not math.isfinite(y) or not (0<=x<=1.01):raise ValueError("Outside domain")
        out.append((float(x),float(y)))
    return out

def run_case(case):
    if set(case)!={"id","train","validation"}:raise ValueError("TEST leak or missing fields")
    train=parse_rows(case["train"]);validation=parse_rows(case["validation"])
    mean=sum(y for x,y in train)/len(train)
    scale=math.sqrt(sum((y-mean)**2 for x,y in train)/len(train))
    base=math.sqrt(sum((y-mean)**2 for x,y in validation)/len(validation))
    if scale<1e-10 or base<1e-10:raise ValueError("Degenerate variance")
    best=None
    for k in (1,2):
        for terms in itertools.combinations(BASIS,k):
            coeff=fit(train,terms)
            if coeff is None or not all(math.isfinite(c) for c in coeff):continue
            val_err=rmse(validation,terms,coeff)
            score=val_err+0.025*k*scale
            if best is None or score<best[0]:
                best=(score,terms,coeff,val_err)
    if best is None:raise ValueError("No candidate")
    score,terms,coeff,val_err=best
    r=val_err/base
    decision="PROPOSE" if r<0.20 else "ABSTAIN"
    record={"id":case["id"],"decision":decision,"validation_rmse":val_err,
            "validation_constant_baseline_rmse":base,"validation_nrmse":r,
            "rule":"TRAIN_OLS_PLUS_VALIDATION_RMSE_COMPLEXITY_0025"}
    if decision=="PROPOSE":
        record["model"]={"basis":list(terms),"coefficients":[round(v,12) for v in coeff]}
    else:
        record["reason"]="FAILED_FROZEN_VALIDATION_GATE"
    return record

def run(obj):
    if set(obj)!={"experiment","phase","source","datasets"} or obj["experiment"]!="JANUS-LOGOS-001" or obj["phase"]!="R1.1" or obj["source"]!="NIST_STRD_OBSERVED_REAL_MEASUREMENTS":
        raise ValueError("Unexpected dataset schema")
    if [d.get("id") for d in obj["datasets"]]!=list(IDS):
        raise ValueError("Frozen datasets changed")
    canonical=json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return {"experiment":"JANUS-LOGOS-001","phase":"R1.1",
            "generator":"REAL_NIST_STRD_TRAIN_VALIDATION_ONLY",
            "source_sha256":hashlib.sha256(canonical).hexdigest(),
            "cases":[run_case(d) for d in obj["datasets"]],
            "provenance":"PUBLIC_NIST_MEASUREMENTS_PUBLISHED_ORIGINAL_REFERENCE_MODEL_NOT_GIVEN_AS_INPUT",
            "scientific_limit":"CANDIDATE_EQUATIONS_UNTIL_INDEPENDENT_TEST"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True);parser.add_argument("--out",required=True)
    args=parser.parse_args()
    obj=json.loads(Path(args.input).read_text(encoding="utf-8"))
    result=run(obj)
    Path(args.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"decisions":{d["id"]:d["decision"] for d in result["cases"]},
                      "note":"NOT_INDEPENDENTLY_VERIFIED_YET"}))
if __name__=="__main__":main()
