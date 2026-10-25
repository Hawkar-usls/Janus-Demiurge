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


def test_need_discovery_refuses_summary_of_summary_family():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo, family="rex_probe_ledger_summary", count=3)
        r = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", ROOT / "rex/need_discovery_policy.json",
            "--repo-root", repo,
        )
        assert r.returncode == 0, r.stderr
        summary = json.loads(r.stdout)
        assert summary["proposal_count"] == 0
        assert any(row.get("reason") == "recursive_summary_family_refused" for row in summary["skipped"])
        assert not (repo / "rex/need_proposals/generated").exists()


def test_nexus_need_gate_independently_refuses_recursive_summary_proposal():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo, family="rex_probe_ledger_summary", count=3)

        permissive = json.loads((ROOT / "rex/need_discovery_policy.json").read_text(encoding="utf-8"))
        permissive["observation"]["refuse_family_suffixes"] = []
        permissive_path = repo / "permissive-discovery-policy.json"
        permissive_path.write_text(json.dumps(permissive) + "\n", encoding="utf-8")

        discover = run(
            "tools/demiurge_rex_need_discovery.py",
            "--policy", permissive_path,
            "--repo-root", repo,
        )
        assert discover.returncode == 0, discover.stderr
        assert json.loads(discover.stdout)["proposal_count"] == 1

        gate = run(
            "tools/nexus_rex_need_gate.py",
            "--policy", ROOT / "rex/need_gate_policy.json",
            "--repo-root", repo,
        )
        assert gate.returncode != 0
        assert "recursive summary family refused" in (gate.stdout + gate.stderr)
        assert not (repo / "rex/desires/approved").exists()


def discover_need(repo: pathlib.Path):
    result = run(
        "tools/demiurge_rex_need_discovery.py",
        "--policy", ROOT / "rex/need_discovery_policy.json",
        "--repo-root", repo,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def gate_need(repo: pathlib.Path):
    return run(
        "tools/nexus_rex_need_gate.py",
        "--policy", ROOT / "rex/need_gate_policy.json",
        "--repo-root", repo,
    )


def test_append_only_growth_is_durable_hold_not_automatic_admission():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo, count=3)
        discover_need(repo)
        seed_receipts(repo, count=4)  # historical proposal still pins three exact rows
        gate = gate_need(repo)
        assert gate.returncode == 0, gate.stderr
        result = json.loads(gate.stdout)
        assert result["status"] == "STALE_SNAPSHOTS_HELD"
        assert result["stale_snapshot_holds"] == 1
        hold = result["skipped"][0]
        assert hold["reason"] == "STALE_SNAPSHOT_GROWTH_HOLD"
        assert hold["snapshot_record_count"] == 3
        assert hold["current_record_count"] == 4
        assert hold["verified_reference_count"] == 3
        assert result["approved_this_run"] == 0
        assert not (repo / "rex/desires/approved").exists()
        receipt_path = repo / result["stale_snapshot_receipt"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        assert receipt["verification_scope"] == "PINNED_REFERENCES_ONLY__NOT_FULL_LEDGER_ANCESTRY"
        assert receipt["automatically_approved_stale_proposals"] == 0
        original = receipt_path.read_bytes()
        assert gate_need(repo).returncode == 0
        assert receipt_path.read_bytes() == original
        assert len(list(receipt_path.parent.glob("REX-STALE-*.json"))) == 1


def test_stale_growth_with_missing_or_tampered_original_ref_hard_fails():
    for tamper in (False, True):
        with tempfile.TemporaryDirectory() as td:
            repo = pathlib.Path(td)
            family = seed_receipts(repo, count=3)
            discover_need(repo)
            seed_receipts(repo, count=5)
            if tamper:
                target = family / "r0.json"
                obj = json.loads(target.read_text())
                obj["result_status"] = "FORGED"
                target.write_text(json.dumps(obj) + "\n", encoding="utf-8")
            else:
                (family / "r0.json").unlink()
            gate = gate_need(repo)
            assert gate.returncode != 0
            assert "evidence SHA mismatch" in (gate.stdout + gate.stderr)
            assert not (repo / "rex/need_gate_observations").exists()
            assert not (repo / "rex/desires/approved").exists()


def test_ledger_shrinkage_is_hard_integrity_failure():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        family = seed_receipts(repo, count=3)
        discover_need(repo)
        (family / "r2.json").unlink()
        gate = gate_need(repo)
        assert gate.returncode != 0
        assert "evidence count regression" in (gate.stdout + gate.stderr)
        assert not (repo / "rex/need_gate_observations").exists()
        assert not (repo / "rex/desires/approved").exists()


def test_stale_family_does_not_block_independent_fresh_proposal():
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td)
        seed_receipts(repo, family="rex_old", count=3)
        discover_need(repo)
        old_proposal_path = next((repo / "rex/need_proposals/generated").glob("*.json"))
        old_snapshot = old_proposal_path.read_bytes()
        seed_receipts(repo, family="rex_old", count=4)
        seed_receipts(repo, family="rex_new", count=3)
        discover_need(repo)
        old_proposal_path.write_bytes(old_snapshot)
        gate = gate_need(repo)
        assert gate.returncode == 0, gate.stderr
        result = json.loads(gate.stdout)
        assert result["stale_snapshot_holds"] == 1
        assert result["approved_this_run"] == 1
        admitted = list((repo / "rex/need_admissions").glob("*.json"))
        assert len(admitted) == 1
        admission = json.loads(admitted[0].read_text())
        assert admission["module_id"] == "rex_new_ledger_summary"
        assert admission["grants_code_admission"] is False
        assert admission["grants_lifecycle"] is False
        assert admission["authority_delta"] == 0
        assert any(x["reason"] == "STALE_SNAPSHOT_GROWTH_HOLD" for x in result["skipped"])
