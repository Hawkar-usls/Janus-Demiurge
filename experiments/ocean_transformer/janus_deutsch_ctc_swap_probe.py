#!/usr/bin/env python3
"""JANUS conditional Deutsch-CTC SWAP test: mathematical signal, NO real CTC.

Deutsch's *hypothetical* chronology-violating register C obeys
    sigma_C = Tr_F[SWAP (rho_F(b) tensor sigma_C) SWAP^dagger] = rho_F(b).
With a REAL CTC this would make the early C state depend on a later free
classical bit b, without selecting only successful late shots.

Ordinary CPU evaluation only obtains sigma_C after rho_F(b) is supplied to
the algorithm, which is a forward classical input dependency. It therefore
CANNOT provide the earlier receiver with an independently future-chosen bit.

This script compares (1) an analytic fixed point, (2) an independent
two-qubit density-matrix SWAP implementation, and (3) an actually
forward-ordered CPU blind control. No user checkpoint or production touched.

Physics reference: David Deutsch, PRD 44, 3197 (1991).
Context: Morapakula & Ikeda arXiv:2607.27473 (2026), idealized
replacement-channel CTC model with hardware simulation, not physical CTC.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random

def tensor_density(rho,sigma):
    joint=[[0j]*4 for _ in range(4)]
    for f in (0,1):
        for g in (0,1):
            for c in (0,1):
                for d in (0,1):
                    joint[f+2*c][g+2*d]=rho[f][g]*sigma[c][d]
    return joint

def swap_basis_index(index):
    return (index>>1)+2*(index&1)

def deutsch_map_swap(rho_future,sigma_ctc):
    joint=tensor_density(rho_future,sigma_ctc)
    permuted=[[joint[swap_basis_index(i)][swap_basis_index(j)]
               for j in range(4)] for i in range(4)]
    return [[sum(permuted[f+2*c][f+2*d] for f in (0,1))
             for d in (0,1)] for c in (0,1)]

def maxdiff(a,b):
    return max(abs(a[i][j]-b[i][j]) for i in (0,1) for j in (0,1))

def solve_future_bit(bit):
    rho=[[1+0j,0j],[0j,0j]] if bit==0 else [[0j,0j],[0j,1+0j]]
    sigma=[[.5+0j,0j],[0j,.5+0j]]
    series=[{"iteration":0,"probability_ctc_early_one":sigma[1][1].real}]
    for step in range(1,5):
        sigma=deutsch_map_swap(rho,sigma)
        series.append({"iteration":step,"probability_ctc_early_one":sigma[1][1].real})
        if maxdiff(sigma,rho)<1e-12:
            break
    if maxdiff(sigma,rho)>1e-12:
        raise RuntimeError("DCTC_SWAP_FIXED_POINT_NOT_FOUND")
    return {
        "hypothetical_later_free_bit":bit,
        "analytic_fixed_point_early_p1":float(rho[1][1].real),
        "iterated_matrix_fixed_point_early_p1":float(sigma[1][1].real),
        "iterations":series,
        "analytic_and_matrix_agree":True,
        "uses_future_bit_as_input_to_cpu_solver":True,
        "early_receiver_did_not_get_this_state_before_input":True,
    }

def real_ordered_control(shots,seed):
    early=random.Random(seed^0x9C112)
    future=random.Random(seed^0xD2193)
    hits=0
    for _ in range(shots):
        precommitted_bit=early.getrandbits(1)
        later_chosen_bit=future.getrandbits(1)
        hits+=int(precommitted_bit==later_chosen_bit)
    return {"shots":shots,"matches":hits,"accuracy":hits/shots,
            "strict_order":"First CPU commits early bit, then future CPU RNG samples later bit",
            "postselection":False,
            "expected_accuracy_under_no_channel":.5,
            "future_input_hidden_from_early_algorithm":True}

def run(shots,seed):
    outcomes=[solve_future_bit(x) for x in (0,1)]
    future_dependence=abs(outcomes[0]["analytic_fixed_point_early_p1"]
                         -outcomes[1]["analytic_fixed_point_early_p1"])
    if future_dependence!=1.0:raise RuntimeError("THEORETICAL_DCTC_SIGNAL_FAILURE")
    actual=real_ordered_control(shots,seed)
    return {
        "schema":"janus.hypothetical_deutsch_ctc.swap_fixed_point.v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "hypothetical_model":"Deutsch D-CTC with a future chronology-respecting bit and CTC register coupled by SWAP",
        "equation":"sigma_C=Tr_F[SWAP(rho_F(b) tensor sigma_C)SWAP^dagger]=rho_F(b)",
        "source_doi":"10.1103/PhysRevD.44.3197",
        "modern_theory_reference":"arXiv:2607.27473",
        "postselection":False,
        "fixed_point_analytic_vs_independent_density":outcomes,
        "hypothetical_early_state_trace_distance_by_late_choice":future_dependence,
        "hypothetical_earlier_readout_would_decode_future_bit_if_real_CTC_existed":True,
        "actual_CPU_requires_later_bit_to_be_supplied_before_solver_runs":True,
        "physical_CTC_created":False,
        "CPU_simulated_backward_message_proven":False,
        "actual_forward_ordered_control":actual,
        "physical_time_machine_supplied":False,
        "early_blind_message_receiver_operational":False,
        "promotion_allowed":False,
        "verdict":"MATHEMATICALLY_POSITIVE_DCTC_ASSUMPTION__PHYSICALLY_UNREALIZED__BLIND_CPU_NULL",
        "missing_resource":"An actual chronology-violating physical system and attested earlier readout. CPU fixed-point calculation feeds future bit forward into the solver and cannot instantiate spacetime CTC.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shots",type=int,default=20000)
    p.add_argument("--seed",type=int,default=20261106)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if not 1000<=a.shots<=200000:raise RuntimeError("BOUNDED_SAMPLES_REQUIRED")
    result=run(a.shots,a.seed)
    dest=Path(a.out)
    if dest.exists():raise RuntimeError("REFUSE_OVERWRITE")
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
