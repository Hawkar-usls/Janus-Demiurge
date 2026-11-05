#!/usr/bin/env python3
"""Two-qubit Bell-state postselection demo with honest no-signalling control.

Conceptually related to delayed selection in PCTC-inspired research, but NOT
the four-qubit protocol of Huang et al., NOT a hardware QPU run, and NOT
proof of retrocausal messaging. Includes raw and selected populations.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import random
from datetime import datetime, timezone

N=20000


def probabilities(future_choice):
    """Amplitudes for |Phi+> followed by I or X on the second qubit.

    Initial joint state (A,B) = (|00> + |11>)/sqrt(2).
    Early measurement A is recorded before future choice X is picked.
    Later X acts only on B; final B is measured and B=0 is postselected.
    """
    z=1/math.sqrt(2)
    amps=[z, 0j, 0j, z]  # |00>, |01>, |10>, |11>
    if future_choice:
        amps=[amps[1],amps[0],amps[3],amps[2]]
    return {(a,b):abs(amps[2*a+b])**2 for a in (0,1) for b in (0,1)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--shots",type=int,default=N)
    args=p.parse_args()
    if not 1000 <= args.shots <= 100000:
        raise RuntimeError("INVALID_SHOT_BUDGET")
    raw={str(x):{f"{a}{b}":probabilities(x)[(a,b)] for a in (0,1) for b in (0,1)} for x in (0,1)}
    for x in (0,1):
        joint=probabilities(x)
        assert abs(sum(joint.values())-1.)<1e-10
        assert all(abs(sum(joint[(a,b)] for b in (0,1))-.5)<1e-10 for a in (0,1))
        assert all(abs(joint[(a,b)]-(.5 if b==(a^x) else 0))<1e-10 for a in (0,1) for b in (0,1))
    # Analytic: P(A=X)=.5 for either X, even when X is chosen AFTER early A.
    unconditional_accuracy=.5
    postselection_acceptance=.5
    conditioned_accuracy=1.
    unconditional_I_AX_bits=0.
    conditioned_I_AX_given_B0_bits=1.
    # Independent seed used only to check agreement with exact probabilities.
    rng=random.Random(20261106)
    total_matched=0
    selected=0
    selected_matched=0
    for _ in range(args.shots):
        early_a=rng.getrandbits(1)
        # The 'future' choice is independently sampled after early A.
        future_x=rng.getrandbits(1)
        late_b=early_a^future_x
        good=early_a==future_x
        total_matched+=good
        if late_b==0:
            selected+=1
            selected_matched+=good
    if selected_matched!=selected:raise RuntimeError("POSTSELECTION_MATH_FAIL")
    result={
        "schema":"janus.retro.quantum.bell_postselection_sim.v1",
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "reference_research":"Phys. Rev. Research 8, 023084 (2026), DOI 10.1103/tm83-sxpm; conceptual inspiration only",
        "reference_information_theory":"Phys. Rev. Lett. 136, 230801 (2026), DOI 10.1103/znyd-npk5; not a reproduction of capacity theorem",
        "model":"2-qubit Bell state |Phi+> with future classical X choice of I vs Pauli-X on B, early Z-measurement on A, late Z-measurement on B, optional conditioning on B=0",
        "chronology":["t0 create Bell state and record early A","t1 choose X independently","t2 apply X^choice to B and measure late B","t3 condition on B=0 for subensemble only"],
        "amplitudes_and_joint_probabilities":raw,
        "exact_quantum_predictions":{
            "P_early_A_equals_future_X_without_postselection":unconditional_accuracy,
            "P_late_B0":postselection_acceptance,
            "P_early_A_equals_future_X_given_late_B0":conditioned_accuracy,
            "mutual_information_A_X_without_postselection_bits":unconditional_I_AX_bits,
            "mutual_information_A_X_given_late_B0_bits":conditioned_I_AX_given_B0_bits,
            "no_signalling_test":"P(A=0|X=0)=P(A=0|X=1)=0.5",
        },
        "seeded_sampling_sanity_check":{
            "shots":args.shots,
            "unconditional_matches":total_matched,
            "unconditional_accuracy":round(total_matched/args.shots,6),
            "selected_shots":selected,
            "selected_fraction":round(selected/args.shots,6),
            "selected_matches":selected_matched,
            "selected_accuracy":selected_matched/selected if selected else None,
        },
        "epistemic_classification":"EXACT_MATH_AND_STANDARD_CLASSICAL_MONTE_CARLO_OF_QUANTUM_Z_STATISTICS__NO_QPU_EXECUTION",
        "physical_backward_signalling_detected":False,
        "why_perfect_selected_accuracy_is_not_a_message":"The needed selection label B is available only after the future operation; all early accessible records contain zero information about X.",
        "actual_PCTC_created":False,
        "real_quantum_hardware_used":False,
    }
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
