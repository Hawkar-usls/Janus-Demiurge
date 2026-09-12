from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args):
    return subprocess.run([PYTHON, *map(str, args)], cwd=ROOT, text=True, capture_output=True)


def seed_receipts(root: pathlib.Path, family: str = "rex_probe", count: int = 3) -> pathlib.Path:
    family_dir = root / "rex/lifecycle_runs" / family
    family_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(count):
        obj = {
            "schema": "janus.rex.lifecycle_run_receipt.v1",
            "module_id": family,
            "state": "EXECUTED_EXACT_SHA",
            "result_status": "ALIVE",
            "source_sha256": f"{idx + 1:064x}",
            "trigger": "schedule",
            "mode": "SCHEDULED",
            "authority_delta": 0,
        }
        (family_dir / f"r{idx}.json").write_text(json.dumps(obj) + "\n", encoding="utf-8")
    return family_dir


def test_need_discovery_proposes_bounded_ledger_summary():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo)
        r = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", ROOT / "rex/need_discovery_policy.json",
            "--repo-root", repo,
        )
        assert r.returncode == 0, r.stderr
        summary = json.loads(r.stdout)
        assert summary["status"] == "PASS"
        assert summary["proposal_count"] == 1
        proposal_path = next((repo / "rex/need_proposals/generated").glob("*.json"))
        proposal = json.loads(proposal_path.read_text())
        assert proposal["schema"] == "janus.rex.desire_proposal.v1"
        assert proposal["state"] == "PROPOSED_ONLY__NEXUS_NEED_GATE_REQUIRED"
        assert proposal["need_kind"] == "ACCUMULATING_JSON_LEDGER"
        assert proposal["evidence"]["record_count"] == 3
        assert proposal["suggested_desire"]["module_id"] == "rex_probe_ledger_summary"
        assert proposal["suggested_desire"]["template"] == "ledger_summary"
        assert proposal["suggested_desire"]["lifecycle"]["mode"] == "SCHEDULED"
        assert proposal["suggested_desire"]["lifecycle"]["interval_minutes"] == 360
        assert len(proposal["suggested_desire"]["lifecycle"]["input"]["rows"]) == 3
        assert proposal["authority"]["proposal_is_admission"] is False
        assert proposal["authority"]["authority_delta"] == 0


def test_nexus_need_gate_approves_desire_only_not_code_admission():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo)
        discover = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", ROOT / "rex/need_discovery_policy.json",
            "--repo-root", repo,
        )
        assert discover.returncode == 0, discover.stderr
        gate = run(
            "tools/nexus_rex_need_gate.py",
            "--policy", ROOT / "rex/need_gate_policy.json",
            "--repo-root", repo,
        )
        assert gate.returncode == 0, gate.stderr
        result = json.loads(gate.stdout)
        assert result["approved_this_run"] == 1
        desire_path = next((repo / "rex/desires/approved").glob("*.json"))
        receipt_path = next((repo / "rex/need_admissions").glob("*.json"))
        desires = json.loads(desire_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        assert desires["schema"] == "janus.rex.desires.v1"
        assert desires["authority"]["desire_grants_admission"] is False
        assert desires["authority"]["desire_grants_lifecycle"] is False
        assert desires["authority"]["authority_delta"] == 0
        assert receipt["state"] == "NEXUS_NEED_APPROVED_FOR_DIRECTOR_ONLY"
        assert receipt["grants_code_admission"] is False
        assert receipt["grants_lifecycle"] is False
        assert receipt["director_required"] is True
        assert receipt["auditor_required"] is True
        assert receipt["exact_sha_nexus_admission_required"] is True
        assert receipt["authority_delta"] == 0


def test_nexus_need_gate_refuses_tampered_evidence_sha():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        family_dir = seed_receipts(repo)
        discover = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", ROOT / "rex/need_discovery_policy.json",
            "--repo-root", repo,
        )
        assert discover.returncode == 0, discover.stderr
        target = family_dir / "r0.json"
        obj = json.loads(target.read_text())
        obj["result_status"] = "MUTATED"
        target.write_text(json.dumps(obj) + "\n", encoding="utf-8")
        gate = run(
            "tools/nexus_rex_need_gate.py",
            "--policy", ROOT / "rex/need_gate_policy.json",
            "--repo-root", repo,
        )
        assert gate.returncode != 0
        assert "SHA mismatch" in (gate.stdout + gate.stderr)


def test_need_discovery_does_not_repropose_existing_organ():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo)
        existing = repo / "rex/specs/generated/rex_probe_ledger_summary.json"
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_text("{}\n", encoding="utf-8")
        r = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", ROOT / "rex/need_discovery_policy.json",
            "--repo-root", repo,
        )
        assert r.returncode == 0, r.stderr
        summary = json.loads(r.stdout)
        assert summary["proposal_count"] == 0
        assert any(row.get("reason") == "summary_module_already_exists" for row in summary["skipped"])
