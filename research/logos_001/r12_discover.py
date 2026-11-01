"""JANUS LOGOS R1.2: frozen nested training-CV symbolic family search.

Only sees train and validation pairs; no import of r12_data or witness.
This code recovers analytic candidates from measurements, not explanations
of physical causality, general laws, or proofs about God Code.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

POSITIVE=("ECKERLE4","CHWIRUT2")
ALL_IDS=POSITIVE+tuple(x+"_SHUFFLED_VALIDATION" for x in POSITIVE)
GAUSS_WIDTHS=(.02,.03,.04,.05,.06,.08,.1,.12,.15,.2,.3,.4,.6)
EXP_RATES=(.25,.5,1,1.5,2,3,4,6,8,12,16,24)
RATIONAL_RATES=(0,.25,.5,1,1.5,2,3,4,6,8,12)
RATIONAL_OFFSETS=(.02,.04,.07,.1,.15,.25,.4,.6,1)

def templates():
    for degree in range(5):yield {"family":"poly","degree":degree}
    for i in range(41):
        for width in GAUSS_WIDTHS:
            yield {"family":"gaussian","center":i/40,"width":width}
    for rate in EXP_RATES:
        yield {"family":"exp_decay","rate":rate}
    for rate,offset in itertools.product(RATIONAL_RATES,RATIONAL_OFFSETS):
        yield {"family":"rational_exp","rate":rate,"offset":offset}

def features(t,x):
    k=t["family"]
    if k=="poly":return [x**i for i in range(t["degree"]+1)]
    if k=="gaussian":
        return [1.,math.exp(-.5*((x-t["center"])/t["width"])**2)]
    if k=="exp_decay":return [1.,math.exp(-t["rate"]*x)]
    if k=="rational_exp":return [1.,math.exp(-t["rate"]*x)/(x+t["offset"])]
    raise ValueError("Unsupported function family")

def parameter_count(t):
    if t["family"]=="poly":return t["degree"]+1
    if t["family"]=="gaussian":return 4
    if t["family"]=="exp_decay":return 3
    if t["family"]=="rational_exp":return 4
    raise ValueError("Unsupported family")

def _linear_system(mat,rhs):
    n=len(rhs)
    a=[list(mat[i])+[rhs[i]] for i in range(n)]
    for k in range(n):
        pivot=max(range(k,n),key=lambda i:abs(a[i][k]))
        if abs(a[pivot][k])<1e-12:return None
        a[k],a[pivot]=a[pivot],a[k]
        scale=a[k][k]
        a[k]=[v/scale for v in a[k]]
        for i in range(n):
            if i==k:continue
            v=a[i][k]
            a[i]=[p-v*q for p,q in zip(a[i],a[k])]
    c=[a[i][-1] for i in range(n)]
    return c if all(math.isfinite(v) and abs(v)<1e12 for v in c) else None

def fit(t,rows):
    a=[features(t,x) for x,y in rows]
    dim=len(a[0])
    gram=[[math.fsum(v[i]*v[j] for v in a) for j in range(dim)] for i in range(dim)]
    rhs=[math.fsum(v[i]*row[1] for v,row in zip(a,rows)) for i in range(dim)]
    return _linear_system(gram,rhs)

def evaluate(t,c,rows):
    return math.sqrt(math.fsum(
        (math.fsum(ci*fi for ci,fi in zip(c,features(t,x)))-y)**2
        for x,y in rows)/len(rows))

def grouped_cv(t,train):
    unique=sorted({x for x,y in train})
    if len(unique)<9:return float("inf")
    mapping={x:i%3 for i,x in enumerate(unique)}
    residual=0.;count=0
    for fold in range(3):
        training=[row for row in train if mapping[row[0]]!=fold]
        testing=[row for row in train if mapping[row[0]]==fold]
        c=fit(t,training)
        if c is None:return float("inf")
        residual+=math.fsum(
            (math.fsum(ci*fi for ci,fi in zip(c,features(t,x)))-y)**2
            for x,y in testing)
        count+=len(testing)
    return math.sqrt(residual/count)

def validate_rows(raw):
    if type(raw)!=list or len(raw)<7:raise ValueError("Insufficient observations")
    rows=[]
    for p in raw:
        if not isinstance(p,list) or len(p)!=2:raise ValueError("Malformed observations")
        x,y=p
        if type(x) not in (float,int) or type(y) not in (float,int) or not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Invalid observation")
        if not 0<=x<=1.01 or abs(y)>10000:raise ValueError("Observation outside frozen domain")
        rows.append((float(x),float(y)))
    return rows

def case_discovery(case):
    if type(case)!=dict or set(case)!={"id","train","validation"}:
        raise ValueError("Holdout leakage / missing field")
    train=validate_rows(case["train"]);valid=validate_rows(case["validation"])
    mu=math.fsum(y for x,y in train)/len(train)
    scale=math.sqrt(math.fsum((y-mu)**2 for x,y in train)/len(train))
    if scale<1e-12:raise ValueError("Near-constant source")
    best_shape={}
    for t in templates():
        cv=grouped_cv(t,train)
        if not math.isfinite(cv):continue
        k=t["family"]
        if k=="poly":k=f"poly{t['degree']}"
        if k not in best_shape or cv<best_shape[k][0]:
            best_shape[k]=(cv,t)
    scored=[]
    for _,t in best_shape.values():
        c=fit(t,train)
        if c is None:continue
        val=evaluate(t,c,valid)
        score=val/scale+0.008*parameter_count(t)
        scored.append((score,t,c,val))
    if not scored:raise ValueError("All models failed")
    scored.sort(key=lambda r:(r[0],r[1]["family"],json.dumps(r[1],sort_keys=True)))
    score,t,c,val=scored[0]
    baseline=min((evaluate(t0,fit(t0,train),valid),t0["degree"]) for t0 in
                 ({"family":"poly","degree":d} for d in range(4)))
    decision="PROPOSE" if val<.98*baseline[0] else "ABSTAIN"
    result={"id":case["id"],"decision":decision,
            "validation_rmse":val,"baseline_validation_rmse":baseline[0],
            "baseline_degree_selected":baseline[1],
            "selected_family":t["family"],"selection_score":score,
            "training_cv_rmse":grouped_cv(t,train)}
    if decision=="PROPOSE":
        result["model"]={"template":t,"coefficients":[round(v,14) for v in c]}
    else:result["reason"]="NO_2PCT_VALIDATION_GAIN_VS_SIMPLE_BASELINE"
    return result

def run(dataset):
    if type(dataset)!=dict or set(dataset)!={"experiment","phase","source","cases"}:
        raise ValueError("Leaking extra input fields")
    if (dataset["experiment"],dataset["phase"],dataset["source"])!=(
        "JANUS-LOGOS-001","R1.2","NIST_STDR_OBSERVED_NONLINEAR_MEASUREMENTS"):
        raise ValueError("Wrong dataset contract")
    if [c.get("id") for c in dataset["cases"]]!=list(ALL_IDS):raise ValueError("Frozen dataset IDs missing")
    encoded=json.dumps(dataset,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return {"experiment":"JANUS-LOGOS-001","phase":"R1.2",
            "source_sha256":hashlib.sha256(encoded).hexdigest(),
            "algorithm":"GROUPED_TRAIN_3FOLD_CV_VALIDATION_COMPLEXITY_GATE",
            "cases":[case_discovery(case) for case in dataset["cases"]],
            "input_access":"TRAIN_VALIDATION_ONLY_NO_HOLDOUT",
            "scientific_claim":"PROPOSAL_ONLY_PENDING_INDEPENDENT_TEST"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",required=True);parser.add_argument("--out",required=True)
    a=parser.parse_args()
    d=json.loads(Path(a.input).read_text(encoding="utf-8"))
    r=run(d)
    Path(a.out).write_text(json.dumps(r,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({c["id"]:c["decision"] for c in r["cases"]},sort_keys=True))
if __name__=="__main__":main()
