#!/usr/bin/env python3
"""Bounded, read-only Wolfram|Alpha math advisory source for JANUS Ocean.

Uses the official Full Results JSON API with a fixed six-query allowlist.
Never sends prompts, private observations, model weights, future random bytes,
or secrets to Wolfram|Alpha. Authentication comes ONLY from environment.

Wolfram is a computational cross-check of predeclared ordinary math, not
an independent physical retrocausality witness or quantum measurement device.
The provider's response is not cryptographically signed by this client.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.wolframalpha.com/v2/query"
SCHEMA = "janus.ocean.wolfram_math_source.v1"
EXPECTED = (
    ("born_plus_x", "cos(pi/4)^2", Fraction(1, 2)),
    ("born_plus_y", "sin(pi/4)^2", Fraction(1, 2)),
    ("unitary_norm", "cos(pi/4)^2+sin(pi/4)^2", Fraction(1, 1)),
    ("dephasing_x", "1/2-(1-1/2)*cos(0)/2", Fraction(1, 4)),
    ("phase_y", "1/2-(1-1/2)*sin(pi/2)/2", Fraction(1, 4)),
    ("postselection_rate", "1/256", Fraction(1, 256)),
)
MAX_RESPONSE_BYTES = 180_000
MAX_QUERIES = 6
TOLERANCE = 1e-7
STATUS_LIVE = "PROVIDER_VERIFIED_NUMERIC_CONTROLS"
STATUS_FIXTURE = "OFFLINE_FIXTURES_ONLY"
GATE = "READ_ONLY_ADVISORY__NOT_FUTURE_INFORMATION__NO_AUTO_PROMOTION"


def query_digest(input_text: str) -> str:
    return hashlib.sha256(input_text.encode("utf-8")).hexdigest()


def as_number(value: str) -> float:
    """Accept only literal real numbers, decimals, and rational fractions."""
    s = value.strip().replace("\u2212", "-").replace("\u2009", "").replace(" ", "")
    if re.fullmatch(r"[+-]?\d+/\d+", s):
        x = float(Fraction(s))
    elif re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", s):
        try:
            x = float(Decimal(s))
        except InvalidOperation:
            raise ValueError("NON_NUMERIC_PROVIDER_RESULT") from None
    else:
        raise ValueError("NON_NUMERIC_PROVIDER_RESULT")
    if not (-1e15 < x < 1e15):
        raise ValueError("NONFINITE_OR_UNBOUNDED")
    return x


def extract_result(response: dict) -> float:
    result = response.get("queryresult")
    if not isinstance(result, dict) or result.get("success") is not True or result.get("error"):
        raise ValueError("PROVIDER_REJECTED_QUERY")
    pods = result.get("pods", [])
    if isinstance(pods, dict):
        pods = [pods]
    if not isinstance(pods, list):
        raise ValueError("BAD_PROVIDER_PODS")
    for podid in ("Result", "DecimalApproximation", "DecimalForm"):
        for pod in pods:
            if not isinstance(pod, dict) or pod.get("id") != podid:
                continue
            subs = pod.get("subpods", [])
            if isinstance(subs, dict):
                subs = [subs]
            if not isinstance(subs, list):
                raise ValueError("BAD_PROVIDER_SUBPODS")
            for item in subs:
                if not isinstance(item, dict):
                    continue
                plaintext = item.get("plaintext")
                if isinstance(plaintext, str):
                    try:
                        return as_number(plaintext)
                    except ValueError:
                        pass
    raise ValueError("NO_STRICT_NUMERIC_PROVIDER_RESULT")


def validate_case(case, response: dict) -> dict:
    case_id, query, expected = case
    value = extract_result(response)
    if abs(value - float(expected)) > TOLERANCE:
        raise ValueError("INDEPENDENT_MATH_DISAGREEMENT:" + case_id)
    return {
        "id": case_id, "input_sha256": query_digest(query),
        "expected": f"{expected.numerator}/{expected.denominator}",
        "computed": format(value, ".12g"), "validated": True,
        "provider_response_sha256": hashlib.sha256(
            json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def fixture_response(expected: Fraction) -> dict:
    return {
        "queryresult": {
            "success": True, "error": False,
            "pods": [{"id": "Result", "subpods": [{"plaintext": str(expected)}]}],
        }
    }


def query_provider(query: str, appid: str) -> dict:
    if not appid or not appid.strip():
        raise ValueError("MISSING_WOLFRAM_ALPHA_APPID")
    if query not in {q for _, q, _ in EXPECTED}:
        raise ValueError("UNAPPROVED_QUERY")
    params = urllib.parse.urlencode({
        "appid": appid, "input": query, "output": "json", "format": "plaintext",
        "scantimeout": "4", "totaltimeout": "12",
    })
    request = urllib.request.Request(
        BASE + "?" + params,
        headers={"User-Agent": "JANUS-Ocean-Math-Witness/1.0", "Accept": "application/json"},
        method="GET",
    )
    # Do not leak the credential-bearing URL from urllib exception strings.
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("WOLFRAM_PROVIDER_REQUEST_FAILED") from None
    if len(payload) > MAX_RESPONSE_BYTES:
        raise RuntimeError("WOLFRAM_PROVIDER_RESPONSE_TOO_LARGE")
    try:
        return json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ValueError("INVALID_PROVIDER_JSON") from None


def create_report(live=False, appid=None) -> dict:
    if len(EXPECTED) > MAX_QUERIES:
        raise RuntimeError("QUERY_BUDGET_EXCEEDED")
    if live and not appid:
        raise RuntimeError("LIVE_PROVIDER_APPID_REQUIRED")
    results = []
    for case in EXPECTED:
        response = query_provider(case[1], appid) if live else fixture_response(case[2])
        results.append(validate_case(case, response))
    return {
        "schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Wolfram|Alpha Full Results API" if live else "local deterministic fixtures",
        "provider_endpoint": BASE if live else None,
        "mode": "LIVE_READ_ONLY" if live else "OFFLINE_TEST_ONLY",
        "status": STATUS_LIVE if live else STATUS_FIXTURE,
        "source_authenticated": False,
        "explanation": "HTTPS result is checked numerically but not cryptographically signed by provider",
        "cases": results,
        "request_count": len(results) if live else 0,
        "bounded_max_requests": MAX_QUERIES,
        "queried_future_data": False,
        "private_inputs_transmitted": False,
        "physical_retrocausality": False,
        "production_model_updated": False,
        "model_promotion_allowed": False,
        "authority": GATE,
    }


def validate_certificate(report: dict) -> None:
    """Fail closed: offline mocks cannot be misrepresented as a live source."""
    if (report.get("schema") != SCHEMA or report.get("status") != STATUS_LIVE
            or report.get("mode") != "LIVE_READ_ONLY"
            or report.get("model_promotion_allowed") is not False
            or report.get("physical_retrocausality") is not False
            or report.get("queried_future_data") is not False
            or report.get("request_count") != len(EXPECTED)):
        raise ValueError("NOT_A_VALID_LIVE_WOLFRAM_CERTIFICATE")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != len(EXPECTED):
        raise ValueError("INVALID_PROVIDER_CASE_COUNT")
    for pair, row in zip(EXPECTED, cases):
        if (not isinstance(row, dict) or row.get("id") != pair[0]
                or row.get("input_sha256") != query_digest(pair[1])
                or row.get("expected") != f"{pair[2].numerator}/{pair[2].denominator}"
                or row.get("validated") is not True):
            raise ValueError("PROVIDER_CERTIFICATE_DRIFT")
        try:
            value = as_number(str(row["computed"]))
        except (KeyError, ValueError):
            raise ValueError("BAD_PROVIDER_CERTIFICATE_VALUE") from None
        if abs(value - float(pair[2])) > TOLERANCE:
            raise ValueError("WRONG_PROVIDER_CERTIFICATE_VALUE")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="Explicit opt-in to credentialed provider")
    ap.add_argument("--out", type=Path, default=Path("artifacts/wolfram_math_evidence.json"))
    args = ap.parse_args()
    result = create_report(live=args.live, appid=os.environ.get("WOLFRAM_ALPHA_APPID"))
    if args.live:
        validate_certificate(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "mode": result["mode"],
        "math_cases_passed": len(result["cases"]),
        "requests": result["request_count"], "destination": str(args.out),
        "authority": GATE,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
