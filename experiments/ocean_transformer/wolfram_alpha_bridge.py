#!/usr/bin/env python3
"""Read-only Wolfram|Alpha Full Results bridge for JANUS Ocean research.

Offline by default, fixed PUBLIC arithmetic only, no arbitrary LLM queries,
no future targets, no credentials in receipts. A provider answer checks
arithmetic; it is NOT independent evidence for physical retrocausality.
Official API: https://products.wolframalpha.com/api/documentation/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import measurement_priors

API_BASE = "https://api.wolframalpha.com/v2/query"
CASES = (
    ("born_balanced", "sin(pi/4)^2", 0.5),
    ("born_z_zero", "sin(0)^2", 0.0),
    ("dephasing_half", "1-1/2", 0.5),
    ("bell_eight_herald", "(1/2)^8", 1/256),
)
SCHEMA = "janus.ocean.wolfram_alpha_measurement_bridge.v1"


class WolframHold(ValueError):
    pass


def numerical_result(text: str) -> float:
    """Read a simple decimal or fraction from an arithmetic Result pod."""
    s = str(text).strip().replace("−", "-").replace("≈", "").strip()
    match = re.match(r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?(?:\s*/\s*\d+)?)", s)
    if not match:
        raise WolframHold("NO_SCALAR_NUMERIC_RESULT")
    try:
        value = float(Fraction(match.group(1).replace(" ", "")))
    except (ValueError, ZeroDivisionError, OverflowError):
        raise WolframHold("INVALID_SCALAR_NUMERIC_RESULT") from None
    if not math.isfinite(value):
        raise WolframHold("NONFINITE_WOLFRAM_RESULT")
    return value


def decode_result(response: dict) -> float:
    qr = response.get("queryresult", {})
    if qr.get("success") not in (True, "true") or qr.get("error") in (True, "true"):
        raise WolframHold("WOLFRAM_UNSUCCESSFUL")
    pods = qr.get("pods", [])
    if not isinstance(pods, list):
        raise WolframHold("WOLFRAM_INVALID_PODS")
    selected = [
        p for p in pods
        if p.get("primary") in (True, "true") or p.get("id") == "Result"
    ]
    for pod in selected:
        parts = pod.get("subpods", [])
        if isinstance(parts, dict):
            parts = [parts]
        for part in parts:
            try:
                return numerical_result(part.get("plaintext", ""))
            except WolframHold:
                continue
    raise WolframHold("WOLFRAM_RESULT_POD_MISSING")


def remote_number(appid: str, expression: str, opener=urlopen) -> float:
    if expression not in [query for _, query, _ in CASES]:
        raise WolframHold("UNAPPROVED_QUERY")
    if not appid or len(appid) > 256 or any(c.isspace() for c in appid):
        raise WolframHold("INVALID_APPID")
    query = urlencode({
        "appid": appid,
        "input": expression,
        "output": "json",
        "format": "plaintext",
        "includepodid": "Result",
    })
    # AppID appears only in the HTTPS request, never the saved record or errors.
    request = Request(API_BASE + "?" + query, headers={"User-Agent": "JANUS-OCEAN-RESEARCH/1"})
    try:
        with opener(request, timeout=12) as response:
            body = response.read(64001)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise WolframHold("WOLFRAM_TRANSPORT_UNAVAILABLE") from None
    if len(body) > 64000:
        raise WolframHold("WOLFRAM_RESPONSE_OVERSIZED")
    try:
        result = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise WolframHold("WOLFRAM_INVALID_JSON") from None
    return decode_result(result)


def check(*, live: bool, appid: str = "", opener=urlopen) -> dict:
    priors = measurement_priors.report()
    source_digest = hashlib.sha256(json.dumps(
        priors, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    records = []
    for name, expression, expected in CASES:
        row = {
            "id": name, "public_expression": expression,
            "analytical_expected": expected,
            "external_checked": live,
        }
        if live:
            actual = remote_number(appid, expression, opener=opener)
            row["wolfram_numeric_result"] = actual
            row["agrees_with_standard_arithmetic"] = abs(actual-expected) <= 1e-9
            if not row["agrees_with_standard_arithmetic"]:
                raise WolframHold("WOLFRAM_ANALYTICAL_MISMATCH")
        records.append(row)
    return {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "LIVE_READ_ONLY_WOLFRAM_ALPHA" if live else "OFFLINE_REFERENCE_ONLY",
        "status": "EXTERNAL_ARITHMETIC_CHECK_PASS" if live else "NO_EXTERNAL_QUERY_PERFORMED",
        "upstream": {
            "service": "Wolfram|Alpha Full Results API",
            "documentation": "https://products.wolframalpha.com/api/documentation/",
            "authenticated": live,
            "external_data_access": "PUBLIC_ARITHMETIC_ONLY",
        },
        "source_binding": {
            "repo": "Hawkar-usls/Janus-Demiurge",
            "dataset_schema": priors["schema"],
            "canonical_dataset_sha256": source_digest,
        },
        "queries": records,
        "quantum_measurement_simulated": True,
        "collapsing_wavefunction_at_will": False,
        "evidence_of_retrocausality": False,
        "model_weights_updated": False,
        "secret_emitted": False,
        "rowan_style": "bounded read-only evidence council; separate scientific authority",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise WolframHold("REFUSE_OVERWRITE_RECEIPT")
    if args.mode == "live" and not os.environ.get("WOLFRAM_ALPHA_APPID"):
        raise WolframHold("WOLFRAM_ALPHA_APPID_REQUIRED")
    result = check(live=args.mode == "live", appid=os.environ.get("WOLFRAM_ALPHA_APPID", ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": result["schema"], "status": result["status"],
        "public_cases": len(result["queries"]),
        "physical_retrocausality_proven": False
    }, sort_keys=True))


if __name__ == "__main__":
    main()
