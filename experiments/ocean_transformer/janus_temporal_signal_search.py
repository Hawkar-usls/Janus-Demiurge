#!/usr/bin/env python3
"""JANUS Temporal Signal Search v1 -- CPU no-postselection, independent audit.

Question: can a *late, freely chosen* local, trace-preserving quantum channel
change the already accessible density matrix of an earlier receiver?

This enumerates ordinary QM candidate circuits across entangled, product and
GHZ/W states with unitary, measurement-discard, noisy and reset channels.
Each candidate is computed INDEPENDENTLY by:
  (1) Kraus density-matrix evolution and partial trace;
  (2) unnormalized statevector branches and partial trace.
All 0/1 future choices, ALL Kraus outcomes, and ALL raw early data enter the
primary test. Late-herald postselection is SECONDARY and never a physical pass.

The no-signalling result is a theorem for local CPTP maps; this search checks
our implementation and catches leakage rather than claiming to discover an
impossible conventional channel. Postselected CTC and physical CTC hypotheses
are distinct experimental assumptions, not simulated physical resources.

References: PRL 136 230801 (2026), DOI 10.1103/znyd-npk5
            PRR 8 023084 (2026), DOI 10.1103/tm83-sxpm
"""
from __future__ import annotations
import argparse
import cmath
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import time

from janus_cpu_quantum_emulator import StateVector, H, X, Z, S, T

I=((1.,0.),(0.,1.))
Y=((0.,-1j),(1j,0.))
P0=((1.,0.),(0.,0.))
P1=((0.,0.),(0.,1.))
SQ=1/math.sqrt(2)


def matmul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
            for i in range(len(a))]


def dag(a):
    return [[a[j][i].conjugate() for j in range(len(a))]
            for i in range(len(a[0]))]


def mul(a,scalar):
    return [[scalar*complex(x) for x in row] for row in a]


def make_states():
    states={}
    states["product_zero"]=(StateVector(2),1)
    states["product_plus"]=(StateVector(2).h(0),1)
    states["bell_phi_plus"]=(StateVector(2).h(0).cx(0,1),1)
    states["bell_phi_minus"]=(StateVector(2).h(0).cx(0,1).z(1),1)
    theta=math.pi/7
    ry=((math.cos(theta),-math.sin(theta)),
        (math.sin(theta),math.cos(theta)))
    states["partial_entanglement"]=(StateVector(2).apply(0,ry).cx(0,1),1)
    states["ghz_3"]=(StateVector(3).h(0).cx(0,1).cx(0,2),2)
    w=[0j]*8
    for i in (1,2,4):w[i]=1/math.sqrt(3)
    states["w_3"]=(StateVector(3,w),2)
    return states


def channels():
    dep=.33
    damp=.25
    return {
      "I_vs_X":([I],[X]),
      "I_vs_Z":([I],[Z]),
      "I_vs_H":([I],[H]),
      "I_vs_S":([I],[S]),
      "I_vs_T":([I],[T]),
      "X_vs_Z":([X],[Z]),
      "I_vs_discard_measureZ":([I],[P0,P1]),
      "I_vs_discard_measureX":([I],[matmul(matmul(H,P0),H),matmul(matmul(H,P1),H)]),
      "I_vs_depolarizing":([I],
        [mul(I,math.sqrt(1-dep)),mul(X,math.sqrt(dep/3)),
         mul(Y,math.sqrt(dep/3)),mul(Z,math.sqrt(dep/3))]),
      "I_vs_amplitude_damping":([I],
        [((1.,0.),(0.,math.sqrt(1-damp))),((0.,math.sqrt(damp)),(0.,0.))]),
      "I_vs_reset_zero":([I],[P0,((0.,1.),(0.,0.))]),
    }


def cptp_valid(ks,tol=1e-11):
    total=[[0j,0j],[0j,0j]]
    for k in ks:
        kd=dag(k)
        prod=matmul(kd,k)
        for i in range(2):
            for j in range(2):
                total[i][j]+=prod[i][j]
    return max(abs(total[i][j]-I[i][j]) for i in range(2) for j in range(2))<tol


def tensor_embed(op,n,q):
    d=1<<n
    if not 0<=q<n:raise ValueError("bad qubit")
    o=[[0j]*d for _ in range(d)]
    mask=(1<<q)
    for i in range(d):
        for j in range(d):
            if (i&~mask)==(j&~mask):
                o[i][j]=complex(op[(i>>q)&1][(j>>q)&1])
    return o


def density_of(state):
    a=state.a
    return [[a[i]*a[j].conjugate() for j in range(len(a))]
            for i in range(len(a))]


def add(a,b):
    return [[a[i][j]+b[i][j] for j in range(len(a[0]))]
            for i in range(len(a))]


def kraus_density(rho,n,q,operators):
    d=1<<n
    answer=[[0j]*d for _ in range(d)]
    for op in operators:
        k=tensor_embed(op,n,q)
        out=matmul(matmul(k,rho),dag(k))
        answer=add(answer,out)
    return answer


def unnormalized_branches(state,n,q,operators):
    """Independent physical implementation: transform amplitudes branchwise."""
    reduced=[[0j,0j],[0j,0j]]
    for op in operators:
        a=state.a.copy()
        bit=1<<q
        for i in range(len(a)):
            if i&bit:continue
            j=i|bit
            x,y=a[i],a[j]
            a[i]=op[0][0]*x+op[0][1]*y
            a[j]=op[1][0]*x+op[1][1]*y
        for e in range(1<<(n-1)):
            for r in (0,1):
                for s in (0,1):
                    reduced[r][s]+=a[2*e+r]*a[2*e+s].conjugate()
    return reduced


def reduced_early(rho,n):
    """Partial trace over all qubits except q0, with little-endian q0."""
    return [[sum(rho[2*e+a][2*e+b] for e in range(1<<(n-1)))
             for b in (0,1)] for a in (0,1)]


def trace(rho):
    return sum(rho[i][i] for i in range(len(rho)))


def matrix_diff(a,b):
    return max(abs(a[i][j]-b[i][j]) for i in range(len(a)) for j in range(len(a)))


def trace_distance(a,b):
    # For two qubit reduced density matrices, delta has eigenvalues ±sqrt(d²+|c|²).
    d=(a[0][0]-b[0][0]).real
    c=a[0][1]-b[0][1]
    return math.sqrt(d*d+abs(c)**2)


def early_measurement_tv(a,b):
    # Total variation of Bernoulli early measurement in Z, X, Y bases.
    # For rho [[p,c],[conj(c),1-p]], P(+X)=(1+2Re c)/2.
    pa=[a[0][0].real, (.5+a[0][1].real),(.5-a[0][1].imag)]
    pb=[b[0][0].real, (.5+b[0][1].real),(.5-b[0][1].imag)]
    return {"Z":abs(pa[0]-pb[0]),"X":abs(pa[1]-pb[1]),"Y":abs(pa[2]-pb[2])}


def conditional_late_zero(rho,n,q):
    # Subnormalized postselected state; must reveal herald at LATER time.
    selected=kraus_density(rho,n,q,[P0])
    p=trace(selected).real
    if p<1e-12:
        return None,p
    result=reduced_early(selected,n)
    result=mul(result,1/p)
    return result,p


def candidate(state,late,channel_id,kraus_pair):
    n=state.n
    original=density_of(state)
    if matrix_diff(reduced_early(original,n),unnormalized_branches(state,n,late,[I]))>2e-11:
        raise RuntimeError("INDEPENDENT_BASELINE_CHECK_FAILED")
    density_results=[]
    branch_results=[]
    selected_results=[]
    pselect=[]
    max_delta=0
    for branch in kraus_pair:
        if not cptp_valid(branch):
            raise RuntimeError("NON_TRACE_PRESERVING_CHANNEL_IN_PRIMARY")
        evolved=kraus_density(original,n,late,branch)
        if abs(trace(evolved)-1)>1e-10:
            raise RuntimeError("CHANNEL_TRACE_FAILED")
        rho=reduced_early(evolved,n)
        independent=unnormalized_branches(state,n,late,branch)
        err=matrix_diff(rho,independent)
        max_delta=max(max_delta,err)
        if err>2e-10:
            raise RuntimeError("INDEPENDENT_METHOD_DISAGREEMENT")
        selected,p=conditional_late_zero(evolved,n,late)
        density_results.append(rho)
        branch_results.append(independent)
        selected_results.append(selected)
        pselect.append(p)
    early_D=trace_distance(*density_results)
    early_tv=early_measurement_tv(*density_results)
    selected_D=(trace_distance(*selected_results) if all(x is not None for x in selected_results) else None)
    return {
       "initial_state":state.name if hasattr(state,"name") else None,
       "channel_pair":channel_id,
       "qubits":n,
       "late_qubit":late,
       "unconditional_trace_distance":round(early_D,14),
       "unconditional_early_TV_ZXY":{k:round(v,14) for k,v in early_tv.items()},
       "max_independent_backend_abs_difference":round(max_delta,15),
       "later_herald_probability_by_choice":[round(p,12) for p in pselect],
       "postselected_conditional_trace_distance":round(selected_D,12) if selected_D is not None else None,
       "postselected_information_accessible_early":False,
       "physical_retrocause_proven":False,
    }


def leakage_positive_control():
    early0=StateVector(1)
    early1=StateVector(1).x(0)
    a=[[1.,0.],[0.,0.]]
    b=[[0.,0.],[0.,1.]]
    return {
      "name":"FORBIDDEN_EARLY_OPERATION_CONTROL",
      "set_early_X_based_on_future_bit":True,
      "unconditional_trace_distance":trace_distance(a,b),
      "illegal_reason":"This applies future-dependent control to EARLY register, requiring future bit before it is chosen.",
      "accepted_as_physical_channel":False
    }


def all_attempts_early_late_control(shots,seed):
    early=random.Random(seed^0x66A12)
    future=random.Random(seed^0xAA802)
    matches=0
    for _ in range(shots):
        a=early.getrandbits(1)     # first t0
        b=future.getrandbits(1)    # only then future choice t1
        matches+=int(a==b)
    return {
      "model":"PRECOMMITTED_INDEPENDENT_BITS_CLASSICAL_SIMULATION",
      "seed":seed,"shots":shots,"matched":matches,"accuracy":matches/shots,
      "expected":.5,"confidence_note":"Random Monte Carlo only; numerical sampling does not prove a physical backward channel.",
    }


def run(shots,seed):
    start=time.monotonic()
    tested=[]
    originals=make_states()
    ops=channels()
    for st_name,(state,late) in originals.items():
        for ch_name,paired in ops.items():
            record=candidate(state,late,ch_name,paired)
            record["initial_state"]=st_name
            tested.append(record)
    max_d=max(x["unconditional_trace_distance"] for x in tested)
    max_tv=max(max(x["unconditional_early_TV_ZXY"].values()) for x in tested)
    max_backend=max(x["max_independent_backend_abs_difference"] for x in tested)
    # Disclose strong correlations after LATE filtering, not physically available early.
    max_selected=max(x["postselected_conditional_trace_distance"] or 0. for x in tested)
    example=next(x for x in tested if x["initial_state"]=="bell_phi_plus" and x["channel_pair"]=="I_vs_X")
    if max_d>1e-10 or max_tv>1e-10 or max_backend>1e-10:
        raise RuntimeError("ALLOWED_QM_MARGINAL_OR_BACKEND_VIOLATION")
    if example["postselected_conditional_trace_distance"]<.999:
        raise RuntimeError("POSTSELECTION_CONTROL_NOT_DETECTED")
    leak=leakage_positive_control()
    if leak["unconditional_trace_distance"]!=1 or leak["accepted_as_physical_channel"]:
        raise RuntimeError("INJECTED_LEAKAGE_SHOULD_BE_REJECTED")
    spec={
      "states":list(originals),
      "future_local_trace_preserving_channel_pairs":list(ops),
      "no_postselection_primary":True,
      "measurement_bases":["Z","X","Y"],
      "two_independent_methods":["Kraus density matrix with partial trace","Statevector Kraus branches with independent partial trace"],
      "seed_is_simulation_only":True,
      "fixed_before_evaluation":True,
    }
    out={
      "schema":"janus.temporal.no_postselection_signal_search.v1",
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "candidate_spec_sha256":hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest(),
      "protocol":spec,
      "candidate_count":len(tested),
      "all_candidates":tested,
      "maximum_unconditional_early_trace_distance":max_d,
      "maximum_unconditional_early_ZXY_tv_distance":max_tv,
      "maximum_independent_backend_disagreement":max_backend,
      "maximum_later_postselected_trace_distance":max_selected,
      "postselection_bell_example":example,
      "intentional_forbidden_leakage_positive_control":leak,
      "simulation_random_control":all_attempts_early_late_control(shots,seed),
      "theorem":"For a local completely-positive trace-preserving future map E_b acting only on B, Tr_B[(I_A tensor E_b)(rho_AB)] = Tr_B(rho_AB); unselected earlier receiver state rho_A cannot depend on future choice b.",
      "operational_early_message_observed":False,
      "physical_time_travel_demonstrated":False,
      "real_qpu_used":False,
      "retrocausal_model_implemented_physically":False,
      "promotion_to_production":"REFUSED_NO_OPERATIONAL_SIGNAL",
      "engineering_result":"PASS_INDEPENDENT_DENSITY_AND_STATEVECTOR_TEST",
      "scientific_result":"NO_SIGNALLING_FOR_ALL_TESTED_STANDARD_CHANNELS",
      "next_hypothesis_requirement":"An externally implemented resource outside standard local CPTP quantum channels with independent early physical readout before later free random choice, time attestation, no late outcome conditioning or forward leakage, and independent replication.",
      "related_janus_early_future_ledger":"Hawkar-usls/Janus-Demiurge janus/retro-quantum-lab-ledger",
      "elapsed_seconds":round(time.monotonic()-start,3)
    }
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shots",type=int,default=20000)
    p.add_argument("--seed",type=int,default=20261106)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    if not 1000<=args.shots<=200000:
        raise RuntimeError("BOUNDED_SHOTS_REQUIRED")
    out=run(args.shots,args.seed)
    dest=Path(args.out)
    if dest.exists():raise RuntimeError("REFUSE_OVERWRITE")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in out.items() if k!="all_candidates"},indent=2))


if __name__=="__main__":
    main()
