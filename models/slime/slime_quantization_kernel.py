# -*- coding: utf-8 -*-
"""JANUS Slime Quantization Kernel.

Modern public-clean reconstruction of the reusable quantization/adaptation gene
found in historical MicroGPTSlime -> MicroGPTSlime_quantized.

This file is NOT byte-identical to the historical model. It preserves the
operator in a small, dependency-free, testable form:
  * oxytocin_bond(error) = exp(-|error|)
  * slime_trace EMA usefulness memory
  * structural cleanup of low-trace parameters
  * per-parameter live quantization: high precision / INT8 / INT4
  * row-wise export quantization: 12 / 8 / 4 bits by average trace

Historical anchors:
  MicroGPTSlime          SHA256 30edde3279d6fa7df206747eeb1fbd18974439e01f05e321ee0c595777dd1d11
  MicroGPTSlime_quantized SHA256 70438393c84775ae24c94172be4aa059c32d45fe41f3fefb58d20c581dda30fa

Terminology boundary: quantization here means numerical weight discretization,
not quantum computing.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

HISTORICAL_SLIME_SHA256 = "30edde3279d6fa7df206747eeb1fbd18974439e01f05e321ee0c595777dd1d11"
HISTORICAL_QUANTIZED_SHA256 = "70438393c84775ae24c94172be4aa059c32d45fe41f3fefb58d20c581dda30fa"


def _levels(bits: int) -> int:
    if bits < 2:
        raise ValueError("bits must be >= 2")
    return (1 << (bits - 1)) - 1


def _quantize_unit(value: float, bits: int) -> float:
    levels = _levels(bits)
    clipped = max(-1.0, min(1.0, float(value)))
    return round(clipped * levels) / levels


@dataclass
class QuantizedRow:
    q: List[int]
    scale: float
    bits: int

    def dequantize(self) -> List[float]:
        if self.scale == 0:
            raise ValueError("scale must be non-zero")
        return [v / self.scale for v in self.q]


class SlimeQuantizationKernel:
    """Importance-weighted numerical adaptation for matrix-like model states."""

    def __init__(self, trace_ema: float = 0.90, cleanup_threshold: float = 0.30):
        if not 0.0 <= trace_ema < 1.0:
            raise ValueError("trace_ema must be in [0, 1)")
        self.trace_ema = float(trace_ema)
        self.cleanup_threshold = float(cleanup_threshold)

    @staticmethod
    def oxytocin_bond(error: float) -> float:
        return math.exp(-min(20.0, abs(float(error))))

    def update_trace(self, old_trace: float, error: float) -> float:
        bond = self.oxytocin_bond(error)
        return self.trace_ema * float(old_trace) + (1.0 - self.trace_ema) * bond

    def update_trace_matrix(self, traces: Sequence[Sequence[float]], errors: Sequence[Sequence[float]]) -> List[List[float]]:
        if len(traces) != len(errors):
            raise ValueError("trace/error row counts differ")
        out: List[List[float]] = []
        for trow, erow in zip(traces, errors):
            if len(trow) != len(erow):
                raise ValueError("trace/error shapes differ")
            out.append([self.update_trace(t, e) for t, e in zip(trow, erow)])
        return out

    def cleanup(self, weights: Sequence[Sequence[float]], traces: Sequence[Sequence[float]]) -> tuple[List[List[float]], int]:
        if len(weights) != len(traces):
            raise ValueError("weight/trace row counts differ")
        cleaned: List[List[float]] = []
        removed = 0
        for wrow, trow in zip(weights, traces):
            if len(wrow) != len(trow):
                raise ValueError("weight/trace shapes differ")
            row: List[float] = []
            for w, trace in zip(wrow, trow):
                if float(trace) < self.cleanup_threshold:
                    removed += int(float(w) != 0.0)
                    row.append(0.0)
                else:
                    row.append(float(w))
            cleaned.append(row)
        return cleaned, removed

    @staticmethod
    def live_precision_class(trace: float) -> str:
        if trace >= 0.70:
            return "HIGH_4_DECIMAL"
        if trace >= 0.30:
            return "INT8"
        return "INT4"

    def quantize_live(self, weights: Sequence[Sequence[float]], traces: Sequence[Sequence[float]]) -> tuple[List[List[float]], Dict[str, int]]:
        if len(weights) != len(traces):
            raise ValueError("weight/trace row counts differ")
        counts = {"HIGH_4_DECIMAL": 0, "INT8": 0, "INT4": 0}
        out: List[List[float]] = []
        for wrow, trow in zip(weights, traces):
            if len(wrow) != len(trow):
                raise ValueError("weight/trace shapes differ")
            qrow: List[float] = []
            for w, trace in zip(wrow, trow):
                cls = self.live_precision_class(float(trace))
                counts[cls] += 1
                if cls == "HIGH_4_DECIMAL":
                    qrow.append(round(float(w), 4))
                elif cls == "INT8":
                    qrow.append(_quantize_unit(float(w), 8))
                else:
                    qrow.append(_quantize_unit(float(w), 4))
            out.append(qrow)
        return out, counts

    @staticmethod
    def export_row_bits(avg_trace: float) -> int:
        if avg_trace >= 0.70:
            return 12
        if avg_trace >= 0.30:
            return 8
        return 4

    def export_mixed(self, matrices: Mapping[str, Sequence[Sequence[float]]], trace_matrices: Mapping[str, Sequence[Sequence[float]]]) -> dict:
        payload = {"format": "JANUS.SlimeMixedQuant.v1", "historical_source_sha256": HISTORICAL_QUANTIZED_SHA256, "matrices": {}}
        for name, matrix in matrices.items():
            if name not in trace_matrices:
                raise KeyError(f"missing trace matrix for {name}")
            traces = trace_matrices[name]
            if len(matrix) != len(traces):
                raise ValueError(f"row count mismatch for {name}")
            rows = []
            for wrow, trow in zip(matrix, traces):
                if len(wrow) != len(trow):
                    raise ValueError(f"shape mismatch for {name}")
                avg_trace = sum(map(float, trow)) / max(1, len(trow))
                bits = self.export_row_bits(avg_trace)
                max_abs = max((abs(float(v)) for v in wrow), default=1.0)
                max_abs = max(max_abs, 1e-8)
                scale = 1000.0 if bits >= 12 else _levels(bits) / max_abs
                q = [int(round(float(v) * scale)) for v in wrow]
                rows.append({"q": q, "scale": scale, "bits": bits})
            payload["matrices"][name] = rows
        return payload

    @staticmethod
    def dequantize_mixed(payload: Mapping) -> Dict[str, List[List[float]]]:
        result: Dict[str, List[List[float]]] = {}
        for name, rows in payload.get("matrices", {}).items():
            result[name] = [QuantizedRow(list(r["q"]), float(r["scale"]), int(r["bits"])).dequantize() for r in rows]
        return result

    @staticmethod
    def save_json(payload: Mapping, path: str | Path) -> None:
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def load_json(path: str | Path) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))


def selftest() -> dict:
    kernel = SlimeQuantizationKernel()
    weights = {"demo": [[0.123456, -0.765432, 0.111111], [0.333333, -0.222222, 0.444444], [0.8, -0.7, 0.6]]}
    traces = {"demo": [[0.85, 0.85, 0.85], [0.50, 0.50, 0.50], [0.15, 0.15, 0.15]]}
    live, classes = kernel.quantize_live(weights["demo"], traces["demo"])
    exported = kernel.export_mixed(weights, traces)
    bits = [row["bits"] for row in exported["matrices"]["demo"]]
    decoded = kernel.dequantize_mixed(exported)
    cleaned, removed = kernel.cleanup(weights["demo"], traces["demo"])
    assert classes == {"HIGH_4_DECIMAL": 3, "INT8": 3, "INT4": 3}
    assert bits == [12, 8, 4]
    assert removed == 3
    assert cleaned[-1] == [0.0, 0.0, 0.0]
    assert len(decoded["demo"]) == 3
    return {"status": "PASS", "live_classes": classes, "export_bits": bits, "removed": removed, "high_example": live[0][0], "mid_example": live[1][0], "low_example": live[2][0]}


if __name__ == "__main__":
    print(json.dumps(selftest(), ensure_ascii=False, indent=2))
