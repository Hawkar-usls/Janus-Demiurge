import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.essence_v45_peer_shadow import (
    CORPUS_SCHEMA, LABEL_SCHEMA, LOCK_SCHEMA, MODEL, PINNED_REVISION,
    inspect_record, preflight, read_corpus, sha, select_examples
)


def fixture():
    req = {
        "schema": "janus.open_llm.request.v1",
        "request_source": "github_issue",
        "issue_number": 39,
        "source_id": 1,
        "requested_by": "Hawkar-usls",
        "execution_authority": "TEXT_ONLY",
        "mode": "qwen",
        "prompt": "What is a witness?",
    }
    req["request_sha256"] = sha(req)
    dialogue = {"schema": "janus.open_llm.dialogue.v1", "request": req,
                "exchanges": [{"role": "initial", "model": MODEL, "text": "Answer"}],
                "final_text": "Answer"}
    dialogue["sha256"] = sha(dialogue)
    record = {
        "schema": CORPUS_SCHEMA, "source_sha256": dialogue["sha256"],
        "source_binding": {"kind": "ISSUE_AND_BOT_REPLY_DIGEST_MATCH"},
        "quality_is_independent_evidence": False,
        "model_weight_change": False, "auto_promotion_authority": False,
        "source_run_id": 2, "dialogue": dialogue,
    }
    record["record_sha256"] = sha(record)
    lock = {
        "schema": LOCK_SCHEMA, "base_model": MODEL, "base_revision": PINNED_REVISION,
        "max_steps": 8, "learning_rate": 0.0001, "seed": 4501, "lora_rank": 4,
        "production_admission": False, "sentinel_dispatch_allowed": False,
        "independent_exam_commitment_sha256": None,
        "independent_custodian": None,
    }
    return record, {"schema": LABEL_SCHEMA, "labels": {}}, lock


class ShadowGateTests(unittest.TestCase):
    def test_zero_verified_ground_truth_is_a_hold(self):
        record, labels, lock = fixture()
        self.assertIs(inspect_record(record), record["dialogue"])
        gate, examples = preflight([record], labels, lock)
        self.assertEqual(examples, [])
        self.assertEqual(gate["reviewed_training_pairs"], 0)
        self.assertFalse(gate["training_allowed"])
        self.assertFalse(gate["production_promotion_allowed"])
        self.assertFalse(gate["native_janus_checkpoint_modified"])
        self.assertFalse(gate["sentinel_dispatch_allowed"])
        self.assertIn("HOLD_PROSPECTIVE_EXAM_NOT_FROZEN", gate["blockers"])

    def test_corpus_tamper_or_authority_spoof_fails(self):
        record, _, _ = fixture()
        for key, value in (("quality_is_independent_evidence", True),
                           ("auto_promotion_authority", True),
                           ("model_weight_change", True)):
            bad = copy.deepcopy(record)
            bad[key] = value
            bad["record_sha256"] = sha({k: v for k, v in bad.items() if k != "record_sha256"})
            with self.assertRaises(ValueError):
                inspect_record(bad)
        record["dialogue"]["request"]["prompt"] = "changed"
        with self.assertRaises(ValueError):
            inspect_record(record)

    def test_unverified_model_answer_cannot_become_training_target(self):
        record, labels, _ = fixture()
        labels["labels"][record["source_sha256"]] = {
            "status": "APPROVED_FOR_SHADOW_TRAINING",
            "human_review_sources": ["https://example.org/one", "https://example.org/two"],
            "independent_evidence": True,
        }
        with self.assertRaisesRegex(ValueError, "MISSING_INDEPENDENT"):
            select_examples([record], labels)
        labels["labels"][record["source_sha256"]]["reference_answer"] = "A human verified corrected answer."
        e = select_examples([record], labels)
        self.assertEqual(e[0]["reference_answer"], "A human verified corrected answer.")
        self.assertNotEqual(e[0]["reference_answer"], record["dialogue"]["final_text"])

    def test_only_records_directory_and_sha_are_accepted(self):
        record, _, _ = fixture()
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "records").mkdir()
            (base / "records" / "a.json").write_text(json.dumps(record), encoding="utf-8")
            self.assertEqual(len(read_corpus(base)), 1)
            changed = copy.deepcopy(record)
            changed["record_sha256"] = "a" * 64
            (base / "records" / "b.json").write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_corpus(base)

    def test_unreviewed_train_lock_fails(self):
        record, labels, lock = fixture()
        lock["base_revision"] = "a" * 40
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_SHADOW"):
            preflight([record], labels, lock)


if __name__ == "__main__":
    unittest.main()
