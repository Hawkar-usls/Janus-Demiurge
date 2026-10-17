"""JANUS Divergent Mind v0: bounded, read-only attention/association/questions.

This is an experimental research *candidate generator*, not a language model,
scientific verifier, or execution controller.  Inputs must be source-bound and
immutable.  Its only outputs are questions and provenance-labelled hypotheses.

The three passes are intentionally separate:
    A - notice time-sensitive changes and uncommon operators;
    B - propose cross-domain analogies without calling them evidence;
    V - ask what would falsify the analogy, preserving an abstention route.

No network, shell, repository writes, secret access, or external-effect API.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "janus.divergent_mind.pilot.v0"
OUTPUT_SCHEMA = "janus.divergent_mind.report.v0"
SAFE_OPERATORS = frozenset({
    "ASSOCIATION_VALIDATION", "CLAIM_BOUNDARY", "DURABLE_CHECKPOINT",
    "FRESHNESS_RECONCILIATION", "MEMORY_CONSUMPTION", "PROVENANCE_CHAIN",
    "SOURCE_INDEPENDENCE", "STATE_TRANSITION", "EXACT_VS_SEMANTIC_IDENTITY",
})
ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,79}\Z")
REPO_RE = re.compile(r"Hawkar-usls/[A-Za-z0-9_.-]+\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
PATH_RE = re.compile(r"[A-Za-z0-9_.@/+-]{1,240}\Z")
LIMITS = {"observations": 80, "attention": 16, "bridges": 24, "questions": 12}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("observed_at must be an explicit UTC ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("observed_at must use UTC")
    return parsed


def validate_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(pack, dict) or pack.get("schema") != SCHEMA:
        raise ValueError("unsupported source pack schema")
    facts = pack.get("observations")
    if not isinstance(facts, list) or not 2 <= len(facts) <= LIMITS["observations"]:
        raise ValueError("observation count outside bounded range")
    seen = set()
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("observation must be an object")
        for field in ("id", "domain", "subject", "lineage"):
            if not isinstance(fact.get(field), str) or not ID_RE.fullmatch(fact[field]):
                raise ValueError(f"invalid {field}")
        if fact["id"] in seen:
            raise ValueError("duplicate observation ID")
        seen.add(fact["id"])
        if not REPO_RE.fullmatch(str(fact.get("repository", ""))):
            raise ValueError("invalid repository")
        if not SHA_RE.fullmatch(str(fact.get("commit", ""))):
            raise ValueError("source must bind an exact 40-digit commit")
        path = str(fact.get("path", ""))
        if (not PATH_RE.fullmatch(path) or path.startswith("/") or
                any(component in {"", ".", ".."} for component in path.split("/"))):
            raise ValueError("invalid source path")
        if not isinstance(fact.get("value"), str) or not 1 <= len(fact["value"]) <= 180:
            raise ValueError("invalid bounded observation value")
        _utc(fact.get("observed_at"))
        ops = fact.get("operators")
        if (not isinstance(ops, list) or not 1 <= len(ops) <= 5 or
                not all(isinstance(x, str) and x in SAFE_OPERATORS for x in ops) or
                len(set(ops)) != len(ops)):
            raise ValueError("unrecognized or duplicate mechanism operator")
        if set(fact) != {"id", "domain", "subject", "lineage", "repository", "commit", "path", "value", "observed_at", "operators"}:
            raise ValueError("unrecognized input field, possibly a hidden verdict/authority label")
    if set(pack) != {"schema", "pack_id", "observations"} or not ID_RE.fullmatch(str(pack["pack_id"])):
        raise ValueError("source pack may not contain answer labels or instructions")
    return sorted(facts, key=lambda f: f["id"])


def _provenance(fact: dict[str, Any]) -> dict[str, str]:
    return {k: fact[k] for k in ("id", "repository", "commit", "path", "lineage")}


def _attention(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        by_subject[fact["subject"]].append(fact)
    for subject, group in sorted(by_subject.items()):
        if len({f["value"] for f in group}) < 2:
            continue
        ordered = sorted(group, key=lambda x: (x["observed_at"], x["id"]))
        earlier, latest = ordered[0], ordered[-1]
        same_time = _utc(earlier["observed_at"]) == _utc(latest["observed_at"])
        events.append({
            "kind": "CONCURRENT_CONFLICT__UNRESOLVED" if same_time else "TEMPORAL_CHANGE__RECHECK_LATEST",
            "subject": subject,
            "older_value": earlier["value"],
            "newer_value": latest["value"],
            "source_refs": [_provenance(earlier), _provenance(latest)],
            "epistemic_status": "ATTENTION_SIGNAL__NOT_EVIDENCE_PROMOTION",
        })
    counts = Counter(op for fact in facts for op in fact["operators"])
    for fact in facts:
        rare = sorted(op for op in fact["operators"] if counts[op] == 1)
        if rare:
            events.append({
                "kind": "RARE_OPERATOR__CHECK_IF_OVERLOOKED",
                "subject": fact["subject"],
                "operators": rare,
                "source_refs": [_provenance(fact)],
                "epistemic_status": "ATTENTION_SIGNAL__NOT_EVIDENCE_PROMOTION",
            })
    return events[:LIMITS["attention"]]


def _bridges(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        for op in fact["operators"]:
            by_operator[op].append(fact)
    candidates: list[dict[str, Any]] = []
    for op, group in sorted(by_operator.items()):
        domains = {f["domain"] for f in group}
        if len(domains) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a["domain"] == b["domain"]:
                    continue
                # Different repository names or agent IDs are not sufficient
                # to establish independent underlying evidence.
                if a["lineage"] == b["lineage"]:
                    continue
                pair = sorted((a["id"], b["id"]))
                candidates.append({
                    "candidate_id": "jdm-" + _digest({"operator": op, "pair": pair})[:16],
                    "operator": op,
                    "domains": sorted((a["domain"], b["domain"])),
                    "hypothesis": f"Could {op} transfer as a testable question between {a['domain']} and {b['domain']}?",
                    "source_ids": pair,
                    "source_refs": [_provenance(x) for x in sorted((a, b), key=lambda x: x["id"])],
                    "lineage_labels_distinct": True,
                    "independence_verified": False,
                    "score_kind": "HEURISTIC_OPERATOR_RARITY__NOT_PROBABILITY",
                    "novelty_score": round(1 / len(group), 6),
                    "epistemic_status": "CROSS_DOMAIN_HYPOTHESIS__UNVERIFIED",
                    "claim_promotion": False,
                    "effect_authority": False,
                })
    return sorted(candidates, key=lambda x: (-x["novelty_score"], x["candidate_id"]))[:LIMITS["bridges"]]


def run(pack: dict[str, Any], mode: str = "divergent") -> dict[str, Any]:
    if mode not in {"structural_baseline", "divergent"}:
        raise ValueError("unknown bounded mode")
    facts = validate_pack(pack)
    attention = _attention(facts)
    bridges = _bridges(facts) if mode == "divergent" else []
    questions = [{
        "candidate_id": b["candidate_id"],
        "question": f"Which observable counterexample would refute transfer of {b['operator']} across {b['domains'][0]} and {b['domains'][1]}?",
        "required_test": "PRE_REGISTER_DOMAIN_NATIVE_FALSIFIER_AND_INDEPENDENT_REPLAY",
        "status": "OPEN_QUESTION__NO_RESULT_CLAIMED",
    } for b in bridges[:LIMITS["questions"]]]
    return {
        "schema": OUTPUT_SCHEMA,
        "mode": mode,
        "source_pack_id": pack["pack_id"],
        "source_pack_sha256": _digest(pack),
        "observation_count": len(facts),
        "A_attention": attention,
        "B_cross_domain_candidates": bridges,
        "V_fundamental_falsification_questions": questions,
        "verifier": {
            "status": "NOT_EXECUTED__CANDIDATES_REQUIRE_INDEPENDENT_VERIFICATION",
            "frozen_scientific_gates_unchanged": True,
            "positive_claim_count": 0,
        },
        "permissions": {
            "source_writeback": False,
            "cross_repo_mutation": False,
            "automatic_merge": False,
            "command_authority": False,
            "external_effect_authority": False,
            "scientific_claim_promotion": False,
            "authority_delta": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS source-bound divergent mind pilot")
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--mode", choices=["structural_baseline", "divergent"], default="divergent")
    parser.add_argument("--out", type=Path, help="write report into caller-controlled isolated output")
    args = parser.parse_args()
    report = run(json.loads(args.pack.read_text(encoding="utf-8")), args.mode)
    rendered = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
