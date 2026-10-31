"""Read fixed public work, independently audit it, append numeric adapter state.

No candidate text is executed. This tool writes only the supplied isolated state
directory. The workflow persists it only to janus/helios-adapter-state.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from tools.extensions.helios_native_calibration import audit, digest
from janus_model.extensions.helios_calibration import canonical, validate_admission

REPO = "Hawkar-usls/Janus-Demiurge"
RAW = "https://raw.githubusercontent.com/" + REPO + "/"
TASK_SHA = "71084dbdebe8f05b961712e0280d3a4945dbc3f20b9eef35d4f9c6d2b9a5098a"
CANDIDATES = "https://tg-pomoyka.hawkarlol.chatgpt.site/api/portal/helios/learning/candidates"


def read_public(url, optional=False):
    if not (url.startswith(RAW) or url == CANDIDATES):
        raise ValueError("FIXED_PUBLIC_SOURCE_REQUIRED")
    request = urllib.request.Request(url, headers={"User-Agent": "JANUS-native-calibration-auditor", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if not response.geturl().startswith((RAW, CANDIDATES)):
                raise ValueError("PUBLIC_SOURCE_REDIRECT_REJECTED")
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError("PUBLIC_SOURCE_TOO_LARGE")
            return raw
    except urllib.error.HTTPError as error:
        if optional and error.code == 404:
            return None
        raise


def collect(state, drill=False):
    if drill:
        rows = [json.loads(read_public(RAW + "janus/helios-learning/operator-drill.json"))]
    else:
        obj = json.loads(read_public(CANDIDATES))
        if obj.get("schema") != "janus.helios.public_candidates.v1" or obj.get("task_sha256") != TASK_SHA:
            raise ValueError("PUBLIC_CANDIDATE_SCHEMA_REJECTED")
        rows = obj.get("candidates")
    if not isinstance(rows, list) or len(rows) > 20:
        raise ValueError("CANDIDATE_BUDGET_REJECTED")
    pending = []
    for row in rows:
        ident = row.get("candidate_id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", ident) or row.get("task_sha256") != TASK_SHA:
            continue
        if not drill and row.get("consent_version") != "HELIOS_NATIVE_CALIBRATION_2026_10_31":
            continue
        if not (state / "attempts" / (ident + ".json")).exists():
            pending.append(row)
    # One bounded, independent admission per run; later jobs learn from its state.
    return pending[:1]


def immutable(path, value):
    raw = canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("CALIBRATION_HISTORY_IS_IMMUTABLE")
    path.write_bytes(raw)


def run_cycle(state, rows):
    raw = read_public(RAW + "janus/helios-learning/tasks/" + TASK_SHA + ".json")
    if digest(raw) != TASK_SHA:
        raise ValueError("PINNED_TASK_HASH_REJECTED")
    task = json.loads(raw)
    checkpoint = Path("janus_model/checkpoints/promoted.pt")
    checkpoint_sha = digest(checkpoint.read_bytes())
    previous_path = state / "ADAPTER_LATEST.json"
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else None
    if previous and previous.get("checkpoint_sha256") != checkpoint_sha:
        previous = None
    if previous:
        validate_admission(previous, checkpoint_sha)
    immutable(state / "baselines" / (checkpoint_sha + ".json"), {
        "checkpoint_sha256": checkpoint_sha, "weights_replaced": False,
        "restore": "Remove optional output adapter; load unchanged promoted.pt from this exact SHA",
        "task_sha256": TASK_SHA,
    })
    for candidate in rows:
        if checkpoint_sha != task.get("checkpoint_sha256"):
            receipt = {"candidate_id": candidate["candidate_id"], "status": "STALE_CHECKPOINT_TASK", "task_sha256": TASK_SHA}
        else:
            receipt = audit(task, candidate, checkpoint, Path("janus_model/eval/JANUS_ANCHOR_EVAL-v1.txt").read_text(encoding="utf-8"), previous)
        # A rejected result is a permanent lesson too; never replace its history.
        immutable(state / "attempts" / (candidate["candidate_id"] + ".json"), receipt)
        if receipt["status"] == "ADMITTED_NATIVE_CALIBRATION":
            immutable(state / "admitted" / (receipt["calibration_sha256"] + ".json"), receipt)
            previous_path.write_bytes(canonical(receipt) + b"\n")
            previous = receipt
        print(json.dumps({"candidate_id": candidate["candidate_id"], "status": receipt["status"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "audit", "fetch-adapter"))
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--pending", type=Path, required=True)
    parser.add_argument("--drill", action="store_true")
    args = parser.parse_args()
    if args.mode == "fetch-adapter":
        raw = read_public(RAW + "janus/helios-adapter-state/ADAPTER_LATEST.json", optional=True)
        if raw is None:
            return
        receipt = json.loads(raw)
        checkpoint_sha = digest(Path("janus_model/checkpoints/promoted.pt").read_bytes())
        if receipt.get("checkpoint_sha256") != checkpoint_sha:
            print("CALIBRATION_SKIPPED_CHECKPOINT_CHANGED")
            return
        validate_admission(receipt, checkpoint_sha)
        args.pending.parent.mkdir(parents=True, exist_ok=True)
        args.pending.write_bytes(raw)
        print("CALIBRATION_EXACT_CHECKPOINT_READY")
    elif args.mode == "preflight":
        rows = collect(args.state, args.drill)
        args.pending.parent.mkdir(parents=True, exist_ok=True)
        args.pending.write_bytes(canonical(rows))
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write("pending=" + ("true" if rows else "false") + "\n")
        print(json.dumps({"pending": len(rows)}))
    else:
        run_cycle(args.state, json.loads(args.pending.read_text()))


if __name__ == "__main__":
    main()
