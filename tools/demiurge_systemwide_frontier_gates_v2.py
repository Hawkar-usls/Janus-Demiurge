#!/usr/bin/env python3
"""Hardened adapter for JANUS whole-system frontier gates v1.

V2 keeps the v1 evidence semantics but improves public-source fallbacks,
waveform query syntax, zero-byte handling and MGDS UID filtering.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Tuple

import requests

import demiurge_systemwide_frontier_gates as gate
from demiurge_mail_research_swarm import USER_AGENT, scrub

# Prefer public surfaces that are reachable from GitHub-hosted runners.
gate.MONOWAI_PDF = "https://files01.core.ac.uk/download/pdf/33672084.pdf"
gate.SMETS_PDF = "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JC018451"
gate.EVERS_2025_PDF = "https://pure.tudelft.nl/ws/portalfiles/portal/249944579/076001_1_10.0037200.pdf"
gate.FRONTIER_DOMAINS.update({"core.ac.uk", "onlinelibrary.wiley.com", "agupubs.onlinelibrary.wiley.com"})


def _filtered_mgds_uids(html: str) -> List[str]:
    raw = gate.BeautifulSoup(html, "html.parser")
    hits: List[str] = []
    for tag in raw.find_all(["input", "a"]):
        attrs = " ".join(f"{k}={v}" for k, v in tag.attrs.items())
        label = f"{attrs} {tag.get_text(' ', strip=True)}"
        for pat in (
            r"(?:data[_-]?uid|file[_-]?uid|uid)[=:/\"'\s]+([A-Za-z0-9_.:-]{4,})",
            r"FileDownloadServer[^\s\"']*[?&](?:id|uid|data_uid)=([A-Za-z0-9_.:-]+)",
        ):
            for m in re.finditer(pat, label, re.I):
                value = m.group(1).strip()
                if value.lower() in {"name", "value", "file", "data", "true", "false"}:
                    continue
                # A numeric token or a token with enough entropy to plausibly be a UID.
                if not (value.isdigit() or len(value) >= 8):
                    continue
                if value not in hits:
                    hits.append(value)
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


def self_test() -> None:
    gate.self_test()
    urls = _waveform_urls_v2()
    assert all("starttime=" in u and "endtime=" in u and "nodata=404" in u for u, _ in urls)
    assert all("location=--" in u for u, _ in urls)
    assert _filtered_mgds_uids('<input name="uid" value="name"><input name="data_uid" value="4430">') == ["4430"]
    print("JANUS_SYSTEMWIDE_FRONTIER_GATE_V2_SELF_TEST=PASS")


def main() -> int:
    import sys
    if "--self-test" in sys.argv:
        self_test()
        return 0
    return gate.main()


if __name__ == "__main__":
    raise SystemExit(main())
