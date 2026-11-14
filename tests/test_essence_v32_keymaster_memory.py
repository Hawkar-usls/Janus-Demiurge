"""ESSENCE v3.2 Keymaster + memory: real-source and adversarial stdlib tests."""
import copy
import json
import unittest
from pathlib import Path

from tools import essence_v32_keymaster_memory as m


class KeymasterMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.original = {}
        cls.hashes = {}
        for role, path in m.PATHS.items():
            cls.original[role], cls.hashes[role] = m.checked_json(cls.root, path)
        cls.source_commit = "a" * 40

    def setUp(self):
        self.keymaster = copy.deepcopy(self.original["keymaster"])
        self.attribution = copy.deepcopy(self.original["attribution"])
        self.outcomes = copy.deepcopy(self.original["outcomes"])

    def evaluate(self, previous=None, *, hashes=None, commit=None):
        return m.evaluate(
            self.keymaster, self.attribution, self.outcomes,
            previous or m.empty_state(),
            source_hashes=hashes or self.hashes,
            source_commit=commit or self.source_commit)

    def test_real_demiurge_inputs_replay_and_never_escalate(self):
        new, report = self.evaluate()
        self.assertEqual(report["microkernels"][0]["source_contributors"], 8)
        self.assertEqual(report["microkernels"][0]["unresolved_contributors"], 8)
        self.assertEqual(report["microkernels"][1]["lesson_count"], 1)
        self.assertEqual(report["microkernels"][0]["state"], "HOLD_UNRESOLVED_KEYMASTER_ATTRIBUTION")
        self.assertEqual(report["memory_generations_recorded"], 1)
        self.assertTrue(m.verify_state(new))
        self.assertEqual(report["receipt_sha256"], m.seal({
            k: v for k, v in report.items() if k != "receipt_sha256"
        }))
        for flag in ("keymaster_can_touch_secrets", "keymaster_can_control_hardware",
                     "keymaster_can_remove_contributors", "historical_python_executed",
                     "raw_memory_text_exported", "scientific_generalization_proven",
                     "neural_weights_changed", "automatic_module_activation",
                     "automatic_production_promotion", "training_data_modified"):
            self.assertIs(report[flag], False)

    def test_no_duplicate_memories_for_same_unchanged_source(self):
        first, report = self.evaluate()
        second, duplicate = self.evaluate(first)
        self.assertEqual(second, first)
        self.assertFalse(duplicate["memory_added_new_evidence"])
        self.assertEqual(duplicate["memory_generations_recorded"], 1)

    def test_one_new_source_snapshot_appends_hash_linked_lesson(self):
        first, _ = self.evaluate()
        hashes = dict(self.hashes, outcomes="a" * 64)
        second, report = self.evaluate(first, hashes=hashes, commit="b" * 40)
        self.assertTrue(report["memory_added_new_evidence"])
        self.assertEqual(second["history"][1]["previous_sha256"],
                         first["history"][0]["receipt_sha256"])
        self.assertEqual(len(second["history"]), 2)
        m.verify_state(second)

    def test_repeated_old_fingerprint_is_not_relearned(self):
        first, _ = self.evaluate()
        second, _ = self.evaluate(first, hashes=dict(self.hashes, keymaster="f" * 64))
        third, receipt = self.evaluate(second, hashes=self.hashes)
        self.assertEqual(len(third["history"]), 2)
        self.assertFalse(receipt["memory_added_new_evidence"])

    def test_tampered_memory_state_is_rejected(self):
        state, _ = self.evaluate()
        state["history"][0]["donor_count"] = 9
        with self.assertRaisesRegex(ValueError, "TAMPERED|CHAIN_BROKEN"):
            self.evaluate(state)

    def test_resealed_tampered_memory_chain_is_rejected(self):
        state, _ = self.evaluate()
        state["history"][0]["training_admission"] = True
        state["history"][0]["receipt_sha256"] = m.seal({
            k:v for k,v in state["history"][0].items() if k != "receipt_sha256"})
        state["state_sha256"] = m.seal({k:v for k,v in state.items() if k != "state_sha256"})
        with self.assertRaisesRegex(ValueError, "AUTHORITY"):
            self.evaluate(state)

    def test_keymaster_missing_one_donor_fails_closed(self):
        self.keymaster["contributors"].pop()
        self.keymaster["contributor_count"] = 7
        with self.assertRaisesRegex(ValueError, "KEYMASTER"):
            self.evaluate()

    def test_keymaster_holdout_and_secret_firewalls(self):
        self.keymaster["learning"]["adaptive_holdout_inclusion"] = True
        with self.assertRaisesRegex(ValueError, "FIREWALL"):
            self.evaluate()
        self.keymaster = copy.deepcopy(self.original["keymaster"])
        self.keymaster["selection"]["secretish_paths_allowed"] = True
        with self.assertRaisesRegex(ValueError, "FIREWALL"):
            self.evaluate()

    def test_keymaster_duplicate_donor_rejected(self):
        self.keymaster["contributors"][0]["id"] = self.keymaster["contributors"][1]["id"]
        with self.assertRaisesRegex(ValueError, "KEYMASTER"):
            self.evaluate()

    def test_r2_attribution_binding_rejects_identity_drift(self):
        self.attribution["attribution"][0]["repository"] = "Hawkar-usls/Fake"
        with self.assertRaisesRegex(ValueError, "BINDING"):
            self.evaluate()

    def test_r2_attribution_no_world_truth_promotion(self):
        self.attribution["claim_ceiling"]["r2_class_is_world_truth"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY"):
            self.evaluate()

    def test_r2_unrecognized_signal_fails_closed(self):
        self.attribution["attribution"][0]["class"] = "P_NP_SOLVED"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_CLASS"):
            self.evaluate()

    def test_outcome_negative_evidence_from_silence_rejected(self):
        self.outcomes["policy"]["silence_is_negative_evidence"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY"):
            self.evaluate()

    def test_outcome_positive_without_local_verifier_is_not_learned(self):
        self.outcomes["records"][0]["terminal_authority"] = "UNVERIFIED_MODEL"
        self.outcomes["records"][0]["record_sha256"] = m.seal({
            k:v for k,v in self.outcomes["records"][0].items() if k!="record_sha256"})
        self.outcomes["training_eligible_count"] = 0
        _, report = self.evaluate()
        self.assertEqual(report["microkernels"][1]["lesson_count"], 0)
        self.assertFalse(report["neural_weights_changed"])

    def test_outcome_record_tamper_fails_closed(self):
        self.outcomes["records"][0]["target_repository"] = "Hawkar-usls/Fake"
        with self.assertRaisesRegex(ValueError, "DIGEST"):
            self.evaluate()

    def test_source_binding_requires_sha256_and_pin(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_COMMIT"):
            self.evaluate(commit="main")
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH"):
            self.evaluate(hashes={"keymaster": "x", "attribution": "a"*64, "outcomes": "b"*64})

    def test_git_source_path_bounded_and_files_are_verified(self):
        for role, path in m.PATHS.items():
            _, checked = m.checked_json(self.root, path)
            self.assertEqual(checked, self.hashes[role])


if __name__ == "__main__":
    unittest.main()
