"""JANUS daemon restoration candidate: observer half only.

This module performs one-shot liveness observations over heartbeat files. It has
NO authority to restart, retry, kill, launch, signal, or contact processes.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "janus.daemon.liveness_observer.v1"
NO_ACTUATION = True


def _safe_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def observe_heartbeat(path: Path, *, stale_after_sec: float = 120.0, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else float(now)
    target = path.resolve()
    receipt: dict[str, Any] = {
        "path": str(target),
        "status": "MISSING",
        "age_sec": None,
        "mtime": None,
        "payload_valid_json": False,
        "payload": None,
        "error": None,
    }
    if not target.exists():
        return receipt
    try:
        stat = target.stat()
    except OSError as exc:
        receipt["status"] = "UNREADABLE"
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        return receipt

    age = max(0.0, now - stat.st_mtime)
    receipt["age_sec"] = round(age, 6)
    receipt["mtime"] = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    payload, error = _safe_json(target)
    receipt["payload_valid_json"] = error is None
    receipt["payload"] = payload if isinstance(payload, dict) else None
    receipt["error"] = error
    if error is not None:
        receipt["status"] = "INVALID"
    elif age > float(stale_after_sec):
        receipt["status"] = "STALE"
    else:
        receipt["status"] = "FRESH"
    return receipt


def snapshot(paths: list[Path], *, stale_after_sec: float = 120.0, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else float(now)
    observations = [observe_heartbeat(p, stale_after_sec=stale_after_sec, now=now) for p in paths]
    counts: dict[str, int] = {}
    for item in observations:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return {
        "schema": SCHEMA,
        "role": "DAEMON_OBSERVER",
        "authority": "READ_ONLY_ONE_SHOT_LIVENESS",
        "no_actuation": NO_ACTUATION,
        "automatic_restart": False,
        "automatic_retry": False,
        "automatic_recovery": False,
        "persistent_daemon": False,
        "observed_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "stale_after_sec": float(stale_after_sec),
        "status_counts": dict(sorted(counts.items())),
        "observations": observations,
        "claim_boundary": "Liveness evidence only; this observer cannot infer safe recovery authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="JANUS one-shot daemon liveness observer")
    parser.add_argument("heartbeat", nargs="+", type=Path)
    parser.add_argument("--stale-after", type=float, default=120.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = snapshot(args.heartbeat, stale_after_sec=args.stale_after)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
