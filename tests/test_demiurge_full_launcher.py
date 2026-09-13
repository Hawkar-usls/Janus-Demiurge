from __future__ import annotations

import importlib.util
import json
import pathlib
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("demiurge_full_launcher", ROOT / "tools/demiurge_full_launcher.py")
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def policy():
    return json.loads((ROOT / "demiurge/DEMIURGE_LAUNCHER_POLICY.json").read_text(encoding="utf-8"))


def write(path: pathlib.Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discovery_launches_every_active_manual_workflow_but_never_self():
    with tempfile.TemporaryDirectory() as td:
        wf = pathlib.Path(td) / ".github/workflows"
        write(wf / "a.yml", "name: A\non:\n  workflow_dispatch:\n")
        write(wf / "b.yml", "name: B\non:\n  schedule:\n    - cron: '0 * * * *'\n")
        write(wf / "janus-demiurge-full-launcher.yml", "name: Launcher\non:\n  workflow_dispatch:\n")
        active = [
            {"path": ".github/workflows/a.yml", "name": "A", "state": "active"},
            {"path": ".github/workflows/b.yml", "name": "B", "state": "active"},
            {"path": ".github/workflows/janus-demiurge-full-launcher.yml", "name": "Launcher", "state": "active"},
        ]
        receipt, rc = mod.run_launcher(
            policy=policy(),
            repo="Hawkar-usls/Janus-Demiurge",
            source_sha="a" * 40,
            workflow_dir=wf,
            active_rows=active,
            dry_run=True,
        )
        assert rc == 0
        assert receipt["manual_active_launchable"] == 1
        assert receipt["planned_count"] == 1
        assert receipt["dispatches"][0]["file"] == "a.yml"
        reasons = {x.get("reason") for x in receipt["passive_or_refused"]}
        assert "self_workflow_refused" in reasons
        assert "no_workflow_dispatch__passive_or_event_driven" in reasons


def test_priority_and_rex_target_sha_are_bound_to_source_commit():
    with tempfile.TemporaryDirectory() as td:
        wf = pathlib.Path(td) / ".github/workflows"
        write(wf / "zzz.yml", "name: Z\non:\n  workflow_dispatch:\n")
        write(
            wf / "janus-rex-lifecycle.yml",
            "name: Rex Lifecycle\non:\n  workflow_dispatch:\n    inputs:\n      target_sha:\n        required: false\n      trigger_mode:\n        default: on_demand\n",
        )
        active = [
            {"path": ".github/workflows/zzz.yml", "name": "Z", "state": "active"},
            {"path": ".github/workflows/janus-rex-lifecycle.yml", "name": "Rex Lifecycle", "state": "active"},
        ]
        sha = "b" * 40
        receipt, rc = mod.run_launcher(
            policy=policy(), repo="Hawkar-usls/Janus-Demiurge", source_sha=sha,
            workflow_dir=wf, active_rows=active, dry_run=True,
        )
        assert rc == 0
        assert receipt["dispatches"][0]["file"] == "janus-rex-lifecycle.yml"
        cmd = receipt["dispatches"][0]["command"]
        assert f"target_sha={sha}" in cmd
        assert "trigger_mode=schedule" in cmd
        assert receipt["authority_delta"] == 0


def test_disabled_manual_workflow_is_not_dispatched():
    with tempfile.TemporaryDirectory() as td:
        wf = pathlib.Path(td) / ".github/workflows"
        write(wf / "disabled.yml", "name: Disabled\non:\n  workflow_dispatch:\n")
        receipt, rc = mod.run_launcher(
            policy=policy(), repo="Hawkar-usls/Janus-Demiurge", source_sha="c" * 40,
            workflow_dir=wf,
            active_rows=[{"path": ".github/workflows/disabled.yml", "name": "Disabled", "state": "disabled_manually"}],
            dry_run=True,
        )
        assert rc == 0
        assert receipt["manual_active_launchable"] == 0
        assert receipt["passive_or_refused"][0]["reason"] == "workflow_state_disabled_manually"


def test_authority_firewall_refuses_launcher_self_crowning():
    bad = policy()
    bad["authority"]["launcher_grants_code_admission"] = True
    with tempfile.TemporaryDirectory() as td:
        wf = pathlib.Path(td) / ".github/workflows"
        write(wf / "a.yml", "name: A\non:\n  workflow_dispatch:\n")
        try:
            mod.run_launcher(
                policy=bad, repo="Hawkar-usls/Janus-Demiurge", source_sha="d" * 40,
                workflow_dir=wf,
                active_rows=[{"path": ".github/workflows/a.yml", "name": "A", "state": "active"}],
                dry_run=True,
            )
        except SystemExit as exc:
            assert "authority firewall" in str(exc)
        else:
            raise AssertionError("authority escalation must be refused")
