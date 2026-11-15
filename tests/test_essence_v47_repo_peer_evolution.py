import copy
import unittest
from pathlib import Path
from tools.essence_v47_repo_peer_evolution import (
    PARENT_ADAPTER_SHA, PARENT_RUN, TRAIN_KEYS, UNSEEN_KEYS,
    examples, expected_text, field_choice, freeze, question, sha, source_bytes_and_json,
    validate_lock, value_at, verify_freeze, checked, train, seal
)
from tools.essence_v46_oracle_descendant import read

LOCK=Path("research/essence/peer_v47/repo_lock.json")


class RepoPeerEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock=validate_lock(read(LOCK))
        cls.src,cls.manifest=source_bytes_and_json(".",cls.lock)

    def test_true_parent_and_no_production_authority(self):
        lock=self.lock
        self.assertEqual(lock["parent_artifact_run_id"],PARENT_RUN)
        self.assertEqual(lock["parent_adapter_sha256"],PARENT_ADAPTER_SHA)
        for prop in ("model_replies_are_ground_truth","automatic_production_promotion",
                     "native_janus_checkpoint_edit","sentinel_dispatch",
                     "independent_external_validation"):
            self.assertIs(lock[prop],False)

    def test_verified_repo_paths_only_and_split_integrity(self):
        self.assertEqual(len(TRAIN_KEYS),12)
        self.assertEqual(len(UNSEEN_KEYS),6)
        self.assertFalse(set(TRAIN_KEYS)&set(UNSEEN_KEYS))
        train=examples(self.manifest,TRAIN_KEYS)
        test=examples(self.manifest,UNSEEN_KEYS)
        self.assertEqual(train[3]["answer"],"128")
        self.assertEqual(test[0]["answer"],"128")
        self.assertEqual(train[10]["answer"],"false")
        self.assertEqual(len({x["key"] for x in train+test}),18)
        with self.assertRaises(ValueError):
            value_at(self.manifest,"../../.github/token")
        with self.assertRaises(ValueError):
            value_at(self.manifest,"architecture.NOT_A_REAL_FIELD")

    def test_first_freeze_is_deterministic(self):
        f1=freeze(".",self.lock)
        f2=freeze(".",self.lock)
        self.assertEqual(f1,f2)
        self.assertEqual(verify_freeze(".",self.lock,f1),f1)
        self.assertEqual(f1["source_manifest_sha256"],self.src)
        self.assertTrue(f1["repository_source_not_peer_opinion"])
        self.assertFalse(f1["independent_external_exam"])
        tampered=dict(f1,unseen_exam_sha256="f"*64)
        with self.assertRaises(ValueError):
            verify_freeze(".",self.lock,tampered)
        tampered["sha256"]=sha({k:v for k,v in tampered.items() if k!="sha256"})
        with self.assertRaisesRegex(ValueError,"COMMITMENT_DRIFT"):
            verify_freeze(".",self.lock,tampered)

    def test_model_cannot_choose_arbitrary_file_paths(self):
        self.assertEqual(field_choice("architecture.n_heads"),"architecture.n_heads")
        self.assertIsNone(field_choice("secrets/private.txt"))
        self.assertIsNone(field_choice("model_id then world_memory"))
        self.assertIn("architecture.n_heads",question("architecture.n_heads",True))

    def test_cannot_mutate_train_authority_or_source_key_lists(self):
        for key,val in [("sentinel_dispatch",True),
                        ("native_janus_checkpoint_edit",True),
                        ("model_replies_are_ground_truth",True),
                        ("train_steps",999),
                        ("train_keys",list(reversed(TRAIN_KEYS))),
                        ("parent_adapter_sha256","f"*64)]:
            drift=copy.deepcopy(self.lock)
            drift[key]=val
            with self.assertRaisesRegex(ValueError,"DRIFTED"):
                validate_lock(drift)

    def test_untrusted_peer_cannot_trigger_training(self):
        # Deliberately avoid importing/installing torch or model weights.
        fake=seal({
            "schema":"janus.essence.source_grounded_peer_dialogue/4.7",
            "source_freeze_sha256":freeze(".",self.lock)["sha256"],
            "parent_adapter_sha256":PARENT_ADAPTER_SHA,
            "peer_output_used_as_training_target":True,
            "selected_verified_key":"model_id",
            "source_ground_truth":expected_text(self.manifest["model_id"]),
        })
        with self.assertRaisesRegex(ValueError,"UNTRUSTED_PEER"):
            train(".",self.lock,freeze(".",self.lock),"nonexistent",fake,"nonexistent")

    def test_model_questions_and_holdout_do_not_equal_training_text(self):
        train_rows=examples(self.manifest,TRAIN_KEYS)
        unseen_rows=examples(self.manifest,UNSEEN_KEYS)
        para=examples(self.manifest,TRAIN_KEYS,True)
        self.assertTrue(set(x["prompt"] for x in para).isdisjoint(
            set(x["prompt"] for x in train_rows)))
        self.assertTrue(set(x["prompt"] for x in unseen_rows).isdisjoint(
            set(x["prompt"] for x in train_rows)))


if __name__=="__main__":
    unittest.main()
