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


def deterministic_candidate_pool(target: dict, donors: list[dict]) -> list[dict]:
    src = str(target.get("from_type") or "SOURCE")
    dst = str(target.get("to_type") or "TARGET")
    donor_titles = [str(x.get("title") or "") for x in donors if x.get("title")]
    donor_ids = [
        str(x.get("archive_id") or x.get("source_url"))
        for x in donors
        if x.get("archive_id") or x.get("source_url")
    ]

    families = [
        {
            "family": "EXACT_INTERFACE_QUOTIENT",
            "strategy": (
                f"Construct an exact observable-signature quotient of {src}; compile quotient transitions into {dst} only "
                "when every source operation preserves the quotient and the quotient interaction graph has fixed width."
            ),
            "steps": [
                "Extract the source incidence/constraint interface and define an exact signature for each live component.",
                "Merge only components with byte-identical exact signatures under all exposed source operations.",
                "Build the quotient interaction graph without semantic-oracle equivalence tests.",
                "Reject the candidate immediately if quotient width or signature count is not polynomially bounded.",
                "Compile each quotient node and interface transition into the target circuit representation.",
                "Reconstruct a source witness by replaying stored exact quotient maps and verify it against the original instance.",
            ],
            "falsifiers": [
                "Search bounded Tseitin families for superpolynomially many exact quotient signatures.",
                "Search for a pair merged by the proposed signature that separates after one legal source operation.",
                "Measure target treewidth on adversarial expander-derived instances and reject on unbounded growth.",
            ],
        },
        {
            "family": "SEPARATOR_SIGNATURE_DP",
            "strategy": (
                f"Derive a source-native separator decomposition for {src}, store only exact boundary signatures, and compile "
                f"the resulting dynamic program into {dst} if separator adhesion and signature algebra remain fixed-width."
            ),
            "steps": [
                "Build a deterministic decomposition from the explicit source incidence structure.",
                "For each separator, enumerate only exact boundary signatures admitted by the frozen interface grammar.",
                "Compose child tables by exact join/projection rules with explicit provenance for every transition.",
                "Reject if separator size, table dimension, or transition fanout lacks a fixed polynomial bound.",
                "Translate the accepted decomposition to a circuit whose bags correspond to separator states.",
                "Recover and verify a satisfying assignment or UNSAT certificate by backward table replay.",
            ],
            "falsifiers": [
                "Construct expander/Tseitin instances that force separator adhesion to grow with input size.",
                "Search for boundary signatures whose exact composition requires exponentially many states.",
                "Compare reconstructed witnesses against brute force on small exhaustive controls.",
            ],
        },
        {
            "family": "CYCLE_SPACE_PARITY_OVERLAY",
            "strategy": (
                f"For parity-heavy {src}, isolate the GF(2) cycle-space component, route it through polynomial linear algebra, "
                f"and expose only the residual interaction to {dst}; reject unless the residual circuit width is fixed."
            ),
            "steps": [
                "Extract the GF(2) incidence matrix and compute a polynomial-size cycle/cut-space basis.",
                "Eliminate pure affine parity degrees of freedom by exact Gaussian elimination.",
                "Represent each remaining non-affine interaction as a typed boundary constraint over the affine quotient.",
                "Reject if the number or arity of non-affine boundary interactions is not polynomially and width-bounded.",
                "Compile the affine solver plus residual boundary controller into the target circuit.",
                "Lift any target witness through the affine basis and verify all original clauses exactly.",
            ],
            "falsifiers": [
                "Search signed Tseitin controls where non-affine residue remains extensive after affine elimination.",
                "Search instances where affine quotienting preserves size but target treewidth still grows linearly.",
                "Exhaustively verify witness lifting on small parity/non-parity mixed instances.",
            ],
        },
        {
            "family": "TRACTABLE_ISLAND_CONTRACTION",
            "strategy": (
                f"Partition {src} into maximal source-certified tractable islands, contract each island to an exact interface "
                f"relation, and compile the island interaction graph into {dst} only if global interface width stays fixed."
            ),
            "steps": [
                "Detect maximal subinstances certified by existing tractable mechanism contracts.",
                "Compute exact interface relations for each island using only their admitted polynomial solvers.",
                "Contract islands while preserving all exposed boundary assignments and reconstruction maps.",
                "Reject if contraction creates a SAT-like selector, unbounded interface relation, or exponential table.",
                "Compile the contracted interaction graph to the target fixed-width circuit form.",
                "Reconstruct island witnesses and verify the complete original assignment.",
            ],
            "falsifiers": [
                "Search mixtures of individually tractable islands whose interface graph encodes unrestricted SAT.",
                "Search contraction steps that silently introduce explicit selector variables or exponential relations.",
                "Stress reconstruction when several islands share correlated boundary variables.",
            ],
        },
        {
            "family": "PROOF_CARRYING_ELIMINATION_SCHEDULE",
            "strategy": (
                f"Generate an elimination schedule for {src} where every step carries a local exactness and width certificate; "
                f"compile the certified schedule into {dst} and reject at the first step lacking a polynomial-width certificate."
            ),
            "steps": [
                "Enumerate a bounded set of deterministic elimination priorities derived from source-local invariants.",
                "For each proposed elimination, construct an exact local replacement plus reconstruction certificate.",
                "Maintain a symbolic width ledger charging every new clause, factor, or circuit dependency.",
                "Reject a schedule immediately if any local certificate fails or cumulative width exceeds the fixed target bound.",
                "Compile the surviving certified schedule into the target circuit decomposition.",
                "Replay all certificates backward to reconstruct and verify the source decision/witness.",
            ],
            "falsifiers": [
                "Run the schedule on known elimination-order counterfamilies and reject if width explodes.",
                "Search for locally cheap steps whose cumulative representation size is superpolynomial.",
                "Cross-check every accepted local replacement by exhaustive truth-table equivalence on bounded supports.",
            ],
        },
    ]

    out = []
    for index, spec in enumerate(families):
        donor_note = donor_titles[index % len(donor_titles)] if donor_titles else "no external donor selected"
        candidate = {
            "schema": CANDIDATE_SCHEMA,
            "candidate_id": f"AUTO_{spec['family']}_{src}_TO_{dst}",
            "title": f"{spec['family']} candidate for {src} -> {dst}",
            "target_from_type": src,
            "target_to_type": dst,
            "strategy": spec["strategy"] + f" Donor-context anchor: {donor_note}.",
            "algorithm_steps": spec["steps"],
            "complexity_plan": {
                "construction": "Require an explicit polynomial bound on decomposition/quotient construction before admission.",
                "state": "Require a polynomial bound on all stored signatures/tables and a fixed bound on target width.",
                "reconstruction": "Store provenance maps at every reduction and require polynomial backward replay.",
                "verification": "Verify the reconstructed source witness/certificate directly in polynomial time.",
            },
            "proof_obligations": [
                {"id": x, "status": "OPEN", "attack": f"Prove or falsify {x} for {spec['family']} on arbitrary input size."}
                for x in REQUIRED_PROOF_OBLIGATIONS
            ],
            "falsification_tests": [
                {"id": f"F{i+1}", "test": test}
                for i, test in enumerate(spec["falsifiers"])
            ],
            "donor_ids": donor_ids[:6],
            "anti_loop_rationale": (
                f"Operator family {spec['family']} must be compared against existing Keymaster barriers and prior fingerprints; "
                "a renamed known route or a route requiring a hidden SAT/semantic-equivalence oracle is rejected."
            ),
            "resource_firewall": {"hidden_oracle": False, "hidden_exponential_state": False},
            "authority": {
                "truth": False,
                "proof": False,
                "scientific_claim_promotion": False,
                "fundamentum_mutation": False,
                "automatic_merge": False,
            },
            "synthesis_origin": "DETERMINISTIC_COMBINATORIAL_FALLBACK",
            "operator_family": spec["family"],
        }
        out.append(candidate)
    return out


def synthesize_deterministic_candidate(
    target: dict | None,
    donors: list[dict],
    previous: dict | None,
) -> dict | None:
    if target is None:
        return None
    seen = set((previous or {}).get("recent_candidate_fingerprints") or [])
    pool = deterministic_candidate_pool(target, donors)
    for row in pool:
        normalized = normalize_candidate(row, target)
        if candidate_fingerprint(normalized) not in seen:
            return row
    return pool[0] if pool else None


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
    proposer = "NONE"
    selected_input = model_candidate
    if target and selected_input is None:
        selected_input = synthesize_deterministic_candidate(target, donors, previous)
        proposer = "DETERMINISTIC_COMBINATORIAL_FALLBACK" if selected_input is not None else "NONE"
    elif selected_input is not None:
        proposer = "EXTERNAL_MODEL"
    if target and selected_input is not None:
        try:
            candidate = normalize_candidate(selected_input, target)
            fp = candidate_fingerprint(candidate)
            duplicate = fp in set(recent)
            candidate["candidate_fingerprint"] = fp
            if duplicate:
                candidate["status"] = "DUPLICATE_CANDIDATE_NO_ADVANCE"
            else:
                recent.append(fp)
        except RuntimeError as err:
            candidate_error = str(err)
            if proposer == "EXTERNAL_MODEL":
                fallback = synthesize_deterministic_candidate(target, donors, previous)
                if fallback is not None:
                    try:
                        candidate = normalize_candidate(fallback, target)
                        proposer = "DETERMINISTIC_COMBINATORIAL_FALLBACK_AFTER_MODEL_REJECTION"
                        fp = candidate_fingerprint(candidate)
                        duplicate = fp in set(recent)
                        candidate["candidate_fingerprint"] = fp
                        if duplicate:
                            candidate["status"] = "DUPLICATE_CANDIDATE_NO_ADVANCE"
                        else:
                            recent.append(fp)
                    except RuntimeError as fallback_err:
                        candidate = None
                        candidate_error = candidate_error + ";FALLBACK:" + str(fallback_err)
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
        "candidate_proposer": proposer,
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
