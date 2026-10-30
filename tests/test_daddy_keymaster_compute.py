"""Cross-architecture compute broker adversarial receipt tests."""
import copy
import json
from pathlib import Path
import unittest

from daddy_keymaster.compute import ARCH, SOURCES, SUITES, ASSIGNMENTS, audit, check_env, manifest
from daddy_keymaster.broker import sha

ROOT = Path(__file__).resolve().parents[1]
ENV = {"GITHUB_ACTIONS":"true",
       "GITHUB_REPOSITORY":"Hawkar-usls/Janus-Demiurge",
       "GITHUB_EVENT_NAME":"push",
       "GITHUB_RUN_ID":"41188880000",
       "GITHUB_RUN_ATTEMPT":"1",
       "GITHUB_SHA":"a"*40,
       "RUNNER_OS":"Linux","RUNNER_ARCH":"X64"}


def receipt(platform):
    obj = {"schema":"janus.daddy_keymaster.github_compute_receipt.v1",
           "run_id":ENV["GITHUB_RUN_ID"],"attempt":ENV["GITHUB_RUN_ATTEMPT"],
           "commit":ENV["GITHUB_SHA"],"repository":ENV["GITHUB_REPOSITORY"],
           "platform":platform,"runner_os":"Linux",
           "source_manifest":manifest(ROOT),
           "suites":[{"suite":name,"cases":10,"status":"PASS"} for name in ASSIGNMENTS[platform]],
           "status":"EXECUTED_ALLOWLISTED_TESTS",
           "auth":"PUBLIC_REPO_GITHUB_RUNNER",
           "external_provider_activation":False,"paid_work":False,
           "arbitrary_code_from_research":False,"authority_delta":0}
    obj["receipt_sha256"]=sha(obj)
    return obj


def reseal(obj):
    obj["receipt_sha256"]=sha({k:v for k,v in obj.items() if k!="receipt_sha256"})
    return obj


class RealComputeTests(unittest.TestCase):
    def test_two_distinct_architectures_verify(self):
        result=audit(ROOT,[receipt("X64"),receipt("ARM64")],ENV)
        self.assertEqual(result["status"],"TWO_EPHEMERAL_WORKERS_VERIFIED")
        self.assertFalse(result["worker_lease_after_job"])
        self.assertFalse(result["persistent_capacity_claim"])
        self.assertFalse(result["claims_full_distributed_recovery"])
        self.assertEqual(result["total_test_cases_by_platform"],{"X64":20,"ARM64":20})
        self.assertEqual({v["platform"] for v in result["workers"]},set(ARCH))
        self.assertEqual(result["receipt_sha256"],sha({k:v for k,v in result.items() if k!="receipt_sha256"}))

    def test_duplicate_architecture_fails(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PLATFORM"):
            audit(ROOT,[receipt("X64"),receipt("X64")],ENV)

    def test_wrong_commit_rejected_even_with_matching_hash(self):
        r=receipt("X64")
        r["commit"]="b"*40
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_wrong_repository_rejected(self):
        r=receipt("X64")
        r["repository"]="attacker/open-servers"
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_remote_provider_false_claim_rejected(self):
        r=receipt("ARM64")
        r["external_provider_activation"]=True
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("X64")],ENV)

    def test_missing_suite_rejected(self):
        r=receipt("X64")
        r["suites"].pop()
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_one_arch_fewer_cases_rejected(self):
        r=receipt("X64")
        r["suites"][1]["cases"]=9
        with self.assertRaisesRegex(ValueError,"ARCH_TEST_DISAGREEMENT"):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_fake_injected_shell_suite_rejected(self):
        r=receipt("X64")
        r["suites"][0]["suite"]="sh -c evil"
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_source_manifest_mutation_rejected(self):
        r=receipt("X64")
        r["source_manifest"]["daddy_keymaster/POLICY.json"]="0"*64
        with self.assertRaises(ValueError):
            audit(ROOT,[reseal(r),receipt("ARM64")],ENV)

    def test_bad_env_rejected(self):
        for key,val in [("GITHUB_REPOSITORY","attacker/repo"),("GITHUB_ACTIONS","false"),
                        ("GITHUB_EVENT_NAME","schedule"),("RUNNER_ARCH","UNKNOWN")]:
            env=dict(ENV)
            env[key]=val
            with self.assertRaises(ValueError):
                check_env(env)

    def test_tampered_hash_rejected(self):
        r=receipt("X64")
        r["receipt_sha256"]="f"*64
        with self.assertRaises(ValueError):
            audit(ROOT,[r,receipt("ARM64")],ENV)


if __name__=="__main__":
    unittest.main()
