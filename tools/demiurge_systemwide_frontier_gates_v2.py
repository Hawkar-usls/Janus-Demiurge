#!/usr/bin/env python3
"""Hardened adapter for JANUS whole-system frontier gates v1.

V2 keeps the v1 evidence semantics but improves public-source fallbacks,
waveform query syntax, zero-byte handling and MGDS UID filtering. For peer
rounds it also closes the Scout microkernel drain after all deterministic
frontier gates have written their findings, then embeds the trace in report.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Tuple

import requests

import demiurge_systemwide_frontier_gates as gate
from demiurge_mail_research_swarm import USER_AGENT, scrub

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import scout_microkernel

FRONTIER_GATE_VERSION = "2.2_MICROKERNEL"

# Prefer public surfaces that are reachable from GitHub-hosted runners.
gate.MONOWAI_PDF = "https://files01.core.ac.uk/download/pdf/33672084.pdf"
gate.SMETS_PDF = "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JC018451"
gate.EVERS_2025_PDF = "https://pure.tudelft.nl/ws/portalfiles/portal/249944579/076001_1_10.0037200.pdf"
gate.FRONTIER_DOMAINS.update({"core.ac.uk", "onlinelibrary.wiley.com", "agupubs.onlinelibrary.wiley.com"})


def _plausible_uid(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if value.lower() in {"name", "value", "file", "data", "true", "false", "uid", "data_uid", "file_uid"}:
        return None
    if value.isdigit() or len(value) >= 8:
        return value
    return None


def _filtered_mgds_uids(html: str) -> List[str]:
    """Extract only plausible values associated with UID-labelled controls/links."""
    soup = gate.BeautifulSoup(html, "html.parser")
    hits: List[str] = []

    def add(value: Any) -> None:
        candidate = _plausible_uid(value)
        if candidate and candidate not in hits:
            hits.append(candidate)

    for tag in soup.find_all(["input", "a"]):
        for key, value in tag.attrs.items():
            key_norm = str(key).lower().replace("-", "_")
            if key_norm in {"uid", "data_uid", "file_uid", "datauid", "fileuid"}:
                add(value)
        control_name = str(tag.get("name") or tag.get("id") or "").lower().replace("-", "_")
        if "uid" in control_name:
            add(tag.get("value"))
        href = str(tag.get("href") or "")
        for m in re.finditer(r"[?&](?:id|uid|data_uid|file_uid)=([A-Za-z0-9_.:-]+)", href, re.I):
            add(m.group(1))
    return hits[:30]


def _waveform_urls_v2() -> List[Tuple[str, str]]:
    start = "2011-05-17T08:50:00"
    end = "2011-05-17T09:20:00"
    base = "https://service.earthscope.org/fdsnws/dataselect/1/query"
    return [
        (f"{base}?network=IM&station=H10N1&location=--&channel=EDH&starttime={start}&endtime={end}&nodata=404", "H10N1"),
        (f"{base}?network=IM&station=H10S2&location=--&channel=EDH&starttime={start}&endtime={end}&nodata=404", "H10S2"),
    ]


def _fetch_binary_v2(url: str, method: str, max_bytes: int = 10_000_000) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "url": url,
        "discovery_method": method,
        "status": "UNFETCHED_BINARY",
        "content_type": "",
        "bytes_read": 0,
        "raw_sha256": None,
    }
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45, stream=True) as r:
            r.raise_for_status()
            h = hashlib.sha256()
            total = 0
            exceeded = False
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    exceeded = True
                    break
                h.update(chunk)
            rec["final_url"] = r.url
            rec["content_type"] = (r.headers.get("content-type") or "").lower()
            rec["bytes_read"] = min(total, max_bytes)
            if exceeded:
                rec["status"] = "FETCH_LIMIT_EXCEEDED"
            elif total == 0:
                rec["status"] = "FETCHED_NO_DATA"
            else:
                rec["status"] = "FETCHED_BINARY"
                rec["raw_sha256"] = h.hexdigest()
    except Exception as exc:
        rec["status"] = "FETCH_FAILED"
        rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1200]
    return rec


gate._extract_mgds_uids = _filtered_mgds_uids
gate._waveform_urls = _waveform_urls_v2
gate.fetch_binary = _fetch_binary_v2


def _close_microkernel_drain(argv: List[str]) -> None:
    if "--report" not in argv:
        return
    idx = argv.index("--report")
    if idx + 1 >= len(argv):
        return
    report_path = Path(argv[idx + 1])
    if not report_path.exists():
        return
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        return
    plan = report.get("microkernel_plan")
    if not isinstance(plan, dict):
        return
    trace = scout_microkernel.finalize_trace(plan, report)
    report["microkernel_trace"] = trace
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    trace_path = report_path.parent / "MICROKERNEL_TRACE.json"
    trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("JANUS_SCOUT_MICROKERNEL_DRAIN=" + str(trace.get("status")))


def self_test() -> None:
    gate.self_test()
    urls = _waveform_urls_v2()
    assert all("starttime=" in u and "endtime=" in u and "nodata=404" in u for u, _ in urls)
    assert all("location=--" in u for u, _ in urls)
    sample = '<input name="uid" value="name"><input name="data_uid" value="4430"><a href="/x?file_uid=abc123456">x</a>'
    assert _filtered_mgds_uids(sample) == ["4430", "abc123456"]
    scout_microkernel.self_test()
    print("JANUS_SYSTEMWIDE_FRONTIER_GATE_V2_SELF_TEST=PASS")


def main() -> int:
    if "--self-test" in sys.argv:
        self_test()
        return 0
    rc = gate.main()
    if rc == 0:
        _close_microkernel_drain(sys.argv)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
