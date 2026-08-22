#!/usr/bin/env python3
"""Deterministic frontier gates for the whole-system JANUS Scout turn.

These probes implement the high-information next actions selected by the current
JANUS lineage. They are evidence gates, not anomaly detectors: raw/public source
bytes are hashed, source semantics are kept explicit, prior negative certificates
remain immutable, and no model output is needed.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from demiurge_mail_research_swarm import USER_AGENT, canonical_hash, scrub

MAX_BYTES = 16_000_000
MAX_TEXT = 90_000

MGDS_DATA = "https://www.marine-geo.org/tools/files/30497"
MGDS_DOI = "https://www.marine-geo.org/doi/10.26022/IEDA/330497"
MGDS_FILESERVER_DOCS = "https://marine-geo.org/tools/fileserverinfo.php"
NOAA_PARNELL = "https://repository.library.noaa.gov/view/noaa/54306/noaa_54306_DS1.pdf"
MONOWAI_PDF = "https://pure.lib.usf.edu/files/40515107/Ultra_Long_Range%20Hydroacoustic%20Observations%20of%20Submarine%20Volcanic.pdf"
SMETS_PDF = "https://pure.tudelft.nl/ws/portalfiles/portal/121753315/JGR_Oceans_2022_Smets_Hydroacoustic_Travel_Time_Variations_as_a_Proxy_for_Passive_Deep_Ocean_Thermometry_A_Cookbook.pdf"
EVERS_2025_PDF = "https://research.tudelft.nl/files/249944579/076001_1_10.0037200.pdf"
CTBTO_CAL = "https://conferences-test.ctbto.org/event/25/contributions/4421/"
BODC_1762365 = "https://www.bodc.ac.uk/data/documents/series/1762365/"
BODC_JR53 = "https://www.bodc.ac.uk/data/documents/cruise/5627/"
BAS_PDC = "https://data.bas.ac.uk/full-record.php?id=GB%2FNERC%2FBAS%2FPDC%2F01236"

FRONTIER_DOMAINS = {
    "marine-geo.org", "repository.library.noaa.gov", "noaa.gov", "pure.lib.usf.edu",
    "lib.usf.edu", "pure.tudelft.nl", "research.tudelft.nl", "ctbto.org", "bodc.ac.uk",
    "bas.ac.uk", "earthscope.org",
}


def _host_ok(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in FRONTIER_DOMAINS)


def _pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    chunks: List[str] = []
    for page in reader.pages[:100]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
        if sum(len(x) for x in chunks) >= MAX_TEXT:
            break
    return "\n".join(chunks)[:MAX_TEXT]


def fetch_text(url: str, method: str) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "url": url, "discovery_method": method, "status": "UNFETCHED", "title": "",
        "content_type": "", "text_sha256": None, "excerpt": "",
    }
    if not _host_ok(url):
        rec["status"] = "REJECTED_DOMAIN"
        return rec
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=35, allow_redirects=True)
        r.raise_for_status()
        data = r.content[:MAX_BYTES]
        ctype = (r.headers.get("content-type") or "").lower()
        rec["final_url"] = r.url
        rec["content_type"] = ctype
        rec["bytes_read"] = len(data)
        if "pdf" in ctype or r.url.lower().endswith(".pdf"):
            text = _pdf_text(data)
            title = Path(urlparse(r.url).path).name
        else:
            decoded = data.decode(r.encoding or "utf-8", errors="replace")
            if "html" in ctype or "<html" in decoded[:1000].lower():
                soup = BeautifulSoup(decoded, "html.parser")
                title = soup.title.get_text(" ", strip=True) if soup.title else ""
                for tag in soup(["script", "style", "noscript", "svg"]):
                    tag.decompose()
                text = "\n".join(x.strip() for x in soup.get_text("\n").splitlines() if x.strip())
                rec["candidate_file_uids"] = _extract_mgds_uids(decoded)
            else:
                title = Path(urlparse(r.url).path).name
                text = decoded
            text = text[:MAX_TEXT]
        text = scrub(text)
        rec["title"] = scrub(title)[:500]
        rec["excerpt"] = text
        rec["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rec["status"] = "FETCHED" if text.strip() else "FETCHED_NO_TEXT"
    except Exception as exc:
        rec["status"] = "FETCH_FAILED"
        rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1200]
    return rec


def _extract_mgds_uids(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    hits: List[str] = []
    for tag in soup.find_all(["input", "a"]):
        attrs = " ".join(f"{k}={v}" for k, v in tag.attrs.items())
        label = f"{attrs} {tag.get_text(' ', strip=True)}"
        for pat in (
            r"(?:data[_-]?uid|file[_-]?uid|uid)[=:/'\"\s]+([A-Za-z0-9_.:-]{4,})",
            r"FileDownloadServer[^\s\"']*[?&](?:id|uid|data_uid)=([A-Za-z0-9_.:-]+)",
        ):
            for m in re.finditer(pat, label, re.I):
                if m.group(1) not in hits:
                    hits.append(m.group(1))
    return hits[:30]


def fetch_binary(url: str, method: str, max_bytes: int = 10_000_000) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "url": url, "discovery_method": method, "status": "UNFETCHED_BINARY",
        "content_type": "", "bytes_read": 0, "raw_sha256": None,
    }
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45, stream=True) as r:
            r.raise_for_status()
            h = hashlib.sha256()
            total = 0
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    rec["status"] = "FETCH_LIMIT_EXCEEDED"
                    break
                h.update(chunk)
            else:
                rec["status"] = "FETCHED_BINARY"
            rec["final_url"] = r.url
            rec["content_type"] = (r.headers.get("content-type") or "").lower()
            rec["bytes_read"] = min(total, max_bytes)
            rec["raw_sha256"] = h.hexdigest() if total and total <= max_bytes else None
    except Exception as exc:
        rec["status"] = "FETCH_FAILED"
        rec["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1200]
    return rec


def _finding(fid: str, claim: str, source: Dict[str, Any], confidence: str = "HIGH", **facts: Any) -> Dict[str, Any]:
    out = {
        "fact_id": fid,
        "claim": claim,
        "status": "FOUND",
        "source_urls": [str(source.get("final_url") or source.get("url"))],
        "confidence": confidence,
        "admission_engine": "JANUS_SYSTEMWIDE_FRONTIER_GATE_V1",
        "source_text_sha256": source.get("text_sha256"),
    }
    if facts:
        out["facts"] = facts
    return out


def _admit_text(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    if source.get("status") != "FETCHED":
        return []
    text = str(source.get("excerpt") or "")
    low = " ".join(text.lower().split())
    out: List[Dict[str, Any]] = []

    if "t-phase location catalog for equatorial atlantic ocean, 2011-2015" in low and "ha10" in low:
        out.append(_finding(
            "MGDS_EA_TPHASE_CATALOG_PUBLIC",
            "MGDS exposes a public equatorial-Atlantic T-phase origin catalog spanning August 2011 to January 2015, located from eight autonomous moored hydrophones plus HA10; the data file is ASCII text.",
            source,
            dataset="EA_Hydroacoustics", doi="10.26022/IEDA/330497",
            temporal_scope="2011-08_to_2015-01", format="ASCII text",
            anchor_blind_eligible=True,
        ))
        uids = source.get("candidate_file_uids") or []
        if uids:
            out.append(_finding(
                "MGDS_EA_TPHASE_FILE_UID_POINTERS",
                "The MGDS landing-page HTML exposed candidate file/data UID tokens that can be tested against its download service.",
                source, confidence="MEDIUM", candidate_uids=uids,
            ))

    if "fileserver service provides access to information about data files" in low and "file data uids" in low:
        out.append(_finding(
            "MGDS_FILESERVER_UID_ROUTE",
            "MGDS documents a FileServer route that returns file data UIDs for direct download and supports geographic/time filters plus full_info, summary and geometry outputs.",
            source,
        ))

    if "hydroacoustic monitoring of seafloor spreading" in low and "6,843" in text and "2011" in low and "2015" in low:
        out.append(_finding(
            "PARNELL_TURNER_EA_CATALOG_6843_EVENTS",
            "The NOAA-hosted 2022 paper reports a final equatorial-Atlantic T-phase catalog of 6,843 events from hydrophones deployed between 2011 and 2015.",
            source, doi="10.1029/2022JB024008", event_count=6843,
        ))
    if "250 hz" in low and "h10" in low and ("2011" in low and "2015" in low):
        out.append(_finding(
            "EA_CORPUS_250HZ_HA10_CONTEXT",
            "The fetched equatorial-Atlantic hydroacoustic paper contains 250-Hz HA10/corpus acquisition context suitable for the preregistered blind 117–121 Hz corpus gate.",
            source, confidence="MEDIUM",
        ))

    if "following the onset of the eruption" in low and "17 may 2011" in low and "both h10 arrays recorded a high incidence" in low:
        facts: Dict[str, Any] = {"date":"2011-05-17", "station":"HA10", "arrays":["H10N","H10S"]}
        if "09:00 utc" in low or "09:00" in low:
            facts["observed_activity_marker_utc"] = "2011-05-17T09:00:00Z"
        out.append(_finding(
            "MONOWAI_2011_HA10_KNOWN_TPHASE_CONTROL",
            "A published Monowai eruption study reports a high incidence of hydroacoustic T phases at both HA10 arrays after eruption onset on 17 May 2011; this is admitted only as a known-signal positive-control candidate, not as a 119-Hz target result.",
            source, **facts,
        ))
    if "instrument response" in low and "4 hz" in low and "12 hz" in low and "h10" in low:
        out.append(_finding(
            "MONOWAI_RESPONSE_CORRECTED_4_12HZ_PIPELINE",
            "The Monowai HA10 study explicitly corrected hydrophone recordings for instrument response before a 4–12 Hz T-phase analysis, providing a published positive-control processing reference.",
            source,
        ))

    if "spurious coherent cross-correlations" in low and "between 2005 and 2009" in low and "electronic noise" in low:
        out.append(_finding(
            "H10S_ELECTRONIC_NOISE_2005_2009_BOUND",
            "A peer-reviewed H10 analysis reports repetitive electronic noise producing spurious zero-lag coherent cross-correlations between 2005 and 2009 and recommends avoiding H10S for that application.",
            source,
            affected_period="2005-2009", exact_onset_not_established=True,
        ))
    if "data of hydrophone s1" in low and "available until october 2013" in low:
        out.append(_finding(
            "H10S1_DATA_AVAILABLE_UNTIL_2013_10",
            "A 2025 JASA Express Letters analysis states that H10S hydrophone S1 data are available until October 2013 and uses only S2/S3 for a homogeneous long-term set.",
            source,
            terminal_availability_bound="2013-10", exact_failure_date_not_established=True,
        ))
    if "continuous data are available from 3/23/2005" in low and "h10" in low:
        out.append(_finding(
            "H10_CONTINUOUS_DATA_FROM_2005_03_23",
            "The 2025 H10 long-term analysis states that continuous H10 data are available from 23 March 2005 onward, with S1 included only until October 2013.",
            source,
            continuous_start="2005-03-23",
        ))
    if "h10s triplet of ha10 ascension island" in low and "cross-talk" in low and "electronic noise" in low:
        out.append(_finding(
            "CTBTO_H10S_CAL_RESPONSE_CROSSTALK",
            "CTBTO calibration material links the onset of electronic noise in one H10S hydrophone channel to changes in calibration response and cross-talk into the other two channels.",
            source,
            exact_epoch_not_stated=True,
        ))

    if "jr15001" in low and ("alatgp01" in low or "alongp01" in low):
        out.append(_finding(
            "BODC_JR15001_NAV_COORDINATE_SERIES_POINTER",
            "The fetched BODC series surface exposes JR15001 navigation coordinate parameters suitable for a coordinate-bearing track reconstruction.",
            source,
            series="1762365", required_next="DELIVER_COORDINATE_BYTES_AND_COMPUTE_CLOSEST_APPROACH",
        ))
    if "jr53" in low and "topas" in low and "em120" in low:
        out.append(_finding(
            "BODC_JR53_EM120_TOPAS_POINTER_FRONTIER",
            "The fetched JR53 cruise surface links the cruise to EM120 multibeam and TOPAS acquisition, retaining JR53 as a parallel native-track branch.",
            source,
        ))
    return out


def _waveform_urls() -> List[Tuple[str, str]]:
    # The 09:00 marker is from the Monowai published HA10 activity plot. This
    # window is a positive-control candidate slice, not a claimed source-origin time.
    start = "2011-05-17T08:50:00"
    end = "2011-05-17T09:20:00"
    base = "https://service.earthscope.org/fdsnws/dataselect/1/query"
    return [
        (f"{base}?net=IM&sta=H10N1&loc=*&cha=EDH&start={start}&end={end}", "H10N1"),
        (f"{base}?net=IM&sta=H10S2&loc=*&cha=EDH&start={start}&end={end}", "H10S2"),
    ]


def _source_plan(track: str, scout_id: str) -> List[Tuple[str, str]]:
    plan: List[Tuple[str, str]] = []
    if track in {"P0_A_HA10_POSITIVE_CONTROL", "P1_B_BLIND_ATLANTIC_117_121", "VERIFY_SYNTHESIZE"}:
        plan += [(MGDS_DATA, "FRONTIER_MGDS_DATASET"), (MGDS_DOI, "FRONTIER_MGDS_DOI"),
                 (MGDS_FILESERVER_DOCS, "FRONTIER_MGDS_FILESERVER"),
                 (NOAA_PARNELL, "FRONTIER_NOAA_PAPER")]
    if track in {"P0_A_HA10_POSITIVE_CONTROL", "VERIFY_SYNTHESIZE"}:
        plan.append((MONOWAI_PDF, "FRONTIER_MONOWAI_CONTROL"))
    if track in {"P1_A_H10S_CALIBRATION_TIMELINE", "VERIFY_SYNTHESIZE"}:
        plan += [(SMETS_PDF, "FRONTIER_H10S_NOISE_HISTORY"),
                 (EVERS_2025_PDF, "FRONTIER_H10S_LONG_TERM_BOUND"),
                 (CTBTO_CAL, "FRONTIER_CTBTO_CALIBRATION")]
    if track in {"P0_B_NATIVE_CRUISE_TRACK", "VERIFY_SYNTHESIZE"}:
        plan += [(BODC_1762365, "FRONTIER_BODC_1762365"),
                 (BODC_JR53, "FRONTIER_BODC_JR53"),
                 (BAS_PDC, "FRONTIER_PDC_LINEAGE")]
    return plan


def process_report(path: Path) -> Dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    track = str(report.get("track") or "")
    scout_id = str(report.get("scout_id") or "")
    discovery = report.setdefault("discovery", {})
    sources = discovery.setdefault("sources", [])
    existing = {str(s.get("final_url") or s.get("url") or "") for s in sources if isinstance(s, dict)}

    frontier_sources: List[Dict[str, Any]] = []
    for url, method in _source_plan(track, scout_id):
        if url in existing:
            src = next((s for s in sources if isinstance(s, dict) and str(s.get("final_url") or s.get("url") or "") == url), None)
            if src:
                frontier_sources.append(src)
            continue
        src = fetch_text(url, method)
        sources.append(src)
        frontier_sources.append(src)
        existing.add(str(src.get("final_url") or src.get("url") or url))

    waveform_records: List[Dict[str, Any]] = []
    if track in {"P0_A_HA10_POSITIVE_CONTROL", "VERIFY_SYNTHESIZE"}:
        for url, station in _waveform_urls():
            rec = fetch_binary(url, f"FRONTIER_MONOWAI_RAW_{station}")
            rec["station"] = station
            rec["window_semantics"] = "PUBLISHED_HA10_ACTIVITY_MARKER_CONTROL_WINDOW__NOT_SOURCE_ORIGIN_TIME"
            sources.append(rec)
            waveform_records.append(rec)

    admitted: List[Dict[str, Any]] = []
    for src in frontier_sources:
        admitted.extend(_admit_text(src))
    for rec in waveform_records:
        if rec.get("status") == "FETCHED_BINARY" and rec.get("raw_sha256"):
            admitted.append({
                "fact_id": f"MONOWAI_CONTROL_RAW_WINDOW_{rec['station']}",
                "claim": f"EarthScope returned raw binary waveform bytes for IM.{rec['station']}..EDH in the frozen 2011-05-17 08:50–09:20 UTC Monowai positive-control candidate window.",
                "status": "FOUND",
                "source_urls": [rec.get("final_url") or rec.get("url")],
                "confidence": "HIGH",
                "admission_engine": "JANUS_SYSTEMWIDE_FRONTIER_GATE_V1",
                "facts": {"station":rec["station"], "start":"2011-05-17T08:50:00Z", "end":"2011-05-17T09:20:00Z", "bytes":rec["bytes_read"], "raw_sha256":rec["raw_sha256"], "positive_signal_detection_claimed":False},
            })

    analysis = report.setdefault("analysis", {})
    current = analysis.get("findings") if isinstance(analysis.get("findings"), list) else []
    seen = {str(x.get("fact_id")) for x in current if isinstance(x, dict) and x.get("fact_id")}
    for item in admitted:
        if item.get("fact_id") not in seen:
            current.append(item)
            seen.add(str(item.get("fact_id")))
    analysis["findings"] = current
    report["systemwide_frontier_gate"] = {
        "schema": "janus.demiurge.systemwide_frontier_gate.v1",
        "model_required": False,
        "track": track,
        "scout_id": scout_id,
        "sources_attempted": len(frontier_sources) + len(waveform_records),
        "admitted_findings": len(admitted),
        "admitted_sha256": canonical_hash(admitted),
        "laws": [
            "PRIOR_HA10_NEGATIVE_IS_IMMUTABLE",
            "POSITIVE_CONTROL_VALIDATES_PIPELINE_ONLY",
            "ORIGIN_TIME_AND_STATION_ARRIVAL_TIME_MUST_NOT_BE_CONFLATED",
            "RAW_WINDOW_FETCH_IS_NOT_SIGNAL_DETECTION",
            "BLIND_CORPUS_SELECTION_PRECEDES_ANCHOR_REVEAL",
            "FAILED_FETCH_IS_NOT_ABSENCE",
            "DUPLICATE_SCOUT_FINDINGS_ARE_NOT_INDEPENDENT_REPLICATION"
        ]
    }
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def self_test() -> None:
    synthetic = {"status":"FETCHED", "url":MGDS_DATA, "text_sha256":"x", "excerpt":"T-phase location catalog for equatorial Atlantic ocean, 2011-2015. Catalog using waveform arrivals by an array of 8 autonomous moored hydrophones and HA10. The data file is in ASCII text format. DOI 10.26022/IEDA/330497"}
    ids = {x["fact_id"] for x in _admit_text(synthetic)}
    assert "MGDS_EA_TPHASE_CATALOG_PUBLIC" in ids
    assert len(_waveform_urls()) == 2
    print("JANUS_SYSTEMWIDE_FRONTIER_GATE_SELF_TEST=PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test(); return 0
    if not args.report:
        ap.error("--report is required")
    result = process_report(Path(args.report))
    print(json.dumps(result.get("systemwide_frontier_gate"), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
