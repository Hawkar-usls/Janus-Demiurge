#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate Janus-Demiurge's bounded Git Habitat admission.

The validator is intentionally local/read-only. It does not contact GitHub,
execute Demiurge runtime modules, dispatch workflows, or mutate source files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class HabitatAdmissionError(RuntimeError):
    pass


def _load_unique_json(path: Path) -> dict[str, Any]:
    def unique_pairs(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise HabitatAdmissionError(f"duplicate JSON key {key!r} in {path}")
            out[key] = value
        return out

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)
    except (OSError, json.JSONDecodeError) as exc:
        raise HabitatAdmissionError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HabitatAdmissionError(f"{path} must contain a JSON object")
    return value


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    link = _load_unique_json(root / ".janus" / "HABITAT_LINK.json")
    admission = _load_unique_json(root / ".janus" / "HABITAT_ADMISSION.json")
    status = _load_unique_json(root / "PROJECT_STATUS.json")

    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(
        link.get("schema") == "janus.genesis.git_habitat.repository_link.v1",
        "link schema mismatch",
    )
    require(link.get("source_repository") == "SELF", "link source must remain SELF")
    target = link.get("target") if isinstance(link.get("target"), dict) else {}
    require(target.get("repository") == "Hawkar-usls/Janus_Genesis", "wrong Habitat repository")
    require(target.get("branch") == "janus/habitat", "wrong Habitat branch")
    require(target.get("room") == "repositories", "wrong Habitat room")
    require(link.get("mode") == "REFERENCE_AND_HANDOFF_ONLY", "link mode widened")
    require(link.get("source_history_remains_authoritative") is True, "source authority lost")
    require(link.get("habitat_command_authority_granted") is False, "Habitat command authority granted")
    require(link.get("write_back_default") == "DENY", "write-back default must be DENY")
    require(link.get("write_back_requires_explicit_human_authorization") is True, "human authorization guard missing")
    require(link.get("issue_or_pr_text_is_command") is False, "issue/PR text promoted to command")
    require(link.get("workflow_status_is_permission") is False, "workflow status promoted to permission")
    require(link.get("private_content_may_be_mirrored_to_public_habitat") is False, "private mirroring widened")
    require(link.get("credentials_may_be_persisted_in_habitat") is False, "credential persistence widened")

    require(
        admission.get("schema") == "janus.genesis.git_habitat.repository_admission.v1",
        "admission schema mismatch",
    )
    source = admission.get("source") if isinstance(admission.get("source"), dict) else {}
    require(source.get("repository") == "Hawkar-usls/Janus-Demiurge", "admission source mismatch")
    require(source.get("repository_id") == "1188744620", "repository id mismatch")
    require(source.get("admission_base_sha") == "98974d9c02637cb471ef73f5b62cf81797895a44", "admission base SHA mismatch")
    require(source.get("project_maturity") == "LEGACY", "maturity widened")
    require(source.get("portfolio_class") == "legacy_experimental_sandbox", "portfolio class widened")
    require(source.get("completion_status") == "ARCHIVAL", "archival boundary widened")

    habitat = admission.get("habitat") if isinstance(admission.get("habitat"), dict) else {}
    require(habitat.get("repository") == target.get("repository"), "admission/link Habitat repository mismatch")
    require(habitat.get("branch") == target.get("branch"), "admission/link Habitat branch mismatch")
    require(habitat.get("room") == target.get("room"), "admission/link Habitat room mismatch")
    require(habitat.get("coordination_issue") == "Hawkar-usls/Janus_Genesis#102", "coordination bus mismatch")

    existing_link = admission.get("existing_link") if isinstance(admission.get("existing_link"), dict) else {}
    require(existing_link.get("blob_sha") == "0c1bfef793be483048a3249a24fa61fb38ee0e3c", "historical Habitat link blob pin changed")
    require(existing_link.get("write_back_default") == "DENY", "admission link write-back widened")

    role = admission.get("habitat_role") if isinstance(admission.get("habitat_role"), dict) else {}
    require(role.get("role_id") == "LEGACY_EXPERIMENTAL_SANDBOX_REFERENCE", "unexpected Habitat role")
    for key in (
        "flagship_research",
        "runtime_activation_implied",
        "scientific_validation_implied",
        "canonical_project_truth",
        "command_authority",
        "permission_authority",
    ):
        require(role.get(key) is False, f"role boundary {key} must remain false")

    denied = set(admission.get("denied_by_default", []))
    for required in (
        "AUTOMATIC_SOURCE_WRITE_BACK",
        "AUTOMATIC_RUNTIME_EXECUTION",
        "AUTOMATIC_MODULE_ACTIVATION",
        "AUTOMATIC_NETWORK_EGRESS",
        "AUTOMATIC_MEMORY_IMPORT",
        "AUTOMATIC_POWER_EXECUTOR_REGISTRATION",
        "AUTOMATIC_PROMOTION_TO_CANONICAL_TRUTH",
    ):
        require(required in denied, f"missing deny guard: {required}")

    boundary = admission.get("memory_power_boundary") if isinstance(admission.get("memory_power_boundary"), dict) else {}
    require(boundary.get("direct_write_to_hippocampus_journal") is False, "direct Hippocampus write admitted")
    require(boundary.get("direct_write_to_cortex_store") is False, "direct Cortex write admitted")
    require(boundary.get("direct_power_executor_registration") is False, "direct Power executor admission widened")
    require(boundary.get("historical_demiurge_output_is_independent_evidence") is False, "historical output promoted to independent evidence")
    require(boundary.get("requires_separate_admission_for_runtime_use") is True, "separate runtime admission guard missing")

    history = admission.get("history_preservation") if isinstance(admission.get("history_preservation"), dict) else {}
    require(history.get("runtime_source_mutation_required_for_habitat_admission") is False, "runtime source mutation unexpectedly required")
    require(history.get("existing_historical_files_deleted") is False, "history deletion claimed")
    require(history.get("existing_historical_files_rewritten") is False, "history rewrite claimed")
    require(history.get("source_history_remains_authoritative") is True, "source history authority lost")

    require(status.get("project") == "Janus Demiurge", "PROJECT_STATUS project mismatch")
    require(status.get("portfolio_class") == "legacy_experimental_sandbox", "PROJECT_STATUS portfolio class widened")
    require(status.get("maturity") == "LEGACY", "PROJECT_STATUS maturity widened")
    require(status.get("completion_status") == "ARCHIVAL", "PROJECT_STATUS archival status widened")
    require(status.get("flagship_research") is False, "PROJECT_STATUS flagship boundary widened")
    not_established = set(status.get("not_established", []))
    for item in (
        "future-event prediction",
        "precognition",
        "physical retrocausality",
        "artificial general intelligence",
        "validated scientific result",
    ):
        require(item in not_established, f"PROJECT_STATUS lost non-claim: {item}")

    require(admission.get("source_writeback") is False, "source_writeback must be false")
    require(admission.get("source_delete") is False, "source_delete must be false")
    require(admission.get("history_rewrite") is False, "history_rewrite must be false")
    require(admission.get("authority_delta") == 0, "authority_delta must be zero")
    require(admission.get("mass_effect_budget_delta") == 0, "mass_effect_budget_delta must be zero")

    if errors:
        raise HabitatAdmissionError("; ".join(errors))

    return {
        "schema": "janus.demiurge.habitat_validation_receipt.v1",
        "result": "PASS",
        "repository": "Hawkar-usls/Janus-Demiurge",
        "admission_base_sha": source["admission_base_sha"],
        "habitat_target": f"{habitat['repository']}:{habitat['branch']}/{habitat['room']}",
        "role": role["role_id"],
        "runtime_activation": False,
        "write_back": False,
        "authority_delta": 0,
        "mass_effect_budget_delta": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        receipt = validate(args.root)
    except HabitatAdmissionError as exc:
        if args.json:
            print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        else:
            print(f"HABITAT_ADMISSION: FAIL: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    else:
        print("HABITAT_ADMISSION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
