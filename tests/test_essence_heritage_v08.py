"""ESSENCE v0.8: audited heritage operators, anti-tamper, non-promotion contracts."""
import copy
import json
from pathlib import Path
import unittest

from tools import essence_heritage_v08 as h

ROOT = Path(__file__).resolve().parents[1]
CAT = ROOT / "research/essence/v08/heritage_sources.json"
MAN = ROOT / ".janus/essence/manifest.json"
R2 = ROOT / "tests/fixtures/essence_r2_real_duration_20261113.json"

def catalog():
    return json.loads(CAT.read_text(encoding="utf-8"))

def manifest():
    return json.loads(MAN.read_text(encoding="utf-8"))

def r2():
    return json.loads(R2.read_text(encoding="utf-8"))

def donor_snapshot():
    donors = [{"repo": f"Hawkar-usls/{r}", "kernel_sha256": "a" * 64}
              for r in ("Janus_Genesis", "Demi_Head", "janus-distributed-ai-swarm")]
    candidates = [
        {"repo": "Hawkar-usls/Demi_Head", "id": "idea-nexus-wal-failclosed-00",
         "role": "recovery", "status": "IDEA_NOT_PERFORMANCE_PROOF",
         "evidence_sha256": "a" * 64, "precommit_sha256": "b" * 64,
         "origin_receipt_sha256": "c" * 64, "source_ideas_sha256": "d" * 64},
        {"repo": "Hawkar-usls/janus-distributed-ai-swarm", "id": "idea-swarm-dual-strand-00",
         "role": "memory", "status": "IDEA_NOT_PERFORMANCE_PROOF",
         "evidence_sha256": "a" * 64, "precommit_sha256": "b" * 64,
         "origin_receipt_sha256": "c" * 64, "source_ideas_sha256": "d" * 64},
    ]
    doc = {"schema": h.SNAPSHOT_SCHEMA,
           "source": "PUBLIC_REPO_DEFAULT_BRANCH_MANIFESTS",
           "verified_donor_count": len(donors),
           "canonical_kernel_sha256": "a" * 64,
           "donors": donors,
           "genes_by_role": {role: ["review"] for role in h.BASE},
           "innovation_candidates": candidates,
           "automatic_replication_enabled": False,
           "source_code_and_weights_transplanted": False}
    doc["snapshot_sha256"] = h.digest(doc)
    return doc

class HeritageContracts(unittest.TestCase):
    def test_exact_local_source_hashes_and_thirteen_legacy_roles(self):
        verified = h.validate_catalog(catalog(), ROOT)
        self.assertGreaterEqual(len(verified), 8)
        self.assertEqual(len(catalog()["entries"]), 18)
        self.assertEqual({x["role"] for x in catalog()["entries"]}, set(h.R0))
        self.assertEqual(len(h.BASE), 6)

    def test_research_gate_on_actual_negative_r2(self):
        report = h.run(catalog(), manifest(), donor_snapshot(), r2(), root=ROOT)
        self.assertEqual(report["historical_sources_in_gene_pool"], 18)
        self.assertEqual(report["research_gate"],
                         "HOLD_UNVERIFIED_PERFORMANCE_AND_R2_NEGATIVE")
        self.assertLess(report["completed_r2_relative_gain"], 0)
        self.assertFalse(report["production_authority"])
        self.assertFalse(report["automatic_offspring"])
        self.assertFalse(report["model_weights_modified"])
        self.assertEqual(len(report["spiral_turns"]), 2)
        self.assertFalse(report["spiral_turns"][1]["promoted"])
        self.assertEqual(report["spiral_turns"][1]["active_state_after"],
                         report["spiral_turns"][0]["active_state_after"])
        self.assertEqual(len(report["proposed_rare_ideas"]), 2)
        self.assertEqual(report["triadic_council"]["accepted"], False)
        self.assertEqual(report["temporal_advisory"]["consensus"], "stabilize")
        self.assertGreater(report["slime_reference_trace"], 0)
        self.assertLess(report["slime_reference_trace"], 0.5)

    def test_all_roles_mapped_but_only_six_base_active(self):
        report = h.run(catalog(), manifest(), donor_snapshot(), r2(), root=ROOT)
        self.assertEqual(set(report["historical_roles"]), set(h.R0))
        for role, info in report["historical_roles"].items():
            self.assertIn(info["parent_base_role"], h.BASE)
            self.assertEqual(info["role_kind"],
                             "BASE_MICROCORE" if role in h.BASE
                             else "LEGACY_ADVISORY_ONLY")

    def test_exact_r2_not_claimed_as_future_proof(self):
        report = h.run(catalog(), manifest(), donor_snapshot(), r2(), root=ROOT)
        self.assertFalse(report["independent_external_authentication"])
        self.assertEqual(report["report_kind"],
                         "READ_ONLY_LIVE_RESEARCH_ADVISORY_NOT_MODEL_TRAINING")

    def test_local_modern_source_git_blob_tamper_fails(self):
        c = catalog()
        c["entries"][3]["git_blob_sha1"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "LOCAL_HERITAGE_SHA_MISMATCH"):
            h.validate_catalog(c, ROOT)

    def test_cannot_activate_legacy_monolith(self):
        c = catalog()
        c["entries"][6]["admission"] = "modern_local_executable"
        with self.assertRaisesRegex(ValueError, "EXECUTABLE_LEGACY_UNREVIEWED"):
            h.validate_catalog(c, ROOT)

    def test_extra_capability_does_not_leak_into_root(self):
        m = manifest()
        m["enabled"] = True
        with self.assertRaisesRegex(ValueError, "ROOT_AUTHORITY_DENIED"):
            h.validate_root(m)

    def test_path_traversal_rejected(self):
        c = catalog()
        c["entries"][0]["path"] = "../.env"
        with self.assertRaisesRegex(ValueError, "UNSAFE_HERITAGE_PATH"):
            h.validate_catalog(c, ROOT)

    def test_rejects_dropped_old_governance_role(self):
        c = catalog()
        c["canonical_13_roles"].remove("governance")
        with self.assertRaisesRegex(ValueError, "LEGACY_R0_ROLE_LOSS"):
            h.validate_catalog(c, ROOT)

    def test_rejects_loss_of_parent_microcore(self):
        m = manifest()
        m["microkernels"] = m["microkernels"][:5]
        with self.assertRaisesRegex(ValueError, "ROOT_SIX_MICROCORES_REQUIRED"):
            h.validate_root(m)

    def test_source_catalog_cannot_assert_new_measurement(self):
        c = catalog()
        c["entries"][0]["independent_performance_gain"] = 0.97
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_OR_UNSAFE_GENE"):
            h.validate_catalog(c, ROOT)

    def test_donor_snapshot_sha_tampering_fails(self):
        s = donor_snapshot()
        s["verified_donor_count"] += 1
        with self.assertRaisesRegex(ValueError, "DONOR_SNAPSHOT_UNVERIFIED"):
            h.validate_snapshot(s)

    def test_donor_snapshot_no_autobirth(self):
        s = donor_snapshot()
        s["automatic_replication_enabled"] = True
        s["snapshot_sha256"] = h.digest({k:v for k,v in s.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError, "UNSAFE_DONOR_SNAPSHOT"):
            h.validate_snapshot(s)

    def test_duplicate_candidate_rejected(self):
        s = donor_snapshot()
        s["innovation_candidates"].append(copy.deepcopy(s["innovation_candidates"][0]))
        s["snapshot_sha256"] = h.digest({k:v for k,v in s.items() if k!="snapshot_sha256"})
        with self.assertRaisesRegex(ValueError, "BAD_IDEA_IDENTITY_OR_PROOF"):
            h.validate_snapshot(s)

    def test_negative_historical_trial_cannot_be_flipped_to_gain(self):
        data = r2()
        data["results_mae_seconds"]["temporal_gene_candidate"] = 1
        # v0.6 historical parser accepts summary but gate must still reject.
        with self.assertRaisesRegex(ValueError, "R2_NEGATIVE_CONTROL_CHANGED"):
            h.run(catalog(), manifest(), donor_snapshot(), data, root=ROOT)

    def test_catalog_not_neural_training_claim(self):
        report = h.run(catalog(), manifest(), donor_snapshot(), r2(), root=ROOT)
        self.assertNotIn("NEURAL_MODEL_TRAINED", report["operators_exercised"])
        self.assertEqual(report["source_class"],
                         "LIVE_PUBLIC_DONOR_INVENTORY_PLUS_REAL_RETROSPECTIVE_R2")

    def test_git_blob_sha_roundtrip(self):
        import hashlib
        raw=b"print(1)\n"
        direct=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
        self.assertEqual(h.git_blob(raw), direct)

    def test_canonical_digest_is_stable(self):
        self.assertEqual(h.digest({"b":2,"a":1}),h.digest({"a":1,"b":2}))

if __name__ == "__main__":
    unittest.main()
