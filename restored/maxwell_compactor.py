"""JANUS Maxwell restoration candidate.

Observer/compactor only. It never deletes source records, never launches processes,
never opens sockets, and never mutates JANUS runtime state. Historical Maxwell's
useful capability is restored as deterministic provenance-preserving compaction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "janus.maxwell.crystal.v1"
TIMESTAMP_KEYS = ("timestamp", "ts", "created_at", "time")
KIND_KEYS = ("type", "event", "kind", "status", "level", "category", "source")


def _canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _normalize_record(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        return dict(record)
    if isinstance(record, str):
        line = record.rstrip("\n")
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
        return {"text": line}
    return {"value": record}


def _kind(record: dict[str, Any]) -> str:
    for key in KIND_KEYS:
        value = record.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    return "unclassified"


def _timestamp(record: dict[str, Any]) -> str | None:
    for key in TIMESTAMP_KEYS:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def compact_records(records: Iterable[Any], *, source: str = "unknown", max_samples: int = 8) -> dict[str, Any]:
    normalized = [_normalize_record(x) for x in records]
    canonical_records = [_canonical(x) for x in normalized]
    kinds = Counter(_kind(x) for x in normalized)
    timestamps = [t for x in normalized if (t := _timestamp(x)) is not None]
    sample_hashes = [_sha256_text(x) for x in canonical_records[: max(0, int(max_samples))]]
    error_like = 0
    for rec, text in zip(normalized, canonical_records):
        kind = _kind(rec).lower()
        if "error" in kind or "fail" in kind or '"error"' in text.lower() or '"exception"' in text.lower():
            error_like += 1

    payload_digest = _sha256_text("\n".join(canonical_records))
    crystal = {
        "schema": SCHEMA,
        "role": "MAXWELL_MEMORY_COMPACTOR",
        "status": "PROBATION_CANDIDATE__NON_DESTRUCTIVE",
        "source": source,
        "record_count": len(normalized),
        "kind_counts": dict(sorted(kinds.items())),
        "error_like_count": error_like,
        "time_window": {
            "first_observed": timestamps[0] if timestamps else None,
            "last_observed": timestamps[-1] if timestamps else None,
        },
        "sample_record_sha256": sample_hashes,
        "source_payload_sha256": payload_digest,
        "originals_preserved": True,
        "destructive_actions": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "This is deterministic log/memory compaction, not a physical entropy measurement.",
    }
    return crystal


def load_records(path: Path) -> list[Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    stripped = text.strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass
    return [line for line in text.splitlines() if line.strip()]


def compact_file(input_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    input_path = input_path.resolve()
    if output_path is not None and input_path == output_path.resolve():
        raise ValueError("Maxwell refuses to overwrite its source; choose a separate crystal path")
    records = load_records(input_path)
    crystal = compact_records(records, source=str(input_path))
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(crystal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return crystal


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS Maxwell non-destructive memory compactor")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    crystal = compact_file(args.input, args.output)
    if args.output is None:
        print(json.dumps(crystal, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
