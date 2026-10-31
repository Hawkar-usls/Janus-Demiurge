"""Strict shared Copilot preflight: only an assistant JSON result grants model access.

A prompt echo, user.message, or CLI diagnostic containing PASS is NOT an
assistant response. A failed preflight never unlocks model calls or evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from demiurge_scout_swarm import extract_copilot_jsonl


def classify(raw: str, return_code: int) -> dict:
    lower = raw.lower()
    if "quota_exceeded" in lower or "exceeded your monthly quota" in lower:
        return {"model_status": "QUOTA_EXHAUSTED", "failure_reason": "rate_limit"}
    if any(k in lower for k in ("was removed", "unknown option",
                               "unknown flag", "unrecognized option")):
        return {"model_status": "UNAVAILABLE", "failure_reason": "invalid_cli_argument"}
    if return_code != 0:
        return {"model_status": "UNAVAILABLE", "failure_reason": "upstream_tool_failure"}
    try:
        response = extract_copilot_jsonl(raw)
    except (ValueError, json.JSONDecodeError):
        response = None
    # Strictly require a JSONL assistant message. Do not accept an unstructured
    # plain-text fallback containing the prompt. The caller invoked --output-format=json.
    assistant_seen = any(
        isinstance(item, dict) and item.get("type") == "assistant.message"
        for line in raw.splitlines()
        for item in (_parse(line),)
    )
    if assistant_seen and response == {"preflight": "PASS"}:
        return {"model_status": "AVAILABLE", "failure_reason": "none"}
    return {"model_status": "UNAVAILABLE", "failure_reason": "invalid_output_format"}


def _parse(line: str):
    try:
        return json.loads(line)
    except (ValueError, TypeError):
        return None


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--return-code", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.log.stat().st_size > 2_000_000:
        data = {"model_status": "UNAVAILABLE", "failure_reason": "oversized_cli_log"}
    else:
        data = classify(a.log.read_text(encoding="utf-8", errors="replace"), a.return_code)
    a.output.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    print("JANUS_SCOUT_MODEL_PREFLIGHT=%s reason=%s" %
          (data["model_status"], data["failure_reason"]))


if __name__ == "__main__":
    main()
