"""R2 fixed-snapshot development retrieval benchmark. NOT independent science.

Source labels are frozen in a committed fixture; they were selected after
inspecting the metadata index. Only query->source retrieval and abstention are
measured. Does not claim answer correctness or improve the native model.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

SCHEMA = "janus.native.hrain_retrieval_benchmark.r2"
FIXTURE_SCHEMA = "janus.native.hrain_retrieval_r2_development_smoke.v1"
PROJECTED_SCHEMA = "janus.hrain.registry_graph_index.v1_0"
REGISTRY = "Hawkar-usls/janus-meta-registry"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_CASES = 32
MAX_INDEX_BYTES = 8_000_000
MAX_FILE_BYTES = 64_000


class BenchmarkHold(ValueError):
    pass


def read_json(path: Path, limit: int) -> tuple[dict, str]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise BenchmarkHold("INPUT_SIZE_OR_SYMLINK_HOLD")
    raw = path.read_bytes()
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise BenchmarkHold("JSON_OBJECT_REQUIRED")
    return obj, hashlib.sha256(raw).hexdigest()


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"\w+", s.lower()) if len(t) > 1}


def filename_baseline(projection: dict, query: str, k: int) -> list[str]:
    """Path-only lexical retrieval, with no HRain graph/metadata."""
    q = _tokens(query)
    if not q:
        return []
    scored = []
    for node in projection["nodes"]:
        if not isinstance(node, dict) or node.get("readOnly") is not True or node.get("deleteAllowed") is not False:
            continue
        path = node.get("path")
        if not isinstance(path, str) or not path:
            continue
        score = len(q & _tokens(path))
        if score:
            scored.append((-score, path))
    scored.sort()
    return [p for _, p in scored[:k]]


def _load_hrain(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise BenchmarkHold("HRAIN_MODULE_UNAVAILABLE")
    # Reuse canonical HRain selection, instead of reimplementing it here.
    sys.path.insert(0, str(path.parent.resolve()))
    spec = importlib.util.spec_from_file_location("hrain_r2_pinned", str(path.resolve()))
    if spec is None or spec.loader is None:
        raise BenchmarkHold("HRAIN_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _evaluate_ranking(cases: list[dict], ranker, limit: int) -> dict:
    results = []
    correct = 0
    total_positive = 0
    successful_abstentions = 0
    total_negatives = 0
    hit_sum = 0
    precision_sum = 0.0
    t0 = time.perf_counter()
    for case in cases:
        top = ranker(case["query"], limit)
        if not isinstance(top, list) or len(top) > limit or len(top) != len(set(top)):
            raise BenchmarkHold("RANKER_OUTPUT_INVALID")
        gold = set(case["gold"])
        tp = len(gold.intersection(top))
        if gold:
            total_positive += 1
            hit = bool(tp)
            hit_sum += int(hit)
            precision_sum += tp / len(top) if top else 0
            recall = tp / len(gold)
            correct += int(recall == 1)
        else:
            total_negatives += 1
            hit = None
            recall = None
            successful_abstentions += int(not top)
            correct += int(not top)
        results.append({
            "case_id": case["id"],
            "query_sha256": hashlib.sha256(case["query"].encode()).hexdigest(),
            "gold_source_paths": sorted(gold),
            "returned_source_paths": top,
            "correct_source_count": tp,
            "recall": recall,
            "hit_at_k": hit,
            "abstained": not top,
            "correct_case": (recall == 1) if gold else (not top),
        })
    return {
        "cases": len(cases),
        "correct_cases": correct,
        "positive_cases": total_positive,
        "negative_cases": total_negatives,
        "hit_at_k_count": hit_sum,
        "mean_precision_over_positive_queries": (precision_sum / total_positive if total_positive else None),
        "no_match_correct_abstentions": successful_abstentions,
        "all_case_accuracy": correct / len(cases),
        "elapsed_ms_for_smoke_only": round((time.perf_counter() - t0) * 1000, 2),
        "cases_detail": results,
    }


def run_benchmark(index_path: Path, fixture_path: Path, hrain_source: Path) -> dict:
    projection, projection_sha = read_json(index_path, MAX_INDEX_BYTES)
    cases_obj, cases_sha = read_json(fixture_path, MAX_FILE_BYTES)
    if (projection.get("schema") != PROJECTED_SCHEMA or
            projection.get("repository") != REGISTRY or
            projection.get("status") != "AUTO_GENERATED_READ_ONLY_ACTIVE_REGISTRY_PROJECTION" or
            not SHA40.fullmatch(str(projection.get("sourceCommit") or "")) or
            projection.get("mutationPolicy", {}).get("interfaceWriteAuthority") is not False or
            projection.get("mutationPolicy", {}).get("interfaceDeleteAuthority") is not False):
        raise BenchmarkHold("PROJECTION_AUTHORITY_OR_SOURCE_HOLD")
    nodes = projection.get("nodes")
    if not isinstance(nodes, list) or len(nodes) > 10000:
        raise BenchmarkHold("PROJECTION_NODE_BUDGET_HOLD")
    if (cases_obj.get("schema") != FIXTURE_SCHEMA or
            cases_obj.get("status") != "FROZEN_DEVELOPMENT_ANCHORS_NOT_INDEPENDENT_HOLDOUT" or
            cases_obj.get("projection_repo") != REGISTRY or
            cases_obj.get("projection_source_commit") != projection["sourceCommit"] or
            cases_obj.get("node_count_expected") != len(nodes) or
            cases_obj.get("limit") != 3):
        raise BenchmarkHold("FIXTURE_SOURCE_DRIFT")
    auth = cases_obj.get("authority") or {}
    if (auth.get("independent_blind_labels") is not False or
            auth.get("models_trained_on_cases") is not False or
            auth.get("scientific_claims_permitted") is not False or
            auth.get("registry_writes") is not False or
            auth.get("candidate_promotion") is not False):
        raise BenchmarkHold("FIXTURE_AUTHORITY_HOLD")
    cases = cases_obj.get("cases")
    if not isinstance(cases, list) or not (1 <= len(cases) <= MAX_CASES):
        raise BenchmarkHold("FIXTURE_CASE_COUNT_HOLD")
    all_paths = {n["path"] for n in nodes if isinstance(n, dict) and isinstance(n.get("path"), str)}
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"id", "query", "gold"}:
            raise BenchmarkHold("CASE_FIELDS_INVALID")
        ident, q, gold = case["id"], case["query"], case["gold"]
        if (not isinstance(ident, str) or not ident or ident in ids or
                not isinstance(q, str) or not q.strip() or len(q) > 200 or
                not isinstance(gold, list) or len(gold) > 3 or
                any(not isinstance(p, str) or p not in all_paths for p in gold)):
            raise BenchmarkHold("CASE_LABELS_INVALID")
        ids.add(ident)
    hrain = _load_hrain(hrain_source)
    hrain.validate_projection(projection)
    def selected(query, limit):
        return [r["path"] for r in hrain.select_nodes(projection, query, limit=limit)]
    graph = _evaluate_ranking(cases, selected, cases_obj["limit"])
    path = _evaluate_ranking(cases, lambda q, k: filename_baseline(projection, q, k), cases_obj["limit"])
    body = {
        "schema": SCHEMA,
        "status": "DEVELOPMENT_SMOKE_ONLY_NO_INDEPENDENT_GAIN_CLAIM",
        "index_source_commit": projection["sourceCommit"],
        "projection_sha256": projection_sha,
        "fixture_sha256": cases_sha,
        "hrain_source_sha256": hashlib.sha256(hrain_source.read_bytes()).hexdigest(),
        "node_count": len(nodes),
        "query_count": len(cases),
        "k": cases_obj["limit"],
        "hrain_graph": graph,
        "filename_only_baseline": path,
        "model_answer_accuracy_measured": False,
        "scientific_holdout_touched": False,
        "claim_of_independent_generalization": False,
        "model_weights_modified": False,
        "source_write_authority": False,
    }
    body["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--projection", type=Path, required=True)
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--hrain-source", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True)
    a = ap.parse_args()
    report = run_benchmark(a.projection, a.cases, a.hrain_source)
    if a.receipt.exists():
        raise BenchmarkHold("RECEIPT_ALREADY_EXISTS")
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({
        "status": report["status"], "query_count": report["query_count"],
        "hrain_correct": report["hrain_graph"]["correct_cases"],
        "filename_correct": report["filename_only_baseline"]["correct_cases"],
        "hrain_abstentions": report["hrain_graph"]["no_match_correct_abstentions"],
        "filename_abstentions": report["filename_only_baseline"]["no_match_correct_abstentions"],
        "receipt_sha256": report["receipt_sha256"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
