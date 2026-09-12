#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

BINDING_SCHEMA = "janus.nexus.rex_lifecycle_binding.v1"
RECEIPT_SCHEMA = "janus.rex.lifecycle_run_receipt.v1"
MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
EVENT_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def cjson(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: pathlib.Path) -> str:
    return digest_bytes(path.read_bytes())


def load(path: pathlib.Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise SystemExit(f"JSON object required: {path}")
    return obj


def write_if_changed(path: pathlib.Path, obj: dict[str, Any]) -> bool:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == raw:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")
    return True


def nexus_lifecycle_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if policy.get("schema") != "janus.nexus.rex_low_risk_policy.v1":
        raise SystemExit("unsupported Nexus policy schema")
    life = policy.get("lifecycle")
    if not isinstance(life, dict) or life.get("enabled") is not True:
        raise SystemExit("NEXUS_LIFECYCLE_POLICY_DISABLED")
    return life


def validate_lifecycle_request(spec: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    req = spec.get("lifecycle")
    if not isinstance(req, dict) or req.get("enabled") is not True:
        raise SystemExit("NO_LIFECYCLE_REQUEST")
    life = nexus_lifecycle_policy(policy)
    mode = str(req.get("mode") or "")
    if mode not in set(life.get("allowed_modes") or []):
        raise SystemExit(f"NEXUS_LIFECYCLE_MODE_REFUSED:{mode}")
    static_input = req.get("input", {})
    if not isinstance(static_input, dict):
        raise SystemExit("LIFECYCLE_INPUT_NOT_OBJECT")
    max_input = int(life.get("max_input_bytes", 10000))
    if len(cjson(static_input)) > max_input:
        raise SystemExit("LIFECYCLE_INPUT_TOO_LARGE")
    out: dict[str, Any] = {"enabled": True, "mode": mode, "input": static_input}
    if mode == "SCHEDULED":
        interval = req.get("interval_minutes")
        allowed = {int(x) for x in life.get("scheduled_intervals_minutes") or []}
        if not isinstance(interval, int) or interval not in allowed:
            raise SystemExit("LIFECYCLE_INTERVAL_REFUSED")
        out["interval_minutes"] = interval
    elif mode == "EVENT_DRIVEN":
        key = str(req.get("event_key") or "")
        if not EVENT_KEY_RE.fullmatch(key):
            raise SystemExit("LIFECYCLE_EVENT_KEY_INVALID")
        out["event_key"] = key
    return out


def exact_source_guard(
    module_id: str,
    expected_source_sha: str,
    candidate_root: pathlib.Path,
    admissions_dir: pathlib.Path,
) -> tuple[pathlib.Path, dict[str, Any], dict[str, Any]]:
    cdir = candidate_root / module_id
    source = cdir / "module.py"
    candidate = load(cdir / "candidate.json")
    audit = load(cdir / "audit.json")
    admission = load(admissions_dir / f"{module_id}.json")
    actual = digest_file(source)
    if (
        candidate.get("module_id") != module_id
        or candidate.get("source_sha256") != actual
        or audit.get("status") != "PASS"
        or audit.get("source_sha256") != actual
        or admission.get("state") != "ADMITTED_EXACT_SHA"
        or admission.get("source_sha256") != actual
        or expected_source_sha != actual
    ):
        raise SystemExit(f"LIFECYCLE_EXACT_SHA_GUARD_FAIL:{module_id}")
    return cdir, candidate, admission


def cmd_register(a: argparse.Namespace) -> int:
    spec = load(pathlib.Path(a.spec))
    policy = load(pathlib.Path(a.nexus_policy))
    req = validate_lifecycle_request(spec, policy)
    module_id = str(spec.get("module_id") or "")
    if not MODULE_ID_RE.fullmatch(module_id):
        raise SystemExit("invalid module_id")
    candidate_root = pathlib.Path(a.candidate_root)
    admissions_dir = pathlib.Path(a.admissions_dir)
    cdir = candidate_root / module_id
    candidate = load(cdir / "candidate.json")
    source_sha = str(candidate.get("source_sha256") or "")
    _, candidate, admission = exact_source_guard(
        module_id, source_sha, candidate_root, admissions_dir
    )
    binding = {
        "schema": BINDING_SCHEMA,
        "module_id": module_id,
        "version": candidate.get("version"),
        "template": candidate.get("template"),
        "source_sha256": source_sha,
        "candidate_manifest_sha256": digest_file(cdir / "candidate.json"),
        "audit_receipt_sha256": digest_file(cdir / "audit.json"),
        "admission_receipt_sha256": digest_file(admissions_dir / f"{module_id}.json"),
        "state": "LIFECYCLE_ADMITTED_EXACT_SHA",
        "authority": "EXPLICIT_EXTERNAL_GATE",
        "mode": req["mode"],
        "input": req["input"],
        "authority_delta": 0,
        "law": "REX_CAN_CREATE_NE_REX_CAN_CROWN",
    }
    if req["mode"] == "SCHEDULED":
        binding["interval_minutes"] = req["interval_minutes"]
    elif req["mode"] == "EVENT_DRIVEN":
        binding["event_key"] = req["event_key"]
    out = pathlib.Path(a.registry_dir) / f"{module_id}.json"
    changed = write_if_changed(out, binding)
    print(json.dumps({"status": "PASS", "changed": changed, "binding": binding}, ensure_ascii=False, indent=2))
    return 0


def load_bindings(registry_dir: pathlib.Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not registry_dir.exists():
        return rows
    for path in sorted(registry_dir.glob("*.json")):
        obj = load(path)
        if obj.get("schema") != BINDING_SCHEMA:
            raise SystemExit(f"unsupported lifecycle binding: {path}")
        if obj.get("state") != "LIFECYCLE_ADMITTED_EXACT_SHA" or obj.get("authority_delta") != 0:
            raise SystemExit(f"invalid lifecycle binding state: {path}")
        rows.append(obj)
    return rows


def execution_key(
    binding: dict[str, Any],
    trigger: str,
    now_epoch: int,
    workflow_run_id: str,
    event_id: str | None,
) -> str:
    module_id = binding["module_id"]
    if trigger == "schedule":
        interval = int(binding["interval_minutes"])
        slot = now_epoch // (interval * 60)
        return f"{module_id}|schedule|{interval}|{slot}"
    if trigger == "on_demand":
        return f"{module_id}|on_demand|{workflow_run_id}"
    if trigger == "event":
        return f"{module_id}|event|{event_id}"
    raise SystemExit(f"unsupported trigger:{trigger}")


def select_bindings(
    bindings: list[dict[str, Any]],
    trigger: str,
    module_id: str | None,
    event_key: str | None,
) -> list[dict[str, Any]]:
    selected = []
    for row in bindings:
        if module_id and row.get("module_id") != module_id:
            continue
        mode = row.get("mode")
        if trigger == "schedule" and mode == "SCHEDULED":
            selected.append(row)
        elif trigger == "on_demand" and mode == "ON_DEMAND":
            selected.append(row)
        elif trigger == "event" and mode == "EVENT_DRIVEN" and row.get("event_key") == event_key:
            selected.append(row)
    if trigger == "on_demand" and not module_id:
        raise SystemExit("ON_DEMAND_REQUIRES_MODULE_ID")
    if trigger == "event" and not event_key:
        raise SystemExit("EVENT_REQUIRES_EVENT_KEY")
    return selected


def cmd_execute(a: argparse.Namespace) -> int:
    policy = load(pathlib.Path(a.nexus_policy))
    life = nexus_lifecycle_policy(policy)
    bindings = load_bindings(pathlib.Path(a.registry_dir))
    trigger = a.trigger
    module_id = a.module_id or None
    event_key = a.event_key or None
    event_id = a.event_id or None
    if trigger == "event":
        if not event_id or not EVENT_ID_RE.fullmatch(event_id):
            raise SystemExit("EVENT_REQUIRES_VALID_EVENT_ID")
        if not event_key or not EVENT_KEY_RE.fullmatch(event_key):
            raise SystemExit("EVENT_REQUIRES_VALID_EVENT_KEY")
    selected = select_bindings(bindings, trigger, module_id, event_key)
    max_exec = min(int(a.max_executions), int(life.get("max_executions_per_run", 16)))
    selected = selected[:max_exec]
    now_epoch = int(a.now_epoch if a.now_epoch is not None else time.time())
    workflow_run_id = str(a.workflow_run_id or os.environ.get("GITHUB_RUN_ID") or now_epoch)
    event_payload: dict[str, Any] = {}
    if trigger == "event" and a.event_payload:
        event_payload = load(pathlib.Path(a.event_payload))
        if len(cjson(event_payload)) > int(life.get("max_event_payload_bytes", 10000)):
            raise SystemExit("EVENT_PAYLOAD_TOO_LARGE")

    candidate_root = pathlib.Path(a.candidate_root)
    admissions_dir = pathlib.Path(a.admissions_dir)
    runs_dir = pathlib.Path(a.runs_dir)
    executed = []
    skipped = []
    for binding in selected:
        mid = str(binding["module_id"])
        cdir, _, _ = exact_source_guard(
            mid, str(binding["source_sha256"]), candidate_root, admissions_dir
        )
        key = execution_key(binding, trigger, now_epoch, workflow_run_id, event_id)
        key_hash = digest_bytes(key.encode())
        receipt = runs_dir / mid / f"{key_hash[:24]}.json"
        if receipt.exists():
            old = load(receipt)
            if old.get("execution_key_sha256") != key_hash or old.get("source_sha256") != binding["source_sha256"]:
                raise SystemExit(f"LIFECYCLE_DEDUPE_COLLISION:{mid}")
            skipped.append({"module_id": mid, "reason": "dedupe", "receipt": receipt.as_posix()})
            continue

        payload = dict(binding.get("input") or {})
        if trigger == "event":
            payload["event"] = {
                "key": event_key,
                "id": event_id,
                "payload": event_payload,
            }
        raw_input = cjson(payload)
        if len(raw_input) > int(life.get("max_input_bytes", 10000)):
            raise SystemExit(f"LIFECYCLE_RUNTIME_INPUT_TOO_LARGE:{mid}")
        with tempfile.TemporaryDirectory() as td:
            inp = pathlib.Path(td) / "input.json"
            inp.write_bytes(raw_input)
            proc = subprocess.run(
                [
                    sys.executable,
                    a.runner,
                    "run",
                    "--candidate-dir",
                    str(cdir),
                    "--admissions-dir",
                    str(admissions_dir),
                    "--input",
                    str(inp),
                    "--timeout",
                    str(int(life.get("run_timeout_seconds", 8))),
                    "--max-input-bytes",
                    str(int(life.get("max_input_bytes", 10000))),
                ],
                text=True,
                capture_output=True,
                timeout=int(life.get("run_timeout_seconds", 8)) + 5,
            )
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            raise SystemExit(f"LIFECYCLE_CHILD_RUN_FAIL:{mid}")
        result = json.loads(proc.stdout)
        if not isinstance(result, dict) or result.get("authority_delta") != 0:
            raise SystemExit(f"LIFECYCLE_RESULT_AUTHORITY_FAIL:{mid}")
        receipt_obj = {
            "schema": RECEIPT_SCHEMA,
            "module_id": mid,
            "source_sha256": binding["source_sha256"],
            "mode": binding["mode"],
            "trigger": trigger,
            "execution_key_sha256": key_hash,
            "input_sha256": digest_bytes(raw_input),
            "result_sha256": digest_bytes(cjson(result)),
            "result_status": result.get("status"),
            "state": "EXECUTED_EXACT_SHA",
            "workflow_run_id": workflow_run_id,
            "authority_delta": 0,
            "privacy": "INPUT_AND_RESULT_HASHED_NOT_PERSISTED",
            "law": "LIFECYCLE_ADMISSION_BINDS_EXACT_SOURCE_SHA256",
        }
        write_if_changed(receipt, receipt_obj)
        executed.append({"module_id": mid, "receipt": receipt.as_posix(), "result_status": result.get("status")})

    summary = {
        "schema": "janus.rex.lifecycle_executor_receipt.v1",
        "status": "PASS",
        "trigger": trigger,
        "selected": len(selected),
        "executed": executed,
        "skipped": skipped,
        "authority_delta": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="JANUS Rex lifecycle admission and runtime")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register")
    r.add_argument("--spec", required=True)
    r.add_argument("--nexus-policy", default="rex/nexus_policy.json")
    r.add_argument("--candidate-root", default="rex/candidates")
    r.add_argument("--admissions-dir", default="rex/admissions")
    r.add_argument("--registry-dir", default="rex/lifecycle")
    r.set_defaults(fn=cmd_register)

    e = sub.add_parser("execute")
    e.add_argument("--trigger", choices=["schedule", "on_demand", "event"], required=True)
    e.add_argument("--module-id")
    e.add_argument("--event-key")
    e.add_argument("--event-id")
    e.add_argument("--event-payload")
    e.add_argument("--now-epoch", type=int)
    e.add_argument("--workflow-run-id")
    e.add_argument("--nexus-policy", default="rex/nexus_policy.json")
    e.add_argument("--candidate-root", default="rex/candidates")
    e.add_argument("--admissions-dir", default="rex/admissions")
    e.add_argument("--registry-dir", default="rex/lifecycle")
    e.add_argument("--runs-dir", default="rex/lifecycle_runs")
    e.add_argument("--runner", default="tools/demiurge_rex.py")
    e.add_argument("--max-executions", type=int, default=16)
    e.set_defaults(fn=cmd_execute)

    a = ap.parse_args()
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
