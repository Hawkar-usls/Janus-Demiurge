#!/usr/bin/env python3
"""JANUS Quantum CPU Engine R1: adaptive mathematical circuit emulator.

Purpose: emulate ideal quantum circuits on ordinary CPUs and automatically
select an appropriate mathematical representation, similar to a virtual CPU
interpreting a common instruction set.

- Clifford circuits: Stim stabilizer/tableau backend (hundreds of qubits).
- General H/X/Z/S/T/CX/CZ/SWAP: vectorized NumPy statevector (up to 20 qubits).
- Backend cross-checks for small Clifford circuits.
- An explicit late-choice audit compares all *unconditional* earlier local
  state Bloch vectors, never a postselected subensemble.

No CPU simulator supplies physical quantum entanglement, time travel, or
knowledge of an independent future choice. Late branch gates are explicitly
supplied as *ordinary present-time inputs*, not physical future messages.

Sources: Qiskit Aer, Google qsim, Stim; no quantum hardware used.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

CLIFFORD = frozenset(("H", "X", "Z", "S", "CX", "CZ", "SWAP"))
GENERAL = CLIFFORD | {"T"}
SINGLE = frozenset(("H", "X", "Z", "S", "T"))
DOUBLE = frozenset(("CX", "CZ", "SWAP"))
MAX_CLIFFORD_QUBITS = 512
MAX_DENSE_QUBITS = 20
MAX_GATES = 20000


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate_circuit(n, gates):
    check(type(n) is int and 1 <= n <= MAX_CLIFFORD_QUBITS,
          "QUBIT_COUNT_BUDGET")
    check(type(gates) is list and len(gates) <= MAX_GATES,
          "GATE_COUNT_BUDGET")
    clean = []
    for g in gates:
        check(type(g) is dict and set(g) == {"name", "qubits"},
              "GATE_FORMAT_UNEXPECTED_FIELDS")
        name, q = g["name"], g["qubits"]
        check(type(name) is str and name in GENERAL, "UNKNOWN_GATE")
        check(type(q) is list and len(q) == (1 if name in SINGLE else 2),
              "GATE_ARITY")
        check(all(type(i) is int and 0 <= i < n for i in q),
              "INVALID_QUBIT_INDEX")
        check(len(set(q)) == len(q), "REPEATED_QUBIT_INDEX")
        clean.append({"name": name, "qubits": q[:]})
    return clean


def select_backend(n, gates, backend="auto"):
    if backend == "auto":
        backend = "stim" if all(g["name"] in CLIFFORD for g in gates) else "numpy"
    check(backend in ("stim", "numpy"), "UNKNOWN_BACKEND")
    if backend == "numpy":
        check(n <= MAX_DENSE_QUBITS, "DENSE_MEMORY_BUDGET_EXCEEDED")
    else:
        check(all(g["name"] in CLIFFORD for g in gates),
              "NON_CLIFFORD_CANNOT_USE_STABILIZER_BACKEND")
    return backend


def numpy_bloch(n, gates, probes):
    import numpy as np
    gates = validate_circuit(n, gates)
    check(n <= MAX_DENSE_QUBITS, "DENSE_MEMORY_BUDGET_EXCEEDED")
    v = np.zeros(1 << n, dtype=np.complex128)
    v[0] = 1
    size = len(v)
    root = 1 / math.sqrt(2)
    t = complex(math.cos(math.pi/4), math.sin(math.pi/4))
    matrices = {
        "H": ((root, root), (root, -root)),
        "X": ((0, 1), (1, 0)),
        "Z": ((1, 0), (0, -1)),
        "S": ((1, 0), (0, 1j)),
        "T": ((1, 0), (0, t)),
    }
    for g in gates:
        name, qubits = g["name"], g["qubits"]
        if name in SINGLE:
            q = qubits[0]
            mat = matrices[name]
            block = 1 << q
            view = v.reshape(-1, 2, block)
            a = view[:, 0, :].copy()
            b = view[:, 1, :].copy()
            view[:, 0, :] = mat[0][0]*a + mat[0][1]*b
            view[:, 1, :] = mat[1][0]*a + mat[1][1]*b
        else:
            q, r = qubits
            idx = np.arange(size)
            qb, rb = 1 << q, 1 << r
            if name == "CX":
                p = idx[((idx & qb) != 0) & ((idx & rb) == 0)]
                other = p | rb
                copy = v[p].copy()
                v[p] = v[other]
                v[other] = copy
            elif name == "CZ":
                v[((idx & qb) != 0) & ((idx & rb) != 0)] *= -1
            else:
                p = idx[((idx & qb) == 0) & ((idx & rb) != 0)]
                other = p ^ qb ^ rb
                copy = v[p].copy()
                v[p] = v[other]
                v[other] = copy
    norm = float(np.vdot(v, v).real)
    check(abs(norm-1) < 1e-9, "DENSE_STATE_NORM_DRIFT")
    bloch = {}
    for q in probes:
        block = 1 << q
        mat = v.reshape(-1, 2, block)
        a, b = mat[:, 0, :], mat[:, 1, :]
        p1 = float(np.vdot(b, b).real)
        coherence = np.sum(a * np.conj(b))
        # rho[0,1] = sum amp_0 * conj(amp_1):
        # <X> = 2 Re(rho[0,1]), <Y> = -2 Im(rho[0,1]).
        bloch[str(q)] = [
            float(2 * coherence.real),
            float(-2 * coherence.imag),
            float(1 - 2*p1),
        ]
    return {"backend": "numpy", "qubits": n, "gates": len(gates),
            "norm_error": abs(norm-1), "bloch": bloch,
            "representation": "2^n complex128 amplitudes",
            "dense_amplitude_count": size}


def stim_bloch(n, gates, probes):
    import stim
    gates = validate_circuit(n, gates)
    check(all(g["name"] in CLIFFORD for g in gates),
          "NON_CLIFFORD_CANNOT_USE_STABILIZER_BACKEND")
    s = stim.TableauSimulator()
    aliases = {
        "H": "h", "X": "x", "Z": "z", "S": "s",
        "CX": "cnot", "CZ": "cz", "SWAP": "swap"
    }
    for g in gates:
        getattr(s, aliases[g["name"]])(*g["qubits"])
    bloch = {}
    for q in probes:
        bloch[str(q)] = [float(s.peek_x(q)),
                         float(s.peek_y(q)),
                         float(s.peek_z(q))]
    return {"backend": "stim", "qubits": n, "gates": len(gates),
            "norm_error": 0., "bloch": bloch,
            "representation": "Clifford stabilizer tableau",
            "dense_amplitude_count": None}


def run(n, gates, probes, backend="auto"):
    gates = validate_circuit(n, gates)
    check(type(probes) is list and probes and
          len(probes) <= min(n, 32) and len(set(probes)) == len(probes) and
          all(type(q) is int and 0 <= q < n for q in probes),
          "INVALID_PROBES")
    selected = select_backend(n, gates, backend)
    return (stim_bloch(n,gates,probes) if selected == "stim" else
            numpy_bloch(n,gates,probes))


def compare_backends(n, gates, probes):
    selected = select_backend(n, validate_circuit(n, gates), "stim")
    check(n <= 12, "CROSSCHECK_DENSE_PROHIBITED_ABOVE_12")
    a = run(n,gates,probes,"stim")
    b = run(n,gates,probes,"numpy")
    discrepancy = max(abs(a["bloch"][str(q)][k]-b["bloch"][str(q)][k])
                      for q in probes for k in range(3))
    if discrepancy > 1e-10:
        raise RuntimeError("INDEPENDENT_CPU_BACKENDS_DISAGREE")
    return {"stim": a, "numpy": b, "maximum_bloch_difference": discrepancy}


def audit_late_choice(n, precommit_circuit, late_branch_0, late_branch_1,
                      early_qubits, late_qubits):
    # A later free input is NOT generated here. Only the mathematical
    # counterfactual circuits for the two possible options are compared.
    base = validate_circuit(n, precommit_circuit)
    late0 = validate_circuit(n, late_branch_0)
    late1 = validate_circuit(n, late_branch_1)
    check(type(early_qubits) is list and early_qubits and
          type(late_qubits) is list and late_qubits and
          len(set(early_qubits)) == len(early_qubits) and
          len(set(late_qubits)) == len(late_qubits) and
          set(early_qubits).isdisjoint(late_qubits) and
          all(type(q) is int and 0 <= q < n for q in early_qubits+late_qubits),
          "INVALID_EARLY_LATE_PARTITION")
    allowed = set(late_qubits)
    check(all(set(g["qubits"]).issubset(allowed) for g in late0+late1),
          "ILLEGAL_LATE_CONTROL_OF_EARLY_REGISTER")
    early = run(n, base, early_qubits)
    x = run(n, base+late0, early_qubits)
    y = run(n, base+late1, early_qubits)
    distances = {
        str(q): math.sqrt(sum((x["bloch"][str(q)][axis] -
                               y["bloch"][str(q)][axis])**2
                              for axis in range(3)))/2
        for q in early_qubits
    }
    if max(distances.values()) > 1e-10:
        raise RuntimeError("LOCAL_CPTP_NOSIGNALLING_VIOLATION_OR_SOFTWARE_ERROR")
    return {
        "early_bloch_before_branch": early["bloch"],
        "branch_0_early_bloch": x["bloch"],
        "branch_1_early_bloch": y["bloch"],
        "trace_distance_each_early_one_qubit": distances,
        "maximum_one_qubit_trace_distance": max(distances.values()),
        "postselection": False,
        "genuine_independent_late_free_choice": False,
        "late_branch_parameter_used_by_emulator_in_present_time": True,
        "physically_recorded_early_output": False,
        "operational_retrocausal_channel": False
    }


def gate(name, *q):
    return {"name": name, "qubits": list(q)}


def standard_report():
    started = time.perf_counter()
    small = [gate("H",0), gate("CX",0,1), gate("S",2),
             gate("CZ",1,2), gate("H",3), gate("CX",3,4)]
    checkresult = compare_backends(6, small, [0,1,2,3,4,5])
    ghz = [gate("H",0)] + [gate("CX",0,i) for i in range(1,256)]
    start_stim = time.perf_counter()
    ghz_result = run(256,ghz,[0,1,127,255])
    ghz_elapsed = time.perf_counter() - start_stim
    check(ghz_result["backend"]=="stim" and
          all(abs(ghz_result["bloch"][str(q)][2])<1e-12
              for q in (0,1,127,255)), "STABILIZER_GHZ_FAILED")
    hard = [gate("H",0), gate("T",0), gate("H",0), gate("CX",0,1)]
    nonclifford = run(16,hard,[0,1,15])
    check(nonclifford["backend"]=="numpy", "NONCLIFFORD_ROUTING_FAILED")
    check(abs(nonclifford["bloch"]["0"][2] -
              1 / math.sqrt(2)) < 1e-10,
          "NONCLIFFORD_PROBABILITY_CHECK_FAILED")
    bell=[gate("H",0),gate("CX",0,1)]
    late = audit_late_choice(2,bell,[],[gate("X",1)],[0],[1])
    byte=[]
    for k in range(8):
        byte.extend((gate("H",2*k),gate("CX",2*k,2*k+1)))
    byte_late = audit_late_choice(
        16,byte,[],[gate("X",2*k+1) for k in range(8)],
        [2*k for k in range(8)], [2*k+1 for k in range(8)])
    spec={
        "backends": {"Clifford": "stim.TableauSimulator",
                     "General": "numpy.complex128 statevector"},
        "little_endian": True,
        "dense_qubit_budget": MAX_DENSE_QUBITS,
        "clifford_qubit_budget": MAX_CLIFFORD_QUBITS,
        "no_hardware_quantum_computer": True,
        "early_choice_audit": "compare all one-qubit Bloch components without postselection",
        "hypothetical_CTC_models_are_separate_from_early_physical_evidence": True,
        "not_a_blind_late_rng_test": True
    }
    spec_sha=hashlib.sha256(json.dumps(
        spec,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {
        "schema": "janus.quantum_cpu_engine.r1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec": spec, "spec_sha256": spec_sha,
        "cross_backend_6q_max_difference":checkresult["maximum_bloch_difference"],
        "large_clifford_case": {"qubits": 256,"gate_count":len(ghz),
                                "backend":ghz_result["backend"],
                                "selected_bloch":ghz_result["bloch"],
                                "elapsed_seconds":round(ghz_elapsed,6)},
        "nonclifford_case":nonclifford,
        "bell_future_local_choice":late,
        "eight_pair_future_local_choice":byte_late,
        "execution_elapsed_seconds":round(time.perf_counter()-started,6),
        "future_entropy_is_supplied_as_known_CPU_parameter":True,
        "external_precommit_or_late_rng_connected":False,
        "physical_past_directed_signal":False,
        "promotion_to_production":False,
        "research_verdict":"CPU_BACKEND_ADAPTIVE_EMULATOR_PASS__NO_PHYSICAL_RETRO_SIGNAL"
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True)
    args=p.parse_args()
    output=Path(args.out)
    if output.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    result=standard_report()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "spec_sha256":result["spec_sha256"],
        "cross_backend_max":result["cross_backend_6q_max_difference"],
        "clifford_qubits":result["large_clifford_case"]["qubits"],
        "clifford_elapsed":result["large_clifford_case"]["elapsed_seconds"],
        "nonclifford_backend":result["nonclifford_case"]["backend"],
        "physical_retro_signal":result["physical_past_directed_signal"]
    },indent=2))


if __name__=="__main__":
    main()
