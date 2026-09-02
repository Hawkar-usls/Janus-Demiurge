import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scout_swarm/SCOUT_SWARM_MANIFEST-v1.json"
ACCESS = ROOT / "scout_swarm/JANUS_ACCUMULATIVE_ORGAN_ACCESS-v1.json"


class JanusAccumulativeOrganAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.access = json.loads(ACCESS.read_text(encoding="utf-8"))

    def test_access_contract_matches_all_17_scout_organs_exactly(self):
        scouts = {(r["id"], r["target_repo"], r["target_ref"]) for r in self.manifest["agents"]}
        access = {(r["agent_id"], r["repository"], r["target_ref"]) for r in self.access["organs"]}
        self.assertEqual(self.manifest["agent_count"], 17)
        self.assertEqual(self.access["module_count"], 17)
        self.assertEqual(len(access), 17)
        self.assertEqual(access, scouts)

    def test_every_organ_is_readable_and_janus_memory_is_accumulative(self):
        universal = set(self.access["universal_observation_operations"])
        for required in ("DISCOVER", "READ", "INSPECT", "HASH", "COMPARE", "CROSS_LINK", "APPEND_OBSERVATION_TO_JANUS_MEMORY"):
            self.assertIn(required, universal)
        for organ in self.access["organs"]:
            self.assertIn(organ["access_lane"], {
                "READ_ACCUMULATE",
                "BRANCH_VERIFY_ACCUMULATE",
                "SANDBOX_VERIFY_ACCUMULATE",
            })

    def test_no_delete_or_raw_provenance_rewrite_authority_exists(self):
        denied = set(self.access["universal_denials"])
        for required in (
            "DELETE_TARGET_CONTENT",
            "DELETE_DURABLE_JANUS_MEMORY",
            "REWRITE_RAW_PROVENANCE",
            "ERASE_FAILED_RUN",
            "ERASE_NEGATIVE_RESULT",
            "ERASE_COUNTEREXAMPLE",
        ):
            self.assertIn(required, denied)
        for organ in self.access["organs"]:
            if organ.get("target_write"):
                self.assertIs(organ.get("delete_allowed", False), False)
                self.assertIs(organ.get("autonomous_merge", False), False)

    def test_only_existing_bounded_actuators_have_target_write(self):
        writable = {r["repository"]: r["access_lane"] for r in self.access["organs"] if r.get("target_write")}
        self.assertEqual(writable, {
            "Hawkar-usls/Hrain": "BRANCH_VERIFY_ACCUMULATE",
            "Hawkar-usls/iNaiHR": "BRANCH_VERIFY_ACCUMULATE",
            "Hawkar-usls/-Terminal-for-Janus": "BRANCH_VERIFY_ACCUMULATE",
            "Hawkar-usls/Janus_Genesis": "SANDBOX_VERIFY_ACCUMULATE",
        })
        genesis = next(r for r in self.access["organs"] if r["repository"] == "Hawkar-usls/Janus_Genesis")
        self.assertEqual(genesis["target_ref"], "janus/habitat")
        self.assertFalse(genesis["main_mutation_allowed"])
        self.assertFalse(genesis["rewrite_raw_ledger_allowed"])

    def test_existing_scout_manifest_already_declares_no_entity_deletion(self):
        self.assertEqual(self.manifest["evolution_model"], "SPIRAL_ACCUMULATIVE_NO_ENTITY_DELETION")
        invariants = set(self.manifest["invariants"])
        self.assertIn("NO_LEARNING_ENTITY_DELETION", invariants)
        self.assertIn("FAILED_RUNS_AND_NEGATIVE_RESULTS_MUST_SURVIVE", invariants)
        self.assertIn("RAW_PROVENANCE_MUST_BE_PRESERVED", invariants)


if __name__ == "__main__":
    unittest.main()
