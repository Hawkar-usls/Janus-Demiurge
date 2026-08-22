#!/usr/bin/env python3
"""Deterministic native-cruise navigation/swath/raw-pointer gate for HA10.

Goal:
    frozen point -> source cruise -> navigation/track record -> native swath/raw holding
    -> exact point-to-track distance when machine-readable navigation is public
    -> public raw/data pointer + provenance

This gate is intentionally model-independent and fail-closed. A metadata bounding box is
never promoted to an exact track crossing. A declared download is preserved separately from
a successfully retrieved raw file. Missing public access becomes a bounded negative result,
not a claim that the cruise/data never existed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse
import zipfile

import requests
from bs4 import BeautifulSoup

from demiurge_mail_research_swarm import USER_AGENT, agent_map, canonical_hash, host_allowed, scrub

TARGETS: Dict[str, Tuple[float, float]] = {
    "H10N1": (-7.845673, -14.480230),
    "H10S2": (-8.959100, -14.645310),
}

CRUISES: Dict[str, Dict[str, Any]] = {
    "JR53-AMT11": {
        "aliases": ["JR53", "JR20000912", "AMT11"],
        "seed_urls": [
            "https://www.bodc.ac.uk/data/documents/cruise/5627/",
        ],
    },
    "JR287": {
        "aliases": ["JR287", "JR254F"],
        "seed_urls": [
            "https://www.bodc.ac.uk/resources/inventories/cruise_inventory/reports/jr287.pdf",
        ],
    },
    "JR15001": {
        "aliases": ["JR15001", "JR864", "AMT25"],
        "seed_urls": [
            "https://www.bodc.ac.uk/data/documents/cruise/15726/",
            "https://www.bodc.ac.uk/data/documents/series/1762365/",
        ],
        "known_navigation_series": ["1762365"],
    },
    "JR16-NG": {
        "aliases": ["JR16-NG", "JR16NG"],
        "seed_urls": [
            "https://data.bas.ac.uk/full-record.php?id=GB%2FNERC%2FBAS%2FPDC%2F01236",
        ],
    },
}

ASSIGNMENTS: Dict[str, List[str]] = {
    "SCOUT_DEMIHEAD_08": ["JR53-AMT11"],
    "SCOUT_FUNDAMENTUM_09": ["JR287"],
    "SCOUT_CAT_10": ["JR15001"],
    "SCOUT_SCOBY_11": ["JR16-NG"],
    "SCOUT_LAPIS_12": ["JR53-AMT11", "JR287", "JR15001", "JR16-NG"],
    "SCOUT_AIFC_16": ["JR53-AMT11", "JR287", "JR15001", "JR16-NG"],
    "SCOUT_GENESIS_17": ["JR53-AMT11", "JR287", "JR15001", "JR16-NG"],
}

MAX_SERIES_PER_CRUISE = 28
MAX_DOWNLOAD_CANDIDATES = 16
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_TRACK_POINTS = 500_000
TRACK_EXACT_TOLERANCE_M = 25.0
TRACK_NEARBY_TOLERANCE_M = 1000.0
SERIES_RE = re.compile(r"/data/documents/series/(\d+)/?", re.I)
FLOAT_RE = r"[-+]?\d+(?:\.\d+)?"
FILE_EXTS = (".csv", ".tsv", ".txt", ".odv", ".kml", ".kmz", ".geojson", ".json", ".zip", ".nc", ".grd", ".asc", ".all", ".raw", ".aco")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(url: str, allowed: Sequence[str], *, binary: bool = False, timeout: int = 25) -> Dict[str, Any]:
    rec: Dict[str, Any] = {"url": scrub(url), "status": "UNFETCHED"}
    if not host_allowed(url, list(allowed)):
        rec["status"] = "BLOCKED_BY_ALLOWLIST"
        return rec
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
        rec["final_url"] = scrub(r.url)
        rec["http_status"] = int(r.status_code)
        rec["content_type"] = scrub(r.headers.get("content-type") or "")
        r.raise_for_status()
        data = r.content
        rec["bytes"] = len(data)
        rec["sha256"] = sha256_bytes(data)
        rec["status"] = "FETCHED"
        if not binary:
            enc = r.encoding or "utf-8"
            try:
                rec["text"] = scrub(data.decode(enc, errors="replace"))
            except Exception:
                rec["text"] = scrub(data.decode("utf-8", errors="replace"))
        else:
            rec["data"] = data
    except Exception as exc:
        rec["status"] = "FETCH_FAILED"
        rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1000]
    return rec


def soup_links(base_url: str, html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out: List[Dict[str, str]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, str(a.get("href") or ""))
        if href in seen:
            continue
        seen.add(href)
        out.append({"url": scrub(href), "label": scrub(a.get_text(" ", strip=True))[:500]})
    return out


def candidate_series_from_html(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    scored: Dict[str, int] = {}
    keywords = ("navigation", "bathym", "single-beam", "multi-beam", "multibeam", "horizontal spatial", "platform movement", "echosounder", "echo sounder")
    for row in soup.find_all(["tr", "li", "p"]):
        text = row.get_text(" ", strip=True).lower()
        score = sum(1 for k in keywords if k in text)
        for a in row.find_all("a", href=True):
            m = SERIES_RE.search(urljoin(base_url, str(a.get("href") or "")))
            if m:
                sid = m.group(1)
                scored[sid] = max(scored.get(sid, 0), score)
    for m in SERIES_RE.finditer(html):
        scored.setdefault(m.group(1), 0)
    ordered = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    return [sid for sid, _ in ordered[:MAX_SERIES_PER_CRUISE]]


def extract_download_candidates(base_url: str, html: str, allowed: Sequence[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for item in soup_links(base_url, html):
        url = item["url"]
        label = item["label"].lower()
        path = urlparse(url).path.lower()
        score = 0
        if any(k in label for k in ("download", "data", "odv", "file", "track", "navigation", "swath", "multibeam")):
            score += 2
        if any(path.endswith(ext) for ext in FILE_EXTS):
            score += 4
        if any(k in url.lower() for k in ("download", "delivery", "data/search", "data/request")):
            score += 2
        if score <= 0 or url in seen or not host_allowed(url, list(allowed)):
            continue
        seen.add(url)
        out.append({"url": url, "label": item["label"], "score": str(score)})
    out.sort(key=lambda x: (-int(x["score"]), x["url"]))
    return out[:MAX_DOWNLOAD_CANDIDATES]


def parse_bounds(text: str) -> Optional[Dict[str, float]]:
    pats = {
        "south": r"Southernmost\s+Latitude\s+(%s)\s*([NS])" % FLOAT_RE,
        "north": r"Northernmost\s+Latitude\s+(%s)\s*([NS])" % FLOAT_RE,
        "west": r"Westernmost\s+Longitude\s+(%s)\s*([EW])" % FLOAT_RE,
        "east": r"Easternmost\s+Longitude\s+(%s)\s*([EW])" % FLOAT_RE,
    }
    vals: Dict[str, float] = {}
    for key, pat in pats.items():
        m = re.search(pat, text, re.I)
        if not m:
            return None
        value = float(m.group(1))
        hemi = m.group(2).upper()
        if hemi in {"S", "W"}:
            value = -value
        vals[key] = value
    return vals


def inside_bounds(lat: float, lon: float, b: Dict[str, float]) -> bool:
    return b["south"] <= lat <= b["north"] and b["west"] <= lon <= b["east"]


def parse_series_metadata(url: str, text: str, allowed: Sequence[str]) -> Dict[str, Any]:
    low = text.lower()
    m_id = re.search(r"BODC\s+Series\s+Reference\s+(\d+)", text, re.I)
    if not m_id:
        m_id = SERIES_RE.search(url)
    m_origin = re.search(r"Originator'?s\s+Identifier\s+([^\n\r]+)", text, re.I)
    m_interval = re.search(r"Nominal\s+Cycle\s+Interval\s+([^\n\r]+)", text, re.I)
    bounds = parse_bounds(text)
    nav_signal = any(k in low for k in ("navigation", "alatgp01", "alongp01", "horizontal spatial co-ordinates", "horizontal platform movement"))
    bathy_signal = any(k in low for k in ("bathymetry", "echosounder", "echo-sounder", "multibeam", "multi-beam", "mbanzz01"))
    declared_download = "download available" in low or "online delivery of data" in low
    pointers = extract_download_candidates(url, text, allowed)
    return {
        "series_id": m_id.group(1) if m_id else None,
        "url": scrub(url),
        "originator_identifier": scrub(m_origin.group(1)).strip()[:300] if m_origin else None,
        "nominal_cycle_interval": scrub(m_interval.group(1)).strip()[:200] if m_interval else None,
        "bounds": bounds,
        "has_navigation_coordinates": nav_signal,
        "has_bathymetry": bathy_signal,
        "declares_online_download": declared_download,
        "download_candidates": pointers,
        "page_sha256": sha256_text(text),
    }


def _xy_m(lat0: float, lon0: float, lat: float, lon: float) -> Tuple[float, float]:
    c = max(0.05, math.cos(math.radians(lat0)))
    return ((lon - lon0) * 111_320.0 * c, (lat - lat0) * 110_574.0)


def point_segment_distance_m(lat0: float, lon0: float, a: Tuple[float, float], b: Tuple[float, float]) -> float:
    ax, ay = _xy_m(lat0, lon0, a[0], a[1])
    bx, by = _xy_m(lat0, lon0, b[0], b[1])
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    if d2 <= 1e-18:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / d2))
    return math.hypot(ax + t * dx, ay + t * dy)


def track_distance(points: Sequence[Tuple[float, float]], target: Tuple[float, float]) -> Optional[float]:
    if not points:
        return None
    if len(points) == 1:
        x, y = _xy_m(target[0], target[1], points[0][0], points[0][1])
        return math.hypot(x, y)
    best = float("inf")
    for i in range(len(points) - 1):
        best = min(best, point_segment_distance_m(target[0], target[1], points[i], points[i + 1]))
    return best if math.isfinite(best) else None


def parse_kml(text: str) -> List[Tuple[float, float]]:
    pts: List[Tuple[float, float]] = []
    for block in re.findall(r"<coordinates[^>]*>(.*?)</coordinates>", text, flags=re.I | re.S):
        for token in re.split(r"\s+", block.strip()):
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except Exception:
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                pts.append((lat, lon))
                if len(pts) >= MAX_TRACK_POINTS:
                    return pts
    return pts


def parse_delimited_track(text: str) -> List[Tuple[float, float]]:
    lines = [ln for ln in text.splitlines() if ln.strip()][:MAX_TRACK_POINTS + 200]
    if not lines:
        return []
    header_idx = None
    lat_idx = lon_idx = None
    sep = None
    for i, line in enumerate(lines[:120]):
        for candidate in ("\t", ",", ";", "|"):
            cols = [c.strip().lower() for c in line.split(candidate)]
            if len(cols) < 2:
                continue
            li = next((j for j, c in enumerate(cols) if "latitude" in c or c in {"lat", "alatgp01"}), None)
            lo = next((j for j, c in enumerate(cols) if "longitude" in c or c in {"lon", "long", "alongp01"}), None)
            if li is not None and lo is not None and li != lo:
                header_idx, lat_idx, lon_idx, sep = i, li, lo, candidate
                break
        if header_idx is not None:
            break
    if header_idx is None or sep is None or lat_idx is None or lon_idx is None:
        return []
    pts: List[Tuple[float, float]] = []
    for line in lines[header_idx + 1:]:
        cols = [c.strip().strip('"') for c in line.split(sep)]
        if max(lat_idx, lon_idx) >= len(cols):
            continue
        try:
            lat, lon = float(cols[lat_idx]), float(cols[lon_idx])
        except Exception:
            continue
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            pts.append((lat, lon))
            if len(pts) >= MAX_TRACK_POINTS:
                break
    return pts


def parse_track_payload(url: str, content_type: str, data: bytes) -> Tuple[List[Tuple[float, float]], str]:
    low_url = url.lower()
    low_ct = content_type.lower()
    if len(data) > MAX_DOWNLOAD_BYTES:
        return [], "TOO_LARGE_TO_PARSE"
    if low_url.endswith(".kmz") or "zip" in low_ct or low_url.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist()[:100]:
                    low = name.lower()
                    if not low.endswith((".kml", ".csv", ".tsv", ".txt", ".odv", ".geojson", ".json")):
                        continue
                    raw = zf.read(name)
                    text = raw.decode("utf-8", errors="replace")
                    pts = parse_kml(text) if low.endswith(".kml") else parse_delimited_track(text)
                    if pts:
                        return pts, f"ZIP_MEMBER:{name}"
        except Exception:
            return [], "ZIP_PARSE_FAILED"
        return [], "ZIP_NO_PARSEABLE_TRACK"
    text = data.decode("utf-8", errors="replace")
    if low_url.endswith(".kml") or "kml" in low_ct or "<coordinates" in text[:20000].lower():
        pts = parse_kml(text)
        return pts, "KML" if pts else "KML_NO_TRACK"
    pts = parse_delimited_track(text)
    return pts, "DELIMITED" if pts else "NO_PARSEABLE_TRACK"


def evaluate_downloads(series: Dict[str, Any], allowed: Sequence[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for pointer in series.get("download_candidates", [])[:MAX_DOWNLOAD_CANDIDATES]:
        url = str(pointer.get("url") or "")
        if not url:
            continue
        rec = fetch(url, allowed, binary=True, timeout=30)
        item: Dict[str, Any] = {k: rec.get(k) for k in ("url", "final_url", "status", "http_status", "content_type", "bytes", "sha256", "error") if rec.get(k) is not None}
        item["label"] = pointer.get("label")
        if rec.get("status") == "FETCHED" and isinstance(rec.get("data"), (bytes, bytearray)):
            pts, parser = parse_track_payload(str(rec.get("final_url") or url), str(rec.get("content_type") or ""), bytes(rec["data"]))
            item["track_parser"] = parser
            item["track_point_count"] = len(pts)
            if pts:
                distances = {}
                for name, target in TARGETS.items():
                    dist = track_distance(pts, target)
                    if dist is not None:
                        distances[name] = round(dist, 3)
                item["point_to_track_distance_m"] = distances
        results.append(item)
    return results


def cruise_from_report_sources(report: Dict[str, Any], aliases: Sequence[str], allowed: Sequence[str]) -> List[str]:
    urls: List[str] = []
    seen = set()
    for src in report.get("discovery", {}).get("sources", []):
        if not isinstance(src, dict) or src.get("status") != "FETCHED":
            continue
        text = str(src.get("excerpt") or "")
        if not any(alias.lower() in text.lower() for alias in aliases):
            continue
        url = str(src.get("final_url") or src.get("url") or "")
        if url and url not in seen and host_allowed(url, list(allowed)):
            seen.add(url)
            urls.append(url)
    return urls[:12]


def gather_cruise(cruise_id: str, report: Dict[str, Any], allowed: Sequence[str], download: bool = True) -> Dict[str, Any]:
    cfg = CRUISES[cruise_id]
    seed_urls = list(cfg.get("seed_urls", [])) + cruise_from_report_sources(report, cfg.get("aliases", []), allowed)
    page_receipts: List[Dict[str, Any]] = []
    series_ids = set(str(x) for x in cfg.get("known_navigation_series", []))
    raw_pointers: List[Dict[str, Any]] = []
    for url in seed_urls:
        if not host_allowed(url, list(allowed)):
            continue
        rec = fetch(url, allowed, binary=False)
        page_receipts.append({k: v for k, v in rec.items() if k != "text"})
        if rec.get("status") != "FETCHED":
            continue
        text = str(rec.get("text") or "")
        if "html" in str(rec.get("content_type") or "").lower() or "<html" in text[:1000].lower():
            series_ids.update(candidate_series_from_html(str(rec.get("final_url") or url), text))
            for p in extract_download_candidates(str(rec.get("final_url") or url), text, allowed):
                if any(str(p.get("url", "")).lower().endswith(ext) for ext in FILE_EXTS):
                    raw_pointers.append(p)

    series: List[Dict[str, Any]] = []
    for sid in sorted(series_ids)[:MAX_SERIES_PER_CRUISE]:
        url = f"https://www.bodc.ac.uk/data/documents/series/{sid}/"
        if not host_allowed(url, list(allowed)):
            continue
        rec = fetch(url, allowed, binary=False)
        if rec.get("status") != "FETCHED":
            series.append({"series_id": sid, "url": url, "status": rec.get("status"), "error": rec.get("error")})
            continue
        meta = parse_series_metadata(str(rec.get("final_url") or url), str(rec.get("text") or ""), allowed)
        meta["status"] = "FETCHED"
        if not (meta.get("has_navigation_coordinates") or meta.get("has_bathymetry")):
            continue
        for name, (lat, lon) in TARGETS.items():
            b = meta.get("bounds")
            if isinstance(b, dict):
                meta.setdefault("target_envelope_membership", {})[name] = inside_bounds(lat, lon, b)
        if download and meta.get("download_candidates"):
            meta["download_attempts"] = evaluate_downloads(meta, allowed)
        series.append(meta)

    dedup_raw = []
    seen_raw = set()
    for p in raw_pointers:
        u = str(p.get("url") or "")
        if u and u not in seen_raw:
            seen_raw.add(u)
            dedup_raw.append(p)

    exact: Dict[str, List[Dict[str, Any]]] = {name: [] for name in TARGETS}
    nearby: Dict[str, List[Dict[str, Any]]] = {name: [] for name in TARGETS}
    for s in series:
        for attempt in s.get("download_attempts", []) if isinstance(s, dict) else []:
            dists = attempt.get("point_to_track_distance_m") if isinstance(attempt, dict) else None
            if not isinstance(dists, dict):
                continue
            for name, value in dists.items():
                try:
                    d = float(value)
                except Exception:
                    continue
                row = {"series_id": s.get("series_id"), "originator_identifier": s.get("originator_identifier"), "distance_m": d, "data_pointer": attempt.get("final_url") or attempt.get("url"), "data_sha256": attempt.get("sha256"), "track_point_count": attempt.get("track_point_count")}
                if d <= TRACK_EXACT_TOLERANCE_M:
                    exact.setdefault(name, []).append(row)
                if d <= TRACK_NEARBY_TOLERANCE_M:
                    nearby.setdefault(name, []).append(row)
    for name in exact:
        exact[name].sort(key=lambda x: float(x["distance_m"]))
        nearby[name].sort(key=lambda x: float(x["distance_m"]))

    nav_series = [s for s in series if isinstance(s, dict) and s.get("has_navigation_coordinates")]
    bathy_series = [s for s in series if isinstance(s, dict) and s.get("has_bathymetry")]
    declared_downloads = [s for s in series if isinstance(s, dict) and s.get("declares_online_download")]
    retrieved = [
        {"series_id": s.get("series_id"), "attempt": a}
        for s in series if isinstance(s, dict)
        for a in s.get("download_attempts", []) if isinstance(a, dict) and a.get("status") == "FETCHED"
    ]
    parseable = [x for x in retrieved if int(x["attempt"].get("track_point_count") or 0) > 0]

    return {
        "cruise_id": cruise_id,
        "aliases": cfg.get("aliases", []),
        "seed_receipts": page_receipts,
        "series_examined": len(series),
        "navigation_series": nav_series,
        "bathymetry_series": bathy_series,
        "declared_online_download_series_count": len(declared_downloads),
        "retrieved_download_count": len(retrieved),
        "parseable_track_download_count": len(parseable),
        "direct_native_file_pointers": dedup_raw[:30],
        "exact_track_hits": exact,
        "nearby_track_hits": nearby,
        "claim_ceiling": "METADATA_ENVELOPE_IS_NOT_EXACT_TRACK__EXACT_REQUIRES_MACHINE_READABLE_NAVIGATION",
    }


def finding(fid: str, claim: str, status: str, urls: Sequence[str], **facts: Any) -> Dict[str, Any]:
    return {
        "fact_id": fid,
        "claim": claim,
        "status": status,
        "source_urls": sorted({scrub(u) for u in urls if u}),
        "confidence": "HIGH" if status == "FOUND" else "MEDIUM",
        "admission_engine": "NATIVE_CRUISE_TRACKLINE_GATE_V1",
        "facts": facts,
    }


def run_gate(report: Dict[str, Any]) -> Dict[str, Any]:
    scout_id = str(report.get("scout_id") or "")
    agents = agent_map()
    agent = agents.get(scout_id)
    assigned = ASSIGNMENTS.get(scout_id, [])
    if not agent or not assigned:
        report["native_cruise_gate"] = {"schema": "janus.demiurge.native_cruise_gate.v1", "status": "NOT_ASSIGNED_TO_THIS_SCOUT", "model_required": False}
        return report
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    cruise_results: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []
    for cruise_id in assigned:
        result = gather_cruise(cruise_id, report, allowed, download=True)
        cruise_results[cruise_id] = result
        urls = [str(x.get("url") or x.get("final_url") or "") for x in result.get("seed_receipts", []) if isinstance(x, dict)]
        nav = result.get("navigation_series", [])
        bathy = result.get("bathymetry_series", [])
        if nav:
            findings.append(finding(
                f"NATIVE_CRUISE_NAV_RECORD_{cruise_id}",
                f"Public BODC metadata exposed {len(nav)} navigation-capable series record(s) for {cruise_id} in this pass.",
                "FOUND", urls + [str(x.get("url") or "") for x in nav],
                cruise=cruise_id,
                series_ids=[x.get("series_id") for x in nav],
                online_download_declared=[x.get("series_id") for x in nav if x.get("declares_online_download")],
            ))
        else:
            findings.append(finding(
                f"NATIVE_CRUISE_NAV_RECORD_{cruise_id}",
                f"No navigation-capable public BODC series record was recovered for {cruise_id} from the bounded source surface in this pass.",
                "NOT_FOUND_IN_THIS_PASS", urls, cruise=cruise_id,
            ))
        if bathy:
            findings.append(finding(
                f"NATIVE_CRUISE_BATHY_RECORD_{cruise_id}",
                f"Public metadata exposed {len(bathy)} bathymetry/echosounder series record(s) for {cruise_id} in this pass.",
                "FOUND", urls + [str(x.get("url") or "") for x in bathy],
                cruise=cruise_id, series_ids=[x.get("series_id") for x in bathy],
            ))
        for target in TARGETS:
            exact = result.get("exact_track_hits", {}).get(target, [])
            nearby = result.get("nearby_track_hits", {}).get(target, [])
            if exact:
                findings.append(finding(
                    f"NATIVE_EXACT_TRACK_{cruise_id}_{target}",
                    f"Machine-readable public navigation for {cruise_id} passes within {TRACK_EXACT_TOLERANCE_M:.0f} m of {target}.",
                    "FOUND", [str(x.get("data_pointer") or "") for x in exact],
                    cruise=cruise_id, target=target, tolerance_m=TRACK_EXACT_TOLERANCE_M, hits=exact[:20],
                ))
            elif nearby:
                findings.append(finding(
                    f"NATIVE_NEARBY_TRACK_{cruise_id}_{target}",
                    f"Machine-readable public navigation for {cruise_id} came within {TRACK_NEARBY_TOLERANCE_M:.0f} m of {target}, but did not pass the frozen exact-crossing tolerance.",
                    "POINTER_ONLY", [str(x.get("data_pointer") or "") for x in nearby],
                    cruise=cruise_id, target=target, exact_tolerance_m=TRACK_EXACT_TOLERANCE_M, nearby_tolerance_m=TRACK_NEARBY_TOLERANCE_M, hits=nearby[:20],
                ))
            else:
                envelope = [
                    {"series_id": s.get("series_id"), "inside": s.get("target_envelope_membership", {}).get(target)}
                    for s in nav if isinstance(s.get("target_envelope_membership"), dict) and target in s.get("target_envelope_membership", {})
                ]
                findings.append(finding(
                    f"NATIVE_EXACT_TRACK_{cruise_id}_{target}",
                    f"No exact public machine-readable navigation crossing for {cruise_id} at {target} was recovered in this pass; metadata envelope membership, when present, is preserved only as a locator.",
                    "NOT_FOUND_IN_THIS_PASS", urls + [str(x.get("url") or "") for x in nav],
                    cruise=cruise_id, target=target, metadata_envelope_membership=envelope,
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
    report["native_cruise_gate"] = {
        "schema": "janus.demiurge.native_cruise_gate.v1",
        "status": "COMPLETE",
        "model_required": False,
        "assigned_cruises": assigned,
        "track_exact_tolerance_m": TRACK_EXACT_TOLERANCE_M,
        "track_nearby_tolerance_m": TRACK_NEARBY_TOLERANCE_M,
        "cruises": cruise_results,
        "finding_count": len(findings),
        "findings_sha256": canonical_hash(findings),
        "claim_ceiling": "POINT_TO_TRACK_ONLY_IF_NAVIGATION_BYTES_PARSED__METADATA_ENVELOPE_NEVER_PROMOTED_TO_CROSSING",
    }
    report["schema"] = "janus.demiurge.public_research_agent_report.v4.native_cruise"
    return report


def process_report(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("REPORT_MUST_BE_OBJECT")
    path.write_text(json.dumps(run_gate(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> None:
    pts = [(-7.845673, -14.49), (-7.845673, -14.47)]
    d = track_distance(pts, TARGETS["H10N1"])
    assert d is not None and d < 1.0
    sample = "Longitude,Latitude\n-14.49,-7.845673\n-14.47,-7.845673\n"
    parsed = parse_delimited_track(sample)
    assert len(parsed) == 2
    assert track_distance(parsed, TARGETS["H10N1"]) is not None
    kml = "<coordinates>-14.49,-7.845673,0 -14.47,-7.845673,0</coordinates>"
    assert len(parse_kml(kml)) == 2
    assert len(CRUISES) == 4 and len(TARGETS) == 2
    print("NATIVE_CRUISE_TRACKLINE_GATE_SELF_TEST=PASS")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.report:
        p.error("--report is required")
    process_report(Path(args.report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
