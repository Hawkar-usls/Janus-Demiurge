from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "janus.keymaster.autonomous_forge.v1"
CANDIDATE_SCHEMA = "janus.keymaster.autonomous_candidate.v1"
KEYMASTER_SCHEMA = "janus.keymaster.mechanism_composition_report.v1"

REQUIRED_PROOF_OBLIGATIONS = (
    "EXACT_SEMANTICS",
    "POLYNOMIAL_CONSTRUCTION",
    "POLYNOMIAL_STATE",
    "POLYNOMIAL_RECONSTRUCTION",
    "POLYNOMIAL_VERIFICATION",
    "UNIVERSAL_SCOPE",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path | None, default: Any = None) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    rows: list[dict] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _terms(*values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[A-Za-z0-9]+", str(value or "").lower()):
            if len(token) < 3 or token in {"the", "and", "for", "with", "from", "into", "fixed"}:
                continue
            if token not in seen:
                seen.add(token)
                out.append(token)
    return out


def validate_keymaster(report: dict) -> dict:
    if report.get("schema") != KEYMASTER_SCHEMA:
        raise RuntimeError("AUTONOMOUS_FORGE_KEYMASTER_SCHEMA_REJECTED")
    firewall = report.get("firewall") or {}
    if firewall.get("P_VS_NP") != "OPEN" or firewall.get("D1") != "EMPTY":
        raise RuntimeError("AUTONOMOUS_FORGE_SCIENTIFIC_BOUNDARY_REJECTED")
    if firewall.get("automatic_theorem_promotion") is not False:
        raise RuntimeError("AUTONOMOUS_FORGE_PROMOTION_FIREWALL_REJECTED")
    gaps = report.get("missing_interface_queue") or []
    if not isinstance(gaps, list):
        raise RuntimeError("AUTONOMOUS_FORGE_GAP_QUEUE_REJECTED")
    return report


def select_target(report: dict) -> dict | None:
    gaps = report.get("missing_interface_queue") or []
    if not gaps:
        return None
    gap = dict(gaps[0])
    return {
        "rank": 1,
        "from_type": gap.get("from_type"),
        "to_type": gap.get("to_type"),
        "lockpick_score": gap.get("lockpick_score"),
        "proved_context_edges": gap.get("proved_context_edges"),
        "complete_path_edges_if_closed": gap.get("complete_path_edges_if_closed"),
        "barrier_penalty": gap.get("barrier_penalty"),
        "barriers": gap.get("barriers") or [],
        "required_contract": gap.get("required_contract") or {},
    }


def select_donors(records: list[dict], target: dict | None, limit: int = 12) -> list[dict]:
    if not target:
        return []
    barrier_text = " ".join(
        f"{x.get('id','')} {x.get('scope','')} {x.get('kind','')}"
        for x in target.get("barriers") or []
    )
    terms = _terms(target.get("from_type"), target.get("to_type"), barrier_text)
    scored: list[tuple[int, str, dict]] = []
    for row in records:
        title = str(row.get("title") or "")
        hay = f"{title} {row.get('text','')}".lower()
        score = sum(4 if t in title.lower() else 1 for t in terms if t in hay)
        if score <= 0:
            continue
        key = str(row.get("archive_id") or row.get("source_url") or title)
        scored.append((score, key, row))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [
        {
            "score": score,
            "provider": row.get("provider"),
            "archive_id": row.get("archive_id"),
            "title": row.get("title"),
            "source_url": row.get("source_url"),
            "review_state": row.get("review_state"),
            "scientific_authority": row.get("scientific_authority"),
        }
        for score, _, row in scored[:limit]
    ]


def build_search_queries(target: dict | None) -> list[str]:
    if not target:
        return []
    src = str(target.get("from_type") or "").replace("_", " ").lower()
    dst = str(target.get("to_type") or "").replace("_", " ").lower()
    scopes = [
        str(x.get("scope") or "").replace("_", " ").lower()
        for x in target.get("barriers") or []
        if x.get("scope")
    ]
    queries = [
        f"{src} {dst} exact polynomial algorithm",
        f"{src} to {dst} reduction reconstruction verification",
        f"{src} {dst} parameterized tractable representation",
        f"{src} {dst} dynamic programming decomposition",
    ]
    for scope in scopes[:2]:
        queries.append(f"{src} {dst} bypass {scope}")
    return queries[:6]


def _extract_json_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[index:])
            return value
        except json.JSONDecodeError:
            continue
    return None


def _unwrap_model_value(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return value
    if isinstance(value, dict):
        if value.get("schema") == CANDIDATE_SCHEMA:
            return value
        for key in ("result", "content", "text", "message", "response", "output"):
            nested = value.get(key)
            if isinstance(nested, str):
                parsed = _extract_json_value(nested)
                if parsed is not None:
                    found = _unwrap_model_value(parsed, depth + 1)
                    if isinstance(found, dict) and found.get("schema") == CANDIDATE_SCHEMA:
                        return found
            elif isinstance(nested, (dict, list)):
                found = _unwrap_model_value(nested, depth + 1)
                if isinstance(found, dict) and found.get("schema") == CANDIDATE_SCHEMA:
                    return found
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                found = _unwrap_model_value(nested, depth + 1)
                if isinstance(found, dict) and found.get("schema") == CANDIDATE_SCHEMA:
                    return found
    if isinstance(value, list):
        for nested in value:
            found = _unwrap_model_value(nested, depth + 1)
            if isinstance(found, dict) and found.get("schema") == CANDIDATE_SCHEMA:
                return found
    return value


def parse_model_candidate(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    value = _extract_json_value(path.read_text(encoding="utf-8", errors="replace"))
    if value is None:
        return None
    value = _unwrap_model_value(value)
    return value if isinstance(value, dict) and value.get("schema") == CANDIDATE_SCHEMA else None


def normalize_candidate(candidate: dict, target: dict) -> dict:
    if candidate.get("schema") != CANDIDATE_SCHEMA:
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_SCHEMA_REJECTED")
    if candidate.get("target_from_type") != target.get("from_type"):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_FROM_TYPE_MISMATCH")
    if candidate.get("target_to_type") != target.get("to_type"):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_TO_TYPE_MISMATCH")
    steps = candidate.get("algorithm_steps")
    if not isinstance(steps, list) or not 3 <= len(steps) <= 16 or not all(isinstance(x, str) and x.strip() for x in steps):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_STEPS_REJECTED")
    obligations = candidate.get("proof_obligations")
    if not isinstance(obligations, list):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_OBLIGATIONS_REJECTED")
    ids = {str(x.get("id")) for x in obligations if isinstance(x, dict)}
    missing = [x for x in REQUIRED_PROOF_OBLIGATIONS if x not in ids]
    if missing:
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_OBLIGATIONS_MISSING:" + ",".join(missing))
    tests = candidate.get("falsification_tests")
    if not isinstance(tests, list) or len(tests) < 3:
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_FALSIFIERS_REJECTED")
    complexity = candidate.get("complexity_plan")
    if not isinstance(complexity, dict):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_COMPLEXITY_REJECTED")
    for key in ("construction", "state", "reconstruction", "verification"):
        if not isinstance(complexity.get(key), str) or not complexity[key].strip():
            raise RuntimeError(f"AUTONOMOUS_FORGE_CANDIDATE_COMPLEXITY_MISSING:{key}")
    authority = candidate.get("authority")
    if not isinstance(authority, dict):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_AUTHORITY_REJECTED")
    for key in ("truth", "proof", "scientific_claim_promotion", "fundamentum_mutation", "automatic_merge"):
        if authority.get(key) is not False:
            raise RuntimeError(f"AUTONOMOUS_FORGE_CANDIDATE_AUTHORITY_ESCALATION:{key}")
    safety = candidate.get("resource_firewall")
    if not isinstance(safety, dict):
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_RESOURCE_FIREWALL_MISSING")
    if safety.get("hidden_oracle") is not False or safety.get("hidden_exponential_state") is not False:
        raise RuntimeError("AUTONOMOUS_FORGE_CANDIDATE_HIDDEN_RESOURCE_REJECTED")
    out = dict(candidate)
    out["candidate_id"] = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(candidate.get("candidate_id") or "JANUS_AUTO_CANDIDATE"))[:120]
    out["status"] = "CANDIDATE_ALGORITHM_PROPOSED_UNVERIFIED"
    out["keymaster_shadow_admission"] = False
    out["keymaster_shadow_admission_reason"] = "PROOF_OBLIGATIONS_UNDISCHARGED"
    return out


def candidate_fingerprint(candidate: dict) -> str:
    return sha256_json({
        "target_from_type": candidate.get("target_from_type"),
        "target_to_type": candidate.get("target_to_type"),
        "strategy": candidate.get("strategy"),
        "algorithm_steps": candidate.get("algorithm_steps"),
        "complexity_plan": candidate.get("complexity_plan"),
    })


def build_prompt_packet(report: dict, target: dict | None, donors: list[dict], previous: dict | None, hrain: dict | None, inaihr: dict | None) -> dict:
    prior = list((previous or {}).get("recent_candidate_fingerprints") or [])[-16:]
    return {
        "role": "JANUS_KEYMASTER_AUTONOMOUS_LOCKPICK_FORGE",
        "mission": "Create one new falsifiable candidate algorithm for the current #1 Keymaster missing interface. Use supplied research memory and donors. Do not claim proof.",
        "target": target,
        "search_queries": build_search_queries(target),
        "discovery_donors": donors,
        "memory": {
            "hrain_source_commit": (hrain or {}).get("source_commit"),
            "hrain_entry_count": (hrain or {}).get("entry_count"),
            "inaihr_source_commit": (inaihr or {}).get("source_commit"),
            "inaihr_query_seeds": (inaihr or {}).get("topa_query_seeds") or [],
        },
        "recent_candidate_fingerprints_do_not_repeat": prior,
        "output_schema": {
            "schema": CANDIDATE_SCHEMA,
            "candidate_id": "short stable id",
            "title": "short title",
            "target_from_type": target.get("from_type") if target else None,
            "target_to_type": target.get("to_type") if target else None,
            "strategy": "precise mechanism idea",
            "algorithm_steps": ["3 to 16 explicit deterministic steps"],
            "complexity_plan": {
                "construction": "polynomial accounting plan",
                "state": "polynomial state-size accounting plan",
                "reconstruction": "polynomial witness reconstruction plan",
                "verification": "polynomial verification plan",
            },
            "proof_obligations": [
                {"id": x, "status": "OPEN", "attack": "how to prove or falsify it"}
                for x in REQUIRED_PROOF_OBLIGATIONS
            ],
            "falsification_tests": [
                {"id": "F1", "test": "bounded exact counterexample search"},
                {"id": "F2", "test": "adversarial representation-growth test"},
                {"id": "F3", "test": "reconstruction/verification mismatch test"},
            ],
            "donor_ids": ["only supplied donor archive ids or source urls"],
            "anti_loop_rationale": "why this is not a previously rejected route or mere renaming",
            "resource_firewall": {"hidden_oracle": False, "hidden_exponential_state": False},
            "authority": {
                "truth": False,
                "proof": False,
                "scientific_claim_promotion": False,
                "fundamentum_mutation": False,
                "automatic_merge": False,
            },
        },
        "rules": [
            "Return JSON only.",
            "Candidate algorithm != proof.",
            "Do not output a P=NP probability.",
            "Do not claim a theorem.",
            "Do not use a SAT oracle, semantic-equivalence oracle, unbounded enumeration, or hidden exponential advice.",
            "Prefer mechanisms falsifiable by a small exact counterexample.",
            "Explicitly account for construction, state size, reconstruction, and verification.",
            "Discovery donor metadata is context, not proof authority.",
        ],
        "keymaster_report_sha256": report.get("report_sha256"),
        "P_VS_NP": "OPEN",
    }


def build_state(report: dict, records: list[dict], *, previous: dict | None = None, model_candidate: dict | None = None, hrain: dict | None = None, inaihr: dict | None = None) -> dict:
    validate_keymaster(report)
    target = select_target(report)
    donors = select_donors(records, target)
    prompt = build_prompt_packet(report, target, donors, previous, hrain, inaihr)
    prev_cycles = int((previous or {}).get("cycle_count") or 0)
    prev_proposals = int((previous or {}).get("candidate_proposal_count") or 0)
    prev_distinct = int((previous or {}).get("distinct_candidate_count") or 0)
    prev_duplicates = int((previous or {}).get("duplicate_candidate_count") or 0)
    recent = list((previous or {}).get("recent_candidate_fingerprints") or [])[-31:]
    candidate = None
    candidate_error = None
    duplicate = False
    if target and model_candidate is not None:
        try:
            candidate = normalize_candidate(model_candidate, target)
            fp = candidate_fingerprint(candidate)
            duplicate = fp in set(recent)
            candidate["candidate_fingerprint"] = fp
            if duplicate:
                candidate["status"] = "DUPLICATE_CANDIDATE_NO_ADVANCE"
            else:
                recent.append(fp)
        except RuntimeError as err:
            candidate_error = str(err)
    if target is None:
        status = "NO_OPEN_INTERFACE"
    elif candidate is None:
        status = "SEARCHED_NO_VALID_MODEL_CANDIDATE"
    elif duplicate:
        status = "DUPLICATE_CANDIDATE_NO_ADVANCE"
    else:
        status = "NEW_CANDIDATE_ALGORITHM_PROPOSED"
    obj = {
        "schema": SCHEMA,
        "status": status,
        "mode": "AUTONOMOUS_TARGETED_LOCKPICK_FORGE",
        "cycle_count": prev_cycles + 1,
        "candidate_proposal_count": prev_proposals + (1 if candidate is not None else 0),
        "distinct_candidate_count": prev_distinct + (1 if candidate is not None and not duplicate else 0),
        "duplicate_candidate_count": prev_duplicates + (1 if duplicate else 0),
        "keymaster_report_sha256": report.get("report_sha256"),
        "target": target,
        "search_queries": build_search_queries(target),
        "selected_donors": donors,
        "candidate": candidate,
        "candidate_error": candidate_error,
        "recent_candidate_fingerprints": recent[-32:],
        "prompt_sha256": sha256_json(prompt),
        "source_memory": {
            "topa_record_count_seen": len(records),
            "hrain_source_commit": (hrain or {}).get("source_commit"),
            "inaihr_source_commit": (inaihr or {}).get("source_commit"),
        },
        "next_action": (
            "RUN_PROOF_OBLIGATION_AND_FALSIFICATION_GATES"
            if candidate is not None and not duplicate
            else "GENERATE_DIFFERENT_CANDIDATE_FOR_SAME_TOP_GAP"
            if target is not None
            else "WAIT_FOR_KEYMASTER_OPEN_INTERFACE"
        ),
        "keymaster_shadow_admission": False,
        "firewall": {
            "branch_only_research": True,
            "writes_fundamentum_main": False,
            "writes_user_research_branch": False,
            "automatic_merge": False,
            "automatic_theorem_promotion": False,
            "automatic_p_equals_np_claim": False,
            "model_output_is_proof": False,
            "topa_metadata_is_proof": False,
            "candidate_algorithm_is_proof": False,
            "P_VS_NP": "OPEN",
            "D1": "EMPTY",
        },
    }
    obj["state_sha256"] = sha256_json(obj)
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keymaster", required=True)
    ap.add_argument("--topa-records")
    ap.add_argument("--hrain")
    ap.add_argument("--inaihr")
    ap.add_argument("--previous")
    ap.add_argument("--model-output")
    ap.add_argument("--prompt-out")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = load_json(Path(args.keymaster))
    records = load_jsonl(Path(args.topa_records)) if args.topa_records else []
    previous = load_json(Path(args.previous), None) if args.previous else None
    hrain = load_json(Path(args.hrain), {}) if args.hrain else {}
    inaihr = load_json(Path(args.inaihr), {}) if args.inaihr else {}
    model_candidate = parse_model_candidate(Path(args.model_output)) if args.model_output else None
    target = select_target(validate_keymaster(report))
    donors = select_donors(records, target)
    prompt = build_prompt_packet(report, target, donors, previous, hrain, inaihr)
    if args.prompt_out:
        p = Path(args.prompt_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(prompt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    obj = build_state(report, records, previous=previous, model_candidate=model_candidate, hrain=hrain, inaihr=inaihr)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": obj["status"],
        "cycle_count": obj["cycle_count"],
        "candidate_proposal_count": obj["candidate_proposal_count"],
        "distinct_candidate_count": obj["distinct_candidate_count"],
        "target": obj["target"],
        "candidate_id": (obj.get("candidate") or {}).get("candidate_id"),
        "keymaster_shadow_admission": obj["keymaster_shadow_admission"],
        "state_sha256": obj["state_sha256"],
        "P_VS_NP": obj["firewall"]["P_VS_NP"],
    }, indent=2))


if __name__ == "__main__":
    main()
