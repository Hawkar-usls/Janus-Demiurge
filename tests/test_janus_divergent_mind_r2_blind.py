"""R2 holdout seals arm labels but never asserts an independent verdict."""
from __future__ import annotations

from copy import deepcopy
import unittest

from janus_model.divergent_mind_r2 import capture
from janus_model.divergent_mind_r2_blind import (
    digest, load_contract, seal_trial, validate_contract, verify_reveal,
)
from test_janus_divergent_mind_r2 import MockReader, frozen


NONCE = "1c" * 32


class R2HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract()
        self.capture = capture(MockReader(frozen()), policy="read_fresh")
        self.assertEqual(self.capture["whole_blobs_verified"], 6)

    def test_public_only_seals_comparable_question_counts(self):
        public, private = seal_trial(self.capture, self.contract, nonce=NONCE)
        self.assertEqual(public["question_budget_per_arm"], 4)
        self.assertEqual(set(public["blinded_arms"]), {"arm_a", "arm_b"})
        self.assertTrue(all(len(q) == 4 for q in public["blinded_arms"].values()))
        self.assertNotIn("nonce", public)
        self.assertNotIn("mapping", public)
        self.assertNotIn("divergent_r1", str(public))
        self.assertEqual(public["scientific_status"], "OPEN")
        self.assertEqual(public["reviewer_assignment"], "OPEN__NO_INDEPENDENT_JUDGE_ASSIGNED")
        self.assertEqual(private["instruction"], "DO_NOT_DISCLOSE_MAPPING_UNTIL_EXTERNAL_RATINGS_FROZEN")

    def test_reveal_verifies_hashes_and_mapping(self):
        public, private = seal_trial(self.capture, self.contract, nonce=NONCE)
        self.assertTrue(verify_reveal(public, private, self.contract))
        self.assertEqual(public["submission_sha256"], digest({
            key: value for key, value in public.items() if key != "submission_sha256"}))

    def test_reveal_rejects_mutated_question(self):
        public, private = seal_trial(self.capture, self.contract, nonce=NONCE)
        public["blinded_arms"]["arm_a"][0]["question"] = "Altered after submission"
        self.assertFalse(verify_reveal(public, private, self.contract))

    def test_reveal_rejects_changed_private_mapping(self):
        public, private = seal_trial(self.capture, self.contract, nonce=NONCE)
        private["mapping"] = {"arm_a": "native_baseline", "arm_b": "native_baseline"}
        self.assertFalse(verify_reveal(public, private, self.contract))

    def test_reveal_rejects_bad_mapping_type(self):
        public, private = seal_trial(self.capture, self.contract, nonce=NONCE)
        private["mapping"] = "fake"
        self.assertFalse(verify_reveal(public, private, self.contract))

    def test_hold_and_unknown_cannot_be_sealed(self):
        for status in ("HOLD_SOURCE_HEAD_DRIFT", "UNKNOWN_NETWORK"):
            c = deepcopy(self.capture)
            c["status"] = status
            c["packet"] = None
            with self.assertRaises(ValueError):
                seal_trial(c, self.contract, nonce=NONCE)

    def test_unverified_capture_cannot_be_sealed(self):
        for prop, value in (("whole_blobs_verified", 5), ("source_writeback", True),
                            ("scientific_claim_promotion", True), ("authority_delta", 1)):
            c = deepcopy(self.capture)
            c[prop] = value
            with self.assertRaises(ValueError):
                seal_trial(c, self.contract, nonce=NONCE)

    def test_question_with_claim_promotion_cannot_be_sealed(self):
        c = deepcopy(self.capture)
        c["packet"]["questions_by_arm"]["divergent_r1"][0]["claim_promotion"] = True
        with self.assertRaises(ValueError):
            seal_trial(c, self.contract, nonce=NONCE)

    def test_invalid_private_nonce_rejected(self):
        for nonce in ("guess", "", "a" * 20, "Z" * 64):
            with self.assertRaises(ValueError):
                seal_trial(self.capture, self.contract, nonce=nonce)

    def test_future_not_yet_collected_and_external_judge_unassigned(self):
        validate_contract(self.contract)
        self.assertEqual(self.contract["registration_status"],
                         "DESIGN_FROZEN__FUTURE_CASES_NOT_YET_COLLECTED")
        self.assertFalse(self.contract["external_judge"]["assigned"])
        self.assertEqual(self.contract["source_policy"]["target_distinct_commit_triplets"], 8)

    def test_no_fictitious_judge_or_proof_status_can_be_passed(self):
        for field, value in (("scientific_gate", "PROVED"),
                             ("registration_status", "REVIEWED")):
            contract = deepcopy(self.contract)
            contract[field] = value
            with self.assertRaises(ValueError):
                seal_trial(self.capture, contract, nonce=NONCE)
        contract = deepcopy(self.contract)
        contract["external_judge"]["assigned"] = True
        with self.assertRaises(ValueError):
            seal_trial(self.capture, contract, nonce=NONCE)

    def test_submission_deterministic_for_same_inputs(self):
        first = seal_trial(self.capture, self.contract, nonce=NONCE)
        second = seal_trial(self.capture, self.contract, nonce=NONCE)
        self.assertEqual(first, second)
        other_public, other_private = seal_trial(self.capture, self.contract, nonce="2d" * 32)
        self.assertNotEqual(other_private["commitment_sha256"], first[1]["commitment_sha256"])
        self.assertEqual(other_public["question_budget_per_arm"], 4)


if __name__ == "__main__":
    unittest.main()
