import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "trump" / "trump_candidate.py"
spec = importlib.util.spec_from_file_location("trump_candidate_runtime", MODULE_PATH)
assert spec and spec.loader
trump = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = trump
spec.loader.exec_module(trump)


class TrumpCandidateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.manifest = trump.load_manifest()
        self.source = trump.primary_source(self.manifest)

    def test_candidate_may_wake_but_has_no_proof_authority(self):
        activation = self.manifest["activation"]
        self.assertTrue(activation["wake_allowed"])
        self.assertTrue(activation["use_allowed"])
        self.assertTrue(activation["self_improvement_allowed"])
        self.assertFalse(activation["proof_authority"])
        self.assertFalse(activation["scientific_claim_promotion_authority"])
        self.assertEqual(self.manifest["scientific_boundary"]["P_VS_NP"], "OPEN")

    def test_primary_source_is_exact_fundamentum_pin(self):
        self.assertEqual(self.source["repository"], "Hawkar-usls/Janus-Fundamentum")
        self.assertEqual(self.source["pinned_commit"], "377668585178995217b681d5ddb1b34b0f8dc386")
        self.assertEqual(self.source["git_blob_sha"], "230ca949bb51f6eeb5e7dbeea364a0752f9d0636")
        self.assertIn("janus_unified_proof_carrying_akinator_jec.py", self.source["path"])

    def test_git_blob_hash_matches_git_object_rule(self):
        data = b"hello\n"
        self.assertEqual(trump.git_blob_sha(data), "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_rejects_authority_escalation_even_if_manifest_is_rehashed(self):
        bad = copy.deepcopy(self.manifest)
        bad["activation"]["proof_authority"] = True
        with self.assertRaisesRegex(trump.TrumpCandidateError, "AUTHORITY_CEILING"):
            trump.validate_manifest(bad)

    def test_rejects_closed_p_vs_np_boundary(self):
        bad = copy.deepcopy(self.manifest)
        bad["scientific_boundary"]["P_VS_NP"] = "SOLVED"
        bad["scientific_boundary"]["P_equals_NP_proved"] = True
        with self.assertRaisesRegex(trump.TrumpCandidateError, "SCIENTIFIC_BOUNDARY"):
            trump.validate_manifest(bad)

    def test_rejects_untrusted_candidate_repository(self):
        bad = copy.deepcopy(self.manifest)
        bad["candidate_sources"][0]["repository"] = "someone/else"
        with self.assertRaisesRegex(trump.TrumpCandidateError, "SOURCE_REPOSITORY_NOT_ADMITTED"):
            trump.validate_manifest(bad)

    def test_status_receipt_is_candidate_only(self):
        receipt = trump.status_receipt()
        self.assertEqual(receipt["terminal"], "TRUMP_CANDIDATE_RUNTIME_AVAILABLE")
        self.assertTrue(receipt["wake_allowed"])
        self.assertFalse(receipt["execution_performed"])
        self.assertFalse(receipt["authority"]["proof_authority"])
        self.assertEqual(receipt["scientific_boundary"]["P_VS_NP"], "OPEN")
        body = dict(receipt)
        digest = body.pop("receipt_hash")
        self.assertEqual(digest, trump.sha256_json(body))

    def test_pinned_source_url_contains_exact_commit_not_tracking_branch(self):
        url = trump.raw_source_url(self.source)
        self.assertIn(self.source["pinned_commit"], url)
        self.assertNotIn(self.source["tracking_ref"], url)

    def test_imported_candidate_requires_declared_entrypoints(self):
        good = b"def solve_fail_closed(*a, **k): return {'scientific_boundary': {'P_VS_NP': 'OPEN'}}\ndef selftest(): return None\n"
        module = trump.import_candidate_module(good, {**self.source, "required_entrypoints": ["solve_fail_closed", "selftest"]})
        self.assertTrue(callable(module.solve_fail_closed))

        bad = b"def selftest(): return None\n"
        with self.assertRaisesRegex(trump.TrumpCandidateError, "ENTRYPOINT_MISSING"):
            trump.import_candidate_module(bad, {**self.source, "required_entrypoints": ["solve_fail_closed", "selftest"]})


if __name__ == "__main__":
    unittest.main()
