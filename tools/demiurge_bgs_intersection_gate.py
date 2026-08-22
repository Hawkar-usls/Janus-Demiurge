#!/usr/bin/env python3
"""Deterministic BGS OGC point/polygon + line intersection gate for HA10.

This module turns the two frozen hydrophone coordinates into machine-queryable
BGS OGC API checks. It is intentionally model-independent and fail-closed:
- exact survey/backscatter polygon membership is computed from returned GeoJSON;
- geophysical/seismic/sonar line intersection is computed with an explicit metre tolerance;
- a wider nearby-line scan is preserved separately and is never promoted to intersection;
- feature properties are reduced to provenance-bearing identifiers and URL pointers;
- missing public OGC hits mean NOT_FOUND_IN_THIS_PASS, not global absence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from demiurge_mail_research_swarm import USER_AGENT, agent_map, canonical_hash, host_allowed, scrub

BGS_API = "https://ogcapi.bgs.ac.uk"
TARGETS: Dict[str, Dict[str, float]] = {
    "H10N1": {"lat": -7.845673, "lon": -14.480230},
    "H10S2": {"lat": -8.959100, "lon": -14.645310},
}
BGS_SCOUTS = {
    "SCOUT_VOICE_13",
    "SCOUT_ECHO_PYRAMID_14",
    "SCOUT_TRANCEPTION_15",
    "SCOUT_AIFC_16",
    "SCOUT_GENESIS_17",
}
COLLECTIONS = {
    "survey": "offshore-survey-overview",
    "line": "offshore-geophysical-survey-lines",
    "backscatter": "offshorebackscatterareas",
    "sea_line": "offshore-sea-doc-event-line",
}
EXACT_LINE_TOLERANCE_M = 25.0
NEARBY_RADIUS_KM = 10.0
MAX_FEATURES = 100
URL_RE = re.compile(r"https?://[^\s<>'\"\]]+", re.I)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bbox_for_radius(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    dlat = radius_km / 110.574
    coslat = max(0.05, math.cos(math.radians(lat)))
    dlon = radius_km / (111.320 * coslat)
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _feature_id(feature: Dict[str, Any]) -> str:
    value = feature.get("id")
    if value not in (None, ""):
        return str(value)
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    for key in ("SURVEY_LINE_ID", "survey_line_id", "CRUISE_ID", "cruise_id", "OBJECTID", "objectid"):
        if props.get(key) not in (None, ""):
            return str(props[key])
    return canonical_hash(feature)[:16]


def _props(feature: Dict[str, Any]) -> Dict[str, Any]:
    value = feature.get("properties")
    return value if isinstance(value, dict) else {}


def _pick(props: Dict[str, Any], names: Sequence[str]) -> Optional[Any]:
    low = {str(k).lower(): v for k, v in props.items()}
    for name in names:
        value = low.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _extract_urls(props: Dict[str, Any]) -> List[Dict[str, str]]:
    pointers: List[Dict[str, str]] = []
    seen = set()
    for key, value in props.items():
        values: Iterable[Any] = value if isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                continue
            for match in URL_RE.findall(item):
                url = scrub(match.rstrip(".,);"))
                if url in seen:
                    continue
                seen.add(url)
                pointers.append({"field": str(key), "url": url})
    return pointers


def _reduce_feature(feature: Dict[str, Any], distance_m: Optional[float] = None) -> Dict[str, Any]:
    props = _props(feature)
    out: Dict[str, Any] = {
        "feature_id": _feature_id(feature),
        "cruise_id": _pick(props, ["CRUISE_ID", "cruise_id"]),
        "cruise": _pick(props, ["CRUISE", "cruise", "CRUISE_ALIAS", "cruise_alias"]),
        "survey": _pick(props, ["SURVEY", "survey", "RESTITLE", "restitle", "SOURCE_TITLE", "source_title"]),
        "survey_line_id": _pick(props, ["SURVEY_LINE_ID", "survey_line_id", "LINE_ID", "line_id"]),
        "line": _pick(props, ["LINE", "line", "LINE_NAME", "line_name", "LINE_NO", "line_no"]),
        "ship": _pick(props, ["SHIP", "ship"]),
        "equipment": _pick(props, ["GEOPHYS_EQUIP_TYPE", "geophys_equip_type", "EQUIPMENT_TYPE", "equipment_type"]),
        "pointers": _extract_urls(props),
    }
    if distance_m is not None:
        out["distance_m"] = round(float(distance_m), 3)
    return {k: v for k, v in out.items() if v not in (None, "", [], {})}


def _request_geojson(collection: str, bbox: Tuple[float, float, float, float], method: str) -> Dict[str, Any]:
    url = f"{BGS_API}/collections/{collection}/items"
    params = {
        "bbox": ",".join(f"{v:.8f}" for v in bbox),
        "limit": str(MAX_FEATURES),
        "f": "json",
    }
    receipt: Dict[str, Any] = {
        "collection": collection,
        "method": method,
        "request_url": "",
        "status": "UNFETCHED",
        "features_returned": 0,
        "response_sha256": None,
        "features": [],
    }
    try:
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        receipt["request_url"] = response.url
        response.raise_for_status()
        text = scrub(response.text)
        receipt["response_sha256"] = _sha256_text(text)
        payload = response.json()
        features = payload.get("features") if isinstance(payload, dict) else None
        if not isinstance(features, list):
            raise ValueError("BGS_OGC_RESPONSE_MISSING_FEATURES")
        receipt["status"] = "FETCHED"
        receipt["features_returned"] = len(features)
        receipt["features"] = [f for f in features if isinstance(f, dict)]
    except Exception as exc:
        receipt["status"] = "FETCH_FAILED"
        receipt["error"] = scrub(f"{type(exc).__name__}:{exc}")[:1200]
    return receipt


def _point_on_segment_distance_m(lat: float, lon: float, a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return float("inf")
    coslat = max(0.05, math.cos(math.radians(lat)))
    ax = (float(a[0]) - lon) * 111_320.0 * coslat
    ay = (float(a[1]) - lat) * 110_574.0
    bx = (float(b[0]) - lon) * 111_320.0 * coslat
    by = (float(b[1]) - lat) * 110_574.0
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-18:
        return math.hypot(ax, ay)
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / denom))
    return math.hypot(ax + t * dx, ay + t * dy)


def _line_distance_m(geometry: Dict[str, Any], lat: float, lon: float) -> float:
    gtype = str(geometry.get("type") or "")
    coords = geometry.get("coordinates")
    lines: List[List[Sequence[float]]] = []
    if gtype == "LineString" and isinstance(coords, list):
        lines = [coords]
    elif gtype == "MultiLineString" and isinstance(coords, list):
        lines = [line for line in coords if isinstance(line, list)]
    elif gtype == "GeometryCollection":
        distances = [
            _line_distance_m(g, lat, lon)
            for g in geometry.get("geometries", [])
            if isinstance(g, dict)
        ]
        return min(distances) if distances else float("inf")
    else:
        return float("inf")
    best = float("inf")
    for line in lines:
        for i in range(len(line) - 1):
            try:
                best = min(best, _point_on_segment_distance_m(lat, lon, line[i], line[i + 1]))
            except Exception:
                continue
    return best


def _point_in_ring(lon: float, lat: float, ring: Sequence[Sequence[float]]) -> bool:
    if len(ring) < 3:
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        try:
            xi, yi = float(ring[i][0]), float(ring[i][1])
            xj, yj = float(ring[j][0]), float(ring[j][1])
        except Exception:
            j = i
            continue
        # Boundary tolerance in coordinate space.
        if _point_on_segment_distance_m(lat, lon, (xi, yi), (xj, yj)) <= 1.0:
            return True
        crosses = (yi > lat) != (yj > lat)
        if crosses:
            x_at_y = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-30) + xi
            if lon < x_at_y:
                inside = not inside
        j = i
    return inside


def _point_in_polygon_coords(lon: float, lat: float, polygon: Sequence[Any]) -> bool:
    if not polygon or not isinstance(polygon[0], list):
        return False
    if not _point_in_ring(lon, lat, polygon[0]):
        return False
    for hole in polygon[1:]:
        if isinstance(hole, list) and _point_in_ring(lon, lat, hole):
            return False
    return True


def _contains_point(geometry: Dict[str, Any], lat: float, lon: float) -> bool:
    gtype = str(geometry.get("type") or "")
    coords = geometry.get("coordinates")
    if gtype == "Polygon" and isinstance(coords, list):
        return _point_in_polygon_coords(lon, lat, coords)
    if gtype == "MultiPolygon" and isinstance(coords, list):
        return any(_point_in_polygon_coords(lon, lat, p) for p in coords if isinstance(p, list))
    if gtype == "GeometryCollection":
        return any(
            _contains_point(g, lat, lon)
            for g in geometry.get("geometries", [])
            if isinstance(g, dict)
        )
    return False


def _exact_polygon_hits(receipt: Dict[str, Any], lat: float, lon: float) -> List[Dict[str, Any]]:
    hits = []
    for feature in receipt.get("features", []):
        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        if _contains_point(geometry, lat, lon):
            hits.append(_reduce_feature(feature))
    return hits


def _line_hits(receipt: Dict[str, Any], lat: float, lon: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    exact: List[Dict[str, Any]] = []
    nearby: List[Dict[str, Any]] = []
    for feature in receipt.get("features", []):
        geometry = feature.get("geometry") if isinstance(feature.get("geometry"), dict) else {}
        distance = _line_distance_m(geometry, lat, lon)
        if not math.isfinite(distance):
            continue
        reduced = _reduce_feature(feature, distance)
        if distance <= EXACT_LINE_TOLERANCE_M:
            exact.append(reduced)
        if distance <= NEARBY_RADIUS_KM * 1000.0:
            nearby.append(reduced)
    exact.sort(key=lambda x: float(x.get("distance_m", 1e99)))
    nearby.sort(key=lambda x: float(x.get("distance_m", 1e99)))
    return exact, nearby[:25]


def _identity_values(feature: Dict[str, Any]) -> set[str]:
    values = set()
    for key in ("cruise_id", "cruise", "survey"):
        value = feature.get(key)
        if value not in (None, ""):
            values.add(str(value).strip().lower())
    return values


def _build_chains(
    point_name: str,
    surveys: List[Dict[str, Any]],
    exact_lines: List[Dict[str, Any]],
    nearby_lines: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    lines = [("EXACT", line) for line in exact_lines] or [("NEARBY", line) for line in nearby_lines[:10]]
    chains: List[Dict[str, Any]] = []
    for relation, line in lines:
        line_ids = _identity_values(line)
        matching_surveys = [s for s in surveys if line_ids & _identity_values(s)] if line_ids else []
        survey_candidates = matching_surveys or surveys or [{}]
        for survey in survey_candidates[:10]:
            pointers: List[Dict[str, str]] = []
            seen = set()
            for source in (survey, line):
                for pointer in source.get("pointers", []) if isinstance(source, dict) else []:
                    key = (str(pointer.get("field")), str(pointer.get("url")))
                    if key not in seen:
                        seen.add(key)
                        pointers.append(pointer)
            data_pointers = [
                p for p in pointers
                if any(word in str(p.get("field", "")).lower() for word in ("data", "download", "file", "zip", "record", "image", "url"))
            ]
            chain = {
                "point": point_name,
                "line_relation": relation,
                "survey": survey or None,
                "line": line,
                "pointers": pointers,
                "raw_or_record_pointer_count": len(data_pointers),
                "chain_status": (
                    "POINT_SURVEY_LINE_POINTER"
                    if survey and relation == "EXACT" and data_pointers
                    else "POINT_LINE_POINTER"
                    if relation == "EXACT" and data_pointers
                    else "PARTIAL_CHAIN"
                ),
            }
            chains.append(chain)
    return chains


def _finding(fid: str, claim: str, status: str, source_urls: List[str], **facts: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "fact_id": fid,
        "claim": claim,
        "status": status,
        "source_urls": source_urls,
        "confidence": "HIGH" if status == "FOUND" else "MEDIUM",
        "admission_engine": "BGS_OGC_DETERMINISTIC_GEOMETRY_GATE_V1",
    }
    if facts:
        item["facts"] = facts
    return item


def run_gate(report: Dict[str, Any]) -> Dict[str, Any]:
    scout_id = str(report.get("scout_id") or "")
    agents = agent_map()
    agent = agents.get(scout_id)
    if not agent or scout_id not in BGS_SCOUTS:
        report["bgs_intersection_gate"] = {
            "schema": "janus.demiurge.bgs_intersection_gate.v1",
            "status": "NOT_ASSIGNED_TO_THIS_SCOUT",
            "model_required": False,
        }
        return report

    allowed = [str(x) for x in agent.get("allowed_domains", [])]
    if not host_allowed(BGS_API + "/", allowed):
        report["bgs_intersection_gate"] = {
            "schema": "janus.demiurge.bgs_intersection_gate.v1",
            "status": "BLOCKED_BY_AGENT_ALLOWLIST",
            "model_required": False,
        }
        return report

    all_findings: List[Dict[str, Any]] = []
    point_results: Dict[str, Any] = {}
    for point_name, point in TARGETS.items():
        lat, lon = point["lat"], point["lon"]
        micro = _bbox_for_radius(lat, lon, 0.05)  # 50 m candidate window; exact geometry is tested locally.
        nearby = _bbox_for_radius(lat, lon, NEARBY_RADIUS_KM)

        survey_receipt = _request_geojson(COLLECTIONS["survey"], micro, "BGS_OGC_POINT_POLYGON_CANDIDATES")
        backscatter_receipt = _request_geojson(COLLECTIONS["backscatter"], micro, "BGS_OGC_POINT_BACKSCATTER_CANDIDATES")
        line_receipt = _request_geojson(COLLECTIONS["line"], nearby, "BGS_OGC_LINE_NEARBY_SCAN")
        sea_line_receipt = _request_geojson(COLLECTIONS["sea_line"], nearby, "BGS_OGC_SEA_LINE_NEARBY_SCAN")

        surveys = _exact_polygon_hits(survey_receipt, lat, lon) if survey_receipt.get("status") == "FETCHED" else []
        backscatter = _exact_polygon_hits(backscatter_receipt, lat, lon) if backscatter_receipt.get("status") == "FETCHED" else []
        exact_lines, nearby_lines = _line_hits(line_receipt, lat, lon) if line_receipt.get("status") == "FETCHED" else ([], [])
        exact_sea_lines, nearby_sea_lines = _line_hits(sea_line_receipt, lat, lon) if sea_line_receipt.get("status") == "FETCHED" else ([], [])
        chains = _build_chains(point_name, surveys, exact_lines, nearby_lines)

        point_results[point_name] = {
            "target": {"lat": lat, "lon": lon},
            "exact_line_tolerance_m": EXACT_LINE_TOLERANCE_M,
            "nearby_radius_km": NEARBY_RADIUS_KM,
            "survey_polygon_intersections": surveys,
            "backscatter_polygon_intersections": backscatter,
            "geophysical_line_intersections": exact_lines,
            "nearby_geophysical_lines": nearby_lines,
            "sea_line_intersections": exact_sea_lines,
            "nearby_sea_lines": nearby_sea_lines,
            "chains": chains,
            "query_receipts": {
                "survey": {k: v for k, v in survey_receipt.items() if k != "features"},
                "backscatter": {k: v for k, v in backscatter_receipt.items() if k != "features"},
                "geophysical_lines": {k: v for k, v in line_receipt.items() if k != "features"},
                "sea_lines": {k: v for k, v in sea_line_receipt.items() if k != "features"},
            },
        }

        survey_url = str(survey_receipt.get("request_url") or "")
        line_url = str(line_receipt.get("request_url") or "")
        backscatter_url = str(backscatter_receipt.get("request_url") or "")
        if survey_receipt.get("status") == "FETCHED":
            all_findings.append(_finding(
                f"BGS_EXACT_SURVEY_POLYGON_{point_name}",
                f"BGS public OGC survey-overview returned {len(surveys)} polygon feature(s) whose GeoJSON geometry contains {point_name}.",
                "FOUND" if surveys else "NOT_FOUND_IN_THIS_PASS",
                [survey_url] if survey_url else [],
                target=point_results[point_name]["target"],
                intersection_count=len(surveys),
                features=surveys,
            ))
        if line_receipt.get("status") == "FETCHED":
            all_findings.append(_finding(
                f"BGS_EXACT_GEOPHYSICAL_LINE_{point_name}",
                f"BGS public OGC geophysical-line scan found {len(exact_lines)} line feature(s) within the frozen {EXACT_LINE_TOLERANCE_M:.0f} m intersection tolerance of {point_name}.",
                "FOUND" if exact_lines else "NOT_FOUND_IN_THIS_PASS",
                [line_url] if line_url else [],
                target=point_results[point_name]["target"],
                intersection_tolerance_m=EXACT_LINE_TOLERANCE_M,
                intersection_count=len(exact_lines),
                features=exact_lines,
            ))
            if nearby_lines:
                all_findings.append(_finding(
                    f"BGS_NEARBY_GEOPHYSICAL_LINES_{point_name}",
                    f"BGS public OGC returned geophysical lines within {NEARBY_RADIUS_KM:.0f} km of {point_name}; these are proximity candidates and are not promoted to exact intersections.",
                    "POINTER_ONLY",
                    [line_url] if line_url else [],
                    nearest=nearby_lines[:10],
                ))
        if backscatter_receipt.get("status") == "FETCHED":
            all_findings.append(_finding(
                f"BGS_EXACT_BACKSCATTER_POLYGON_{point_name}",
                f"BGS public OGC backscatter collection returned {len(backscatter)} polygon feature(s) whose GeoJSON geometry contains {point_name}.",
                "FOUND" if backscatter else "NOT_FOUND_IN_THIS_PASS",
                [backscatter_url] if backscatter_url else [],
                intersection_count=len(backscatter),
                features=backscatter,
            ))
        complete = [c for c in chains if c.get("chain_status") in {"POINT_SURVEY_LINE_POINTER", "POINT_LINE_POINTER"}]
        if complete:
            chain_urls = sorted({
                str(p.get("url"))
                for chain in complete
                for p in chain.get("pointers", [])
                if p.get("url")
            })
            all_findings.append(_finding(
                f"BGS_POINT_TO_RAW_POINTER_CHAIN_{point_name}",
                f"A deterministic BGS chain from {point_name} to survey/line metadata and public record/data pointer(s) was recovered.",
                "FOUND",
                [u for u in [survey_url, line_url, *chain_urls] if u],
                chains=complete[:20],
            ))

    analysis = report.setdefault("analysis", {})
    existing = analysis.get("findings") if isinstance(analysis.get("findings"), list) else []
    combined: List[Dict[str, Any]] = []
    seen = set()
    for item in [*all_findings, *existing]:
        if not isinstance(item, dict):
            continue
        key = canonical_hash({
            "fact_id": item.get("fact_id"),
            "claim": item.get("claim"),
            "source_urls": sorted(item.get("source_urls") or []),
        })
        if key in seen:
            continue
        seen.add(key)
        combined.append(item)
    analysis["findings"] = combined

    report["bgs_intersection_gate"] = {
        "schema": "janus.demiurge.bgs_intersection_gate.v1",
        "status": "COMPLETE",
        "model_required": False,
        "geometry_engine": "LOCAL_GEOJSON_POINT_IN_POLYGON_PLUS_POINT_TO_LINE_DISTANCE",
        "exact_line_tolerance_m": EXACT_LINE_TOLERANCE_M,
        "nearby_radius_km": NEARBY_RADIUS_KM,
        "points": point_results,
        "finding_count": len(all_findings),
        "findings_sha256": canonical_hash(all_findings),
        "claim_ceiling": "PUBLIC_BGS_OGC_INTERSECTION_OR_PROXIMITY_ONLY__NO_GLOBAL_ABSENCE_INFERENCE",
    }
    report["schema"] = "janus.demiurge.public_research_agent_report.v3.bgs_intersection"
    return report


def process_report(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("REPORT_MUST_BE_OBJECT")
    report = run_gate(report)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def self_test() -> None:
    square = {
        "type": "Polygon",
        "coordinates": [[[-15.0, -9.0], [-14.0, -9.0], [-14.0, -7.0], [-15.0, -7.0], [-15.0, -9.0]]],
    }
    assert _contains_point(square, -7.845673, -14.480230)
    assert not _contains_point(square, -10.0, -14.5)
    line = {"type": "LineString", "coordinates": [[-14.49, -7.845673], [-14.47, -7.845673]]}
    assert _line_distance_m(line, -7.845673, -14.480230) < 1.0
    props = {"CRUISE_ID": 42, "CRUISE_DATA_URL": "https://example.invalid/data.zip"}
    reduced = _reduce_feature({"id": "x", "properties": props})
    assert reduced["cruise_id"] == 42
    assert reduced["pointers"][0]["url"].endswith("data.zip")
    assert len(TARGETS) == 2
    print("BGS_POINT_LINE_INTERSECTION_GATE_SELF_TEST=PASS")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if args.report:
        process_report(Path(args.report))
        return 0
    parser.error("choose --report or --self-test")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
