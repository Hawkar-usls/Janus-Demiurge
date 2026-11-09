#!/usr/bin/env python3
"""JANUS Ocean: honest quantum-measurement priors for a *classical* transformer.

This is a deterministic density-matrix calculation, not quantum hardware.
The parameter q is the probability of *unread* Z-basis dephasing before an
independent projective Z or X readout. It models loss of coherence, not a knob
which chooses a particular random measurement outcome. "Collapse" depends on
interpretation; conditioning on a recorded outcome is not retro-signalling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

THETAS = (0.0, math.pi/8, math.pi/4, 3*math.pi/8, math.pi/2)
DEPHASING = (0.0, 0.5, 1.0)
BASES = ("Z", "X")
SCHEMA = "janus.ocean.quantum_measurement_priors.v1"


def born_probability(theta_index: int, basis: str, dephasing_index: int) -> float:
    """P(readout=1). X outcome 1 is |->; Z outcome 1 is |1>."""
    if type(theta_index) is not int or not 0 <= theta_index < len(THETAS):
        raise ValueError("INVALID_THETA_INDEX")
    if basis not in BASES:
        raise ValueError("INVALID_BASIS")
    if type(dephasing_index) is not int or not 0 <= dephasing_index < len(DEPHASING):
        raise ValueError("INVALID_DEPHASING_INDEX")
    theta, q = THETAS[theta_index], DEPHASING[dephasing_index]
    c, s = math.cos(theta), math.sin(theta)
    if basis == "Z":
        return s*s
    return 0.5 - (1-q)*c*s


def density_matrix(theta_index: int, dephasing_index: int) -> list[list[float]]:
    theta, q = THETAS[theta_index], DEPHASING[dephasing_index]
    c, s = math.cos(theta), math.sin(theta)
    return [[c*c, (1-q)*c*s], [(1-q)*c*s, s*s]]


def model_tokens(theta_index: int, basis: str, dephasing_index: int) -> list[int]:
    """Lossless three-token input to the existing JanusTinyTransformer."""
    born_probability(theta_index, basis, dephasing_index)  # validate
    return [2+theta_index, 8+BASES.index(basis), 11+dephasing_index]


def report() -> dict:
    from janus_cpu_quantum_emulator import bell_late_message
    rows = []
    for ti in range(len(THETAS)):
        for basis in BASES:
            for qi in range(len(DEPHASING)):
                p1 = born_probability(ti, basis, qi)
                rho = density_matrix(ti, qi)
                if not -1e-12 <= p1 <= 1+1e-12:
                    raise RuntimeError("INVALID_BORN_PROBABILITY")
                if abs(sum(rho[k][k] for k in range(2))-1) > 1e-12:
                    raise RuntimeError("INVALID_TRACE")
                rows.append({
                    "input_tokens": model_tokens(ti, basis, qi),
                    "theta_radians": round(THETAS[ti], 12),
                    "basis": basis, "unread_z_dephasing_probability": DEPHASING[qi],
                    "density_matrix_real": [[round(v, 12) for v in row] for row in rho],
                    "p_readout_one": round(p1, 12),
                })
    bell = [bell_late_message(k) for k in (0, 1)]
    if any(abs(v["early_marginal_after_late_choice"][1]-.5)>1e-12 for v in bell):
        raise RuntimeError("BELL_NO_SIGNALLING_INVARIANT_FAILED")
    return {
        "schema": SCHEMA,
        "source": "analytical Born rule, unread Z-dephasing instrument, existing JANUS Bell emulator",
        "source_code_path": "experiments/ocean_transformer/measurement_priors.py",
        "dataset_class": "SYNTHETIC_ORDINARY_QUANTUM_MECHANICS",
        "grid": rows,
        "late_choice_no_signalling": bell,
        "quantum_hardware_used": False,
        "physical_retrocausality_proven": False,
        "electron_is_tachyon_proven": False,
        "collapse_interpretation_resolved": False,
        "measurement_protocol": (
            "Prepare cos(theta)|0>+sin(theta)|1>; probabilistically apply unread "
            "Z-basis projective dephasing at rate q; then measure Z or X "
            "projectively. Environmental which-path recording may cause "
            "decoherence; a recorded outcome is stochastic, not selectable."
        ),
        "no_future_labels_enter_training": True,
        "production_model_promotion": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise RuntimeError("REFUSE_OVERWRITE_EVIDENCE")
    data = report()
    serialized = json.dumps(data, sort_keys=True, indent=2) + "\n"
    out.write_text(serialized, encoding="utf-8")
    print(json.dumps({
        "schema": data["schema"], "cases": len(data["grid"]),
        "sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "no_signalling": True, "retrocausality_proven": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
