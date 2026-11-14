"""ESSENCE v1.7 review verifier tests. Positive fixtures are SYNTHETIC ONLY.

Ephemeral SSH keys here test signature verification; they are NOT owner trust
roots and are never installed, logged, or claimed as real-world attestations.
"""
from __future__ import annotations
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import essence_v17_three_gate_review as a

def fixture():
    cohorts=[]
    for name,offset in (("future_private_group_a",0),("future_private_group_b",1000)):
        docs=[{"document_sha256":f"{i+offset:064x}",
               "n_tokens":32,"argmax_matches":32,
               "baseline_ce":1.5,"candidate_ce":1.5001}
              for i in range(1,101)]
        cohorts.append({"name":name,"documents":docs})
    target="janus-service-hardware-2026"
    artifact="9"*64
    runs=[{
      "device_id":target,
      "baseline_p95_ms":2.2,"candidate_p95_ms":2.1,
      "baseline_rss_bytes":350000000,"candidate_rss_bytes":348000000,
      "baseline_median_ms":1.8,"candidate_median_ms":1.7,
      "run_receipt_sha256":f"{500+i:064x}"
    } for i in range(5)]
    evidence={
      "schema":a.SCHEMA,
      "candidate":{
         "repository":a.TARGET_REPO,"candidate_id":a.CANDIDATE,
         "selected_model_commit":a.SELECTED_SOURCE_COMMIT,
         "source_checkpoint_sha256":a.ORIGINAL_SHA,
         "source_checkpoint_git_blob":a.FROZEN_MODEL_BLOB,
         "quantized_layer_names":list(a.SELECTED_LAYERS),
         "production_change_requested":False
       },
      "holdout":{
         "source_class":"INDEPENDENT_UNSEEN_PRIVATE_CUSTODIAN",
         "certified_not_used_for_training":True,
         "certified_not_seen_during_candidate_selection":True,
         "raw_holdout_sha256":"1"*64,
         "scoring_code_sha256":"2"*64,
         "cohorts":cohorts
       },
      "hardware":{
         "source_class":"REAL_TARGET_HARDWARE",
         "actual_native_int8_operator_count":3,
         "independent_process_per_run":True,
         "hardware_matched_to_target_service":True,
         "allocator_confounded":False,
         "hardware_profile_sha256":"3"*64,
         "candidate_artifact_sha256":artifact,
         "target_id":target,
         "runs":runs,
         "baseline_serialized_bytes":1794511,
         "candidate_serialized_bytes":1207229
       },
      "rollback":{
         "source_class":"REAL_DEPLOYED_MODEL_SERVICE",
         "target_id":target,"service_id":"test-only-model-service",
         "service_revision_before":"service-release-before",
         "service_revision_canary":"service-release-canary",
         "service_revision_after":"service-release-rollback",
         "baseline_checkpoint_sha256":a.ORIGINAL_SHA,
         "candidate_artifact_sha256":artifact,
         "active_checkpoint_sha256_after":a.ORIGINAL_SHA,
         "monitoring_source_sha256":"4"*64,
         "deployment_proof_sha256":"5"*64,
         "rollback_proof_sha256":"6"*64,
         "real_canary_requests":200,
         "real_rollback_triggered":True,
         "healthy_after_revert":True,
         "healthcheck_baseline_response_sha256":"7"*64,
         "healthcheck_postrollback_response_sha256":"7"*64,
         "candidate_was_live_for_canary":True,
         "rollback_was_on_actual_service":True
       },
      "attestations":{}
    }
    return evidence

class ThreeGateRealModelReview(unittest.TestCase):
    def test_present_real_world_status_is_hold(self):
        result=a.review()
        self.assertEqual(result["review_gate"],
                         "HOLD_INDEPENDENT_BLIND_TARGET_HARDWARE_AND_REAL_SERVICE_ROLLBACK")
        self.assertFalse(result["production_authority"])
        self.assertFalse(result["automatic_promotion"])

    def test_synthetic_contract_metrics_only(self):
        e=fixture()
        self.assertEqual(len(a.holdout_results(e["holdout"])),2)
        self.assertEqual(a.hardware_results(e["hardware"])["paired_runs"],5)
        h=a.hardware_results(e["hardware"])
        h["candidate_artifact_sha256"]=e["hardware"]["candidate_artifact_sha256"]
        self.assertTrue(a.rollback_results(e["rollback"],h)["rollback_checkpoint_restored"])
        self.assertEqual(a.review(e,None)["review_gate"],
                         "HOLD_INDEPENDENT_BLIND_TARGET_HARDWARE_AND_REAL_SERVICE_ROLLBACK")

    def test_reject_reused_document_identifiers(self):
        e=fixture()
        e["holdout"]["cohorts"][1]["documents"][0]["document_sha256"]=e["holdout"]["cohorts"][0]["documents"][0]["document_sha256"]
        with self.assertRaisesRegex(ValueError,"DUPLICATE_OR_INVALID_BLIND_DOCUMENT"):
            a.holdout_results(e["holdout"])

    def test_document_cluster_bootstrap_rejects_weak_quality(self):
        e=fixture()
        for d in e["holdout"]["cohorts"][0]["documents"][:15]:
            d["argmax_matches"]=12
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_HOLDOUT_QUALITY_HOLD"):
            a.holdout_results(e["holdout"])

    def test_reject_mixed_hardware(self):
        e=fixture()
        e["hardware"]["runs"][0]["device_id"]="different-device"
        with self.assertRaisesRegex(ValueError,"BAD_HARDWARE_RUN"):
            a.hardware_results(e["hardware"])

    def test_reject_confounded_rss(self):
        e=fixture()
        e["hardware"]["allocator_confounded"]=True
        with self.assertRaisesRegex(ValueError,"TARGET_HARDWARE_PROOF_MISSING"):
            a.hardware_results(e["hardware"])

    def test_reject_regressed_latency(self):
        e=fixture()
        e["hardware"]["runs"][3]["candidate_median_ms"]=2.2
        with self.assertRaisesRegex(ValueError,"TARGET_HARDWARE_PER_RUN_REGRESSION"):
            a.hardware_results(e["hardware"])

    def test_reject_fake_shadow_not_service_rollback(self):
        e=fixture()
        h=a.hardware_results(e["hardware"])
        h["candidate_artifact_sha256"]=e["hardware"]["candidate_artifact_sha256"]
        e["rollback"]["rollback_was_on_actual_service"]=False
        with self.assertRaisesRegex(ValueError,"UNPROVEN_LIVE_CANARY_OR_ROLLBACK"):
            a.rollback_results(e["rollback"],h)

    def test_reject_wrong_candidate_artifact(self):
        e=fixture()
        h=a.hardware_results(e["hardware"])
        h["candidate_artifact_sha256"]=e["hardware"]["candidate_artifact_sha256"]
        e["rollback"]["candidate_artifact_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"INCONSISTENT_REAL_SERVICE_IDENTITY"):
            a.rollback_results(e["rollback"],h)

    def test_reject_unpinned_original_model(self):
        e=fixture()
        e["candidate"]["source_checkpoint_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"UNPINNED_OR_PRODUCTION_CANDIDATE"):
            a.fixed_candidate(e["candidate"])

    @unittest.skipUnless(shutil.which("ssh-keygen"),"ssh-keygen unavailable")
    def test_ephemeral_crypto_proves_review_only_never_release(self):
        e=fixture();trust={}
        with tempfile.TemporaryDirectory() as folder:
            for i,role in enumerate(a.ROLES):
                identity=("role_" + role)[:60]
                name=Path(folder)/f"tempkey{i}"
                gen=subprocess.run(["ssh-keygen","-q","-t","ed25519",
                                    "-N","","-f",str(name)],capture_output=True)
                self.assertEqual(gen.returncode,0,gen.stderr.decode())
                public=" ".join(Path(str(name)+".pub").read_text().split()[:2])
                trust[role]={"identity":identity,"public_key":public,
                             "organization":f"synthetic_test_org_{i}"}
                part="holdout" if i<2 else ("hardware" if i==2 else "rollback")
                body={"schema":a.ATTEST_SCHEMA,"role":role,
                      "candidate_id":a.CANDIDATE,
                      "payload_sha256":a.sha(e[part]),
                      "signed_at_utc":"2026-11-14T00:00:00Z",
                      "scope":"INDEPENDENT_REVIEW_NO_MODEL_DISPATCH"}
                sign=subprocess.run(["ssh-keygen","-Y","sign","-f",str(name),
                                     "-n",a.NAMESPACE],input=a.canonical(body),
                                    capture_output=True)
                self.assertEqual(sign.returncode,0,sign.stderr.decode())
                e["attestations"][role]={"body":body,"signature":sign.stdout.decode()}
            result=a.review(e,trust)
            self.assertEqual(result["review_gate"],
                "REVIEW_EVIDENCE_CRYPTO_VERIFIED_OWNER_APPROVAL_STILL_REQUIRED")
            self.assertFalse(result["production_authority"])
            self.assertFalse(result["owner_approved"])
            self.assertEqual(result["attestation"]["cryptographic_attesters"],4)
            e["hardware"]["candidate_serialized_bytes"]=1794511
            with self.assertRaises(ValueError):
                a.review(e,trust)

if __name__=="__main__":unittest.main()
