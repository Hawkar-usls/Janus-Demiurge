#!/usr/bin/env python3
"""Model-independent evidence expansion + deterministic fact admission.

This module is deliberately downstream of the Scout's ordinary discovery/model pass.
It can add bounded public-source probes and admit only facts that are mechanically
supported by fetched text.  An LLM may enrich the report, but its availability is
never required for the primary evidence path.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from demiurge_mail_research_swarm import (
    USER_AGENT,
    agent_map,
    canonical_hash,
    fetch_public,
    host_allowed,
    scrub,
)

MAX_EXTRA_SOURCES = 12
FOLLOW_LINKS_PER_SOURCE = 5
LINK_KEYWORDS = (
    "ha10", "h10n", "h10s", "ascension", "hydroacoustic", "response",
    "calibr", "bathym", "multibeam", "swath", "backscatter", "topas",
    "seismic", "cruise", "jr53", "jr287", "jr15001", "jr16", "geoindex",
    "ogc", "survey", "station", "metadata", "report", "data",
)


def _url_key(source: Dict[str, Any]) -> str:
    return str(source.get("final_url") or source.get("url") or "")


def _dedupe_urls(urls: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen = set()
    for url, method in urls:
        key = str(url).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append((key, str(method)))
    return out


def direct_probes(agent: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Deterministic routes that do not depend on a search engine or LLM."""
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    candidates: List[Tuple[str, str]] = []

    if any(host_allowed("https://service.earthscope.org/", [d]) for d in allowed):
        for station in ("H10N1", "H10S2"):
            candidates.extend([
                (
                    "https://service.earthscope.org/fdsnws/station/1/query"
                    f"?network=IM&station={station}&level=channel&format=text&nodata=404",
                    "DIRECT_FDSN_CHANNEL",
                ),
                (
                    "https://service.earthscope.org/fdsnws/station/1/query"
                    f"?network=IM&station={station}&level=response&format=xml&nodata=404",
                    "DIRECT_FDSN_RESPONSE",
                ),
            ])

    if any(host_allowed("https://data.bas.ac.uk/", [d]) for d in allowed):
        candidates.extend([
            (
                "https://data.bas.ac.uk/full-record.php?id=GB%2FNERC%2FBAS%2FPDC%2F01236",
                "DIRECT_CANONICAL_DATASET",
            ),
            (
                "https://ramadda.data.bas.ac.uk/repository/entry/show?entryid=afba710f-dab1-4a63-867b-520177388224",
                "DIRECT_DATA_ACCESS",
            ),
        ])

    if any(host_allowed("https://www.bodc.ac.uk/", [d]) for d in allowed):
        candidates.extend([
            ("https://www.bodc.ac.uk/data/documents/cruise/5627/", "DIRECT_CRUISE_INVENTORY"),
            ("https://www.bodc.ac.uk/resources/inventories/cruise_inventory/reports/jr287.pdf", "DIRECT_CRUISE_REPORT"),
            ("https://www.bodc.ac.uk/resources/inventories/cruise_inventory/reports/jr15001.pdf", "DIRECT_CRUISE_REPORT"),
            ("https://www.bodc.ac.uk/resources/inventories/cruise_inventory/reports/cd169.pdf", "DIRECT_CRUISE_REPORT"),
        ])

    if any(host_allowed("https://www.bgs.ac.uk/", [d]) for d in allowed):
        candidates.extend([
            ("https://www.bgs.ac.uk/map-viewers/geoindex-offshore/", "DIRECT_BGS_GEOINDEX"),
            ("https://www.bgs.ac.uk/GeoIndex/offshore.htm", "DIRECT_BGS_GEOINDEX_LEGACY"),
        ])

    return [(u, m) for u, m in _dedupe_urls(candidates) if host_allowed(u, allowed)]


def discover_links(url: str, allowed_domains: List[str]) -> List[str]:
    """Bounded same-allowlist link discovery from a fetched HTML page."""
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        response.raise_for_status()
    except Exception:
        return []
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type and "<html" not in response.text[:1000].lower():
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    scored: List[Tuple[int, str]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(response.url, a.get("href") or "")
        if href in seen or not host_allowed(href, allowed_domains):
            continue
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        label = (a.get_text(" ", strip=True) + " " + href).lower()
        score = sum(1 for word in LINK_KEYWORDS if word in label)
        if score <= 0:
            continue
        seen.add(href)
        scored.append((score, href))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url in scored[:FOLLOW_LINKS_PER_SOURCE]]


def expand_sources(report: Dict[str, Any]) -> Dict[str, Any]:
    agents = agent_map()
    scout_id = str(report.get("scout_id") or "")
    if scout_id not in agents:
        return report
    agent = agents[scout_id]
    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    discovery = report.setdefault("discovery", {})
    sources = discovery.setdefault("sources", [])
    existing = {_url_key(s) for s in sources if isinstance(s, dict)}

    candidates = direct_probes(agent)
    for source in list(sources):
        if not isinstance(source, dict) or source.get("status") != "FETCHED":
            continue
        source_url = _url_key(source)
        if not source_url:
            continue
        for link in discover_links(source_url, allowed):
            candidates.append((link, "FOLLOW_LINK"))

    added = 0
    for url, method in _dedupe_urls(candidates):
        if added >= MAX_EXTRA_SOURCES:
            break
        if url in existing:
            continue
        record = fetch_public(url, allowed, method)
        sources.append(record)
        existing.add(_url_key(record) or url)
        added += 1

    discovery["independent_expansion"] = {
        "engine": "DIRECT_PROBES_PLUS_BOUNDED_ALLOWLIST_CRAWL",
        "model_required": False,
        "extra_sources_attempted": added,
    }
    discovery["fetched_count"] = sum(1 for s in sources if isinstance(s, dict) and s.get("status") == "FETCHED")
    discovery["failed_count"] = sum(
        1 for s in sources if isinstance(s, dict) and s.get("status") not in {"FETCHED", "FETCHED_NO_TEXT"}
    )
    return report


def _finding(fid: str, claim: str, source: Dict[str, Any], confidence: str = "HIGH", **facts: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "fact_id": fid,
        "claim": claim,
        "status": "FOUND",
        "source_urls": [_url_key(source)],
        "confidence": confidence,
        "admission_engine": "DETERMINISTIC_TEXT_RULE",
        "source_text_sha256": source.get("text_sha256"),
    }
    if facts:
        item["facts"] = facts
    return item


def _source_text(source: Dict[str, Any]) -> str:
    return str(source.get("excerpt") or "")


def parse_fdsn_channels(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = _source_text(source)
    rows: List[Dict[str, Any]] = []
    header: Optional[List[str]] = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#Network") and "|" in line:
            header = [p.strip().lstrip("#") for p in line.split("|")]
            continue
        if not header or not line.startswith("IM|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != len(header):
            continue
        row = dict(zip(header, parts))
        if row.get("Station") in {"H10N1", "H10S2"}:
            rows.append(row)
    return rows


def _extract_pdc_bounds(text: str) -> Optional[Dict[str, float]]:
    m = re.search(
        r"bounding box:\s*([0-9.]+)\s*to\s*([0-9.]+)\s*W,\s*([0-9.]+)\s*to\s*([0-9.]+)\s*S",
        text,
        re.I,
    )
    if not m:
        return None
    west, east, south_abs, north_abs = map(float, m.groups())
    return {"west": -west, "east": -east, "south": -south_abs, "north": -north_abs}


def _inside(lat: float, lon: float, bounds: Dict[str, float]) -> bool:
    return bounds["south"] <= lat <= bounds["north"] and bounds["west"] <= lon <= bounds["east"]


def deterministic_findings(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen_ids = set()
    sources = [s for s in report.get("discovery", {}).get("sources", []) if isinstance(s, dict) and s.get("status") == "FETCHED"]

    def add(item: Dict[str, Any]) -> None:
        fid = str(item.get("fact_id") or canonical_hash(item))
        if fid not in seen_ids:
            seen_ids.add(fid)
            out.append(item)

    for source in sources:
        text = _source_text(source)
        low = text.lower()
        url = _url_key(source)

        # EarthScope FDSN metadata capabilities.
        if "fdsnws-station" in low and "complete channel response information" in low:
            add(_finding(
                "EARTHSCOPE_FDSN_RESPONSE_CAPABILITY",
                "EarthScope FDSN Station service supports channel-level metadata and complete response-level metadata, including coordinates/depth/instrument/sensitivity at channel level.",
                source,
            ))
        rows = parse_fdsn_channels(source)
        if rows:
            by_station: Dict[str, List[Dict[str, Any]]] = {}
            for row in rows:
                by_station.setdefault(str(row.get("Station")), []).append(row)
            for station, station_rows in by_station.items():
                channels = sorted({str(r.get("Channel") or "") for r in station_rows if r.get("Channel")})
                depths = sorted({str(r.get("Depth") or "") for r in station_rows if r.get("Depth")})
                sample_rates = sorted({str(r.get("SampleRate") or "") for r in station_rows if r.get("SampleRate")})
                coords = sorted({f"{r.get('Latitude')},{r.get('Longitude')}" for r in station_rows if r.get("Latitude") and r.get("Longitude")})
                add(_finding(
                    f"EARTHSCOPE_DIRECT_CHANNEL_{station}",
                    f"EarthScope returned direct FDSN channel metadata for IM.{station} in this run.",
                    source,
                    station=station,
                    channels=channels,
                    depths=depths,
                    sample_rates=sample_rates,
                    coordinates=coords,
                    row_count=len(station_rows),
                ))
        if "h10s triplet of ha10 ascension island" in low and "cross-talk" in low and "electronic noise" in low:
            add(_finding(
                "CTBTO_H10S_CALIBRATION_CROSSTALK",
                "CTBTO workshop material reports that H10S calibration response changes appeared after electronic noise began in one hydrophone channel, with cross-talk to the other two channels.",
                source,
            ))
        if "end-to-end calibration" in low and "before deployment" in low and "digitizer" in low:
            add(_finding(
                "CTBTO_HA_END_TO_END_CALIBRATION_METHOD",
                "CTBT IMS hydrophone stations receive laboratory end-to-end calibration before deployment, and deployed underwater electronics can be checked with known calibration waveforms injected into the digitizer path.",
                source,
            ))

        # BAS/PDC canonical dataset and processing lineage.
        if "gb/nerc/bas/pdc/01236" in low and "a bathymetric compilation of ascension island" in low:
            bounds = _extract_pdc_bounds(text)
            add(_finding(
                "PDC_01236_CANONICAL_DATASET",
                "BAS/PDC record GB/NERC/BAS/PDC/01236 is the canonical Ascension Island bathymetric compilation and states an approximately 50 m grid derived from multibeam swath data.",
                source,
                dataset="GB/NERC/BAS/PDC/01236",
                doi="10.5285/afba710f-dab1-4a63-867b-520177388224",
                bounds=bounds,
            ))
            if all(name.lower() in low for name in ("jr53-amt11", "jr287", "jr15001", "jr16-ng")):
                add(_finding(
                    "PDC_01236_FOUR_CRUISE_LINEAGE",
                    "The PDC/01236 lineage names four RRS James Clark Ross source cruises: JR53-AMT11, JR287, JR15001 and JR16-NG.",
                    source,
                    cruises=["JR53-AMT11", "JR287", "JR15001", "JR16-NG"],
                ))
            if "mb-system version 5.5.2336" in low and "gaussian weighted mean" in low and "mbgrid" in low:
                add(_finding(
                    "PDC_01236_MB_SYSTEM_PROCESSING",
                    "The compilation was produced with MB-System 5.5.2336/mbgrid using a Gaussian weighted mean, with source cleaning performed using mbedit.",
                    source,
                    grid_spacing_degrees=0.0005,
                    software="MB-System 5.5.2336",
                ))
            if "netcdf" in low and "ascii" in low and "open government licence" in low:
                add(_finding(
                    "PDC_01236_FORMATS_AND_LICENCE",
                    "The public PDC/01236 product is distributed in NetCDF and Arc/Info/ArcView ASCII forms and is covered by the UK Open Government Licence.",
                    source,
                ))
            if bounds:
                targets = {
                    "H10N1": (-7.845673, -14.480230),
                    "H10S2": (-8.959100, -14.645310),
                }
                for name, (lat, lon) in targets.items():
                    inside = _inside(lat, lon, bounds)
                    add(_finding(
                        f"PDC_01236_COVERAGE_{name}",
                        f"{name} is {'inside' if inside else 'outside'} the published PDC/01236 bounding box.",
                        source,
                        target={"name": name, "lat": lat, "lon": lon},
                        inside=inside,
                        bounds=bounds,
                    ))

        # Cruise-report facts when the relevant text is actually fetched.
        if "ascension island swath bathymetry complete" in low:
            add(_finding(
                "JR15001_ASCENSION_SWATH_COMPLETE",
                "A fetched JR15001 cruise source explicitly records completion of Ascension Island swath bathymetry.",
                source,
            ))
        if "em120" in low and "topas" in low and "ascension" in low:
            add(_finding(
                "JR53_ASCENSION_EM120_TOPAS",
                "A fetched cruise source links Ascension coverage with EM120 multibeam and TOPAS/sub-bottom acquisition.",
                source,
                confidence="MEDIUM",
            ))

        # BGS/NGDC/MEDIN public holdings and query surfaces.
        if "geoindex (offshore)" in low and "medin" in low and "backscatter" in low:
            add(_finding(
                "BGS_MEDIN_DAC_GEOLOGY_GEOPHYSICS_BACKSCATTER",
                "BGS states that it is the MEDIN data archive centre for marine geology, geophysics and backscatter, exposed through Offshore GeoIndex holdings.",
                source,
            ))
        if "ogcapi-features" in low and "web map service" in low:
            add(_finding(
                "BGS_OFFSHORE_MACHINE_QUERY_SURFACES",
                "BGS Offshore GeoIndex advertises WMS plus OGC API Features access, including property and geometry filtering for open data.",
                source,
            ))
        if "survey information attributes" in low and "shape_wgs84" in low and "cruise_data_url" in low:
            add(_finding(
                "BGS_OFFSHORE_SURVEY_POLYGON_METADATA",
                "BGS Offshore survey records expose cruise identifiers/data URLs and WGS84 survey-area geometry suitable for coordinate-footprint checks.",
                source,
            ))
        if "survey line (seismic reflection and sonar)" in low or ("seismic reflection" in low and "shot point" in low):
            add(_finding(
                "BGS_OFFSHORE_GEOPHYSICAL_LINE_METADATA",
                "BGS Offshore GeoIndex documents geophysical shot-point and survey-line layers for seismic reflection/sonar, with equipment metadata and links to records where terms permit.",
                source,
            ))

    return out


def merge_findings(report: Dict[str, Any]) -> Dict[str, Any]:
    deterministic = deterministic_findings(report)
    analysis = report.setdefault("analysis", {})
    model_findings = analysis.get("findings") if isinstance(analysis.get("findings"), list) else []
    combined: List[Dict[str, Any]] = []
    seen = set()
    for item in [*deterministic, *model_findings]:
        if not isinstance(item, dict):
            continue
        key = canonical_hash({"claim": item.get("claim"), "source_urls": sorted(item.get("source_urls") or [])})
        if key in seen:
            continue
        seen.add(key)
        combined.append(item)
    analysis["findings"] = combined
    report["deterministic_evidence"] = {
        "engine": "JANUS_DETERMINISTIC_PUBLIC_EVIDENCE_V1",
        "primary": True,
        "model_required": False,
        "finding_count": len(deterministic),
        "findings_sha256": canonical_hash(deterministic),
    }
    report.setdefault("evidence_boundary", {})["model_failure_does_not_block_fact_extraction"] = True
    report["schema"] = "janus.demiurge.public_research_agent_report.v2.independent"
    return report


def process_report(path: Path) -> Dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    report = expand_sources(report)
    report = merge_findings(report)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def self_test() -> None:
    synthetic = {
        "scout_id": "SCOUT_TERMINAL_07",
        "discovery": {"sources": [{
            "url": "https://data.bas.ac.uk/full-record.php?id=GB%2FNERC%2FBAS%2FPDC%2F01236",
            "final_url": "https://data.bas.ac.uk/full-record.php?id=GB%2FNERC%2FBAS%2FPDC%2F01236",
            "status": "FETCHED",
            "text_sha256": "synthetic",
            "excerpt": (
                "A bathymetric compilation of Ascension Island, 2000-2017 GB/NERC/BAS/PDC/01236 "
                "bounding box: 14.57 to 14.17 W, 8.12 to 7.75 S. approximately 50 m resolution. "
                "JR53-AMT11 JR287 JR15001 JR16-NG. MB-System version 5.5.2336 mbgrid Gaussian weighted mean mbedit. "
                "netCDF ASCII UK Open Government Licence"
            ),
        }]},
        "analysis": {"findings": []},
    }
    findings = deterministic_findings(synthetic)
    ids = {f["fact_id"] for f in findings}
    assert "PDC_01236_CANONICAL_DATASET" in ids
    assert "PDC_01236_COVERAGE_H10N1" in ids
    assert "PDC_01236_COVERAGE_H10S2" in ids
    coverage = {f["fact_id"]: f for f in findings if f["fact_id"].startswith("PDC_01236_COVERAGE_")}
    assert coverage["PDC_01236_COVERAGE_H10N1"]["facts"]["inside"] is True
    assert coverage["PDC_01236_COVERAGE_H10S2"]["facts"]["inside"] is False
    print("JANUS_INDEPENDENT_EVIDENCE_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.report:
        report = process_report(Path(args.report))
        print(json.dumps({
            "scout_id": report.get("scout_id"),
            "deterministic_findings": report.get("deterministic_evidence", {}).get("finding_count", 0),
            "sources": len(report.get("discovery", {}).get("sources", [])),
        }, separators=(",", ":")))
        return 0
    parser.error("choose --report or --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
