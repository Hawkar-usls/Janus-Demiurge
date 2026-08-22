#!/usr/bin/env python3
"""Prefetch BODC cruise-inventory surfaces that can remain available when data/documents returns 500.

The output is appended to the normal discovery.sources list so the native-cruise gate can
reuse the page, discover linked BODC series IDs, and keep the fetch hash/provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from demiurge_mail_research_swarm import USER_AGENT, agent_map, host_allowed, scrub

URLS: Dict[str, List[str]] = {
    "SCOUT_DEMIHEAD_08": ["https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/5627/"],
    "SCOUT_CAT_10": ["https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/15726/"],
    "SCOUT_LAPIS_12": [
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/5627/",
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/15726/",
    ],
    "SCOUT_AIFC_16": [
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/5627/",
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/15726/",
    ],
    "SCOUT_GENESIS_17": [
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/5627/",
        "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/15726/",
    ],
}


def run(report: Dict[str, Any]) -> Dict[str, Any]:
    scout = str(report.get("scout_id") or "")
    agent = agent_map().get(scout)
    urls = URLS.get(scout, [])
    receipts = []
    if not agent or not urls:
        report["bodc_inventory_fallback"] = {"status": "NOT_ASSIGNED", "model_required": False}
        return report
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    sources = report.setdefault("discovery", {}).setdefault("sources", [])
    seen = {str(x.get("url") or "") for x in sources if isinstance(x, dict)}
    for url in urls:
        rec: Dict[str, Any] = {"url": url, "status": "UNFETCHED"}
        if not host_allowed(url, allowed):
            rec["status"] = "BLOCKED_BY_ALLOWLIST"
            receipts.append(rec)
            continue
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25, allow_redirects=True)
            rec.update({"final_url": scrub(r.url), "http_status": int(r.status_code), "content_type": scrub(r.headers.get("content-type") or "")})
            r.raise_for_status()
            raw = r.content
            text = raw.decode(r.encoding or "utf-8", errors="replace")
            clean = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
            rec.update({"status": "FETCHED", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            if url not in seen:
                sources.append({
                    "url": url,
                    "final_url": scrub(r.url),
                    "status": "FETCHED",
                    "title": scrub(BeautifulSoup(text, "html.parser").title.get_text(" ", strip=True) if BeautifulSoup(text, "html.parser").title else ""),
                    "content_type": rec["content_type"],
                    "text_sha256": rec["sha256"],
                    "excerpt": scrub(clean)[:120000],
                    "discovery_method": "BODC_CRUISE_INVENTORY_FALLBACK",
                })
                seen.add(url)
        except Exception as exc:
            rec["status"] = "FETCH_FAILED"
            rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1000]
        receipts.append(rec)
    report["bodc_inventory_fallback"] = {"status": "COMPLETE", "model_required": False, "receipts": receipts}
    return report


def self_test() -> None:
    assert "SCOUT_CAT_10" in URLS and "15726" in URLS["SCOUT_CAT_10"][0]
    print("BODC_CRUISE_INVENTORY_FALLBACK_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test(); return 0
    if not a.report:
        p.error("--report is required")
    path = Path(a.report)
    d = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(run(d), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
