#!/usr/bin/env python3
"""Extract cruise -> BODC series/track-chart pointers directly from Cruise Inventory HTML.

This is a metadata-pointer gate. It is deliberately weaker than the native-track gate:
series rows and track-chart links can establish that a cruise has a public navigation or
bathymetry holding/pointer, but cannot establish an exact H10 crossing without parsing the
underlying navigation coordinates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from demiurge_mail_research_swarm import USER_AGENT, agent_map, canonical_hash, host_allowed, scrub

INVENTORY_URLS: Dict[str, Dict[str, Any]] = {
    "JR53-AMT11": {
        "url": "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/5627/",
        "aliases": ["JR53", "JR20000912", "AMT11"],
    },
    "JR15001": {
        "url": "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/report/15726/",
        "aliases": ["JR15001", "JR864", "AMT25"],
    },
}

ASSIGNMENTS = {
    "SCOUT_DEMIHEAD_08": ["JR53-AMT11"],
    "SCOUT_CAT_10": ["JR15001"],
    "SCOUT_LAPIS_12": ["JR53-AMT11", "JR15001"],
    "SCOUT_AIFC_16": ["JR53-AMT11", "JR15001"],
    "SCOUT_GENESIS_17": ["JR53-AMT11", "JR15001"],
}

SERIES_RE = re.compile(r"/data/documents/series/(\d+)/?", re.I)
SERIES_ID_TEXT_RE = re.compile(r"\b(\d{6,9})\b")
NAV_WORDS = (
    "horizontal spatial co-ordinates", "horizontal spatial coordinates", "navigation",
    "platform movement", "single-beam echosounder", "single beam echosounder",
    "bathymetry and elevation", "bathymetry",
)
SWATH_WORDS = ("multibeam", "multi-beam", "swath", "em122", "em120")
TRACK_WORDS = ("track chart", "track charts", "trackchart", "cruise track")


def _fetch_html(url: str, allowed: Sequence[str]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {"url": url, "status": "UNFETCHED"}
    if not host_allowed(url, list(allowed)):
        rec["status"] = "BLOCKED_BY_ALLOWLIST"
        return rec
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, allow_redirects=True)
        rec.update({
            "final_url": scrub(r.url),
            "http_status": int(r.status_code),
            "content_type": scrub(r.headers.get("content-type") or ""),
        })
        r.raise_for_status()
        raw = r.content
        rec.update({
            "status": "FETCHED",
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "html": raw.decode(r.encoding or "utf-8", errors="replace"),
        })
    except Exception as exc:
        rec["status"] = "FETCH_FAILED"
        rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1000]
    return rec


def _series_rows(base_url: str, html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: List[Dict[str, Any]] = []
    seen = set()
    # Standard linked rows first.
    for tr in soup.find_all("tr"):
        text = scrub(tr.get_text(" ", strip=True))
        low = text.lower()
        series_ids = set()
        links = []
        for a in tr.find_all("a", href=True):
            href = urljoin(base_url, str(a.get("href") or ""))
            m = SERIES_RE.search(href)
            if m:
                series_ids.add(m.group(1))
                links.append(href)
        # Some BODC inventory tables render the id as text and only the doc icon is linked.
        if not series_ids and any(w in low for w in NAV_WORDS):
            for m in SERIES_ID_TEXT_RE.finditer(text):
                sid = m.group(1)
                if len(sid) >= 6:
                    series_ids.add(sid)
        if not series_ids:
            continue
        for sid in sorted(series_ids):
            key = (sid, text)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "series_id": sid,
                "row_text": text[:5000],
                "series_url": f"https://www.bodc.ac.uk/data/documents/series/{sid}/",
                "linked_urls": sorted(set(scrub(x) for x in links)),
                "navigation_signal": any(w in low for w in NAV_WORDS),
                "swath_signal": any(w in low for w in SWATH_WORDS),
            })
    # Fallback: scan local text blocks around known series links.
    if not rows:
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, str(a.get("href") or ""))
            m = SERIES_RE.search(href)
            if not m:
                continue
            container = a.find_parent(["tr", "li", "div", "p"]) or a.parent
            text = scrub(container.get_text(" ", strip=True) if container else a.get_text(" ", strip=True))
            low = text.lower()
            rows.append({
                "series_id": m.group(1),
                "row_text": text[:5000],
                "series_url": scrub(href),
                "linked_urls": [scrub(href)],
                "navigation_signal": any(w in low for w in NAV_WORDS),
                "swath_signal": any(w in low for w in SWATH_WORDS),
            })
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sid = str(row["series_id"])
        current = dedup.get(sid)
        if current is None or (row["navigation_signal"], row["swath_signal"], len(row["row_text"])) > (current["navigation_signal"], current["swath_signal"], len(current["row_text"])):
            dedup[sid] = row
    return [dedup[k] for k in sorted(dedup)]


def _track_links(base_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, str(a.get("href") or ""))
        label = scrub(a.get_text(" ", strip=True))
        context = scrub((a.parent.get_text(" ", strip=True) if a.parent else label))
        low = (label + " " + context + " " + href).lower()
        if not any(w in low for w in TRACK_WORDS):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": scrub(href), "label": label[:500], "context": context[:1200]})
    return out[:30]


def _finding(fid: str, claim: str, status: str, urls: List[str], **facts: Any) -> Dict[str, Any]:
    return {
        "fact_id": fid,
        "claim": claim,
        "status": status,
        "source_urls": sorted({u for u in urls if u}),
        "confidence": "HIGH" if status == "FOUND" else "MEDIUM",
        "admission_engine": "BODC_CRUISE_INVENTORY_SERIES_GATE_V1",
        "facts": facts,
    }


def run_gate(report: Dict[str, Any]) -> Dict[str, Any]:
    scout_id = str(report.get("scout_id") or "")
    agent = agent_map().get(scout_id)
    assigned = ASSIGNMENTS.get(scout_id, [])
    if not agent or not assigned:
        report["bodc_inventory_series_gate"] = {"schema": "janus.demiurge.bodc_inventory_series_gate.v1", "status": "NOT_ASSIGNED", "model_required": False}
        return report
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    cruises: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []
    for cruise in assigned:
        cfg = INVENTORY_URLS[cruise]
        rec = _fetch_html(cfg["url"], allowed)
        rows: List[Dict[str, Any]] = []
        tracks: List[Dict[str, str]] = []
        if rec.get("status") == "FETCHED":
            html = str(rec.get("html") or "")
            rows = _series_rows(str(rec.get("final_url") or cfg["url"]), html)
            tracks = _track_links(str(rec.get("final_url") or cfg["url"]), html)
        nav_rows = [r for r in rows if r.get("navigation_signal")]
        swath_rows = [r for r in rows if r.get("swath_signal")]
        cruises[cruise] = {
            "inventory_url": cfg["url"],
            "status": rec.get("status"),
            "http_status": rec.get("http_status"),
            "response_sha256": rec.get("sha256"),
            "series_rows": rows,
            "navigation_or_bathymetry_series": nav_rows,
            "swath_series": swath_rows,
            "track_chart_pointers": tracks,
            "claim_ceiling": "CRUISE_TO_SERIES_OR_CHART_POINTER_ONLY__NO_EXACT_TRACK_FROM_METADATA",
        }
        if nav_rows:
            findings.append(_finding(
                f"BODC_INVENTORY_NAV_SERIES_{cruise}",
                f"BODC Cruise Inventory exposes {len(nav_rows)} navigation/bathymetry series pointer(s) for {cruise} on the successfully fetched inventory surface.",
                "FOUND", [cfg["url"]] + [r["series_url"] for r in nav_rows],
                cruise=cruise,
                series=[{"series_id": r["series_id"], "series_url": r["series_url"], "row_text": r["row_text"]} for r in nav_rows[:30]],
            ))
        else:
            findings.append(_finding(
                f"BODC_INVENTORY_NAV_SERIES_{cruise}",
                f"No navigation/bathymetry series pointer was parsed for {cruise} from the bounded Cruise Inventory page in this pass.",
                "NOT_FOUND_IN_THIS_PASS", [cfg["url"]], cruise=cruise,
            ))
        if tracks:
            findings.append(_finding(
                f"BODC_INVENTORY_TRACK_CHART_{cruise}",
                f"BODC Cruise Inventory exposes track-chart pointer(s) for {cruise}; chart presence is not an exact coordinate crossing.",
                "POINTER_ONLY", [cfg["url"]] + [x["url"] for x in tracks], cruise=cruise, pointers=tracks,
            ))

    analysis = report.setdefault("analysis", {})
    existing = analysis.get("findings") if isinstance(analysis.get("findings"), list) else []
    combined = []
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
    report["bodc_inventory_series_gate"] = {
        "schema": "janus.demiurge.bodc_inventory_series_gate.v1",
        "status": "COMPLETE",
        "model_required": False,
        "assigned_cruises": assigned,
        "cruises": cruises,
        "finding_count": len(findings),
        "findings_sha256": canonical_hash(findings),
        "claim_ceiling": "SERIES_AND_TRACK_CHART_POINTERS_ONLY__EXACT_CROSSING_REQUIRES_NAVIGATION_BYTES",
    }
    return report


def self_test() -> None:
    html = '<table><tr><td><a href="/data/documents/series/1762365/">1762365</a></td><td>Horizontal spatial co-ordinates Bathymetry and Elevation</td></tr></table>'
    rows = _series_rows("https://www.bodc.ac.uk/x", html)
    assert rows and rows[0]["series_id"] == "1762365" and rows[0]["navigation_signal"]
    print("BODC_CRUISE_INVENTORY_SERIES_GATE_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test(); return 0
    if not a.report:
        p.error("--report required")
    path = Path(a.report)
    d = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(run_gate(d), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
