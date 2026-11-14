#!/usr/bin/env python3
"""ESSENCE v2.2 lightweight source watcher (research only, never promotion).

Scans the same dated JSON/key-only task as JANUS R1 without importing Torch.
This is a *screen*, not a hidden-test verdict. Only unique suitable public
source datasets can request a v1.9 research trial. The v2.1 sentinel must
independently recheck split evidence and remains authoritative to block training.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
from urllib import request

SCHEMA = "janus.essence.source_watch/2.2"
REPOSITORY = "Hawkar-usls/Janus-Demiurge"
WORKFLOW = "essence-v19-gradirnya.yml"
LABELS = ("LINEAR", "TRUMP", "OSIRIS", "ECHO", "CONNECTION",
          "ROWAN", "SCOBY", "EYE", "OTHER")
DATE = re.compile(r"2026[-_]([01]\d)[-_]([0-3]\d)")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILES = 4200
MAX_FILE_BYTES = 100_000
MAX_HISTORY_PAGES = 20


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def label_for(filename):
    name = filename.upper()
    for index, category in enumerate(LABELS[:-1]):
        if category in ("ROWAN", "SCOBY", "EYE"):
            if name.startswith(category + "-"):
                return index
        elif name.startswith("JANUS-" + category + "-"):
            return index
    return len(LABELS) - 1


def tokenize_keys(keys):
    tokens = [1]
    for key in sorted(k for k in keys if isinstance(k, str))[:15]:
        tokens.append(8 + (int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 248))
    tokens = tokens[:16]
    return [0] * (16 - len(tokens)) + tokens


def collect(root):
    root = Path(root).resolve(strict=True)
    paths = sorted(root.rglob("*.json"))
    if len(paths) > MAX_FILES:
        raise ValueError("UNBOUNDED_ARCHIVE")
    rows = []
    seen = set()
    skipped = {"undated": 0, "invalid_json": 0, "oversize": 0,
               "duplicate": 0, "missing_keys": 0}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("UNSAFE_ARCHIVE_PATH")
        match = DATE.search(path.name)
        if not match:
            skipped["undated"] += 1
            continue
        date = "2026-" + match.group(1) + "-" + match.group(2)
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            skipped["undated"] += 1
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            skipped["oversize"] += 1
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8"),
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (UnicodeError, ValueError, OSError, RecursionError):
            skipped["invalid_json"] += 1
            continue
        if not isinstance(obj, dict) or not 1 <= len(obj) <= 300:
            skipped["missing_keys"] += 1
            continue
        stem = re.sub(r"(?:[-_]v\d+(?:[._]\d+)*)$", "", path.stem, flags=re.I)
        identity = (path.parent.relative_to(root).as_posix(), stem.upper())
        if identity in seen:
            skipped["duplicate"] += 1
            continue
        seen.add(identity)
        rows.append({"date": date, "x": tokenize_keys(obj.keys()),
                     "label": label_for(path.name), "identity": digest(identity)})
    rows.sort(key=lambda row: (row["date"], row["identity"]))
    dates = sorted(set(row["date"] for row in rows))
    if len(rows) < 130 or len(dates) < 30:
        raise ValueError("INSUFFICIENT_DATED_HISTORY")
    cut1 = max(1, int(0.7 * len(dates)))
    cut2 = max(cut1 + 1, int(0.85 * len(dates)))
    if cut2 >= len(dates):
        raise ValueError("INSUFFICIENT_HELDOUT_DATES")
    bounds = dates[cut1], dates[cut2]
    parts = {
        "train": [row for row in rows if row["date"] < bounds[0]],
        "validation": [row for row in rows if bounds[0] <= row["date"] < bounds[1]],
        "holdout": [row for row in rows if row["date"] >= bounds[1]],
    }
    if min(len(part) for part in parts.values()) < 12:
        raise ValueError("INSUFFICIENT_DATE_SPLIT")
    return rows, parts, skipped


def is_diverse(rows):
    counts = Counter(row["label"] for row in rows)
    support = sum(count >= 3 for count in counts.values())
    dominant = max(counts.values()) / len(rows)
    entropy = -sum((count / len(rows)) * math.log2(count / len(rows))
                   for count in counts.values())
    return support >= 3 and dominant <= 0.85 and entropy >= 0.65


def audit(root, source_sha):
    if not HEX40.fullmatch(source_sha):
        raise ValueError("UNPINNED_META_REGISTRY_COMMIT")
    try:
        rows, parts, skipped = collect(root)
        reasons = []
        for role in ("validation", "holdout"):
            if not is_diverse(parts[role]):
                reasons.append("HOLD_" + role.upper() + "_LOW_INFORMATION")
        ready = not reasons
        report = {"schema": SCHEMA,
                  "status": "READY_FOR_RESEARCH_TRIAL" if ready else "HOLD_UNSUITABLE_COHORT",
                  "eligible_for_research_trial": ready,
                  "rejection_codes": reasons,
                  "source_commit": source_sha,
                  "dataset_sha256": digest(rows),
                  "split_sizes": {k: len(v) for k, v in parts.items()},
                  "split_date_ranges": {k: [v[0]["date"], v[-1]["date"]]
                                        for k, v in parts.items()},
                  "total_documents": len(rows),
                  "skipped": skipped}
    except ValueError as exc:
        if str(exc) not in ("INSUFFICIENT_DATED_HISTORY", "INSUFFICIENT_HELDOUT_DATES",
                            "INSUFFICIENT_DATE_SPLIT"):
            raise
        report = {"schema": SCHEMA, "status": "HOLD_INSUFFICIENT_HISTORY",
                  "eligible_for_research_trial": False,
                  "rejection_codes": [str(exc)],
                  "source_commit": source_sha, "dataset_sha256": None}
    report.update({"training_saw_holdout": False,
                   "public_historical_not_external_blind": True,
                   "model_quality_improvement_proven": False,
                   "production_authority": False, "automatic_promotion": False})
    report["receipt_sha256"] = digest(report)
    return report


def validate_report(report):
    if (not isinstance(report, dict) or report.get("schema") != SCHEMA
        or report.get("receipt_sha256") !=
           digest({k: v for k, v in report.items() if k != "receipt_sha256"})
        or not HEX40.fullmatch(str(report.get("source_commit", "")))
        or report.get("production_authority") is not False
        or report.get("automatic_promotion") is not False):
        raise ValueError("UNTRUSTED_SOURCE_READINESS")
    ready = report.get("eligible_for_research_trial")
    if type(ready) is not bool:
        raise ValueError("INVALID_SOURCE_READINESS")
    if ready and (not HEX64.fullmatch(str(report.get("dataset_sha256", "")))
                  or report.get("rejection_codes") != []
                  or report.get("status") != "READY_FOR_RESEARCH_TRIAL"):
        raise ValueError("UNTRUSTED_READY_DATASET")
    return ready


def decision(report, runs, *, exhaustive=True):
    ready = validate_report(report)
    if not ready:
        return "HOLD_SOURCE_NOT_READY"
    if not exhaustive:
        return "HOLD_DISPATCH_HISTORY_NOT_EXHAUSTIVE"
    title = "ESSENCE dataset " + report["dataset_sha256"]
    if any(item.get("head_branch") == "main" and
           item.get("display_title") == title for item in runs):
        return "HOLD_DATASET_ALREADY_ATTEMPTED"
    return "DISPATCH_RESEARCH_ONLY"


def api_json(url, token, *, data=None):
    if not token or len(token) > 4096:
        raise ValueError("MISSING_OR_INVALID_GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json",
               "Authorization": "Bearer " + token,
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "janus-essence-v22-research"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = request.Request(url, headers=headers, data=canonical(data) if data else None,
                          method="POST" if data is not None else "GET")
    with request.urlopen(req, timeout=20) as response:
        if data is not None:
            if response.status != 204:
                raise ValueError("DISPATCH_NOT_ACCEPTED")
            return {}
        return json.load(response)


def dispatch(report, token):
    validate_report(report)
    if not report["eligible_for_research_trial"]:
        return "HOLD_SOURCE_NOT_READY"
    base = "https://api.github.com/repos/" + REPOSITORY
    runs = []
    complete = False
    for page in range(1, MAX_HISTORY_PAGES + 1):
        url = (base + "/actions/workflows/" + WORKFLOW +
               "/runs?branch=main&per_page=100&page=" + str(page))
        batch = api_json(url, token).get("workflow_runs")
        if not isinstance(batch, list):
            raise ValueError("UNTRUSTED_WORKFLOW_HISTORY")
        runs.extend(batch)
        if len(batch) < 100:
            complete = True
            break
    gate = decision(report, runs, exhaustive=complete)
    if gate != "DISPATCH_RESEARCH_ONLY":
        return gate
    api_json(base + "/actions/workflows/" + WORKFLOW + "/dispatches", token,
             data={"ref": "main", "inputs": {
                 "registry_sha": report["source_commit"],
                 "dataset_sha": report["dataset_sha256"]}})
    return "RESEARCH_TRIAL_REQUESTED_NOT_VERIFIED"


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--root", required=True)
    s.add_argument("--source", required=True)
    s.add_argument("--out", required=True)
    d = sub.add_parser("dispatch")
    d.add_argument("--report", required=True)
    a = p.parse_args()
    if a.cmd == "scan":
        path = Path(a.out)
        if path.exists():
            raise FileExistsError("IMMUTABLE_READINESS_REPORT")
        result = audit(a.root, a.source)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"status": result["status"], "reasons": result["rejection_codes"],
                          "dataset_sha256": result["dataset_sha256"],
                          "production_authority": False}))
    else:
        report = json.loads(Path(a.report).read_text(encoding="utf-8"))
        status = dispatch(report, os.environ.get("GH_TOKEN", ""))
        print(json.dumps({"status": status, "production_authority": False}))


if __name__ == "__main__":
    main()
