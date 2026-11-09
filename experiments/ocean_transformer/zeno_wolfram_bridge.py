#!/usr/bin/env python3
"""Bounded Wolfram|Alpha checks for JANUS-ZENO-TEMPORAL-001.

Uses the already installed Full Results API adapter's result decoding, but
has a separate fixed Zeno query list and manual credential gate. No arbitrary
queries, cache of provider output, changes to Rowan or production weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import zeno_temporal_001 as z
from wolfram_alpha_bridge import API_BASE, WolframHold, decode_result

SCHEMA = "janus.ocean.zeno_wolfram_verification.v1"
MAX_LIVE_QUERIES = 4
CASES = (
    ("n0_no_measurement_final_p0", "cos(pi/2)^2", z.probabilities(math.pi, 0)["unconditional_final_p0"]),
    ("n2_all_zero_record", "cos(pi/4)^4", z.probabilities(math.pi, 2)["all_zero_measurement_record_probability"]),
    ("n2_unconditional_final_p0", "(1+cos(pi/2)^2)/2", z.probabilities(math.pi, 2)["unconditional_final_p0"]),
    ("n4_unconditional_final_p0", "(1+cos(pi/4)^4)/2", z.probabilities(math.pi, 4)["unconditional_final_p0"]),
)


def report_sha256():
    return hashlib.sha256(json.dumps(
        z.build_report(), sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def remote_value(appid: str, expression: str, opener=urlopen) -> float:
    if expression not in {q for _, q, _ in CASES}:
        raise WolframHold("ZEN0_UNAPPROVED_EXPRESSION")
    if not appid or len(appid) > 256 or any(ch.isspace() for ch in appid):
        raise WolframHold("ZEN0_APPID_REQUIRED")
    query = urlencode({
        "appid": appid, "input": expression,
        "output": "json", "format": "plaintext", "includepodid": "Result",
    })
    req = Request(API_BASE + "?" + query, headers={"User-Agent": "JANUS-ZENO-RESEARCH/1"})
    try:
        with opener(req, timeout=12) as response:
            data = response.read(64001)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise WolframHold("ZEN0_REMOTE_NOT_AVAILABLE") from None
    if len(data) > 64000:
        raise WolframHold("ZEN0_RESPONSE_TOO_LARGE")
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise WolframHold("ZEN0_INVALID_JSON") from None
    return decode_result(result)


def verify(live=False, appid="", opener=urlopen):
    rows = []
    for name, expression, expected in CASES:
        row = {"id": name, "public_expression": expression,
               "our_analytic_expected": expected, "external_checked": live}
        if live:
            result = remote_value(appid, expression, opener=opener)
            row["math_agrees"] = abs(result - expected) <= 1e-9
            if row["math_agrees"] is not True:
                raise WolframHold("ZEN0_WOLFRAM_MATH_DISAGREEMENT")
        rows.append(row)
    return {
        "schema": SCHEMA, "experiment_id": z.EXPERIMENT_ID,
        "mode": "LIVE_READ_ONLY" if live else "OFFLINE_ONLY",
        "status": "WOLFRAM_LIVE_MATH_CHECKED" if live else "NO_LIVE_API_CALL",
        "zeno_standard_qm_report_sha256": report_sha256(),
        "provider": "Wolfram|Alpha Full Results API",
        "provider_documentation": "https://products.wolframalpha.com/api/documentation/",
        "max_live_requests": MAX_LIVE_QUERIES,
        "queries": rows,
        "provider_result_text_or_values_cached": False,
        "future_data_transmitted": False,
        "external_physical_experiment": False,
        "proof_of_retrocausality": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("offline", "live"), default="offline")
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    path = Path(a.output)
    if path.exists():
        raise WolframHold("ZEN0_REFUSE_OVERWRITE")
    live = a.mode == "live"
    appid = os.environ.get("WOLFRAM_ALPHA_APPID", "") if live else ""
    if live and not appid:
        raise WolframHold("WOLFRAM_ALPHA_APPID_REQUIRED")
    record = verify(live, appid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"experiment": z.EXPERIMENT_ID, "wolfram_status": record["status"],
                      "queries": len(record["queries"]), "retrocausality_proven": False}))


if __name__ == "__main__":
    main()
