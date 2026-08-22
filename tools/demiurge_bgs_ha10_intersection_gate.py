#!/usr/bin/env python3
"""Deterministic BGS OGC API intersection gate for HA10 H10N1/H10S2.

Queries BGS offshore survey/polygon/line collections directly. The gate distinguishes
collection coverage from query result: a zero result outside a collection's declared
extent is NOT evidence that no marine data exist at the target point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

USER_AGENT = "JANUS-Demiurge-BGS-Intersection/1.0 (+https://github.com/Hawkar-usls/Janus-Demiurge)"
COLLECTIONS_URL = "https://ogcapi.bgs.ac.uk/collections?f=json"
POINTS = {
    "H10N1": {"lat": -7.845673, "lon": -14.480230},
    "H10S2": {"lat": -8.959100, "lon": -14.645310},
}
COLLECTIONS = {
    "survey_polygons": "offshore-survey-overview",
    "geophysical_lines": "offshore-geophysical-survey-lines",
    "backscatter_polygons": "offshorebackscatterareas",
    "sea_data_polygons": "offshore-sea-doc-event-area",
}
# ~1.1 km latitude half-width. A hit is a candidate until geometry is reviewed.
QUERY_EPSILON_DEG = 0.01


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_json(url: str) -> Dict[str, Any]:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    obj = r.json()
    if not isinstance(obj, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return obj


def point_inside_bbox(lat: float, lon: float, bbox: Iterable[float]) -> bool:
    west, south, east, north = [float(x) for x in bbox]
    return west <= lon <= east and south <= lat <= north


def collection_index(doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(c.get("id")): c for c in doc.get("collections", []) if isinstance(c, dict) and c.get("id")}


def declared_extent(collection: Dict[str, Any]) -> Optional[List[float]]:
    boxes = collection.get("extent", {}).get("spatial", {}).get("bbox", [])
    if not boxes or not isinstance(boxes[0], list) or len(boxes[0]) < 4:
        return None
    return [float(x) for x in boxes[0][:4]]


def query_bbox(lat: float, lon: float, eps: float = QUERY_EPSILON_DEG) -> str:
    return f"{lon-eps:.6f},{lat-eps:.6f},{lon+eps:.6f},{lat+eps:.6f}"


def query_collection(collection_id: str, lat: float, lon: float) -> Tuple[str, Dict[str, Any]]:
    url = (
        f"https://ogcapi.bgs.ac.uk/collections/{collection_id}/items"
        f"?bbox={query_bbox(lat, lon)}&limit=100&f=json"
    )
    return url, fetch_json(url)


def props_ci(feature: Dict[str, Any], names: Iterable[str]) -> Dict[str, Any]:
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    lower = {str(k).lower(): v for k, v in props.items()}
    out: Dict[str, Any] = {}
    for name in names:
        key = name.lower()
        if key in lower and lower[key] not in (None, ""):
            out[name] = lower[key]
    return out


def compact_feature(feature: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": feature.get("id"),
        "geometry_type": (feature.get("geometry") or {}).get("type") if isinstance(feature.get("geometry"), dict) else None,
        "pointers": props_ci(feature, [
            "cruise", "cruise_id", "cruise_line", "svy_line", "svy_line_id",
            "geophys_equip", "geophys_equip_type", "cruise_data_url", "scan_url",
            "data_url", "download_url", "terms_of_use_url", "restitle", "ship",
        ]),
    }


def run_gate() -> Dict[str, Any]:
    collections_doc = fetch_json(COLLECTIONS_URL)
    idx = collection_index(collections_doc)
    targets: Dict[str, Any] = {}

    for point_id, point in POINTS.items():
        lat, lon = float(point["lat"]), float(point["lon"])
        per_collection: Dict[str, Any] = {}
        for role, collection_id in COLLECTIONS.items():
            coll = idx.get(collection_id)
            if not coll:
                per_collection[role] = {
                    "collection_id": collection_id,
                    "status": "COLLECTION_NOT_FOUND",
                    "query_performed": False,
                }
                continue
            extent = declared_extent(coll)
            in_extent = point_inside_bbox(lat, lon, extent) if extent else None
            record: Dict[str, Any] = {
                "collection_id": collection_id,
                "title": coll.get("title"),
                "declared_extent_crs84": extent,
                "target_inside_declared_extent": in_extent,
            }
            # Query even outside extent as a direct negative-control against API behavior.
            try:
                url, data = query_collection(collection_id, lat, lon)
                features = data.get("features", []) if isinstance(data.get("features"), list) else []
                record.update({
                    "query_performed": True,
                    "query_url": url,
                    "number_matched": data.get("numberMatched"),
                    "number_returned": data.get("numberReturned", len(features)),
                    "returned_features": [compact_feature(f) for f in features[:25] if isinstance(f, dict)],
                })
                if in_extent is False and not features:
                    record["status"] = "ZERO_RESULTS__TARGET_OUTSIDE_DECLARED_COLLECTION_EXTENT"
                elif features:
                    record["status"] = "CANDIDATE_FEATURES_RETURNED__GEOMETRY_REVIEW_REQUIRED"
                else:
                    record["status"] = "ZERO_RESULTS_WITHIN_DECLARED_EXTENT"
            except Exception as exc:
                record.update({
                    "query_performed": True,
                    "status": "QUERY_FAILED",
                    "error": f"{type(exc).__name__}:{exc}"[:1000],
                })
            per_collection[role] = record
        targets[point_id] = {"point": point, "collections": per_collection}

    declared_records = [
        rec
        for target in targets.values()
        for rec in target["collections"].values()
        if rec.get("declared_extent_crs84") is not None
    ]
    all_outside = bool(declared_records) and all(rec.get("target_inside_declared_extent") is False for rec in declared_records)
    any_features = any(
        bool(rec.get("returned_features"))
        for target in targets.values()
        for rec in target["collections"].values()
    )

    verdict = (
        "BGS_OGC_HA10_POINTS_OUTSIDE_DECLARED_OFFSHORE_COLLECTION_EXTENTS"
        if all_outside and not any_features
        else "BGS_OGC_CANDIDATES_REQUIRE_GEOMETRY_REVIEW"
    )
    result: Dict[str, Any] = {
        "schema": "janus.demiurge.bgs_ha10_intersection_gate.v1",
        "status": "COMPLETE",
        "verdict": verdict,
        "targets": targets,
        "collection_catalog_source": COLLECTIONS_URL,
        "query_epsilon_degrees": QUERY_EPSILON_DEG,
        "claim_ceiling": [
            "A BGS OGC zero result outside the collection extent does not prove absence of marine surveys or geophysical data at Ascension.",
            "It only shows that these published BGS offshore OGC collections do not declare spatial coverage at the HA10 points.",
            "Exact point-to-survey or point-to-line linkage remains open in other custodians (BAS/PDC/BODC/CTBTO or broader BGS holdings not exposed by these collections).",
        ],
        "next_routes": [
            "BAS_PDC_SOURCE_CRUISE_TRACKLINES",
            "BODC_JR53_AMT11_JR287_JR15001_JR16_NG_NATIVE_TRACKS",
            "BGS_CUSTODIAN_REPLY_IF_HOLDINGS_EXIST_OUTSIDE_PUBLIC_OGC_EXTENT",
        ],
    }
    result["result_sha256"] = canonical_hash(result)
    return result


def self_test() -> None:
    assert point_inside_bbox(50, 0, [-9, 49.5, 3, 61])
    assert not point_inside_bbox(-7.845673, -14.480230, [-9, 49.5, 3, 61])
    assert query_bbox(-7.845673, -14.480230).startswith("-14.490230,-7.855673")
    print("BGS_HA10_INTERSECTION_SELF_TEST=PASS")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    result = run_gate()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
