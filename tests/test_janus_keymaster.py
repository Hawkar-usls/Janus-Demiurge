import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from janus_model.corpus import _learning_cycle_digest, _load_keymaster
from janus_model.keymaster import _validate_config, eligible_tracked_files


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "janus_model/keymaster/PRIMARY_REPOSITORY_CONTRIBUTORS-v2.json"
HISTORICAL_V1 = ROOT / "janus_model/keymaster/PRIMARY_REPOSITORY_CONTRIBUTORS-v1.json"
CORE_5 = {
    "Hawkar-usls/TOPA",
    "Hawkar-usls/tranception",
    "Hawkar-usls/janus-lapis",
    "Hawkar-usls/janus-io-public",
    "Hawkar-usls/Fast-CAT-SHAiTan",
}
EXTENDED_3 = {
    "Hawkar-usls/Janus-Fundamentum",
    "Hawkar-usls/Demi_Head",
    "Hawkar-usls/aura-oracle-tg",
}
EXPECTED = CORE_5 | EXTENDED_3


class JanusKeymasterTests(unittest.TestCase):
    def test_exact_eight_primary_contributors_and_authority_firewalls(self):
        obj = json.loads(CONFIG.read_text(encoding="utf-8"))
        contributors, count = _validate_config(obj)
        self.assertEqual(obj["status"], "ACTIVE_REQUIRED_8_OF_8")
        self.assertEqual(count, 8)
        self.assertEqual(obj["contributor_count"], 8)
        self.assertEqual({row["repository"] for row in contributors}, EXPECTED)
        self.assertEqual(len({row["id"] for row in contributors}), 8)
        self.assertEqual({row["repository"] for row in contributors if row["cohort"] == "CORE_5"}, CORE_5)
        self.assertEqual({row["repository"] for row in contributors if row["cohort"] == "EXTENDED_3"}, EXTENDED_3)
        self.assertEqual(obj["learning"]["lane"], "TRAIN_ONLY")
        self.assertFalse(obj["learning"]["adaptive_holdout_inclusion"])
        self.assertFalse(obj["learning"]["frozen_anchor_inclusion"])
        self.assertFalse(obj["learning"]["training_material_is_truth"])
        self.assertFalse(obj["learning"]["contribution_grants_authority"])
        self.assertTrue(obj["attribution"]["enabled"])
        self.assertFalse(obj["attribution"]["single_run_establishes_causality"])
        self.assertFalse(obj["attribution"]["automatic_contributor_removal"])
        self.assertFalse(obj["firewalls"]["cross_repository_write"])
        self.assertFalse(obj["firewalls"]["source_execution"])
        self.assertEqual(obj["firewalls"]["authority_delta"], 0)
        self.assertFalse(obj["firewalls"]["tranception_native_janus_authorship_claim"])
        self.assertFalse(obj["firewalls"]["aura_output_is_evidence"])
        self.assertFalse(obj["firewalls"]["demihead_preference_is_evidence"])
        self.assertFalse(obj["firewalls"]["fundamentum_finite_result_is_global_theorem"])

    def test_historical_five_contract_remains_frozen_history(self):
        obj = json.loads(HISTORICAL_V1.read_text(encoding="utf-8"))
        self.assertEqual(obj["schema"], "janus.keymaster.primary_learning_contributors.v1")
        self.assertEqual(obj["status"], "ACTIVE_REQUIRED_5_OF_5")
        self.assertEqual(obj["contributor_count"], 5)
        self.assertEqual({row["repository"] for row in obj["contributors"]}, CORE_5)

    def test_keymaster_pack_requires_eight_nonzero_and_never_enters_eval(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = root / "training.txt"
            pack.write_text("bounded contribution", encoding="utf-8")
            raw = pack.read_bytes()
            rows = []
            ordered = sorted(CORE_5) + sorted(EXTENDED_3)
            for i, repo in enumerate(ordered):
                rows.append({
                    "id": f"C{i}",
                    "repository": repo,
                    "ref": "main",
                    "head_sha": f"{i + 1:040x}",
                    "provenance": "TEST",
                    "cohort": "CORE_5" if i < 5 else "EXTENDED_3",
                    "selected_files": [{"path": "README.md"}],
                    "selected_file_count": 1,
                    "contributed_bytes": 10,
                    "training_pack_sha256": "c" * 64,
                    "contribution_sha256": "a" * 64,
                })
            manifest = {
                "schema": "janus.keymaster.learning_contribution_manifest.v2",
                "config_schema": "janus.keymaster.primary_learning_contributors.v2",
                "status": "READY_8_OF_8",
                "required_contributor_count": 8,
                "contributor_count": 8,
                "contributors": rows,
                "training_only": True,
                "adaptive_holdout_inclusion": False,
                "frozen_anchor_inclusion": False,
                "training_material_is_truth": False,
                "contribution_grants_authority": False,
                "source_execution": False,
                "cross_repository_write": False,
                "authority_delta": 0,
                "contribution_sha256": "b" * 64,
                "training_pack_sha256": hashlib.sha256(raw).hexdigest(),
                "training_bytes": len(raw),
            }
            mpath = root / "manifest.json"
            mpath.write_text(json.dumps(manifest), encoding="utf-8")
            text, loaded = _load_keymaster(pack, mpath)
            self.assertEqual(text, "bounded contribution")
            self.assertEqual(loaded["contributor_count"], 8)
            bad = dict(manifest)
            bad["adaptive_holdout_inclusion"] = True
            mpath.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "EVALUATION_LEAKAGE"):
                _load_keymaster(pack, mpath)

    def test_keymaster_digest_is_a_learning_cycle_wake_input(self):
        registry = "1" * 64
        evaluation = "2" * 64
        first = _learning_cycle_digest(registry, "3" * 64, evaluation)
        second = _learning_cycle_digest(registry, "4" * 64, evaluation)
        self.assertNotEqual(first, second)
        self.assertEqual(first, _learning_cycle_digest(registry, "3" * 64, evaluation))

    def test_tracked_selection_excludes_generated_and_secretish_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            paths = {
                "README.md": "safe",
                "src/engine.py": "safe",
                "outbox/model.json": "generated",
                "receipts/r.json": "generated",
                "config.secret.json": "do not learn",
                "notes/token.txt": "do not learn",
                "binary.bin": "ignored",
            }
            for rel, text in paths.items():
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            selected = set(eligible_tracked_files(repo))
            self.assertIn("README.md", selected)
            self.assertIn("src/engine.py", selected)
            self.assertNotIn("outbox/model.json", selected)
            self.assertNotIn("receipts/r.json", selected)
            self.assertNotIn("config.secret.json", selected)
            self.assertNotIn("notes/token.txt", selected)
            self.assertNotIn("binary.bin", selected)


if __name__ == "__main__":
    unittest.main()
