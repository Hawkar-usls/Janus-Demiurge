import json
from pathlib import Path

from tools.activator_readonly_execution import (
    TARGET,
    canonical_hash,
    execute,
    orientation_snapshot,
    verify_execution_receipt,
)


def valid_grant():
    grant = {
        "schema": "janus.activator.execution_grant.v0.7",
        "grant_id": "",
        "created_at": 1.0,
        "parent_grant_hash": None,
        "authenticated_final_receipt_hash": "a" * 64,
        "finalization_id": "ackf-" + "b" * 64,
        "packet_id": "dsp-" + "c" * 64,
        "packet_hash": "d" * 64,
        "target_organ": TARGET,
        "operation": "READ_ONLY_ORIENTATION_SNAPSHOT",
        "risk_class": "R0_INTERNAL_READ_ONLY_ORIENTATION",
        "execution_scope": "TARGET_REPOSITORY_LOCAL_READ_ONLY_METADATA",
        "target_execution_authorized": True,
        "repository_write_authorized": False,
        "network_access_authorized": False,
        "model_access_authorized": False,
        "command_authority_granted": False,
        "claim_authority_granted": False,
        "scientific_evidence_authority_granted": False,
        "external_effect_authorized": False,
        "physical_runtime_effect_authorized": False,
        "terminal": "EXECUTION_GRANT_ISSUED_READ_ONLY_ORIENTATION",
        "reasons": ["unit-test bounded grant"],
    }
    grant["grant_id"] = "xg-" + canonical_hash({
        "authenticated_final_receipt_hash": grant["authenticated_final_receipt_hash"],
        "packet_id": grant["packet_id"],
        "packet_hash": grant["packet_hash"],
        "target_organ": grant["target_organ"],
        "operation": grant["operation"],
    })
    grant["grant_hash"] = canonical_hash(grant)
    return grant


def make_repo(tmp_path: Path):
    (tmp_path / ".github" / "agents").mkdir(parents=True)
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "protocol").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / ".github" / "agents" / "a.agent.md").write_text("agent\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "a.yml").write_text("name: a\n", encoding="utf-8")
    (tmp_path / "protocol" / "DEMIURGE_SPIRAL_EVOLUTION-v1.json").write_text('{"x":1}\n', encoding="utf-8")
    (tmp_path / "tests" / "test_a.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "tools" / "a.py").write_text("x=1\n", encoding="utf-8")


def file_state(root: Path):
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_valid_grant_performs_only_readonly_orientation(tmp_path):
    make_repo(tmp_path)
    before = file_state(tmp_path)

    result = execute(
        valid_grant(),
        repo_root=tmp_path,
        target_head_sha="1" * 40,
        source_actor="Hawkar-usls",
    )

    receipt = result["receipt"]
    snapshot = result["snapshot"]
    assert receipt["terminal"] == "EXECUTED_READ_ONLY_ORIENTATION"
    assert receipt["execution_authorized"] is True
    assert receipt["execution_performed"] is True
    assert receipt["repository_write_performed"] is False
    assert receipt["target_process_network_access"] is False
    assert receipt["model_access"] is False
    assert receipt["claim_authority_granted"] is False
    assert receipt["scientific_evidence_authority_granted"] is False
    assert receipt["external_effect_performed"] is False
    assert verify_execution_receipt(receipt) is True
    assert snapshot["counts"]["agent_manifests"] == 1
    assert snapshot["counts"]["workflows"] == 1
    assert snapshot["target_head_sha"] == "1" * 40
    assert file_state(tmp_path) == before


def test_untrusted_actor_is_blocked_before_execution(tmp_path):
    make_repo(tmp_path)
    result = execute(valid_grant(), repo_root=tmp_path, target_head_sha="2" * 40, source_actor="someone-else")
    assert result["snapshot"] is None
    assert result["receipt"]["terminal"] == "EXECUTION_BLOCKED_UNTRUSTED_GITHUB_ACTOR"
    assert result["receipt"]["execution_performed"] is False
    assert verify_execution_receipt(result["receipt"]) is True


def test_tampered_grant_is_blocked(tmp_path):
    make_repo(tmp_path)
    grant = valid_grant()
    grant["operation"] = "EXECUTE_AND_WRITE"
    result = execute(grant, repo_root=tmp_path, target_head_sha="3" * 40, source_actor="Hawkar-usls")
    assert result["snapshot"] is None
    assert result["receipt"]["terminal"] == "EXECUTION_BLOCKED_INVALID_GRANT"
    assert result["receipt"]["execution_performed"] is False


def test_resealed_authority_escalation_is_still_blocked(tmp_path):
    make_repo(tmp_path)
    grant = valid_grant()
    grant.pop("grant_hash")
    grant["network_access_authorized"] = True
    grant["grant_hash"] = canonical_hash(grant)
    result = execute(grant, repo_root=tmp_path, target_head_sha="4" * 40, source_actor="Hawkar-usls")
    assert result["receipt"]["terminal"] == "EXECUTION_BLOCKED_INVALID_GRANT"
    assert result["receipt"]["target_process_network_access"] is False


def test_orientation_snapshot_is_deterministic_for_same_checkout_and_head(tmp_path):
    make_repo(tmp_path)
    a = orientation_snapshot(tmp_path, "5" * 40)
    b = orientation_snapshot(tmp_path, "5" * 40)
    assert a == b
    assert a["snapshot_hash"] == b["snapshot_hash"]


def test_snapshot_changes_when_selected_control_file_changes(tmp_path):
    make_repo(tmp_path)
    first = orientation_snapshot(tmp_path, "6" * 40)
    path = tmp_path / "protocol" / "DEMIURGE_SPIRAL_EVOLUTION-v1.json"
    path.write_text('{"x":2}\n', encoding="utf-8")
    second = orientation_snapshot(tmp_path, "6" * 40)
    assert first["snapshot_hash"] != second["snapshot_hash"]
