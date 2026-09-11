import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from janus_model.extensions import trump_frontier_memory as tfm


class TrumpFrontierMemoryTests(unittest.TestCase):
    def make_repo(self, root: Path) -> tuple[Path, dict]:
        repo = root / "source"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "JANUS test"], check=True)
        (repo / "proof").mkdir()
        (repo / "proof" / "contract.json").write_text('{"gate":"OPEN","note":"useful exact proof context"}\n', encoding="utf-8")
        fake_token = "gh" + "p_" + ("A" * 32)
        (repo / "secrets.json").write_text(json.dumps({"token": fake_token}) + "\n", encoding="utf-8")
        (repo / "notes.md").write_text("bounded research note\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)
        commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        tree = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD^{tree}"], text=True).strip()

        rows = []
        for rel in ["proof/contract.json", "secrets.json", "notes.md"]:
            raw = (repo / rel).read_bytes()
            rows.append({
                "path": rel,
                "git_blob_sha": tfm.git_blob_sha1(raw),
                "size_bytes": len(raw),
            })
        intake = {
            "schema": tfm.INTAKE_SCHEMA,
            "status": "READ_ONLY_EXACT_COMMIT_INTAKE",
            "attention_id": "jta-test",
            "repository": tfm.EXPECTED_REPOSITORY,
            "selected_ref": "refs/heads/research/trump-test",
            "selected_commit": commit,
            "tree_sha": tree,
            "commit_subject": "fixture",
            "author_date": "2026-09-11T00:00:00Z",
            "relevant_file_count_capped": len(rows),
            "relevant_files": rows,
            "P_VS_NP": "OPEN",
            "authority": {
                "read_only": True,
                "source_repository_mutated": False,
                "active_lineage_changed": False,
                "proof_ladder_changed": False,
                "theorem_promoted": False,
                "runtime_promoted": False,
                "authority_delta": 0,
            },
        }
        intake["intake_sha256"] = hashlib.sha256(tfm.canonical_bytes(intake)).hexdigest()
        return repo, intake

    def test_build_memory_is_read_only_training_only_and_secret_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, intake = self.make_repo(root)
            intake_path = root / "intake.json"
            intake_path.write_text(json.dumps(intake), encoding="utf-8")
            out_text = root / "memory.txt"
            out_manifest = root / "manifest.json"
            manifest = tfm.build_memory(repo, intake_path, out_text, out_manifest)

            text = out_text.read_text(encoding="utf-8")
            self.assertIn("proof/contract.json", text)
            self.assertIn("useful exact proof context", text)
            self.assertIn("notes.md", text)
            self.assertNotIn("secrets.json", text)
            self.assertNotIn("gh" + "p_", text)
            self.assertEqual(manifest["status"], "READY_READ_ONLY_TRAINING_MEMORY")
            self.assertTrue(manifest["training_only"])
            self.assertFalse(manifest["adaptive_holdout_inclusion"])
            self.assertFalse(manifest["frozen_anchor_inclusion"])
            self.assertFalse(manifest["training_material_is_truth"])
            self.assertFalse(manifest["contribution_grants_authority"])
            self.assertFalse(manifest["source_execution"])
            self.assertFalse(manifest["cross_repository_write"])
            self.assertEqual(manifest["P_VS_NP"], "OPEN")
            self.assertEqual(manifest["included_file_count"], 2)
            self.assertIn(
                {"path": "secrets.json", "reason": "SECRETISH_PATH"},
                manifest["skipped_files"],
            )

    def test_authority_leak_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _repo, intake = self.make_repo(root)
            intake["authority"]["runtime_promoted"] = True
            unsigned = dict(intake)
            unsigned.pop("intake_sha256", None)
            intake["intake_sha256"] = hashlib.sha256(tfm.canonical_bytes(unsigned)).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "AUTHORITY_REJECTED"):
                tfm.validate_intake(intake)

    def test_blob_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, intake = self.make_repo(root)
            intake["relevant_files"][0]["git_blob_sha"] = "0" * 40
            unsigned = dict(intake)
            unsigned.pop("intake_sha256", None)
            intake["intake_sha256"] = hashlib.sha256(tfm.canonical_bytes(unsigned)).hexdigest()
            intake_path = root / "intake.json"
            intake_path.write_text(json.dumps(intake), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "BLOB_MISMATCH"):
                tfm.build_memory(repo, intake_path, root / "memory.txt", root / "manifest.json")


if __name__ == "__main__":
    unittest.main()
