from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def jdump(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args):
    return subprocess.run([PYTHON, *map(str, args)], cwd=ROOT, text=True, capture_output=True)


def fixture(td: pathlib.Path, mode: str = "SCHEDULED"):
    candidate_root = td / "candidates"
    admissions = td / "admissions"
    registry = td / "lifecycle"
    runs = td / "runs"
    cdir = candidate_root / "organ"
    cdir.mkdir(parents=True)
    source = "async def run(context):\n    return {'status':'ALIVE','authority_delta':0}\n"
    (cdir / "module.py").write_text(source, encoding="utf-8")
    source_sha = sha(cdir / "module.py")
    candidate = {
        "schema": "janus.rex.candidate.v1",
        "module_id": "organ",
        "version": "1.0.0",
        "template": "heartbeat",
        "source_sha256": source_sha,
        "authority_delta": 0,
    }
    jdump(cdir / "candidate.json", candidate)
    audit = {
        "schema": "janus.rex.audit_receipt.v1",
        "module_id": "organ",
        "source_sha256": source_sha,
        "status": "PASS",
        "errors": [],
        "admission": "NOT_GRANTED",
        "authority_delta": 0,
    }
    jdump(cdir / "audit.json", audit)
    admission = {
        "schema": "janus.nexus.rex_admission.v1",
        "module_id": "organ",
        "version": "1.0.0",
        "source_sha256": source_sha,
        "state": "ADMITTED_EXACT_SHA",
        "authority": "EXPLICIT_EXTERNAL_GATE",
        "authority_delta": 0,
    }
    jdump(admissions / "organ.json", admission)
    policy = {
        "schema": "janus.nexus.rex_low_risk_policy.v1",
        "lifecycle": {
            "enabled": True,
            "allowed_modes": ["ON_DEMAND", "SCHEDULED", "EVENT_DRIVEN"],
            "scheduled_intervals_minutes": [15, 30, 60],
            "max_input_bytes": 10000,
            "max_event_payload_bytes": 10000,
            "run_timeout_seconds": 8,
            "max_executions_per_run": 16,
        },
    }
    jdump(td / "policy.json", policy)
    lifecycle = {"enabled": True, "mode": mode, "input": {"tick": 1}}
    if mode == "SCHEDULED":
        lifecycle["interval_minutes"] = 60
    if mode == "EVENT_DRIVEN":
        lifecycle["event_key"] = "janus.test"
    spec = {
        "schema": "janus.rex.module_spec.v1",
        "module_id": "organ",
        "version": "1.0.0",
        "purpose": "test",
        "template": "heartbeat",
        "config": {},
        "lifecycle": lifecycle,
    }
    jdump(td / "spec.json", spec)
    fake_runner = td / "runner.py"
    fake_runner.write_text(
        "import json,sys\n"
        "if 'run' not in sys.argv: raise SystemExit(2)\n"
        "print(json.dumps({'status':'ALIVE','authority_delta':0},sort_keys=True))\n",
        encoding="utf-8",
    )
    return candidate_root, admissions, registry, runs, fake_runner


def register(td: pathlib.Path, mode: str = "SCHEDULED"):
    candidate_root, admissions, registry, runs, fake_runner = fixture(td, mode)
    r = run(
        "tools/demiurge_rex_lifecycle.py",
        "register",
        "--spec", td / "spec.json",
        "--nexus-policy", td / "policy.json",
        "--candidate-root", candidate_root,
        "--admissions-dir", admissions,
        "--registry-dir", registry,
    )
    assert r.returncode == 0, r.stderr
    return candidate_root, admissions, registry, runs, fake_runner


def test_scheduled_lifecycle_register_execute_and_slot_dedupe():
    with tempfile.TemporaryDirectory() as raw:
        td = pathlib.Path(raw)
        candidate_root, admissions, registry, runs, fake_runner = register(td, "SCHEDULED")
        binding = json.loads((registry / "organ.json").read_text())
        assert binding["state"] == "LIFECYCLE_ADMITTED_EXACT_SHA"
        assert binding["mode"] == "SCHEDULED"
        assert binding["interval_minutes"] == 60
        args = [
            "tools/demiurge_rex_lifecycle.py", "execute",
            "--trigger", "schedule",
            "--now-epoch", "3600",
            "--workflow-run-id", "101",
            "--nexus-policy", td / "policy.json",
            "--candidate-root", candidate_root,
            "--admissions-dir", admissions,
            "--registry-dir", registry,
            "--runs-dir", runs,
            "--runner", fake_runner,
        ]
        first = run(*args)
        assert first.returncode == 0, first.stderr
        summary = json.loads(first.stdout)
        assert len(summary["executed"]) == 1
        receipt = next((runs / "organ").glob("*.json"))
        obj = json.loads(receipt.read_text())
        assert obj["state"] == "EXECUTED_EXACT_SHA"
        assert obj["authority_delta"] == 0
        assert obj["privacy"] == "INPUT_AND_RESULT_HASHED_NOT_PERSISTED"
        second = run(*args)
        assert second.returncode == 0, second.stderr
        summary2 = json.loads(second.stdout)
        assert len(summary2["executed"]) == 0
        assert summary2["skipped"][0]["reason"] == "dedupe"


def test_source_change_revokes_lifecycle_execution():
    with tempfile.TemporaryDirectory() as raw:
        td = pathlib.Path(raw)
        candidate_root, admissions, registry, runs, fake_runner = register(td, "SCHEDULED")
        (candidate_root / "organ" / "module.py").write_text(
            "async def run(context):\n    return {'status':'CHANGED','authority_delta':0}\n",
            encoding="utf-8",
        )
        r = run(
            "tools/demiurge_rex_lifecycle.py", "execute",
            "--trigger", "schedule",
            "--now-epoch", "3600",
            "--nexus-policy", td / "policy.json",
            "--candidate-root", candidate_root,
            "--admissions-dir", admissions,
            "--registry-dir", registry,
            "--runs-dir", runs,
            "--runner", fake_runner,
        )
        assert r.returncode != 0
        assert "LIFECYCLE_EXACT_SHA_GUARD_FAIL" in (r.stdout + r.stderr)


def test_event_driven_requires_key_and_dedupes_event_id():
    with tempfile.TemporaryDirectory() as raw:
        td = pathlib.Path(raw)
        candidate_root, admissions, registry, runs, fake_runner = register(td, "EVENT_DRIVEN")
        jdump(td / "event.json", {"value": 7})
        args = [
            "tools/demiurge_rex_lifecycle.py", "execute",
            "--trigger", "event",
            "--event-key", "janus.test",
            "--event-id", "evt-001",
            "--event-payload", td / "event.json",
            "--nexus-policy", td / "policy.json",
            "--candidate-root", candidate_root,
            "--admissions-dir", admissions,
            "--registry-dir", registry,
            "--runs-dir", runs,
            "--runner", fake_runner,
        ]
        first = run(*args)
        assert first.returncode == 0, first.stderr
        second = run(*args)
        assert second.returncode == 0, second.stderr
        assert json.loads(second.stdout)["skipped"][0]["reason"] == "dedupe"


def test_on_demand_only_selects_on_demand_binding():
    with tempfile.TemporaryDirectory() as raw:
        td = pathlib.Path(raw)
        candidate_root, admissions, registry, runs, fake_runner = register(td, "ON_DEMAND")
        r = run(
            "tools/demiurge_rex_lifecycle.py", "execute",
            "--trigger", "on_demand",
            "--module-id", "organ",
            "--workflow-run-id", "777",
            "--nexus-policy", td / "policy.json",
            "--candidate-root", candidate_root,
            "--admissions-dir", admissions,
            "--registry-dir", registry,
            "--runs-dir", runs,
            "--runner", fake_runner,
        )
        assert r.returncode == 0, r.stderr
        assert len(json.loads(r.stdout)["executed"]) == 1
