#!/usr/bin/env python3
"""ESSENCE external GitHub discovery — read-only, metadata-only license gate.

Separate scout from the offline ESSENCE runtime. No git clone, file download,
source import, model training, code execution, or repository write.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

QUERIES = (
    "tiny transformer python",
    "micrograd automatic differentiation",
    "small gpt pytorch",
)
ALLOWED_SPDX = frozenset(("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause"))
MAX_RESULTS = 18
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SCHEMA = "janus.essence.github_scout/0.1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_search(query, token=""):
    if query not in QUERIES:
        raise ValueError("QUERY_OUTSIDE_CURATED_SET")
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": query, "per_page": 9, "sort": "stars", "order": "desc"})
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "JANUS-ESSENCE-legal-reference-scout/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                timeout=12) as response:
        data = response.read(750_001)
    if len(data) > 750_000:
        raise ValueError("RESPONSE_LIMIT")
    return json.loads(data)


def curate(search):
    """search(query) returns GitHub metadata; no code or text from repos is read."""
    sources = {}
    for query in QUERIES:
        response = search(query)
        if not isinstance(response, dict) or not isinstance(response.get("items"), list):
            raise ValueError("MALFORMED_GITHUB_RESPONSE")
        for raw in response["items"][:9]:
            if not isinstance(raw, dict):
                continue
            name = raw.get("full_name")
            if not isinstance(name, str) or not REPO_NAME.fullmatch(name):
                continue
            if raw.get("private") or raw.get("archived") or raw.get("disabled"):
                continue
            spdx = raw.get("license")
            spdx = spdx.get("spdx_id") if isinstance(spdx, dict) else None
            permitted = spdx in ALLOWED_SPDX
            sources[name] = {
                "repository": name,
                "github_url": "https://github.com/" + name,
                "observed_spdx": spdx if isinstance(spdx, str) and len(spdx) <= 40 else "UNKNOWN",
                "repository_level_license_gate": (
                    "METADATA_MATCH_REVIEW_REQUIRED" if permitted else "LICENSE_HOLD"),
                "reported_stars": raw.get("stargazers_count") if type(raw.get("stargazers_count")) is int else None,
                "discovery_queries": sorted(set(sources.get(name, {}).get("discovery_queries", [])) | {query}),
                "candidate_only": True,
                "source_downloaded": False,
                "source_executed": False,
                "needs_file_license_dependency_security_attribution_review": True,
            }
    ranked = sorted(sources.values(), key=lambda s:(s["repository_level_license_gate"] !=
              "METADATA_MATCH_REVIEW_REQUIRED", -(s["reported_stars"] or 0), s["repository"]))
    result = {
        "schema": SCHEMA,
        "queries": list(QUERIES),
        "repositories": ranked[:MAX_RESULTS],
        "total_unique_metadata_matches": len(sources),
        "code_downloaded": False,
        "code_executed": False,
        "automatic_copy_or_install": False,
        "independent_legal_clearance": False,
        "model_weight_training": False,
        "gate": "DISCOVERY_ONLY_REVIEW_REQUIRED",
    }
    result["sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def verify(report):
    if not isinstance(report, dict) or report.get("schema") != SCHEMA:
        raise ValueError("INVALID_SCOUT_REPORT")
    stamp = report.get("sha256")
    if stamp != hashlib.sha256(canonical({k:v for k,v in report.items()
                                           if k != "sha256"})).hexdigest():
        raise ValueError("SCOUT_SHA_MISMATCH")
    if any(report.get(k) is not False for k in ("code_downloaded", "code_executed",
             "automatic_copy_or_install", "independent_legal_clearance",
             "model_weight_training")):
        raise ValueError("SCOUT_AUTHORITY_ESCALATION")
    for row in report.get("repositories", []):
        if row.get("source_executed") is not False or row.get("source_downloaded") is not False:
            raise ValueError("UNAUTHORIZED_CODE_REUSE")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    parser.add_argument("--verify")
    args = parser.parse_args()
    if args.verify:
        report = json.loads(Path(args.verify).read_text(encoding="utf-8"))
        print(json.dumps({"verified": verify(report)}))
        return
    if not args.out:
        parser.error("--out required")
    report = curate(lambda q: read_search(q, os.environ.get("GH_TOKEN", "")))
    verify(report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"total": len(report["repositories"]), "status": report["gate"]}))


if __name__ == "__main__":
    main()
