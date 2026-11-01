"""JANUS LOGOS R1 -- deterministic, dependency-free symbolic law discovery.

The discoverer sees TRAIN and VALIDATION only. It has no oracle definitions,
holdout dataset, or imports from the independent witness. It is a bounded
symbolic search over a predeclared grammar, not an LLM or arbitrary science.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

BASIS = ("x", "x2", "x3", "x4", "sin_pi_x", "cos_pi_x", "sin_2pi_x", "exp_x", "inv1p_x2")
PROTOCOL = "JANUS_LOGOS_001_R1_1_0"
MAX_TERMS = 2
MAX_NRMSE = 0.08
MIN_GAIN_OVER_MEAN = 0.90

def basis_value(name: str, x: float) -> float:
    if name == "x": return x
    if name == "x2": return x*x
    if name == "x3": return x*x*x
    if name == "x4": return x*x*x*x
    if name == "sin_pi_x": return math.sin(math.pi*x)
    if name == "cos_pi_x": return math.cos(math.pi*x)
    if name == "sin_2pi_x": return math.sin(2*math.pi*x)
    if name == "exp_x": return math.exp(x)
    if name == "inv1p_x2": return 1.0/(1.0+x*x)
    raise ValueError("Unapproved basis: "+str(name))

def solve_linear(a, b):
    """Independent implementation in the witness never uses this routine."""
    n=len(b)
    aug=[list(row)+[b[i]] for i,row in enumerate(a)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(aug[i][k]))
        if abs(aug[pivot][k])<1e-10:return None
        aug[k],aug[pivot]=aug[pivot],aug[k]
        scale=aug[k][k]
        aug[k]=[v/scale for v in aug[k]]
        for i in range(n):
            if i==k:continue
            z=aug[i][k]
            aug[i]=[u-z*v for u,v in zip(aug[i],aug[k])]
    return [aug[i][-1] for i in range(n)]

def fit(train, names):
    cols=[(1.0,)+tuple(basis_value(n,x) for n in names) for x,y in train]
    ncols=len(names)+1
    gram=[[sum(c[i]*c[j] for c in cols) for j in range(ncols)] for i in range(ncols)]
    rhs=[sum(c[i]*p[1] for c,p in zip(cols,train)) for i in range(ncols)]
    return solve_linear(gram,rhs)

def rmse(points, names, coeff):
    return math.sqrt(sum((sum(v * f for v,f in zip(coeff,(1.0,)+tuple(basis_value(n,x) for n in names)))-y)**2 for x,y in points)/len(points))

def validate_points(points):
    if not isinstance(points,list) or len(points)<20:raise ValueError("Insufficient points")
    result=[]
    for p in points:
        if not isinstance(p,list) or len(p)!=2:raise ValueError("Malformed point")
        x,y=p
        if type(x) not in (int,float) or type(y) not in (int,float):raise ValueError("Non-numeric point")
        if not math.isfinite(x) or not math.isfinite(y) or abs(x)>5 or abs(y)>10000:raise ValueError("Unsafe value")
        result.append((float(x),float(y)))
    return result

def discover_case(case):
    if set(case)!={"id","train","validation"}:raise ValueError("Input leakage or missing field")
    train=validate_points(case["train"])
    valid=validate_points(case["validation"])
    mean=sum(y for x,y in train)/len(train)
    baseline=math.sqrt(sum((y-mean)**2 for x,y in valid)/len(valid))
    if baseline<1e-9:
        return {"id":case["id"],"decision":"ABSTAIN","reason":"FLAT_BASELINE","validation_baseline_rmse":baseline}
    best=None
    for k in range(1,MAX_TERMS+1):
        for names in itertools.combinations(BASIS,k):
            coeff=fit(train,names)
            if coeff is None or not all(math.isfinite(v) for v in coeff):continue
            err=rmse(valid,names,coeff)
            score=err/baseline+0.001*k+0.0002*sum(BASIS.index(n)+1 for n in names)
            if best is None or score<best[0]:
                best=(score,names,coeff,err)
    if best is None:raise RuntimeError("No invertible hypothesis")
    score,names,coeff,error=best
    nrmse=error/baseline
    decision="PROPOSE" if nrmse<MAX_NRMSE and (baseline-error)/baseline>MIN_GAIN_OVER_MEAN else "ABSTAIN"
    record={"id":case["id"],"decision":decision,
            "validation_baseline_rmse":baseline,"validation_rmse":error,
            "validation_nrmse":nrmse,
            "selection":"ENUMERATIVE_TRAIN_OLS_VALIDATION_MDL"}
    if decision=="PROPOSE":
        record["model"]={"basis":list(names),"coefficients":[round(c,12) for c in coeff]}
    else:record["reason"]="VALIDATION_GATE_NOT_MET"
    return record

def discover(dataset):
    if set(dataset)!={"experiment","phase","protocol","cases"}:raise ValueError("Extra/missing dataset fields")
    if (dataset["experiment"],dataset["phase"],dataset["protocol"])!=("JANUS-LOGOS-001","R1",PROTOCOL):
        raise ValueError("Unexpected experiment contract")
    if len(dataset["cases"])!=6:raise ValueError("Expected six frozen cases")
    ids=[v.get("id") for v in dataset["cases"]]
    if ids!=["C01","C02","C03","C04","N01","N02"]:raise ValueError("Case set changed")
    cases=[discover_case(c) for c in dataset["cases"]]
    canonical=json.dumps(dataset,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
    return {"experiment":"JANUS-LOGOS-001","phase":"R1","protocol":PROTOCOL,
            "evidence_type":"BOUNDED_SYMBOLIC_SEARCH_ON_SYNTHETIC_DATA",
            "dataset_sha256":hashlib.sha256(canonical).hexdigest(),
            "data_access":"TRAIN_AND_VALIDATION_ONLY__NO_TEST",
            "cases":cases,"scientific_claim_ceiling":"SYNTHETIC_DISCOVERY_NOT_NEW_PHYSICS_NOT_DIVINE_PROOF"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result=discover(json.loads(Path(args.input).read_text(encoding="utf-8")))
    Path(args.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"proposed":[v["id"] for v in result["cases"] if v["decision"]=="PROPOSE"],
                      "abstained":[v["id"] for v in result["cases"] if v["decision"]=="ABSTAIN"]}))

if __name__=="__main__":main()
