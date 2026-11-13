"""ESSENCE v1.0 adversarial research-to-model review gate tests.

All prospective-looking observations and keypairs here are SYNTHETIC fixtures,
not evidence that the actual ESSENCE model has improved in production.
"""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import essence_model_admission_v10 as a

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/"research/essence/v10/locked_v07_protocol.json"

def protocol():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))

def mock_report(candidate="idea-swarm-dual-strand-00"):
    arm=next(x for x in protocol()["arms"] if x["id"]==candidate)
    cohorts={}
    for label in ("future-1","future-2"):
        cohorts[label]={
            "n":60,"correct_baseline":0,"correct_candidate":60,
            "wins_candidate":60,"wins_baseline":0,
            "candidate_false_reject_healthy":0,
            "absolute_accuracy_gain":1.0,
            "mcnemar_one_sided_p":0.0,
            "internal_scientific_gate":"METRIC_PASS_UNAUTHENTICATED",
        }
    x={
        "schema":a.REPORT,"candidate_id":candidate,
        "source_kind":arm["source_kind"],
        "protocol_sha256":a.digest(protocol()),
        "rows_sha256":"1"*64,
        "research_gate":"RESEARCH_METRIC_PASS_REQUIRES_EXTERNAL_AUTHENTICATION",
        "source_claims_not_authenticated":True,
        "independent_external_replication":False,
        "production_authority":False,"offspring_activated":False,
        "cohorts":cohorts,
    }
    x["report_sha256"]=a.digest(x)
    return x

def seal(x):
    x["report_sha256"]=a.digest({k:v for k,v in x.items() if k!="report_sha256"})

def context(report):
    return {
        "target_repo":a.TARGET_REPO,
        "baseline_commit_sha1":"a"*40,
        "candidate_commit_sha1":"b"*40,
        "baseline_checkpoint_sha256":"c"*64,
        "candidate_checkpoint_sha256":"d"*64,
        "rollback_checkpoint_sha256":"c"*64,
        "rollback_drill_sha256":"e"*64,
        "canary_receipt_sha256":"f"*64,
        "canary_status":"PASS",
        "rollback_status":"PASS",
        "checkpoint_preflight_status":"PASS_NO_DESERIALIZATION",
        "heldout_raw_rows_sha256":report["rows_sha256"],
        "evaluation_report_sha256":report["report_sha256"],
        "independent_verifier_organization":"EXTERNAL_UNATTESTED_TEST_FIXTURE",
        "request_kind":"HUMAN_REVIEW_ONLY",
    }

class ModelPromotionAdmission(unittest.TestCase):
    def setUp(self):
        self.p=protocol()
        self.r=mock_report()

    def test_frozen_reference(self):
        self.assertTrue(a.frozen(self.p))
        self.assertEqual(a.digest(self.p),a.LOCKED_PROTOCOL_SHA256)

    def test_synthetic_like_positive_metrics_do_not_produce_authority(self):
        r=a.review(self.p,self.r)
        self.assertEqual(r["review_gate"],"HOLD_EXTERNAL_ATTESTATIONS_AND_SAFETY_PROOFS")
        self.assertFalse(r["production_authority"])
        self.assertFalse(r["checkpoint_swapped"])
        self.assertFalse(r["owner_approval_obtained"])

    def test_correct_chronology_two_cohorts_required(self):
        del self.r["cohorts"]["future-2"];seal(self.r)
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_FUTURE_COHORTS"):
            a.review(self.p,self.r)

    def test_negative_gain_fails(self):
        c=self.r["cohorts"]["future-2"]
        c.update(correct_baseline=60,correct_candidate=59,wins_candidate=0,
                 wins_baseline=1,absolute_accuracy_gain=-1/60,
                 mcnemar_one_sided_p=1.0)
        seal(self.r)
        with self.assertRaisesRegex(ValueError,"NO_REPLICATED_PAIRED_GAIN"):
            a.review(self.p,self.r)

    def test_report_digest_tamper_fails(self):
        self.r["cohorts"]["future-1"]["n"]=61
        with self.assertRaisesRegex(ValueError,"UNSEALED_TRIAL_REPORT"):
            a.review(self.p,self.r)

    def test_changing_freeze_or_thresholds_fails(self):
        self.p["thresholds"]["min_cases_each_cohort"]=1
        with self.assertRaisesRegex(ValueError,"CHANGED_FROZEN_PROTOCOL"):
            a.review(self.p,self.r)

    def test_claiming_automatic_promotion_fails(self):
        self.r["production_authority"]=True;seal(self.r)
        with self.assertRaisesRegex(ValueError,"PREMATURE_OR_FORGED_TRIAL_AUTHORITY"):
            a.review(self.p,self.r)

    def test_bad_p_value_recomputed_not_trusted(self):
        self.r["cohorts"]["future-1"]["mcnemar_one_sided_p"]=1.0
        seal(self.r)
        with self.assertRaisesRegex(ValueError,"NO_SIGNIFICANT_PAIRED_REPLICATION"):
            a.review(self.p,self.r)

    def test_one_healthy_false_rejection_blocks(self):
        self.r["cohorts"]["future-1"]["candidate_false_reject_healthy"]=1
        seal(self.r)
        with self.assertRaisesRegex(ValueError,"TRIAL_COUNT_OR_HEALTHY_SAFETY_FAILURE"):
            a.review(self.p,self.r)

    def test_empty_context_not_eligible_for_owner_approval(self):
        r=a.review(self.p,self.r,context(self.r))
        self.assertEqual(r["review_gate"],"HOLD_OUT_OF_BAND_TRUST_PINS_REQUIRED")

    def test_missing_rollback_fails(self):
        c=context(self.r);c["rollback_status"]="NO"
        with self.assertRaisesRegex(ValueError,"ADMISSION_PREREQUISITE_MISSING"):
            a.review(self.p,self.r,c)

    def test_candidate_must_be_new(self):
        c=context(self.r);c["candidate_checkpoint_sha256"]=c["baseline_checkpoint_sha256"]
        with self.assertRaisesRegex(ValueError,"ADMISSION_NO_NEW_MODEL"):
            a.review(self.p,self.r,c)

    def test_bad_target_fails(self):
        c=context(self.r);c["target_repo"]="Hawkar-usls/Other"
        with self.assertRaisesRegex(ValueError,"ADMISSION_PREREQUISITE_MISSING"):
            a.review(self.p,self.r,c)

    def test_missing_two_roles_fails(self):
        with self.assertRaisesRegex(ValueError,"MISSING_REQUIRED_TWO_INDEPENDENT_ROLES"):
            a.review(self.p,self.r,context(self.r),{},{})

    def test_forged_signature_binding_fails(self):
        c=context(self.r)
        bad={"source_custodian":{"body":{"report_sha256":"x"},"signature":"bad"},
             "external_model_reviewer":{"body":{"report_sha256":"x"},"signature":"bad"}}
        pins={k:{"identity":"fake-review","public_key":"ssh-ed25519 AAAA"}
              for k in bad}
        with self.assertRaisesRegex(ValueError,"SIGNATURE_BINDING_DOES_NOT_MATCH"):
            a.review(self.p,self.r,c,bad,pins)

    @unittest.skipUnless(shutil.which("ssh-keygen"),"OpenSSH required for signature contracts")
    def test_two_distinct_ephemeral_crypto_signers_only_allow_human_review(self):
        # These are local test keys, NOT independent real lab identities.
        with tempfile.TemporaryDirectory() as tmp:
            c=context(self.r); pins={}; proofs={}
            for role,identity in (("source_custodian","synthetic_source_00"),
                                  ("external_model_reviewer","synthetic_reviewer_01")):
                path=Path(tmp)/role
                cp=subprocess.run(["ssh-keygen","-q","-t","ed25519","-N","","-f",str(path)],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=10)
                self.assertEqual(cp.returncode,0,cp.stderr)
                key=path.with_suffix(".pub").read_text().split()[:2]
                pins[role]={"identity":identity,"public_key":" ".join(key)}
                body={
                    "schema":a.ATTEST,"role":role,"identity":identity,
                    "report_sha256":self.r["report_sha256"],
                    "context_sha256":a.digest(c),
                    "attested_at":"2026-12-01T00:00:00Z",
                    "scope":"INDEPENDENT_REVIEW_NO_PRODUCTION_DISPATCH",
                }
                sig=subprocess.run(["ssh-keygen","-Y","sign","-f",str(path),
                                    "-n",a.NAMESPACE],input=a.canonical(body),
                                    capture_output=True,check=False,timeout=10)
                self.assertEqual(sig.returncode,0,sig.stderr)
                proofs[role]={"body":body,"signature":sig.stdout.decode()}
            outcome=a.review(self.p,self.r,c,proofs,pins)
            self.assertEqual(outcome["review_gate"],
                             "CRYPTO_REVIEW_COMPLETE_OWNER_APPROVAL_STILL_REQUIRED")
            self.assertEqual(outcome["cryptographically_distinct_signers"],2)
            self.assertTrue(outcome["scientific_independence_needs_human_confirmation"])
            self.assertFalse(outcome["independently_verified"])
            self.assertFalse(outcome["production_authority"])
            self.assertFalse(outcome["checkpoint_swapped"])
            self.assertFalse(outcome["owner_approval_obtained"])
            # Replay the same public key in two roles: fail closed.
            forged=copy.deepcopy(pins)
            forged["external_model_reviewer"]=dict(forged["source_custodian"])
            with self.assertRaises(ValueError):
                a.review(self.p,self.r,c,proofs,forged)

    def test_v07_nexus_arm_may_be_reviewed_but_not_promoted(self):
        report=mock_report("idea-nexus-wal-failclosed-00")
        x=a.review(self.p,report)
        self.assertEqual(x["candidate_id"],"idea-nexus-wal-failclosed-00")
        self.assertFalse(x["production_authority"])

    def test_old_real_negative_r2_is_not_a_prospective_pass(self):
        old=json.loads((ROOT/"tests/fixtures/essence_r2_real_duration_20261113.json").read_text())
        with self.assertRaisesRegex(ValueError,"INVALID_TRIAL_REPORT"):
            a.review(self.p,old)

if __name__=="__main__":
    unittest.main()
