#!/usr/bin/env python3
"""ESSENCE v3.6 JUXTAPOSE: bounded exact-backed research microkernel.

Reengineered from JANUS-Fundamentum JUXTAPOSE 250:250 exact search and
Meta Registry's Keymaster/PIPPI COLD/WARM/HOT search contract.
Legacy modules are NOT imported, loaded, or executed.

Learning may change search *order/width*, never exact outcomes. All accepted
CNF transitions are independently truth-table replayed for <=6 variables.
Unknown, cap overflow, failed proof, or missing receipts never become truth.
This is research organogenesis only: no model update, theorem, or module
production activation.
"""
from __future__ import annotations

import argparse
from itertools import product
import hashlib
import json
from pathlib import Path

from tools import essence_v32_keymaster_memory as km
from tools import essence_v33_epistemic_exchange as spi

SCHEMA = "janus.essence.juxtapose_exact_microcore/3.6"
CASES_SCHEMA = "janus.essence.juxtapose_frozen_cases/3.6"
SOURCE_CODE = {
    "repo": "Hawkar-usls/Janus-Fundamentum",
    "branch": "research/janus-keymaster-calibration-pivot-slime-topa-2026-08-28",
    "path": "experiments/mad_lab/juxtapose_250x250_exact.py",
    "git_blob_sha1": "0b2325d8207440a12413edc05351c1bae269dd2f",
}
SOURCES = {
    "calibration_json": {
        "repo": "Hawkar-usls/janus-meta-registry",
        "path": "data/JANUS-KEYMASTER-JUXTAPOSE-PIVOT-SLIME-M2R-TOPA-CALIBRATION-2026-08-28-v1.0.json",
        "git_blob_sha1": "7b1f45b1b575cc16460b13362b9fab039f6188a1",
    },
    "pippi_checkpoint": {
        "repo": "Hawkar-usls/janus-meta-registry",
        "path": "data/JANUS-PIPPI-WARM-INSTINCTIVE-JUXTAPOSE-V3-2026-08-28.json",
        "git_blob_sha1": "a72936f598c15b4470875928f51008c260bbdab5",
    },
}
ROOT = "0" * 64
MAX_VARIABLES = 6
MAX_CLAUSES = 48
MAX_CASES = 8
MAX_CAP = 50_000


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def require(cond, code):
    if not cond:
        raise ValueError(code)


def normalize(clauses):
    require(isinstance(clauses, list) and len(clauses) <= MAX_CLAUSES,
            "JUXTAPOSE_CLAUSE_BOUND")
    raw = []
    for clause in clauses:
        require(isinstance(clause, list) and len(clause) <= MAX_VARIABLES
                and all(type(v) is int and 0 < abs(v) <= MAX_VARIABLES
                        for v in clause), "INVALID_CNF_LITERAL")
        s = frozenset(clause)
        # Drop tautological clauses; they are true under every assignment.
        if any(-v in s for v in s):
            continue
        raw.append(s)
    unique = sorted(set(raw), key=lambda c: (len(c), sorted(c)))
    reduced = []
    for clause in unique:
        if not any(existing <= clause for existing in reduced):
            reduced.append(clause)
    return tuple(sorted((tuple(sorted(c)) for c in reduced)))


def truth(cnf, assignment):
    return all(any(assignment[abs(v)] == (v > 0) for v in clause)
               for clause in cnf)


def exact_exists_replay(before, after, pivot):
    others = sorted({abs(v) for c in before for v in c} - {pivot})
    require(len(others) <= MAX_VARIABLES - 1, "EXACT_REPLAY_VAR_LIMIT")
    for values in product((False, True), repeat=len(others)):
        state = dict(zip(others, values))
        expected = (
            truth(before, dict(state, **{pivot: False})) or
            truth(before, dict(state, **{pivot: True}))
        )
        observed = truth(after, state)
        if observed != expected:
            return False
    return True


def raw_units(cnf):
    return 1 + sum(1 + len(c) for c in cnf)


def cheap_score(cnf, pivot):
    pos = [c for c in cnf if pivot in c]
    neg = [c for c in cnf if -pivot in c]
    # Source-informed structural features, never numeric ID as a model feature.
    # Numeric pivot only tie-breaks exact equal feature values.
    return (len(pos) * len(neg), len(pos) + len(neg),
            sum(len(c) for c in pos + neg))


def transition(cnf, pivot, cap):
    require(type(cap) is int and 1 <= cap <= MAX_CAP, "INVALID_RAW_RESOURCE_CAP")
    available = {abs(v) for c in cnf for v in c}
    require(pivot in available, "UNKNOWN_PIVOT")
    positives = [frozenset(c) for c in cnf if pivot in c]
    negatives = [frozenset(c) for c in cnf if -pivot in c]
    retained = [frozenset(c) for c in cnf if pivot not in c and -pivot not in c]
    work = len(positives) * len(negatives)
    # Verify exact root transition from all pairwise resolvents; do not
    # substitute predictions for resolution or finite truth-table replay.
    resolvents = set()
    tautologies = 0
    for pos in positives:
        for neg in negatives:
            resolvent = (pos - {pivot}) | (neg - {-pivot})
            if any(-lit in resolvent for lit in resolvent):
                tautologies += 1
                continue
            resolvents.add(frozenset(resolvent))
    raw = tuple(sorted([tuple(sorted(x)) for x in set(retained) | resolvents]))
    charged = raw_units(raw)
    base = {"pivot": pivot, "pair_work": work,
            "tautological_pairs": tautologies,
            "raw_units_before_canonical_compression": charged,
            "cap": cap, "raw_resolvents": len(resolvents),
            "exact_replay_required": True}
    if charged > cap:
        receipt = dict(base, status="OVERFLOW", exact_verified=False,
                       resulting_cnf_sha256=None)
        receipt["receipt_sha256"] = seal(receipt)
        return receipt
    after = normalize([list(c) for c in raw])
    require(exact_exists_replay(cnf, after, pivot),
            "EXACT_EXISTENTIAL_REPLAY_MISMATCH")
    state = "TERMINAL_UNSAT" if () in after else "SAFE"
    receipt = dict(base, status=state, exact_verified=True,
                   canonical_units=raw_units(after),
                   resulting_cnf_sha256=seal(after))
    receipt["receipt_sha256"] = seal(receipt)
    return receipt


def search_mode(authority, independent_exact_epochs):
    require(type(authority) in (int, float) and 0 <= authority <= 1,
            "INVALID_ADVISER_AUTHORITY")
    require(type(independent_exact_epochs) is int and independent_exact_epochs >= 0,
            "INVALID_EPOCH_SUPPORT")
    # PIPPI checkpoint v3: 0.42/0.70 thresholds. There is currently no
    # source-bound independent per-geometry epoch support in ESSENCE memory.
    if authority < 0.42 or independent_exact_epochs < 2:
        return "COLD_JUXTAPOSE_FULL"
    if authority < 0.70 or independent_exact_epochs < 3:
        return "WARM_JUXTAPOSE_HYBRID"
    return "HOT_PREDICTIVE"


def field_search(clauses, cap, *, authority=0.0, independent_exact_epochs=0):
    cnf = normalize(clauses)
    pivots = sorted({abs(v) for c in cnf for v in c})
    require(pivots and len(pivots) <= MAX_VARIABLES,
            "NO_NONTERMINAL_ROOT_PIVOTS")
    mode = search_mode(authority, independent_exact_epochs)
    ranked = sorted(pivots, key=lambda p: (cheap_score(cnf, p), p))
    # Cold measures every clone; warm's first wave diversifies coverage by
    # probing alternating ends of advisory ranking. Hot probes rank order.
    if mode == "WARM_JUXTAPOSE_HYBRID":
        wave = []
        left, right = 0, len(ranked) - 1
        while left <= right:
            wave.append(ranked[left])
            left += 1
            if left <= right:
                wave.append(ranked[right])
                right -= 1
        ranked = wave
    records = []
    target = len(pivots) if mode == "COLD_JUXTAPOSE_FULL" else 1
    scanned = set()
    acceptable = []
    for pivot in ranked:
        r = transition(cnf, pivot, cap)
        records.append(r)
        scanned.add(pivot)
        if r["exact_verified"] and r["status"] in ("SAFE", "TERMINAL_UNSAT"):
            acceptable.append(r)
        # Hot/warm may stop after verified witness, not an unverified guess.
        # If first attempts overflow, widen until success or full coverage.
        if len(records) >= target and acceptable and mode != "COLD_JUXTAPOSE_FULL":
            break
    if mode == "COLD_JUXTAPOSE_FULL":
        require(len(records) == len(pivots), "COLD_ROOT_FIELD_NOT_COVERED")
    if acceptable:
        best = min(acceptable, key=lambda x: (
            x["raw_units_before_canonical_compression"],
            x["pair_work"], x["pivot"]))
        decision = "EXACT_TRANSITION_WITNESS_FOUND"
    else:
        best = None
        decision = "UNKNOWN_RESOURCE_LIMIT"
    total_pairs = sum(x["pair_work"] for x in records)
    report = {
        "schema": SCHEMA, "status": decision,
        "mode": mode, "available_pivots": len(pivots),
        "exact_probed_pivots": len(records), "coverage_ratio": len(records) / len(pivots),
        "root_cnf_sha256": seal(cnf), "rank_order": ranked,
        "advisory_structural_scores": [
            {"rank": i+1, "features": list(cheap_score(cnf, pivot))}
            for i, pivot in enumerate(ranked)],
        "receipts": records, "chosen_verified_receipt": (
            best["receipt_sha256"] if best else None),
        "total_pair_work_not_free": total_pairs,
        "exact_verifier_has_veto": True,
        "model_predicted_truth": False,
        "model_weights_modified": False,
        "theorem_or_p_vs_np_proved": False,
        "production_authority": False,
    }
    report["receipt_sha256"] = seal(report)
    return report


def validate_memory(v32, v33):
    km.verify_state(v32)
    spi.verify_state(v33)
    require(bool(v32["history"]) and bool(v33["history"]),
            "MISSING_ESSENCE_VERIFIED_MEMORY")
    last = v33["history"][-1]
    guards = {x.get("id"): x.get("status") for x in last.get("negative_evidence", [])
              if isinstance(x, dict)}
    require(guards.get("DOVOD_SHA_25_OF_50_TEST_LEAKAGE") ==
            "NEGATIVE_CONTROL_CONTAMINATED" and
            guards.get("ESSENCE_NEURAL_PROSPECTIVE_EXAM_20261114") ==
            "HOLD_FUTURE_NEURAL_GAIN_NOT_PROVEN" and
            guards.get("KEYMASTER_R2_REPLICATED_ABLATIONS") ==
            "UNRESOLVED_EIGHT_CONTRIBUTORS" and
            len(last["scout_identities"]) == 17,
            "INHERITED_NEGATIVE_CONTROLS_OR_SCOUTS_MISSING")
    require(v32["history"][-1]["keymaster_guard"] ==
            "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION",
            "KEYMASTER_UNRESOLVED_AUTHORITY_GATE")
    return {
        "v32_memory_sha256": v32["state_sha256"],
        "v33_memory_sha256": v33["state_sha256"],
        "negative_result_ids": sorted(guards),
        "independent_calibrated_juxtapose_epochs": 0,
        "research_mode": "COLD_ONLY_UNTIL_EXACT_INDEPENDENT_CALIBRATION",
    }


def load(path, size=120000):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 2 <= path.stat().st_size <= size:
        raise ValueError("UNSAFE_OR_UNAVAILABLE_RESEARCH_SOURCE")
    return json.loads(path.read_text(encoding="utf-8"),
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("NONFINITE_JSON")))


def run_cases(cases, v32, v33):
    require(isinstance(cases, dict) and cases.get("schema") == CASES_SCHEMA
            and cases.get("scientific_independent_holdout") is False
            and cases.get("automatic_module_activation") is False
            and cases.get("frozen_public_development_fixture") is True,
            "JUXTAPOSE_FROZEN_RESEARCH_FIXTURE_REQUIRED")
    entries = cases.get("cases")
    require(isinstance(entries, list) and 2 <= len(entries) <= MAX_CASES,
            "JUXTAPOSE_CASE_COUNT")
    memory = validate_memory(v32, v33)
    results = []
    for item in entries:
        require(isinstance(item, dict) and
                item.get("expected_status") in (
                    "EXACT_TRANSITION_WITNESS_FOUND", "UNKNOWN_RESOURCE_LIMIT")
                and isinstance(item.get("name"), str),
                "INVALID_JUXTAPOSE_TEST_CASE")
        report = field_search(item.get("clauses"), item.get("cap"),
                              authority=0, independent_exact_epochs=0)
        require(report["status"] == item["expected_status"] and
                report["coverage_ratio"] == 1.0 and
                report["mode"] == "COLD_JUXTAPOSE_FULL",
                "JUXTAPOSE_SOURCE_BOUND_EXACT_REGRESSION")
        results.append({"case": item["name"], "report": report})
    out = {
        "schema": "janus.essence.juxtapose_research_receipt/3.6",
        "status": "COLD_FULL_EXACT_RESEARCH_PASS_NOT_MODEL_GAIN",
        "source_code": SOURCE_CODE, "source_contracts": SOURCES,
        "frozen_cases_sha256": seal(cases),
        "memory_bound": memory,
        "cases": results, "cases_verified": len(results),
        "unresolved_negative_cases_preserved": sum(
            x["report"]["status"] == "UNKNOWN_RESOURCE_LIMIT" for x in results),
        "full_field_coverage_for_development_cases": True,
        "historical_source_python_executed": False,
        "warm_or_hot_authority_earned": False,
        "external_independent_evaluation": False,
        "future_prospective_gain_proven": False,
        "microkernel_research_execution": True,
        "auto_install_new_microcore": False,
        "production_neural_weights_changed": False,
        "production_authority": False,
    }
    out["receipt_sha256"] = seal(out)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--v32", required=True)
    parser.add_argument("--v33", required=True)
    parser.add_argument("--receipt", required=True)
    a = parser.parse_args()
    packet = run_cases(load(a.cases), load(a.v32), load(a.v33))
    p = Path(a.receipt)
    require(not p.exists(), "IMMUTABLE_RECEIPT_PATH_ALREADY_USED")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(packet, ensure_ascii=False, sort_keys=True,
                            indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": packet["status"], "cases": packet["cases_verified"],
        "unresolved": packet["unresolved_negative_cases_preserved"],
        "warm_or_hot_authority": False, "production_authority": False,
        "receipt_sha256": packet["receipt_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
