from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "janus.chronos.backup_candidate.v1"
REPORT_SCHEMA = "janus.chronos.scavenge_report.v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def discover_backups(root: str | Path, suffixes: Iterable[str] = (".db", ".sqlite", ".sqlite3")) -> list[Path]:
    base = Path(root).resolve()
    allowed = {s.lower() for s in suffixes}
    return [p for p in sorted(base.rglob("*"), key=lambda x: x.as_posix()) if p.is_file() and p.suffix.lower() in allowed]


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def extract_candidates(db_path: str | Path, *, limit: int = 64) -> dict[str, Any]:
    path = Path(db_path).resolve()
    source_sha = sha256_file(path)
    candidates: list[dict[str, Any]] = []
    findings: list[str] = []
    try:
        with _connect_read_only(path) as conn:
            tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "thoughts" not in tables:
                findings.append("THOUGHTS_TABLE_ABSENT")
            else:
                cols = _table_columns(conn, "thoughts")
                if "content" not in cols:
                    findings.append("THOUGHTS_CONTENT_COLUMN_ABSENT")
                else:
                    order_col = "id" if "id" in cols else "rowid"
                    rows = conn.execute(
                        f"SELECT {order_col}, content FROM thoughts ORDER BY {order_col} ASC LIMIT ?",
                        (max(0, int(limit)),),
                    ).fetchall()
                    for row_id, content in rows:
                        text = "" if content is None else str(content)
                        body = {
                            "schema": SCHEMA,
                            "source_db_name": path.name,
                            "source_db_sha256": source_sha,
                            "source_table": "thoughts",
                            "source_row_id": row_id,
                            "content_sha256": _sha256_bytes(text.encode("utf-8")),
                            "content": text,
                            "historical_label": "ANCIENT_WISDOM",
                            "status": "CANDIDATE_ONLY",
                            "authority": {
                                "injects_memory": False,
                                "promotes_truth": False,
                                "modifies_backup": False,
                            },
                            "law": "RECOVERED_MEMORY_IS_EVIDENCE_CANDIDATE_NOT_AUTOMATIC_WISDOM",
                        }
                        candidate_identity = {k: v for k, v in body.items() if k != "content"}
                        body["candidate_id"] = _sha256_bytes(
                            json.dumps(candidate_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
                        )
                        candidates.append(body)
    except sqlite3.DatabaseError as exc:
        findings.append(f"SQLITE_ERROR:{type(exc).__name__}")
    return {
        "schema": REPORT_SCHEMA,
        "source_db_name": path.name,
        "source_db_sha256": source_sha,
        "candidate_count": len(candidates),
        "findings": findings,
        "candidates": candidates,
        "authority": {
            "read_only_sqlite": True,
            "injects_memory": False,
            "writes_backup": False,
        },
    }


def scavenge_directory(root: str | Path, *, per_db_limit: int = 64) -> dict[str, Any]:
    reports = [extract_candidates(p, limit=per_db_limit) for p in discover_backups(root)]
    return {
        "schema": "janus.chronos.directory_report.v1",
        "backup_count": len(reports),
        "candidate_count": sum(r["candidate_count"] for r in reports),
        "reports": reports,
        "authority": {"injects_memory": False, "network_io": False, "modifies_backups": False},
    }
