from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from janus_model.outcome_memory import _record_sha, _validate_previous, sealed_proposal_bytes, validate_pair


class JanusOutcomeMemoryTests(unittest.TestCase):
    def _pair(self, root: Path, native_model_selected: bool) -> tuple[Path, Path]:
        proposal = {
            "schema": "janus.patch_proposal.v1",
            "proposal_id": "jpatch-test-001",
            "decision_id": "jnd-test-001",
            "status": "PROPOSED",
            "create_only": True,
            "native_model_selected": native_model_selected,
            "risk_lane": "LOW",
            "target": {
                "repository": "Hawkar-usls/Janus-Demiurge",
                "expected_target_commit": "a" * 40,
            },
            "verification_profile": "DEMIURGE_EXTENSION_STATIC_TEST",
            "files": [],
        }
        proposal_path = root / "proposal.json"
        proposal_path.write_text(json.dumps(proposal, sort_keys=True) + "\n", encoding="utf-8")
        proposal_sha = hashlib.sha256(sealed_proposal_bytes(proposal)).hexdigest()
        receipt = {
            "schema": "janus.module_actuator.receipt.v1",
            "proposal_id": proposal["proposal_id"],
            "status": "VERIFY_PASS",
            "target_repository": "Hawkar-usls/Janus-Demiurge",
            "base_commit": "a" * 40,
            "patch_commit": "b" * 40,
            "branch": "janus-self/jpatch-test-001",
            "proposal_sha256": proposal_sha,
            "verification_profile": "DEMIURGE_EXTENSION_STATIC_TEST",
            "autonomous_merge": False,
            "main_mutated": False,
            "terminal_authority": "TARGET_LOCAL_VERIFIER",
        }
        receipt_path = root / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
        return proposal_path, receipt_path

    def test_only_native_selected_clean_lineage_verify_pass_is_training_eligible(self) -> None:
        clean_lineage = {
            "patch_diff_exact": True,
            "patch_parent_exact": True,
            "receipt_parent_exact": True,
            "receipt_diff_exact": True,
            "gitlink_count": 0,
            "proposal_file_count": 1,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_path, receipt_path = self._pair(root, native_model_selected=False)
            with patch("janus_model.outcome_memory._validate_checkout_lineage", return_value=clean_lineage):
                canary = validate_pair(proposal_path, receipt_path, "c" * 40, "run-1", checkout=root)
            self.assertFalse(canary["training_eligible"])
            self.assertTrue(canary["lineage_verified"])

            proposal_path, receipt_path = self._pair(root, native_model_selected=True)
            without_lineage = validate_pair(proposal_path, receipt_path, "c" * 40, "run-1")
            self.assertFalse(without_lineage["training_eligible"])
            self.assertFalse(without_lineage["lineage_verified"])

            with patch("janus_model.outcome_memory._validate_checkout_lineage", return_value=clean_lineage):
                native = validate_pair(proposal_path, receipt_path, "c" * 40, "run-1", checkout=root)
            self.assertTrue(native["training_eligible"])
            self.assertTrue(native["lineage_verified"])
            self.assertFalse(native["truth_claim"])
            self.assertFalse(native["mutation_authority_granted"])

    def test_tampered_proposal_hash_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_path, receipt_path = self._pair(root, native_model_selected=True)
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
            proposal["files"] = [{"path": "unexpected"}]
            proposal_path.write_text(json.dumps(proposal, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "PROPOSAL_HASH_REJECTED"):
                validate_pair(proposal_path, receipt_path, "c" * 40, "run-1")

    def test_previous_memory_record_is_hash_bound_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_path, receipt_path = self._pair(root, native_model_selected=True)
            record = validate_pair(proposal_path, receipt_path, "c" * 40, "run-1")
            record["first_seen_run_id"] = "run-1"
            record["record_sha256"] = _record_sha(record)
            memory = {
                "schema": "janus.verified_outcome_memory.v1",
                "status": "VERIFIED_OUTCOME_MEMORY_READY",
                "policy": {
                    "silence_is_negative_evidence": False,
                    "only_target_local_verify_pass_is_positive_feedback": True,
                    "native_model_selected_required_for_training_prior": True,
                    "feedback_grants_mutation_authority": False,
                },
                "records": [record],
            }
            path = root / "memory.json"
            path.write_text(json.dumps(memory), encoding="utf-8")
            loaded = _validate_previous(path)
            self.assertEqual(loaded[0]["first_seen_run_id"], "run-1")
            memory["records"][0]["truth_claim"] = True
            path.write_text(json.dumps(memory), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "RECORD_HASH_REJECTED"):
                _validate_previous(path)


if __name__ == "__main__":
    unittest.main()
