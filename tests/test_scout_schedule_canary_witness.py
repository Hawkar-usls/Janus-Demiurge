"""Synthetic and adversarial read-only Scout scheduled canary audit tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.scout_schedule_canary_witness import CANARY, audit, digest

RUN = "41245405862"
SHA = "a" * 40


def fixture(root: Path, *, positive: bool = False):
    repo_dir = root / "scout_swarm"
    folder = repo_dir / "outbox/runs" / RUN
    folder.mkdir(parents=True)
    agents = [{"id": CANARY, "target_repo": "example/canary", "target_ref": "main"}]
    agents += [{"id": f"SCOUT_SYNTH_{i:02d}", "target_repo": f"example/repo-{i}",
                "target_ref": "main"} for i in range(16)]
    (repo_dir / "SCOUT_SWARM_MANIFEST-v1.json").write_text(
        json.dumps({"agents": agents, "agent_count": 17}))
    summary = {
        "run_id": RUN, "control_sha": SHA, "agents_expected": 17,
        "agents_received": 17, "agents_snapshot_observed": 17,
        "agents_model_synthesis_ok": 1 if positive else 0,
        "world_truth": False, "write_authority_over_targets": False,
    }
    (folder / "SWARM_SUMMARY.json").write_text(json.dumps(summary))
    for agent in agents:
        ok = positive and agent["id"] == CANARY
        record = {
            "agent_id": agent["id"],
            "status": "OBSERVED_REPOSITORY_STATE" if ok else "DEGRADED_MODEL_UNAVAILABLE",
            "model_error": None if ok else "quota_exceeded",
            "synthesis_failure_reason": None if ok else "rate_limit",
            "target": {"repository": agent["target_repo"], "ref": "main"},
            "repository_snapshot": {"target_commit": "b" * 40},
            "authority": {"target_repository_write": False},
            "evidence_gate": {"world_truth": False,
                              "model_output_is_independent_confirmation": False},
            "analysis": {
                "summary": "Changed README as observed at commit",
                "observations": [{"claim": "README present", "support": {
                    "path": "README.md", "commit": "b" * 40}}],
            } if ok else {"summary": "Model unavailable", "observations": []},
        }
        (folder / (agent["id"] + ".json")).write_text(json.dumps(record))
    return folder


class ScoutScheduleCanaryWitnessTests(unittest.TestCase):
    def test_quota_block_is_not_model_synthesis(self):
        with tempfile.TemporaryDirectory() as td:
            folder = fixture(Path(td))
            record = audit(Path(td), RUN, SHA)
            self.assertEqual(record["status"], "CANARY_NO_MODEL_SYNTHESIS")
            self.assertEqual(record["model_synthesis_count"], 0)
            self.assertEqual(record["snapshots_observed"], 17)
            self.assertEqual(record["canary_failure_reason"], "rate_limit")
            self.assertTrue(record["unverified_model_response_not_world_truth"])
            self.assertEqual(record["receipt_sha256"], digest({
                k: v for k, v in record.items() if k != "receipt_sha256"}))

    def test_single_scoped_positive_is_not_world_truth(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), positive=True)
            record = audit(Path(td), RUN, SHA)
            self.assertEqual(record["model_synthesis_count"], 1)
            self.assertEqual(record["status"],
                             "CANARY_MODEL_RESPONSE_STRUCTURALLY_VERIFIED_UNVERIFIED_TRUTH")
            self.assertFalse(record["independent_external_lab_validation"])
            self.assertFalse(record["paid_resources_requested"])

    def test_rejects_hallucinated_or_wrong_commit_support(self):
        with tempfile.TemporaryDirectory() as td:
            folder = fixture(Path(td), positive=True)
            p = folder / (CANARY + ".json")
            obj = json.loads(p.read_text())
            obj["analysis"]["observations"][0]["support"]["commit"] = "f" * 40
            p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "FABRICATED_MODEL_SUCCESS"):
                audit(Path(td), RUN, SHA)

    def test_never_accepts_unsanctioned_model_fanout(self):
        with tempfile.TemporaryDirectory() as td:
            folder = fixture(Path(td), positive=True)
            p = folder / "SCOUT_SYNTH_00.json"
            obj = json.loads(p.read_text())
            obj["status"] = "OBSERVED_REPOSITORY_STATE"
            obj["model_error"] = None
            obj["analysis"]["summary"] = "Unverified generated summary"
            p.write_text(json.dumps(obj))
            summary = folder / "SWARM_SUMMARY.json"
            s = json.loads(summary.read_text())
            s["agents_model_synthesis_ok"] = 2
            summary.write_text(json.dumps(s))
            with self.assertRaisesRegex(ValueError, "UNAUTHORIZED_MODEL_FANOUT"):
                audit(Path(td), RUN, SHA)

    def test_missing_report_and_wrong_run_sha_are_hard_holds(self):
        with tempfile.TemporaryDirectory() as td:
            folder = fixture(Path(td))
            with self.assertRaisesRegex(ValueError, "SOURCE_OR_COMPLETENESS"):
                audit(Path(td), RUN, "c" * 40)
            (folder / "SCOUT_SYNTH_01.json").unlink()
            with self.assertRaisesRegex(ValueError, "MISSING_OR_EXTRA"):
                audit(Path(td), RUN, SHA)

    def test_spoofed_target_and_mutation_authority_are_refused(self):
        with tempfile.TemporaryDirectory() as td:
            folder = fixture(Path(td))
            p = folder / (CANARY + ".json")
            obj = json.loads(p.read_text())
            obj["authority"]["target_repository_write"] = True
            p.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError, "PROVENANCE_OR_AUTHORITY"):
                audit(Path(td), RUN, SHA)


if __name__ == "__main__":
    unittest.main()
