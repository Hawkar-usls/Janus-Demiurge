from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

SCHEMA = "janus.archivist_memory_graph_projection.v2"
HISTORICAL_SOURCE_SHA256 = "4b1c2571c9e053663ed0748d5bacc1fd0f84176ae52a2519aa3a3b7b4fd5d2d3"


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [x.strip() for x in value.replace(";", ",").split(",")]
        return [x for x in parts if x]
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value).strip()]


def derive_checkpoint(existing_node_ids: Iterable[str]) -> dict[str, Any]:
    checkpoint = 0
    recognized: list[str] = []
    ignored: list[str] = []
    for raw in existing_node_ids:
        value = str(raw)
        if not value.startswith("MEM_"):
            ignored.append(value)
            continue
        suffix = value[4:]
        if not suffix.isdigit():
            ignored.append(value)
            continue
        memory_id = int(suffix)
        checkpoint = max(checkpoint, memory_id)
        recognized.append(value)
    body = {
        "schema": "janus.archivist.checkpoint.v1",
        "checkpoint_max_memory_id": checkpoint,
        "recognized_node_ids": sorted(set(recognized)),
        "ignored_node_ids": sorted(set(ignored)),
        "historical_source_sha256": HISTORICAL_SOURCE_SHA256,
        "authority": {"reads_database": False, "writes_database": False, "writes_graph": False},
        "law": "CHECKPOINT_DERIVATION_NE_DATABASE_CURSOR_OR_GRAPH_WRITE_AUTHORITY",
    }
    body["checkpoint_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        tid = value.get("id")
        source = value.get("source", "")
        content = value.get("content", "")
        tags = value.get("tags")
        reply_to = value.get("reply_to")
    elif isinstance(value, (list, tuple)) and len(value) >= 4:
        tid, source, content, tags = value[:4]
        reply_to = value[4] if len(value) > 4 else None
    else:
        raise ValueError("row must be a dict or tuple/list with id, source, content, tags")
    if isinstance(tid, bool):
        raise ValueError("id must be an integer")
    try:
        tid = int(tid)
    except Exception as exc:
        raise ValueError("id must be an integer") from exc
    if tid < 0:
        raise ValueError("id must be non-negative")
    return {
        "id": tid,
        "source": str(source or "").strip(),
        "content": str(content or ""),
        "tags": _tags(tags),
        "reply_to": None if reply_to is None else str(reply_to),
    }


def project_rows(rows: Iterable[Any], existing_node_ids: Iterable[str] = (), core_id: str = "CORE") -> dict[str, Any]:
    existing = {str(x) for x in existing_node_ids}
    existing_checkpoint = derive_checkpoint(existing)
    normalized = sorted((_row(row) for row in rows), key=lambda x: x["id"])
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, str]] = []
    skipped: list[dict[str, Any]] = []
    checkpoint = existing_checkpoint["checkpoint_max_memory_id"]

    for row in normalized:
        checkpoint = max(checkpoint, row["id"])
        node_id = f"MEM_{row['id']}"
        content = row["content"].strip()
        if node_id in existing:
            skipped.append({"id": row["id"], "reason": "ALREADY_PRESENT"})
            continue
        if len(content) < 2:
            skipped.append({"id": row["id"], "reason": "EMPTY_OR_TRIVIAL_CONTENT"})
            continue

        tag_upper = {tag.upper() for tag in row["tags"]}
        tombstone = "DIGESTED" in tag_upper or "DELETED" in tag_upper or "TOMBSTONE" in tag_upper
        source_upper = row["source"].upper()

        if tombstone:
            node_type = "ghost"
            node_class = "TOMBSTONE"
            desc = content[:50]
        elif source_upper == "USER":
            node_type = "user"
            node_class = "USER_MEMORY"
            desc = content[:500]
        elif source_upper in {"JANUS", "AI"}:
            node_type = "ai"
            node_class = "AI_MEMORY"
            desc = content[:500]
        elif source_upper.startswith("FILE:") or "FILE:" in source_upper:
            node_type = "file"
            node_class = "FILE_MEMORY"
            desc = content[:500]
        else:
            node_type = "memory"
            node_class = "GENERIC_MEMORY"
            desc = content[:500]

        node = {
            "id": node_id,
            "memory_id": row["id"],
            "type": node_type,
            "class": node_class,
            "source": row["source"],
            "tags": row["tags"],
            "tombstone": tombstone,
            "label": ("[GHOST] " if tombstone else "") + desc[:30],
            "desc": ("[GHOST] " if tombstone else "") + desc,
        }
        nodes.append(node)

        parent = row["reply_to"] if row["reply_to"] else core_id
        links.append({"source": parent, "target": node_id, "relation": "memory_projection"})

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "APPEND_ONLY_GRAPH_PROJECTION_PLAN",
        "existing_checkpoint": existing_checkpoint,
        "checkpoint_max_memory_id": checkpoint,
        "nodes_to_append": nodes,
        "links_to_append": links,
        "skipped": skipped,
        "historical_source_sha256": HISTORICAL_SOURCE_SHA256,
        "authority": {
            "reads_database": False,
            "writes_database": False,
            "writes_graph": False,
            "deletes_graph_nodes": False,
            "deletes_source_memory": False,
        },
        "laws": [
            "MEMORY_PROJECTION_NE_GRAPH_WRITE_AUTHORITY",
            "CHECKPOINT_DERIVATION_NE_DATABASE_CURSOR_OR_GRAPH_WRITE_AUTHORITY",
            "TOMBSTONE_PRESERVES_EXISTENCE_WITHOUT_REPUBLISHING_FULL_CONTENT",
            "TOMBSTONE_TAG_OVERRIDES_DISPLAY_SOURCE_CLASS",
            "APPEND_ONLY_NE_UNBOUNDED_RENDER_REQUIREMENT",
            "EXPLICIT_REPLY_EDGE_NE_POSITIONAL_PREVIOUS_NODE_HEURISTIC",
            "NOTHING_DISAPPEARS_NE_EVERYTHING_IS_TRUE",
        ],
    }
    body["projection_sha256"] = hashlib.sha256(_canon(body)).hexdigest()
    return body
