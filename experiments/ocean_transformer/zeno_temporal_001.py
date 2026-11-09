#!/usr/bin/env python3
"""JANUS-ZENO-TEMPORAL-001: standard two-level quantum Zeno CPU baseline.

Hamiltonian H = hbar*Omega*sigma_x/2, initially |0>.
N *equally spaced, unread* projective Z measurements over T. The final
unconditional P(|0>) is NOT the same as P(all measurement records are 0).
No tachyon, forced quantum outcome, time stop or backward-time signalling.
This synthetic simulation is an analytical CPU reference, not experimental data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

EXPERIMENT_ID = "JANUS-ZENO-TEMPORAL-001"
SCHEMA = "janus.ocean.zeno_temporal_001.v1"
ROTATIONS = (math.pi / 2, math.pi)
MEASUREMENT_COUNTS = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)


def probabilities(total_rotation: float, n: int) -> dict:
    """N measurements AFTER each free evolution interval, including final."""
    if type(n) is not int or not 0 <= n <= 4096:
        raise ValueError("INVALID_MEASUREMENT_COUNT")
    if not isinstance(total_rotation, (float, int)) or not math.isfinite(total_rotation):
        raise ValueError("INVALID_ROTATION")
    if not 0 <= total_rotation <= 4 * math.pi:
        raise ValueError("ROTATION_OUT_OF_SCOPE")
    if n == 0:
        p = math.cos(total_rotation / 2) ** 2
        return {
            "n_measurements": n,
            "unconditional_final_p0": p,
            "all_zero_measurement_record_probability": None,
            "analytic_unconditional_final_p0": p,
            "analytic_all_zero_record_probability": None,
        }
    c2 = math.cos(total_rotation / (2 * n)) ** 2
    s2 = 1 - c2
    # Density matrix is diagonal after each nonselective Z measurement.
    # This Markov step is explicitly independent of any measured outcome.
    p0 = 1.0
    for _ in range(n):
        p0 = p0 * c2 + (1.0 - p0) * s2
    # Two distinct analytic formulas for two distinct events:
    analytic_final = 0.5 * (1 + math.cos(total_rotation / n) ** n)
    analytic_all_zero = c2 ** n
    if abs(p0 - analytic_final) > 1e-11:
        raise ArithmeticError("DENSITY_MATRIX_VS_ANALYTIC_DISAGREEMENT")
    if not 0 <= p0 <= 1 or not 0 <= analytic_all_zero <= 1:
        raise ArithmeticError("INVALID_PROBABILITIES")
    return {
        "n_measurements": n,
        "unconditional_final_p0": p0,
        "all_zero_measurement_record_probability": analytic_all_zero,
        "analytic_unconditional_final_p0": analytic_final,
        "analytic_all_zero_record_probability": analytic_all_zero,
    }


def build_report() -> dict:
    grids = []
    for rotation in ROTATIONS:
        rows = [probabilities(rotation, n) for n in MEASUREMENT_COUNTS]
        grids.append({
            "omega_times_T_radians": rotation,
            "counts": rows,
        })
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "source_video": "https://youtu.be/e4k4kHzbYyU?t=837",
        "status": "STANDARD_QM_CPU_REFERENCE_ONLY",
        "physics": {
            "initial": "|0>",
            "hamiltonian": "H = hbar * Omega/2 * sigma_x",
            "measurement": "unread (non-selective) projective Z at equal intervals",
            "p_all_zero_record": "cos(Omega*T/(2*N))^(2*N)",
            "p_final_zero_nonselective": "(1 + cos(Omega*T/N)^N)/2",
            "n_zero": "no intermediate measurement, final Born readout",
        },
        "fixed_before_evaluation": {
            "rotation_grid": list(ROTATIONS),
            "N_grid": list(MEASUREMENT_COUNTS),
            "comparison": "N=0 vs repeated measurements at fixed Omega*T",
        },
        "grids": grids,
        "scope": {
            "quantum_hardware_used": False,
            "real_physical_measurement_performed": False,
            "physical_retrocausality_proven": False,
            "electron_is_tachyon_proven": False,
            "forced_collapse_outcome": False,
            "anti_zeno_regime_claimed": False,
        },
    }


def chart_svg(report: dict) -> str:
    """Self-contained plot of both observables; no external chart dependencies."""
    w, h = 700, 375
    left, right, top, bottom = 80, 670, 48, 310
    def px(n): return left + (math.log2(n) + 1) / 9 * (right - left)
    def py(p): return bottom - p * (bottom - top)
    grid = report["grids"][-1]["counts"]  # Omega T == pi
    positive = [r for r in grid if r["n_measurements"] > 0]
    def path(key):
        return " ".join(
            ("M" if i == 0 else "L") + f"{px(row['n_measurements']):.1f},{py(row[key]):.1f}"
            for i, row in enumerate(positive)
        )
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="700" height="375" fill="white"/>',
        '<text x="70" y="26" font-size="18" font-family="sans-serif">JANUS · Zeno CPU · Omega T = pi</text>',
        f'<path d="M{left},{top} V{bottom} H{right}" stroke="#333" fill="none"/>',
    ]
    for p in (0, .25, .5, .75, 1):
        y = py(p)
        pieces.append(f'<path d="M{left},{y:.1f} H{right}" stroke="#ddd"/>')
        pieces.append(f'<text x="42" y="{y+5:.1f}" font-size="12">{p:.2f}</text>')
    for row in positive:
        n = row["n_measurements"]
        x = px(n)
        pieces.append(f'<text x="{x:.1f}" y="330" text-anchor="middle" font-size="11">{n}</text>')
    pieces += [
        f'<path d="{path("unconditional_final_p0")}" stroke="#176aa6" stroke-width="3" fill="none"/>',
        f'<path d="{path("all_zero_measurement_record_probability")}" stroke="#d06a25" stroke-width="3" fill="none"/>',
        '<text x="95" y="351" font-size="12">N measurements (logarithmic)</text>',
        '<text x="364" y="55" font-size="11" fill="#176aa6">Final |0>, outcome ignored</text>',
        '<text x="364" y="73" font-size="11" fill="#d06a25">All measurement results = 0</text>',
        '<text x="10" y="195" font-size="12" transform="rotate(-90,10,195)">Probability</text>',
        '</svg>',
    ]
    return "\n".join(pieces) + "\n"


def write_once(path: str, text: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise RuntimeError("REFUSE_OVERWRITE_EVIDENCE")
    p.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--chart", required=True)
    args = parser.parse_args()
    report = build_report()
    digest = write_once(args.output, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_once(args.chart, chart_svg(report))
    print(json.dumps({"experiment": EXPERIMENT_ID, "status": report["status"],
                      "data_sha256": digest, "chart": args.chart,
                      "physical_retrocausality_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
