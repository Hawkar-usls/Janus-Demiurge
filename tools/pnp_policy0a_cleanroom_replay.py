#!/usr/bin/env python3
"""Clean-room Policy-0A n=3 finite mechanics and closed-form sink inequality.

Not a proof of the Beame et al. directed GT_n lower bound, nor of P vs NP.
Never imports or executes TOPA code or trusts source-reported PASS values.
"""
from __future__ import annotations
import argparse
from collections import Counter
from itertools import combinations, permutations
import json

class ReplayHold(ValueError):
    pass

def canon(clauses):
    return tuple(sorted({tuple(sorted(set(c), key=lambda x:(abs(x),x<0)))
                         for c in clauses if not any(-v in c for v in c)},key=lambda c:(len(c),c)))

def restrict(clauses, var, value):
    yes=var if value else -var
    no=-yes
    reduced=[]
    for c in clauses:
        if yes in c:
            continue
        remain=tuple(v for v in c if v!=no)
        if not remain:
            return None
        reduced.append(remain)
    return canon(reduced)

def propagate(clauses):
    while clauses is not None:
        singles=[c[0] for c in clauses if len(c)==1]
        if not singles:
            return clauses
        for v in singles:
            clauses=restrict(clauses,abs(v),v>0)
            if clauses is None:
                return None

def explicit_n3():
    n=3; B=256*n*n; p=64*n*n
    d,a=1,2; nextvar=3
    u=list(range(nextvar,nextvar+p));nextvar+=p
    v=list(range(nextvar,nextvar+p));nextvar+=p
    x={}
    for i in range(n):
        for j in range(n):
            if i!=j:
                x[i,j]=nextvar;nextvar+=1
    core=[]
    for i,j in combinations(range(n),2):
        core.extend(((x[i,j],x[j,i]),(-x[i,j],-x[j,i])))
    for i,j,k in permutations(range(n),3):
        core.append((-x[i,j],-x[j,k],x[i,k]))
    for j in range(n):
        core.append(tuple(x[i,j] for i in range(n) if i!=j))
    boosts=[]
    for var in sorted(x.values()):
        for _ in range(B):
            leaf=nextvar;nextvar+=1
            boosts.append((var,leaf))
    sink=[(d,a,w) for w in u]+[(-d,-a,w) for w in v]
    allclauses=canon(core+boosts+sink)
    raw_core=canon(core)
    if len(allclauses)!=14991 or sum(map(len,allclauses))!=31140:
        raise ReplayHold("INDEPENDENT_SOURCE_FORMULA_SIZE_DRIFT")
    if len(raw_core)!=15 or nextvar-1!=14984:
        raise ReplayHold("INDEPENDENT_SOURCE_GADGET_DRIFT")
    # All initial clauses have length >= 2; no unit propagation occurs.
    if propagate(allclauses)!=allclauses or propagate(raw_core)!=raw_core:
        raise ReplayHold("ROOT_PROPAGATION_MISMATCH")
    attempts=4*sum(map(len,allclauses))
    if attempts!=124560 or p*p!=331776:
        raise ReplayHold("BUDGET_MISMATCH")
    # The first pivot is d=1. Its first p^2 candidate resolvents contain a
    # and -a and thus cannot be added within the capped attempt budget.
    count=0
    for left,right in ((l,r) for l in u for r in v):
        pos={d,a,left};neg={-d,-a,right}
        resolution=(pos-{d})|(neg-{-d})
        if a not in resolution or -a not in resolution:
            raise ReplayHold("NONTAUTOLOGICAL_SINK_RESOLVENT")
        count+=1
    if count!=p*p or attempts>=count:
        raise ReplayHold("SINK_BUDGET_NOT_STARVED")
    freq=Counter(abs(v) for clause in allclauses for v in clause)
    choice=min(k for k,val in freq.items() if val==max(freq.values()))
    corevars=set(x.values())
    if choice not in corevars or choice!=min(corevars) or freq[d]!=2*p or freq[a]!=2*p:
        raise ReplayHold("CORE_BRANCH_MISMATCH")
    for value in (False,True):
        full=restrict(allclauses,choice,value)
        c=restrict(raw_core,choice,value)
        pf=propagate(full)
        pc=propagate(c)
        if (pf is None)!=(pc is None):
            raise ReplayHold("BRANCH_CONTRADICTION_MISMATCH")
        if pf is not None:
            projected=canon(cl for cl in pf if cl and all(abs(z) in corevars for z in cl))
            if projected!=pc:
                raise ReplayHold("BRANCH_CORE_PROJECTION_MISMATCH")
    return {"n":3,"total_clauses":len(allclauses),"total_literals":sum(map(len,allclauses)),
            "attempt_budget":attempts,"sink_pairs_checked":count,
            "first_pivot_resolvents_all_tautological":True,
            "core_branch_variable":choice,"both_branch_projections_checked":True,
            "source_code_imported":False,"full_asymptotic_lower_bound_proved":False}

def symbolic_sink_inequality():
    # For arbitrary integer n>=3:
    # p=64 n^2, B=256 n^2, V=n(n-1).
    # L0_upper=3n^3+2VB+6p=512n^4-509n^3+384n^2.
    # p^2-4L0_upper=2048n^4+2036n^3-1536n^2>0.
    # This analytic inequality does not establish hardness of the GT core.
    for n in range(3,32):
        B=256*n*n;p=64*n*n;V=n*(n-1)
        L=3*n**3+2*V*B+6*p
        difference=p*p-4*L
        expression=2048*n**4+2036*n**3-1536*n*n
        if difference!=expression or difference<=0:
            raise ReplayHold("SINK_SYMBOLIC_IDENTITY")
    return {"domain":"ALL_INTEGERS_N_GE_3",
            "closed_form_difference":"n^2*(2048*n^2+2036*n-1536)",
            "positive_for_n_ge_3":True,
            "reason":"2048*n^2 + 2036*n - 1536 > 0 for n>=3",
            "external_GT_lower_bound_independently_established":False,
            "full_policy0a_asymptotic_result_independently_proved":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    result={"schema":"janus.topa.policy0a.cleanroom_finite_and_sink_inequality.v1",
            "status":"CLEANROOM_FINITE_REPLAY_PASS_ASYMPTOTIC_OPEN",
            "finite":explicit_n3(),"symbolic_sink":symbolic_sink_inequality(),
            "P_VS_NP":"OPEN","promotion_authority":False}
    from pathlib import Path
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":result["status"],"sink_pairs":result["finite"]["sink_pairs_checked"]}))
if __name__=="__main__":
    main()
