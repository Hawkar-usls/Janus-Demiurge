"""Fail-closed, source-pinned Beetle / Research Spine / Rex code-need bridge.

The only possible output is a review-only request for an EXISTING pure-code
contract. Research text never becomes instructions, code, or authorizations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "janus.rex.research_code_need.v1"
TASK = "is_fresh"
STATUS = "TRIAGED_TO_RESEARCH_CONTEXT_NOT_VERIFIED"
CAPABILITIES = {"may_generate_research_questions": True, "is_verified_evidence": False,
                "may_grant_mutation_authority": False, "is_direct_gradient_signal": False}
NAMES = ("research", "beetle", "delivery", "coder")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def read(path):
    raw = Path(path).read_bytes()
    if len(raw) > 200000:
        raise ValueError("CODE_NEED_SOURCE_TOO_LARGE")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("CODE_NEED_OBJECT_REQUIRED")
    return obj, hashlib.sha256(raw).hexdigest()


def verify_beetle(beetle):
    payload = dict(beetle)
    claimed = payload.pop("context_sha256", None)
    routes = beetle.get("research_routes")
    titles = beetle.get("hypothesis_routes")
    seq = beetle.get("last_processed_sequence")
    if (beetle.get("schema") != "janus.beetle.runtime_context.v1" or
        beetle.get("status") != STATUS or
        beetle.get("target_repository") != "Hawkar-usls/Janus-Demiurge" or
        beetle.get("capabilities") != CAPABILITIES or
        claimed != digest(payload) or type(seq) is not int or seq <= 0 or
        not isinstance(routes, list) or not isinstance(titles, list) or
        len(routes) != len(titles) or len(routes) > 8 or
        any(not isinstance(row, dict) or not isinstance(row.get("title"), str)
            for row in routes) or
        [row["title"] for row in routes] != titles):
        raise ValueError("CODE_NEED_BEETLE_REJECTED")
    return seq


def evaluate(research, beetle, delivery, coder, commits, hashes):
    if (set(commits) != set(NAMES) or set(hashes) != set(NAMES) or
        any(not isinstance(v, str) or not HEX40.fullmatch(v) for v in commits.values()) or
        any(not isinstance(v, str) or not HEX64.fullmatch(v) for v in hashes.values())):
        raise ValueError("CODE_NEED_UNPINNED_INPUT")
    seq = verify_beetle(beetle)
    ex = research.get("external_context") or {}
    limits = research.get("claim_ceiling") or {}
    policy = research.get("improvement_policy") or {}
    if (research.get("schema") != "janus.research_spine.v1" or
        research.get("status") != "READY" or
        (research.get("research_spine") or {}).get("beetle") != beetle or
        ex.get("beetle_processed_sequence") != seq or
        ex.get("beetle_processing_status") != STATUS or
        ex.get("beetle_route_count") != len(beetle["hypothesis_routes"]) or
        limits.get("beetle_triage_is_model_learning") is not False or
        limits.get("beetle_triage_is_independent_verification") is not False or
        policy.get("autonomous_merge") is not False or
        policy.get("direct_target_main_write") is not False):
        raise ValueError("CODE_NEED_RESEARCH_REBINDING")
    if (delivery.get("schema") != "janus.beetle.delivery_health.v1" or
        delivery.get("ack_semantics") != "INBOX_DURABLE_ONLY_NOT_RUNTIME_CONSUMPTION" or
        type(delivery.get("total_pending")) is not int or
        delivery["total_pending"] < 0 or
        not isinstance(delivery.get("repositories"), dict)):
        raise ValueError("CODE_NEED_DELIVERY_REJECTED")
    receivers = delivery["repositories"]
    if any(not isinstance(row, dict) or type(row.get("pending")) is not int or row["pending"] < 0
           for row in receivers.values()):
        raise ValueError("CODE_NEED_RECEIVER_SCHEMA")
    if sum(row["pending"] for row in receivers.values()) != delivery["total_pending"]:
        raise ValueError("CODE_NEED_PENDING_REBINDING")
    if (coder.get("schema") != "janus.autonomous_coder.state.v1" or
        coder.get("authority_delta") != 0 or coder.get("universal_code_writer_proven") is not False or
        type(coder.get("sequence")) is not int or coder["sequence"] < 0 or
        not isinstance(coder.get("accepted"), dict)):
        raise ValueError("CODE_NEED_CODER_UNTRUSTED")
    unavailable = sorted(name for name, row in receivers.items()
                         if row.get("status") == "ACK_UNAVAILABLE" and row["pending"] > 0)
    result = {
        "schema": SCHEMA, "source_commits": dict(commits), "source_sha256": dict(hashes),
        "beetle_sequence": seq, "beetle_context_sha256": beetle["context_sha256"],
        "research_context_sha256": research.get("context_sha256"),
        "coder_state_sequence": coder["sequence"], "delivery_pending": delivery["total_pending"],
        "ack_unavailable_receivers": unavailable,
        "authority": {"delta": 0, "code_admission": False, "runtime_import": False,
                      "auto_merge": False, "paid_jobs": False},
        "claim_ceiling": "DIAGNOSTIC_PURE_FUNCTION_ONLY_NOT_A_RECEIVER_REPAIR"
    }
    if not unavailable:
        result.update(status="IDLE_NO_ACK_VISIBILITY_GAP", task_id=None)
    elif TASK in coder["accepted"]:
        result.update(status="IDLE_TASK_ALREADY_ACCEPTED", task_id=None)
    else:
        result.update(status="PROPOSED_REVIEW_ONLY", task_id=TASK,
                      target_repository="Hawkar-usls/janus-meta-registry",
                      need_kind="ACK_FRESHNESS_DIAGNOSTIC",
                      signature="def is_fresh(age, max_age)",
                      task_source="REX_NEED_DISCOVERY_WITH_SOURCE_BOUND_RESEARCH",
                      explanation="Propose preadmitted pure freshness predicate for ACK age diagnostics. This cannot fix private receiver visibility or grant code admission.",
                      author_model_scope="EXTERNAL_OPEN_WEIGHTS_ONLY",
                      admission="INDEPENDENT_CODER_EVALUATOR_AND_HUMAN_REVIEW_REQUIRED")
    result["need_id"] = "code_need_" + digest(result)[:20]
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in NAMES:
        p.add_argument("--" + key, type=Path, required=True)
        p.add_argument("--" + key + "-commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    objects, hashes, commits = {}, {}, {}
    for key in NAMES:
        objects[key], hashes[key] = read(getattr(args, key))
        commits[key] = getattr(args, key + "_commit")
    result = evaluate(objects["research"], objects["beetle"], objects["delivery"],
                      objects["coder"], commits, hashes)
    payload = canonical(result) + b"\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists() and args.out.read_bytes() != payload:
        raise ValueError("CODE_NEED_IMMUTABLE_CONFLICT")
    args.out.write_bytes(payload)
    print(json.dumps({"status": result["status"], "task_id": result["task_id"],
                      "need_id": result["need_id"], "authority_delta": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
