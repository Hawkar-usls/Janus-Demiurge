"""Independent, model-free quality screening of JANUS's tiny native LM output.

This is NOT a semantic correctness judge. Failing outputs remain archived as
negative evidence, and passing outputs remain unverified proposals. Never
promotes model truth, code, weights, or training sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "janus.native.inference_structural_quality.v1"
TOKEN = re.compile(r"\b[\w-]{2,}\b", re.UNICODE)
RESPONSE_MARKER = "\nJANUS:"
MAX_INPUT_BYTES = 150_000


def assess(text: str) -> dict:
    if not isinstance(text, str):
        raise ValueError("NATIVE_QUALITY_TEXT_REQUIRED")
    raw = text.encode("utf-8", errors="replace")
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("NATIVE_QUALITY_OVERSIZE_HOLD")
    reasons = []
    response = text.rsplit(RESPONSE_MARKER, 1)[-1] if RESPONSE_MARKER in text else ""
    if RESPONSE_MARKER not in text:
        reasons.append("MISSING_ASSISTANT_MARKER")
    response = response.strip()
    if not response or len(response) < 32:
        reasons.append("TOO_SHORT")
    if not response or sum(ch.isprintable() or ch in "\n\t" for ch in response) / max(len(response), 1) < 0.95:
        reasons.append("CONTROL_CHARACTER_RATIO")
    if response.count("\ufffd") > 0:
        reasons.append("INVALID_UNICODE_REPLACEMENT")
    tokens = TOKEN.findall(response)
    if len(tokens) < 6:
        reasons.append("INSUFFICIENT_LEXICAL_SIGNAL")
    if response:
        # Byte-token text often degenerates into punctuation or raw code fragments.
        alpha_fraction = sum(ch.isalpha() for ch in response) / len(response)
        if alpha_fraction < 0.3:
            reasons.append("LOW_ALPHABETIC_FRACTION")
    # This is a structural check only. Not all valid prose is JSON.
    stripped = response.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
        except (ValueError, TypeError):
            reasons.append("TRUNCATED_OR_INVALID_JSON")
    if response.count('"') % 2 != 0:
        reasons.append("UNBALANCED_DOUBLE_QUOTE")
    # Detect exact prompt/control payload echo, not semantic repetition.
    if RESPONSE_MARKER in text:
        head = text.rsplit(RESPONSE_MARKER, 1)[0]
        if response and response in head:
            reasons.append("ECHO_OF_INPUT_CONTEXT")
    status = "LOW_SIGNAL_HOLD" if reasons else "STRUCTURAL_CANDIDATE_UNVERIFIED"
    return {
        "schema": SCHEMA,
        "status": status,
        "reasons": sorted(set(reasons)),
        "native_output_sha256": hashlib.sha256(raw).hexdigest(),
        "response_chars": len(response),
        "response_tokens_heuristic": len(tokens),
        "model_truth": False,
        "model_output_is_independent_evidence": False,
        "eligible_for_training": False,
        "eligible_for_autonomous_merge": False,
        "semantic_quality_verified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.input.is_symlink() or a.input.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("NATIVE_QUALITY_INPUT_REFUSED")
    result = assess(a.input.read_text(encoding="utf-8", errors="replace"))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    # A quality witness is append-only and never overwrites native output.
    with a.out.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"status": result["status"],
                      "reasons": result["reasons"],
                      "sha256": result["native_output_sha256"]}))


if __name__ == "__main__":
    main()
