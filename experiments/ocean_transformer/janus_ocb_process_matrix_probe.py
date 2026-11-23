#!/usr/bin/env python3
"""JANUS OCB process matrix — a theoretical causal inequality, NOT past signalling.

Oreshkov, Costa, Brukner, Nature Communications 3, 1092 (2012)
DOI 10.1038/ncomms2076.

Four qubit tensor order: A_in, A_out, B_in, B_out. Local Choi
operators use unnormalized measure/reprepare instruments. W(v):
[I + v/sqrt(2) (I Z Z I + Z I X Z)] / 4.

The OCB game may violate the causal bound. That does NOT demonstrate
that A was physically measured before the independent choice of B.
Every requested CPU "future" parameter is an ordinary known input.
No postselection, hardware CTC, physical retrochannel or QPU is used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

I = ((1., 0.), (0., 1.))
X = ((0., 1.), (1., 0.))
Z = ((1., 0.), (0., -1.))
PZ = (((1., 0.), (0., 0.)), ((0., 0.), (0., 1.)))
PX = (((.5, .5), (.5, .5)), ((.5, -.5), (-.5, .5)))


def kron(a, b):
    return tuple(tuple(a[i][j] * b[k][l]
                       for j in range(len(a)) for l in range(len(b)))
                 for i in range(len(a)) for k in range(len(b)))


def kron4(a, b, c, d):
    return kron(kron(kron(a, b), c), d)


def trace(a):
    return sum(a[i][i] for i in range(len(a)))


def trace_product(a, b):
    return sum(a[i][j] * b[j][i]
               for i in range(len(a)) for j in range(len(a)))


def add(*ms):
    n = len(ms[0])
    return tuple(tuple(sum(m[i][j] for m in ms) for j in range(n))
                 for i in range(n))


def scale(m, s):
    return tuple(tuple(s * x for x in row) for row in m)


def ocb_matrix(visibility):
    if not 0 <= visibility <= 1:
        raise ValueError("Visibility outside [0,1]")
    return scale(add(kron4(I, I, I, I),
                     scale(kron4(I, Z, Z, I), visibility / math.sqrt(2)),
                     scale(kron4(Z, I, X, Z), visibility / math.sqrt(2))), .25)


def alice_instrument(a, x):
    # Z measurement x, Z state a prepared at A_out.
    return kron(PZ[x], PZ[a])


def bob_instrument(b, task, y):
    # Task 0: measure B_in in X, encode b XOR y into B_out.
    # Task 1: measure B_in in Z, prepare output 0.
    if task == 0:
        return kron(PX[y], PZ[b ^ y])
    if task == 1:
        return kron(PZ[y], PZ[0])
    raise ValueError("Unsupported causal game task")


def probability_full(w, a, b, task, x, y):
    return trace_product(w, kron(alice_instrument(a, x),
                                 bob_instrument(b, task, y)))


def probability_pauli(v, a, b, task, x, y):
    """Independent Pauli-factor contraction: no full W constructed."""
    ma, mb = alice_instrument(a, x), bob_instrument(b, task, y)
    t0 = trace(ma) * trace(mb)
    t1 = trace_product(ma, kron(I, Z)) * trace_product(mb, kron(Z, I))
    t2 = trace_product(ma, kron(Z, I)) * trace_product(mb, kron(X, Z))
    return (t0 + v / math.sqrt(2) * (t1 + t2)) / 4


def probability_analytic(v, a, b, task, x, y):
    sign = (-1) ** (x ^ b) if task == 0 else (-1) ** (y ^ a)
    return (1 + v / math.sqrt(2) * sign) / 4


def check_trace_preserving():
    # Sum over all measured results. Partial trace over each local output
    # must equal identity on that party's input system.
    for a in (0, 1):
        total = add(*(alice_instrument(a, x) for x in (0, 1)))
        for u in (0, 1):
            for v in (0, 1):
                got = sum(total[2*u+o][2*v+o] for o in (0, 1))
                if abs(got - I[u][v]) > 1e-12:
                    raise RuntimeError("Alice local instrument not TP")
    for b in (0, 1):
        for task in (0, 1):
            total = add(*(bob_instrument(b, task, y) for y in (0, 1)))
            for u in (0, 1):
                for v in (0, 1):
                    got = sum(total[2*u+o][2*v+o] for o in (0, 1))
                    if abs(got - I[u][v]) > 1e-12:
                        raise RuntimeError("Bob local instrument not TP")
    return True


def run(visibilities=(0., .5, .75, 1.)):
    check_trace_preserving()
    spec = {
        "W": "(I + v/sqrt(2)*(IZZI+ZIXZ))/4",
        "tensor_order": ["A_in", "A_out", "B_in", "B_out"],
        "visibilities": list(visibilities),
        "A": "measure Z output x, prepare Z(a)",
        "B_task_0": "measure X output y, prepare Z(b XOR y)",
        "B_task_1": "measure Z output y, prepare Z(0)",
        "input_distribution": "uniform a,b,task",
        "score": "(P(x=b|task=0)+P(y=a|task=1))/2",
        "postselection": False,
        "physical_clock_order": "NOT ESTABLISHED"
    }
    spec_sha = hashlib.sha256(json.dumps(
        spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    rows = []
    max_backend_difference = 0.
    for v in visibilities:
        w = ocb_matrix(v)
        if abs(trace(w)-4) > 1e-12:
            raise RuntimeError("Invalid W trace")
        # A and B are anticommuting Hermitian Pauli strings, square to I.
        # Thus eigenvalues of W are (1+-v)/4, eight of each.
        if (1-v)/4 < -1e-12:
            raise RuntimeError("Invalid W positivity")
        tasks = []
        for task in (0, 1):
            score = 0.
            for a in (0, 1):
                for b in (0, 1):
                    total = 0.
                    for x in (0, 1):
                        for y in (0, 1):
                            p = probability_full(w,a,b,task,x,y)
                            p2 = probability_pauli(v,a,b,task,x,y)
                            p3 = probability_analytic(v,a,b,task,x,y)
                            max_backend_difference = max(
                                max_backend_difference, abs(p-p2), abs(p-p3))
                            if abs(p-p2)>1e-12 or abs(p-p3)>1e-12:
                                raise RuntimeError("Independent computation disagreement")
                            if not -1e-12<=p<=1+1e-12:
                                raise RuntimeError("Invalid Born probability")
                            total += p
                            if (task==0 and x==b) or (task==1 and y==a):
                                score += p/4
                    if abs(total-1)>1e-12:
                        raise RuntimeError("Missing branches or invalid normalization")
            tasks.append(score)
        game_score = sum(tasks)/2
        expected = (2+math.sqrt(2)*v)/4
        if abs(game_score-expected)>1e-12:
            raise RuntimeError("OCB causal inequality score mismatch")
        p0 = sum(probability_full(w,0,0,0,0,y) for y in (0,1))
        p1 = sum(probability_full(w,0,1,0,0,y) for y in (0,1))
        marginal_tv = abs(p0-p1)
        if abs(marginal_tv-v/math.sqrt(2))>1e-12:
            raise RuntimeError("OCB marginal disagreement")
        rows.append({
            "visibility": v, "score": game_score,
            "task_success_probabilities": tasks, "causal_bound": .75,
            "causal_inequality_violated": game_score>.75+1e-12,
            "ocb_model_B_input_to_A_marginal_TV": marginal_tv,
            "Alice_is_not_a_clock_certified_early_receiver": True,
            "postselection_used": False
        })
    return {
        "schema": "janus.ocb.process_matrix.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_spec_sha256": spec_sha,
        "specification": spec,
        "source_doi": "10.1038/ncomms2076",
        "independent_methods": [
            "full_16x16_Generalized_Born_rule",
            "Pauli_factor_contraction",
            "analytic_probability_formula"
        ],
        "max_backend_absolute_difference": max_backend_difference,
        "process_trace": 4.,
        "process_spectrum": "(1-v)/4 and (1+v)/4, multiplicity 8 each",
        "causal_inequality_visibility_threshold": 1/math.sqrt(2),
        "all_visibilities": rows,
        "all_outcomes_retained": True,
        "late_postselection_used": False,
        "independently_generated_late_choice": False,
        "earlier_physical_clock_recording": False,
        "physical_OCB_process_implemented": False,
        "past_directed_message_detected": False,
        "interpretation": "Mathematical noncausal process; Bob's input is explicitly fed into the CPU computation. No externally established Alice-before-Bob clock ordering and no physical backward-message resource.",
        "production_promotion": "REFUSED_RESEARCH_ONLY",
        "verdict": "THEORETICAL_CAUSAL_INEQUALITY_VIOLATED__NO_PHYSICAL_RETROCAUSAL_MESSAGE"
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    args=parser.parse_args()
    result=run()
    dest=Path(args.out)
    if dest.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, sort_keys=True, indent=2)+"\n",
                    encoding="utf-8")
    print(json.dumps({
        "spec_sha256": result["candidate_spec_sha256"],
        "scores": [(z["visibility"], z["score"]) for z in result["all_visibilities"]],
        "max_disagreement": result["max_backend_absolute_difference"],
        "physical_signal": result["past_directed_message_detected"]
    }, indent=2))


if __name__ == "__main__":
    main()
