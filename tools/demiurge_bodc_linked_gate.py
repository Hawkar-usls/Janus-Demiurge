#!/usr/bin/env python3
"""BODC Linked Open Data fallback for the HA10 native-cruise gate.

The ordinary www.bodc.ac.uk document surface can intermittently return HTTP 500 to
GitHub-hosted runners. This module independently queries BODC's documented NODB
SPARQL endpoint and preserves any series/distribution/download URIs it exposes.
It does not turn RDF metadata into an exact ship-track claim; exact crossing remains
reserved for parsed machine-readable navigation bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import requests

from demiurge_mail_research_swarm import USER_AGENT, agent_map, canonical_hash, host_allowed, scrub

ENDPOINTS = [
    "https://linked.bodc.ac.uk/sparql/",
    "http://linked.bodc.ac.uk/sparql/",
]

CRUISES: Dict[str, Dict[str, Any]] = {
    "JR53-AMT11": {"aliases": ["jr20000912", "amt11", "jr53"], "known_series": []},
    "JR287": {"aliases": ["jr287"], "known_series": []},
    "JR15001": {"aliases": ["jr15001", "amt25", "jr864", "jr15001_prodqxf_nav"], "known_series": ["1762365"]},
    "JR16-NG": {"aliases": ["jr16-ng", "jr16ng"], "known_series": []},
}

ASSIGNMENTS = {
    "SCOUT_DEMIHEAD_08": ["JR53-AMT11"],
    "SCOUT_FUNDAMENTUM_09": ["JR287"],
    "SCOUT_CAT_10": ["JR15001"],
    "SCOUT_SCOBY_11": ["JR16-NG"],
    "SCOUT_LAPIS_12": list(CRUISES),
    "SCOUT_AIFC_16": list(CRUISES),
    "SCOUT_GENESIS_17": list(CRUISES),
}

SERIES_URI_RE = re.compile(r"https?://linked\.bodc\.ac\.uk/series/(\d+)", re.I)
POINTER_WORDS = ("download", "distribution", "access", "delivery", "file", "data", "resource", "landing")
MAX_DISCOVERED_SERIES = 32
MAX_TRIPLES = 600


def _binding_value(binding: Dict[str, Any], key: str) -> str:
    item = binding.get(key)
    return str(item.get("value") or "") if isinstance(item, dict) else ""


def _sparql(query: str, allowed: Sequence[str]) -> Dict[str, Any]:
    errors: List[str] = []
    for endpoint in ENDPOINTS:
        if not host_allowed(endpoint, list(allowed)):
            errors.append(f"BLOCKED_BY_ALLOWLIST:{endpoint}")
            continue
        try:
            r = requests.get(
                endpoint,
                params={"query": query, "output": "json"},
                headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json, application/json"},
                timeout=35,
            )
            status = int(r.status_code)
            raw = r.content
            digest = hashlib.sha256(raw).hexdigest()
            r.raise_for_status()
            payload = r.json()
            bindings = payload.get("results", {}).get("bindings", []) if isinstance(payload, dict) else []
            return {
                "status": "FETCHED",
                "endpoint": scrub(r.url.split("?", 1)[0]),
                "http_status": status,
                "response_sha256": digest,
                "binding_count": len(bindings),
                "bindings": bindings[:MAX_TRIPLES],
            }
        except Exception as exc:
            errors.append(scrub(f"{endpoint}:{type(exc).__name__}:{exc}")[:1200])
    return {"status": "FETCH_FAILED", "errors": errors}


def _alias_query(aliases: Iterable[str]) -> str:
    filters = []
    for alias in aliases:
        safe = str(alias).lower().replace('"', '\\"')
        filters.append(f'CONTAINS(LCASE(STR(?o)), "{safe}")')
    expr = " || ".join(filters) or "false"
    return f"SELECT ?s ?p ?o WHERE {{ ?s ?p ?o . FILTER({expr}) }} LIMIT {MAX_TRIPLES}"


def _series_query(series_id: str) -> str:
    uri = f"http://linked.bodc.ac.uk/series/{series_id}"
    uri_https = f"https://linked.bodc.ac.uk/series/{series_id}"
    return (
        "SELECT ?s ?p ?o WHERE { "
        f"{{ BIND(<{uri}> AS ?s) ?s ?p ?o }} UNION "
        f"{{ BIND(<{uri_https}> AS ?s) ?s ?p ?o }} "
        f"}} LIMIT {MAX_TRIPLES}"
    )


def _describe_resource(uri: str, allowed: Sequence[str]) -> Dict[str, Any]:
    safe = uri.replace(">", "")
    query = f"SELECT ?s ?p ?o WHERE {{ BIND(<{safe}> AS ?s) ?s ?p ?o }} LIMIT {MAX_TRIPLES}"
    return _sparql(query, allowed)


def _reduce_bindings(bindings: List[Dict[str, Any]]) -> Dict[str, Any]:
    series = set()
    pointers: List[Dict[str, str]] = []
    literals: List[Dict[str, str]] = []
    seen_pointer = set()
    for row in bindings:
        s, p, o = (_binding_value(row, k) for k in ("s", "p", "o"))
        for value in (s, o):
            m = SERIES_URI_RE.search(value)
            if m:
                series.add(m.group(1))
        if o.startswith(("http://", "https://")):
            low = (p + " " + o).lower()
            if any(word in low for word in POINTER_WORDS):
                key = (p, o)
                if key not in seen_pointer:
                    seen_pointer.add(key)
                    pointers.append({"predicate": scrub(p), "url": scrub(o)})
        elif o and len(literals) < 100:
            literals.append({"predicate": scrub(p), "value": scrub(o)[:1000]})
    return {"series_ids": sorted(series), "pointers": pointers[:100], "literals": literals}


def run_cruise(cruise_id: str, allowed: Sequence[str]) -> Dict[str, Any]:
    cfg = CRUISES[cruise_id]
    alias_receipt = _sparql(_alias_query(cfg["aliases"]), allowed)
    alias_bindings = alias_receipt.get("bindings", []) if alias_receipt.get("status") == "FETCHED" else []
    reduced_alias = _reduce_bindings(alias_bindings)
    series_ids = set(str(x) for x in cfg.get("known_series", []))
    series_ids.update(reduced_alias["series_ids"])
    series_ids = set(list(sorted(series_ids))[:MAX_DISCOVERED_SERIES])

    series_receipts: Dict[str, Any] = {}
    all_pointers: List[Dict[str, str]] = list(reduced_alias["pointers"])
    seen_pointer = {(p["predicate"], p["url"]) for p in all_pointers}
    for sid in sorted(series_ids):
        receipt = _sparql(_series_query(sid), allowed)
        bindings = receipt.get("bindings", []) if receipt.get("status") == "FETCHED" else []
        reduced = _reduce_bindings(bindings)
        series_receipts[sid] = {
            "query_status": receipt.get("status"),
            "endpoint": receipt.get("endpoint"),
            "http_status": receipt.get("http_status"),
            "response_sha256": receipt.get("response_sha256"),
            "binding_count": receipt.get("binding_count", 0),
            "pointers": reduced["pointers"],
            "literals": reduced["literals"][:60],
        }
        for p in reduced["pointers"]:
            key = (p["predicate"], p["url"])
            if key not in seen_pointer:
                seen_pointer.add(key)
                all_pointers.append(p)

    # One-hop describe pointer-like linked resources. This can expose dcat distributions/access URLs.
    described: List[Dict[str, Any]] = []
    for pointer in all_pointers[:20]:
        url = pointer["url"]
        if not url.startswith(("http://linked.bodc.ac.uk/", "https://linked.bodc.ac.uk/")):
            continue
        rec = _describe_resource(url, allowed)
        bindings = rec.get("bindings", []) if rec.get("status") == "FETCHED" else []
        reduced = _reduce_bindings(bindings)
        described.append({
            "resource": url,
            "status": rec.get("status"),
            "response_sha256": rec.get("response_sha256"),
            "binding_count": rec.get("binding_count", 0),
            "pointers": reduced["pointers"],
        })
        for p in reduced["pointers"]:
            key = (p["predicate"], p["url"])
            if key not in seen_pointer:
                seen_pointer.add(key)
                all_pointers.append(p)

    external = [p for p in all_pointers if "linked.bodc.ac.uk" not in p["url"]]
    return {
        "cruise_id": cruise_id,
        "aliases": cfg["aliases"],
        "alias_query": {
            "status": alias_receipt.get("status"),
            "endpoint": alias_receipt.get("endpoint"),
            "http_status": alias_receipt.get("http_status"),
            "response_sha256": alias_receipt.get("response_sha256"),
            "binding_count": alias_receipt.get("binding_count", 0),
        },
        "series_ids": sorted(series_ids),
        "series": series_receipts,
        "linked_pointer_count": len(all_pointers),
        "external_pointer_count": len(external),
        "external_pointers": external[:100],
        "described_linked_resources": described,
        "claim_ceiling": "LINKED_DATA_POINTER_ONLY__NOT_EXACT_TRACK_WITHOUT_NAVIGATION_BYTES",
    }


def _finding(fid: str, claim: str, status: str, urls: List[str], **facts: Any) -> Dict[str, Any]:
    return {
        "fact_id": fid,
        "claim": claim,
        "status": status,
        "source_urls": sorted({scrub(u) for u in urls if u}),
        "confidence": "HIGH" if status == "FOUND" else "MEDIUM",
        "admission_engine": "BODC_NODB_SPARQL_GATE_V1",
        "facts": facts,
    }


def run_gate(report: Dict[str, Any]) -> Dict[str, Any]:
    scout_id = str(report.get("scout_id") or "")
    agents = agent_map()
    agent = agents.get(scout_id)
    assigned = ASSIGNMENTS.get(scout_id, [])
    if not agent or not assigned:
        report["bodc_linked_gate"] = {"schema": "janus.demiurge.bodc_linked_gate.v1", "status": "NOT_ASSIGNED_TO_THIS_SCOUT", "model_required": False}
        return report
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    results: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []
    for cruise in assigned:
        r = run_cruise(cruise, allowed)
        results[cruise] = r
        endpoint = str(r.get("alias_query", {}).get("endpoint") or "")
        if r.get("series_ids"):
            findings.append(_finding(
                f"BODC_LINKED_SERIES_{cruise}",
                f"BODC NODB Linked Open Data exposed {len(r['series_ids'])} series identifier(s) associated with the bounded {cruise} alias query/seed set.",
                "FOUND", [endpoint], cruise=cruise, series_ids=r["series_ids"],
            ))
        else:
            findings.append(_finding(
                f"BODC_LINKED_SERIES_{cruise}",
                f"No BODC NODB series identifier was recovered for {cruise} from this bounded Linked Open Data query pass.",
                "NOT_FOUND_IN_THIS_PASS", [endpoint], cruise=cruise,
            ))
        if r.get("external_pointers"):
            findings.append(_finding(
                f"BODC_LINKED_EXTERNAL_POINTER_{cruise}",
                f"BODC NODB exposed external access/data pointer candidate(s) for {cruise}; these remain pointer-level until fetched and parsed.",
                "POINTER_ONLY", [endpoint] + [p["url"] for p in r["external_pointers"]],
                cruise=cruise, pointers=r["external_pointers"],
            ))

    analysis = report.setdefault("analysis", {})
    existing = analysis.get("findings") if isinstance(analysis.get("findings"), list) else []
    combined: List[Dict[str, Any]] = []
    seen = set()
    for item in [*findings, *existing]:
        if not isinstance(item, dict):
            continue
        key = canonical_hash({"fact_id": item.get("fact_id"), "claim": item.get("claim"), "source_urls": sorted(item.get("source_urls") or [])})
        if key in seen:
            continue
        seen.add(key)
        combined.append(item)
    analysis["findings"] = combined
    report["bodc_linked_gate"] = {
        "schema": "janus.demiurge.bodc_linked_gate.v1",
        "status": "COMPLETE",
        "model_required": False,
        "documented_endpoint": "http://linked.bodc.ac.uk/sparql/",
        "assigned_cruises": assigned,
        "cruises": results,
        "finding_count": len(findings),
        "findings_sha256": canonical_hash(findings),
        "claim_ceiling": "RDF_SERIES_AND_ACCESS_POINTERS_ONLY__NO_EXACT_TRACK_INFERENCE",
    }
    return report


def process(path: Path) -> None:
    d = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(d, dict):
        raise ValueError("REPORT_MUST_BE_OBJECT")
    path.write_text(json.dumps(run_gate(d), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> None:
    b = {"s": {"type": "uri", "value": "http://linked.bodc.ac.uk/series/1762365"}, "p": {"type": "uri", "value": "http://www.w3.org/ns/dcat#distribution"}, "o": {"type": "uri", "value": "http://linked.bodc.ac.uk/foo"}}
    r = _reduce_bindings([b])
    assert r["series_ids"] == ["1762365"]
    assert len(r["pointers"]) == 1
    assert "1762365" in _series_query("1762365")
    print("BODC_LINKED_DATA_GATE_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return 0
    if not a.report:
        p.error("--report is required")
    process(Path(a.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
