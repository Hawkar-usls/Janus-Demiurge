#!/usr/bin/env python3
"""Bounded P-vs-NP evidence ingestion for the existing Demiurge supervisor.

Only source-bound, independently recomputed *finite* invariants are called
checked. The upstream theorem/counterexample claims remain source-reported.
"""
from __future__ import annotations
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import subprocess

from beetle_runtime_consumer import load_context

SCHEMA = "janus.pnp.content_evidence_bundle.v1"
FUNDAMENTUM_STATUS = "docs/CURRENT_RESEARCH_STATUS.md"
TOPA_COUNTEREXAMPLE = "data/TOPA-P-VS-NP-ISSUE-211-REFUTATION-FINAL-2026-08-24-v1.0.json"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceHold(ValueError):
    pass


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def source_sha(root: Path) -> str:
    proc = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                          check=True, capture_output=True, text=True, timeout=10)
    sha = proc.stdout.strip()
    if not SHA40.fullmatch(sha):
        raise EvidenceHold("SOURCE_COMMIT_INVALID")
    return sha


def bounded_file(root: Path, relative: str, maximum: int = 150_000) -> tuple[bytes, str]:
    path = root / relative
    if not path.is_file() or path.is_symlink() or path.resolve().is_relative_to(root.resolve()) is False:
        raise EvidenceHold("SOURCE_PATH_INVALID")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if not raw or len(raw) > maximum:
        raise EvidenceHold("SOURCE_SIZE_LIMIT")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceHold("SOURCE_ENCODING") from exc
    return raw, decoded


def check_a3_finite_enumeration() -> dict:
    # Independent, straightforward enumeration of the claimed 2-state and
    # 3-state mixed-radix DP transition graph (NOT the full A3 theorem).
    checked = []
    for s in range(4):
        for r in range(4):
            radix = (2,) * s + (3,) * r
            states = list(product(*(range(n) for n in radix)))
            directed_edges = sum(
                sum(digit < base - 1 for digit, base in zip(state, radix))
                for state in states
            )
            expected_states = 2 ** s * 3 ** r
            expected_edges = ((s * 2 ** (s - 1) * 3 ** r if s else 0)
                              + (2 * r * 2 ** s * 3 ** (r - 1) if r else 0))
            if len(states) != expected_states or directed_edges != expected_edges:
                raise EvidenceHold("A3_FINITE_IDENTITY_MISMATCH")
            checked.append({"singletons": s, "repeated": r,
                            "state_count": len(states),
                            "transition_count": directed_edges})
    return {"method": "INDEPENDENT_EXPLICIT_MIXED_RADIX_STATE_ENUMERATION",
            "case_count": len(checked), "cases": checked,
            "general_theorem_proved": False}


def check_topa_finite_sink(artifact: dict) -> dict:
    if artifact.get("artifact_id") != "TOPA-P-VS-NP-ISSUE-211-REFUTATION-FINAL-2026-08-24-v1.0" \
            or artifact.get("status") != "REFUTED_FOR_CURRENT_POLICY0A" \
            or artifact.get("mathematical_effect", {}).get("P_VS_NP") != "OPEN" \
            or artifact.get("mathematical_effect", {}).get("P_EQUALS_NP") != "NOT_ESTABLISHED":
        raise EvidenceHold("TOPA_COUNTEREXAMPLE_SCOPE_MISMATCH")
    frozen = artifact.get("ci", {}).get("frozen_n3")
    family = artifact.get("counterfamily", {})
    if not isinstance(frozen, dict) or family.get("name") != "PADDED_DIRECTED_GT_WITH_RESOLUTION_SINK" \
            or family.get("n_min") != 3:
        raise EvidenceHold("TOPA_FROZEN_CASE_INVALID")
    n = 3
    p = 64 * n * n
    B = 256 * n * n
    if family.get("p") != "64*n^2" or family.get("B") != "256*n^2":
        raise EvidenceHold("TOPA_SINK_PARAMETERS_MISMATCH")
    if frozen.get("attempt_budget") != 16 * B + 16 * p or frozen.get("sink_pair_attempts_available") != p * p \
            or frozen.get("resolution_attempts") != frozen.get("attempt_budget") \
            or frozen.get("resolution_additions") != 0 or frozen.get("branch_variable_class") != "GT_CORE":
        raise EvidenceHold("TOPA_FROZEN_N3_NUMERIC_MISMATCH")
    # Completely independent of TOPA's solver: each positive sink clause
    # (d,a,u_i) and negative sink clause (-d,-a,v_j) has tautological d-resolvent
    # (a,-a,u_i,v_j). Loop rather than borrowing a source-reported PASS.
    checked = 0
    for u in range(p):
        for v in range(p):
            positive = {1, 2, 3 + u}
            negative = {-1, -2, 3 + p + v}
            resolvent = (positive - {1}) | (negative - {-1})
            if 2 not in resolvent or -2 not in resolvent:
                raise EvidenceHold("TOPA_SINK_RESOLVENT_NOT_TAUTOLOGY")
            checked += 1
    if checked != p * p or not frozen["attempt_budget"] < checked:
        raise EvidenceHold("TOPA_SINK_STARVATION_MISMATCH")
    return {"method": "INDEPENDENT_SINK_PAIR_RESOLVENT_ENUMERATION",
            "n": n, "sink_pair_resolvents_checked": checked,
            "attempt_budget": frozen["attempt_budget"],
            "all_sink_resolvents_tautological": True,
            "source_refutation_proved_from_finite_check": False,
            "full_policy0a_replay_executed": False}


def check_beetle(context_path: Path, ack_path: Path, commit: str) -> dict:
    if not SHA40.fullmatch(commit):
        raise EvidenceHold("BEETLE_SOURCE_COMMIT_INVALID")
    ctx = load_context(context_path)  # existing canonical hash and capability validator
    ack = json.loads(ack_path.read_text(encoding="utf-8"))
    if not isinstance(ack, dict) or ack.get("schema") != "janus.beetle.processing_ack.v1" \
            or ack.get("status") != "TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED" \
            or ack.get("target_repository") != "Hawkar-usls/Janus-Demiurge" \
            or type(ack.get("last_sequence")) is not int \
            or ack["last_sequence"] != ctx["last_processed_sequence"] \
            or not isinstance(ack.get("receipt_sha256"), str) \
            or not SHA64.fullmatch(ack["receipt_sha256"]):
        raise EvidenceHold("BEETLE_CONTEXT_ACK_MISMATCH")
    routes = []
    for item in ctx["research_routes"]:
        # Route data is untrusted and never used as executable code.
        url, title = item.get("source_url"), item.get("title")
        if not isinstance(url, str) or not url.startswith("https://") \
                or not isinstance(title, str) or not title.strip() \
                or not isinstance(item.get("direction_id"), str):
            raise EvidenceHold("BEETLE_UNSAFE_ROUTE")
        routes.append({
            "candidate_id": item["candidate_id"],
            "source_url": url,
            "direction_id": item["direction_id"],
            "title": title,
            "input_sha256": item["input_sha256"],
            "status": "DISCOVERY_ONLY_NOT_INDEPENDENT_EVIDENCE",
        })
    return {"source_commit": commit,
            "source_context_sha256": ctx["context_sha256"],
            "last_processed_sequence": ctx["last_processed_sequence"],
            "last_processing_receipt_sha256": ack["receipt_sha256"],
            "routes": routes,
            "route_count": len(routes),
            "receipt_bytes_replayed": False,
            "independent_source_truth_established": False}


def build(fundamentum: Path, topa: Path, beetle_context: Path, beetle_ack: Path,
          beetle_commit: str) -> dict:
    f_head, t_head = source_sha(fundamentum), source_sha(topa)
    f_raw, f_text = bounded_file(fundamentum, FUNDAMENTUM_STATUS)
    if re.search(r"(?m)^P_VS_NP\s*=\s*OPEN\s*$", f_text) is None \
            or "2^s * 3^r" not in f_text \
            or "GENERAL_MATROID_PATHWIDTH_COMPLEXITY = UNCHANGED" not in f_text:
        raise EvidenceHold("FUNDAMENTUM_STATUS_OR_A3_SOURCE_MISMATCH")
    t_raw, t_text = bounded_file(topa, TOPA_COUNTEREXAMPLE)
    try:
        t_case = json.loads(t_text)
    except json.JSONDecodeError as exc:
        raise EvidenceHold("TOPA_SOURCE_NOT_JSON") from exc
    if not isinstance(t_case, dict):
        raise EvidenceHold("TOPA_SOURCE_NOT_OBJECT")
    f_check = check_a3_finite_enumeration()
    t_check = check_topa_finite_sink(t_case)
    beetle = check_beetle(beetle_context, beetle_ack, beetle_commit)
    obj = {
        "schema": SCHEMA, "status": "BOUNDED_SOURCE_CONTENT_REPLAYED",
        "p_vs_np": "OPEN",
        "fundamentum": {
            "repository": "Hawkar-usls/Janus-Fundamentum",
            "source_commit": f_head, "path": FUNDAMENTUM_STATUS,
            "sha256": hashlib.sha256(f_raw).hexdigest(),
            "source_research_claim": "A3_SCOPED_RESULT_AND_C023_OPEN",
            "independent_finite_replay": f_check,
        },
        "topa": {
            "repository": "Hawkar-usls/TOPA",
            "source_commit": t_head, "path": TOPA_COUNTEREXAMPLE,
            "sha256": hashlib.sha256(t_raw).hexdigest(),
            "targeted_hypothesis": "C024_POLICY0A_RESIDUAL_POLYNOMIAL_BOUND",
            "source_reported_result": "REFUTED_FOR_CURRENT_POLICY0A",
            "independent_finite_replay": t_check,
            "global_p_vs_np_result": "OPEN",
        },
        "beetle": beetle,
        "research_handback": {
            "JANUS-PNP-POLY-SAT-CANDIDATE": [
                "TOPA:C024_POLICY0A_RESIDUAL_POLYNOMIAL_BOUND",
                "FUNDAMENTUM:A3_SCOPED_DP_COUNTS",
            ],
            "JANUS-C023-SIMULATION-ATTACK": [
                "TOPA:C024_POLICY0A_RESIDUAL_POLYNOMIAL_BOUND",
                "BEETLE:DISCOVERY_ROUTES_NOT_PROOF",
            ],
            "JANUS-C023-REASON-REUSE-ATTACK": [
                "TOPA:C024_POLICY0A_RESIDUAL_POLYNOMIAL_BOUND",
            ],
        },
        "authority": {
            "is_universal_proof": False, "promote_p_vs_np": False,
            "scientific_promotion": False, "mutate_fundamentum": False,
            "autonomous_merge": False, "beetle_candidates_are_truth": False,
            "finite_replay_proves_asymptotics": False,
        },
        "independence_limit": "A3 formula enumeration and TOPA sink algebra were recomputed "
                              "independently in this adapter; full source theorems, "
                              "Policy-0A behavior, upstream proofs, and Beetle external "
                              "sources have NOT been independently reproduced.",
    }
    obj["bundle_sha256"] = digest(obj)
    return obj


def validate_bundle(obj: object, expected_fundamentum_commit: str) -> dict:
    if not isinstance(obj, dict) or obj.get("schema") != SCHEMA \
            or obj.get("status") != "BOUNDED_SOURCE_CONTENT_REPLAYED" \
            or obj.get("p_vs_np") != "OPEN":
        raise EvidenceHold("EVIDENCE_BUNDLE_SCHEMA_OR_SCOPE")
    signed = dict(obj)
    supplied_digest = signed.pop("bundle_sha256", None)
    if not isinstance(supplied_digest, str) or digest(signed) != supplied_digest:
        raise EvidenceHold("EVIDENCE_BUNDLE_DIGEST")
    f = obj.get("fundamentum")
    t = obj.get("topa")
    b = obj.get("beetle")
    if not isinstance(f, dict) or f.get("source_commit") != expected_fundamentum_commit \
            or not isinstance(t, dict) or not SHA40.fullmatch(str(t.get("source_commit"))) \
            or not isinstance(b, dict) or not SHA40.fullmatch(str(b.get("source_commit"))):
        raise EvidenceHold("EVIDENCE_BUNDLE_SOURCE_MISMATCH")
    a = obj.get("authority")
    if not isinstance(a, dict) or set(a) != {
        "is_universal_proof", "promote_p_vs_np", "scientific_promotion",
        "mutate_fundamentum", "autonomous_merge", "beetle_candidates_are_truth",
        "finite_replay_proves_asymptotics",
    } or any(v is not False for v in a.values()):
        raise EvidenceHold("EVIDENCE_BUNDLE_AUTHORITY_DRIFT")
    if not isinstance(obj.get("research_handback"), dict) \
            or t.get("source_reported_result") != "REFUTED_FOR_CURRENT_POLICY0A" \
            or t.get("global_p_vs_np_result") != "OPEN" \
            or t.get("independent_finite_replay", {}).get("full_policy0a_replay_executed") is not False \
            or f.get("independent_finite_replay", {}).get("general_theorem_proved") is not False \
            or b.get("independent_source_truth_established") is not False:
        raise EvidenceHold("EVIDENCE_BUNDLE_PROMOTION_MISCLASSIFICATION")
    return obj


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--fundamentum", type=Path, required=True)
    cli.add_argument("--topa", type=Path, required=True)
    cli.add_argument("--beetle-context", type=Path, required=True)
    cli.add_argument("--beetle-ack", type=Path, required=True)
    cli.add_argument("--beetle-commit", required=True)
    cli.add_argument("--out", type=Path, required=True)
    args = cli.parse_args()
    bundle = build(args.fundamentum, args.topa, args.beetle_context,
                   args.beetle_ack, args.beetle_commit)
    validate_bundle(bundle, bundle["fundamentum"]["source_commit"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": bundle["status"], "bundle_sha256": bundle["bundle_sha256"],
                      "topa_sink_pairs": bundle["topa"]["independent_finite_replay"]["sink_pair_resolvents_checked"],
                      "beetle_sequence": bundle["beetle"]["last_processed_sequence"],
                      "p_vs_np": bundle["p_vs_np"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
