#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PAGE_SIZE = 4096
SAMPLE_BYTES = 256


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _default_primary_path() -> Path:
    env_path = str(os.environ.get("JANUS_DB_PATH", "") or "").strip()
    if env_path:
        return Path(env_path)
    root_dir = Path(os.environ.get("JANUS_ROOT_DIR", Path(__file__).resolve().parents[1]))
    return root_dir / "janus.db"


def _meta_dir(primary_path: Path) -> Path:
    root_dir = primary_path.parent
    candidates = [
        root_dir / "runtime" / "meta",
        root_dir / "janus_nas" / "runtime" / "meta",
        root_dir / "temp",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue
    raise PermissionError(f"cannot create guard metadata directory for {primary_path}")


def _safe_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp_path, path)


def probe_sqlite(path: Path) -> dict:
    result = {
        "path": str(path),
        "exists": path.exists(),
        "ok": False,
        "reason": "",
        "size": path.stat().st_size if path.exists() else 0,
    }
    if not path.exists():
        result["reason"] = "missing"
        return result

    try:
        with path.open("rb") as handle:
            header = handle.read(16)
        result["header_hex"] = header.hex()
    except Exception as exc:
        result["reason"] = "header_read_failed"
        result["error"] = str(exc)
        return result

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 12")
        result["table_sample"] = [row[0] for row in cur.fetchall()]
        conn.close()
        result["ok"] = True
        result["reason"] = "ok"
        return result
    except Exception as exc:
        result["reason"] = "sqlite_open_failed"
        result["error"] = str(exc)
        return result


def discover_candidates(primary_path: Path) -> list[Path]:
    root_dir = primary_path.parent
    raw_candidates: list[Path] = []

    env_candidates = str(os.environ.get("JANUS_DB_REPAIR_CANDIDATES", "") or "").strip()
    if env_candidates:
        for item in env_candidates.split(","):
            item = item.strip()
            if item:
                raw_candidates.append(Path(item))

    raw_candidates.append(root_dir / "janus_data" / "janus.db")

    for pattern in (
        "backups/janus_boot_*.db",
        "wormhole_digested/*janus_boot_*.db",
        "wormhole_digested/*janus_backup_*.db",
    ):
        raw_candidates.extend(root_dir.glob(pattern))

    dedup: list[Path] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        try:
            key = str(candidate.resolve())
        except Exception:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if str(candidate) == str(primary_path):
            continue
        if candidate.exists():
            dedup.append(candidate)

    dedup.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return dedup


def _sample_positions(file_size: int) -> list[int]:
    positions = [PAGE_SIZE, PAGE_SIZE * 2, 1024 * 1024, 128 * 1024 * 1024, 512 * 1024 * 1024]
    if file_size > PAGE_SIZE * 3:
        positions.append(max(PAGE_SIZE, file_size - PAGE_SIZE))
    usable: list[int] = []
    for pos in positions:
        if pos + SAMPLE_BYTES <= file_size:
            usable.append(pos)
    return usable


def same_after_first_page(primary_path: Path, candidate_path: Path) -> bool:
    if not primary_path.exists() or not candidate_path.exists():
        return False
    if primary_path.stat().st_size != candidate_path.stat().st_size:
        return False

    positions = _sample_positions(primary_path.stat().st_size)
    if not positions:
        return False

    with primary_path.open("rb") as primary_handle, candidate_path.open("rb") as candidate_handle:
        for pos in positions:
            primary_handle.seek(pos)
            candidate_handle.seek(pos)
            if primary_handle.read(SAMPLE_BYTES) != candidate_handle.read(SAMPLE_BYTES):
                return False
    return True


def backup_primary_page(primary_path: Path) -> Path:
    meta_dir = _meta_dir(primary_path)
    meta_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = meta_dir / f"{primary_path.name}.page0.before_repair.{stamp}.bin"
    with primary_path.open("rb") as source, backup_path.open("wb") as target:
        target.write(source.read(PAGE_SIZE))
    return backup_path


def repair_first_page(primary_path: Path, candidate_path: Path) -> dict:
    backup_path = backup_primary_page(primary_path)
    with candidate_path.open("rb") as source:
        replacement = source.read(PAGE_SIZE)
    with primary_path.open("r+b") as target:
        target.seek(0)
        target.write(replacement)
        target.flush()
    return {"backup_path": str(backup_path)}


def restore_full_copy(primary_path: Path, candidate_path: Path) -> dict:
    meta_dir = _meta_dir(primary_path)
    meta_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    moved_path = meta_dir / f"{primary_path.name}.corrupt_snapshot.{stamp}.db"
    shutil.copy2(primary_path, moved_path)
    shutil.copy2(candidate_path, primary_path)
    return {"backup_path": str(moved_path)}


def ensure_primary_db(primary_path: Path | None = None) -> dict:
    primary = Path(primary_path) if primary_path else _default_primary_path()
    report = {
        "ts": utc_now(),
        "primary_path": str(primary),
        "action": "none",
        "ok": False,
        "primary_probe_before": probe_sqlite(primary),
        "candidate_count": 0,
        "candidate_path": "",
    }

    if report["primary_probe_before"].get("ok"):
        report["action"] = "healthy"
        report["ok"] = True
        report["primary_probe_after"] = report["primary_probe_before"]
        _safe_write_json(_meta_dir(primary) / "primary_db_guard.json", report)
        return report

    candidates = discover_candidates(primary)
    report["candidate_count"] = len(candidates)

    valid_candidates: list[tuple[Path, dict]] = []
    for candidate in candidates:
        candidate_probe = probe_sqlite(candidate)
        if candidate_probe.get("ok"):
            valid_candidates.append((candidate, candidate_probe))

    allow_full_restore = str(os.environ.get("JANUS_DB_GUARD_ALLOW_FULL_RESTORE", "1") or "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    for candidate, candidate_probe in valid_candidates:
        report["candidate_path"] = str(candidate)
        report["candidate_probe"] = candidate_probe
        if same_after_first_page(primary, candidate):
            repair_meta = repair_first_page(primary, candidate)
            report["action"] = "patched_first_page"
            report.update(repair_meta)
            report["primary_probe_after"] = probe_sqlite(primary)
            report["ok"] = bool(report["primary_probe_after"].get("ok"))
            _safe_write_json(_meta_dir(primary) / "primary_db_guard.json", report)
            return report

    if allow_full_restore and valid_candidates:
        candidate, candidate_probe = valid_candidates[0]
        report["candidate_path"] = str(candidate)
        report["candidate_probe"] = candidate_probe
        repair_meta = restore_full_copy(primary, candidate)
        report["action"] = "restored_full_copy"
        report.update(repair_meta)
        report["primary_probe_after"] = probe_sqlite(primary)
        report["ok"] = bool(report["primary_probe_after"].get("ok"))
        _safe_write_json(_meta_dir(primary) / "primary_db_guard.json", report)
        return report

    report["action"] = "unrepaired"
    report["primary_probe_after"] = probe_sqlite(primary)
    report["ok"] = False
    _safe_write_json(_meta_dir(primary) / "primary_db_guard.json", report)
    return report


def main(argv: list[str]) -> int:
    command = argv[1].strip().lower() if len(argv) > 1 else "repair"
    primary_path = _default_primary_path()

    if command == "probe":
        result = probe_sqlite(primary_path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1

    if command != "repair":
        print(json.dumps({"ok": False, "error": f"unknown command: {command}"}, ensure_ascii=False, indent=2))
        return 2

    result = ensure_primary_db(primary_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
