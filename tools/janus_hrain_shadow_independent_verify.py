#!/usr/bin/env python3
"""Independent read-only verifier for owner-private HRAiN shadow archives.

Does NOT import the shadow generator, engine, or owner-specific graph modules.
Never prints node labels/edge records and never mutates files.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import zlib

SCHEMA = "janus.hrain.private_lossless_shadow_compaction.v1"
MAX_SOURCE_BYTES = 32_000_000
MAX_ARCHIVE_BASE64 = 40_000_000


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def verify(snapshot_path: Path, shadow_path: Path) -> dict:
    if snapshot_path.name != "hrain_graph_state.json" or snapshot_path.parent.name != "raw_logs":
        raise ValueError("INDEPENDENT_SOURCE_PATH_HOLD")
    if snapshot_path.is_symlink() or shadow_path.is_symlink():
        raise ValueError("INDEPENDENT_SYMLINK_HOLD")
    if not snapshot_path.is_file() or not shadow_path.is_file():
        raise ValueError("INDEPENDENT_SOURCE_MISSING_HOLD")
    if not 1 <= snapshot_path.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("INDEPENDENT_SOURCE_SIZE_HOLD")
    source = snapshot_path.read_bytes()
    if shadow_path.stat().st_size > MAX_ARCHIVE_BASE64 + 1_000_000:
        raise ValueError("INDEPENDENT_SHADOW_SIZE_HOLD")
    packet = json.loads(shadow_path.read_text(encoding="utf-8"))
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ValueError("INDEPENDENT_SCHEMA_HOLD")
    archive = packet.get("archive")
    if not isinstance(archive, dict) or archive.get("codec") != "zlib+base64":
        raise ValueError("INDEPENDENT_ARCHIVE_HOLD")
    payload = archive.get("payload")
    if not isinstance(payload, str) or len(payload) > MAX_ARCHIVE_BASE64:
        raise ValueError("INDEPENDENT_PAYLOAD_BOUNDS_HOLD")
    try:
        packed = base64.b64decode(payload, validate=True)
        inflate = zlib.decompressobj()
        restored = inflate.decompress(packed, MAX_SOURCE_BYTES + 1)
        if len(restored) > MAX_SOURCE_BYTES or inflate.unconsumed_tail or inflate.unused_data or not inflate.eof:
            raise ValueError("INDEPENDENT_DECOMPRESSION_BOUND_HOLD")
    except (ValueError, zlib.error) as exc:
        raise ValueError("INDEPENDENT_DECOMPRESSION_HOLD") from exc
    if source != restored or packet.get("sourceSha256") != _sha(source) or packet.get("sourceBytes") != len(source):
        raise ValueError("INDEPENDENT_SOURCE_MISMATCH_HOLD")
    record = json.loads(restored)
    if not isinstance(record, dict):
        raise ValueError("INDEPENDENT_GRAPH_SCHEMA_HOLD")
    nodes, edges = record.get("nodes"), record.get("edges")
    if not isinstance(nodes, dict) or not isinstance(edges, dict):
        raise ValueError("INDEPENDENT_GRAPH_SCHEMA_HOLD")
    view = packet.get("compactView")
    if not isinstance(view, dict) or view.get("sourceGraphMutationAllowed") is not False:
        raise ValueError("INDEPENDENT_PRODUCTION_HOLD")
    if view.get("originalNodesRepresented") != len(nodes) or view.get("originalEdgeCount") != len(edges):
        raise ValueError("INDEPENDENT_COUNTS_HOLD")
    vnodes, relations = view.get("nodes"), view.get("relations")
    if not isinstance(vnodes, dict) or not isinstance(relations, list):
        raise ValueError("INDEPENDENT_VIEW_SCHEMA_HOLD")
    relation_keys = set()
    projected_total = 0
    for rel in relations:
        if not isinstance(rel, dict):
            raise ValueError("INDEPENDENT_RELATION_HOLD")
        src, dst = rel.get("source"), rel.get("target")
        count = rel.get("originalEdgeMultiplicity")
        if src not in vnodes or dst not in vnodes or not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ValueError("INDEPENDENT_RELATION_HOLD")
        if (src, dst) in relation_keys:
            raise ValueError("INDEPENDENT_DUPLICATE_RELATION_HOLD")
        relation_keys.add((src, dst))
        projected_total += count
    if len(relations) != view.get("projectedRelationCount") or projected_total != len(edges):
        raise ValueError("INDEPENDENT_MULTIPLICITY_HOLD")
    return {
        "status": "INDEPENDENT_BYTE_EXACT_SHADOW_VERIFIED",
        "sourceSha256": _sha(source),
        "sourceBytes": len(source),
        "originalNodes": len(nodes),
        "originalEdges": len(edges),
        "projectedRelations": len(relations),
        "sourceModified": False,
        "scientificVerdict": "NOT_TOPA_ADJUDICATED",
        "productionUseAuthorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.snapshot, args.shadow), sort_keys=True))


if __name__ == "__main__":
    main()
