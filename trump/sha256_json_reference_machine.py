#!/usr/bin/env python3
"""Executable positive control for the TRUMP PCNER_GPEI contract.

This module interprets the frozen SHA-256 JSON machine as a deterministic
route law.  It is intentionally *not* a SAT solver and never promotes any
P-vs-NP claim.  The control demonstrates what FIND/HOLD/ADVANCE look like
when the next transition and a polynomially bounded rank are actually known.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MASK = 0xFFFFFFFF
SPEC_PATH = Path(__file__).resolve().parent / "reference" / "sha256_json_reference_machine.v1.json"


def rotr(x: int, n: int) -> int:
    return ((x >> n) | ((x << (32 - n)) & MASK)) & MASK


def ch(x: int, y: int, z: int) -> int:
    return (x & y) ^ ((~x) & z)


def maj(x: int, y: int, z: int) -> int:
    return (x & y) ^ (x & z) ^ (y & z)


def big_sigma0(x: int) -> int:
    return rotr(x, 2) ^ rotr(x, 13) ^ rotr(x, 22)


def big_sigma1(x: int) -> int:
    return rotr(x, 6) ^ rotr(x, 11) ^ rotr(x, 25)


def small_sigma0(x: int) -> int:
    return rotr(x, 7) ^ rotr(x, 18) ^ (x >> 3)


def small_sigma1(x: int) -> int:
    return rotr(x, 17) ^ rotr(x, 19) ^ (x >> 10)


def load_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec["schema"] != "janus.trump.reference.sha256_json_machine.v1":
        raise ValueError("unexpected SHA-256 reference schema")
    if spec["typed_semantics"]["word_type"] != "uint32":
        raise ValueError("reference machine must explicitly use uint32")
    if spec["typed_semantics"]["arithmetic"] != "mod_2^32":
        raise ValueError("reference machine must explicitly use mod_2^32")
    if len(spec["round_constants_hex"]) != 64:
        raise ValueError("SHA-256 requires exactly 64 round constants")
    return spec


def pad(message: bytes) -> bytes:
    bit_len = len(message) * 8
    out = bytearray(message)
    out.append(0x80)
    while len(out) % 64 != 56:
        out.append(0)
    out.extend(bit_len.to_bytes(8, "big"))
    return bytes(out)


def execute(message: bytes, *, include_round_receipts: bool = False) -> dict[str, Any]:
    spec = load_spec()
    h = [int(x, 16) for x in spec["initial_hash_words_hex"]]
    k = [int(x, 16) for x in spec["round_constants_hex"]]
    padded = pad(message)
    blocks = len(padded) // 64
    total_rounds = blocks * 64
    completed = 0
    max_working_words = 0
    round_receipts: list[dict[str, Any]] = []

    for block_index in range(blocks):
        block = padded[block_index * 64 : (block_index + 1) * 64]
        w = [int.from_bytes(block[i : i + 4], "big") for i in range(0, 64, 4)]
        for t in range(16, 64):
            w.append((small_sigma1(w[t - 2]) + w[t - 7] + small_sigma0(w[t - 15]) + w[t - 16]) & MASK)
        max_working_words = max(max_working_words, 8 + len(w))

        a, b, c, d, e, f, g, hh = h
        for t in range(64):
            mu_before = total_rounds - completed
            t1 = (hh + big_sigma1(e) + ch(e, f, g) + k[t] + w[t]) & MASK
            t2 = (big_sigma0(a) + maj(a, b, c)) & MASK
            a, b, c, d, e, f, g, hh = (
                (t1 + t2) & MASK,
                a,
                b,
                c,
                (d + t1) & MASK,
                e,
                f,
                g,
            )
            completed += 1
            mu_after = total_rounds - completed
            if mu_after != mu_before - 1:
                raise AssertionError("NO_HOTEL_CALIFORNIA: reference rank failed strict unit descent")
            if include_round_receipts:
                round_receipts.append(
                    {
                        "block": block_index,
                        "round": t,
                        "mu_before": mu_before,
                        "mu_after": mu_after,
                        "working_state_hex": [f"{x:08x}" for x in (a, b, c, d, e, f, g, hh)],
                    }
                )

        h = [
            (h[0] + a) & MASK,
            (h[1] + b) & MASK,
            (h[2] + c) & MASK,
            (h[3] + d) & MASK,
            (h[4] + e) & MASK,
            (h[5] + f) & MASK,
            (h[6] + g) & MASK,
            (h[7] + hh) & MASK,
        ]

    digest_hex = "".join(f"{x:08x}" for x in h)
    reference_hex = hashlib.sha256(message).hexdigest()
    exact_match = digest_hex == reference_hex
    if not exact_match:
        raise AssertionError("JSON route disagrees with independent hashlib verifier")

    receipt: dict[str, Any] = {
        "schema": "janus.trump.reference.sha256_json_route_receipt.v1",
        "terminal": "SHA256_JSON_PCNER_POSITIVE_CONTROL_PASS",
        "message_bytes": len(message),
        "padded_blocks": blocks,
        "rounds_executed": completed,
        "initial_rank": total_rounds,
        "final_rank": total_rounds - completed,
        "rank_strict_unit_descent": True,
        "candidate_next_action_count_per_round": 1,
        "max_working_words_observed": max_working_words,
        "declared_working_words_upper_bound": spec["pcner_positive_control"]["POLY_HOLD"]["working_words_upper_bound"],
        "digest_hex": digest_hex,
        "independent_hashlib_digest_hex": reference_hex,
        "exact_match": exact_match,
        "pcner_axes": {
            "POLY_FIND": "PASS_FOR_SHA256_CONTROL",
            "POLY_HOLD": "PASS_FOR_SHA256_CONTROL",
            "POLY_ADVANCE": "PASS_FOR_SHA256_CONTROL",
            "EXACTNESS_CERTIFICATION": "PASS_FOR_FINITE_CONTROL_VECTORS_AND_HASHLIB_REPLAY",
            "DEBT_RESOURCE_ACCOUNTING": "PASS_FOR_DECLARED_CONTROL_EXECUTION"
        },
        "scientific_boundary": {
            "SAT_transfer_claimed": False,
            "universal_GPEI_for_SAT_proved": False,
            "P_equals_NP_proved": False,
            "P_VS_NP": "OPEN"
        }
    }
    if max_working_words > spec["pcner_positive_control"]["POLY_HOLD"]["working_words_upper_bound"]:
        raise AssertionError("working-state bound exceeded frozen JSON declaration")
    if include_round_receipts:
        receipt["round_receipts"] = round_receipts
    return receipt


def selftest() -> dict[str, Any]:
    spec = load_spec()
    results = []
    for vector in spec["known_test_vectors"]:
        message = vector["message_utf8"].encode("utf-8")
        receipt = execute(message)
        if receipt["digest_hex"] != vector["digest_hex"]:
            raise AssertionError("published SHA-256 vector mismatch")
        results.append(
            {
                "message_bytes": len(message),
                "digest_hex": receipt["digest_hex"],
                "rounds_executed": receipt["rounds_executed"],
                "initial_rank": receipt["initial_rank"],
                "final_rank": receipt["final_rank"]
            }
        )
    return {
        "terminal": "SHA256_JSON_REFERENCE_MACHINE_SELFTEST_PASS",
        "vectors_passed": len(results),
        "vectors": results,
        "scientific_boundary": "P_VS_NP_OPEN"
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--text", default=None)
    parser.add_argument("--round-receipts", action="store_true")
    args = parser.parse_args()
    if args.selftest or args.text is None:
        out = selftest()
    else:
        out = execute(args.text.encode("utf-8"), include_round_receipts=args.round_receipts)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
