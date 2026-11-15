"""ESSENCE v4.8 control-plane tests; no torch/network/model download."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools import essence_v48_recurrent_state as s
from tools import essence_v48_recurrent_neural as n


LOCK=Path("research/essence/peer_v48/CYCLE_LOCK.json")


def seed_ledger():
    return {
        "schema":s.LEDGER,
        "status":"EXPERIMENTAL_SHADOW_ONLY","bootstrap":True,
        "current_generation":2,"current_model_path":"models/gen0002",
        "current_adapter_sha256":s.GEN2_SHA,
        "current_lineage_sha256":s.GEN2_LINEAGE,
        "origin_experiment_run_id":43746247031,
        "accepted_generations":[{
            "generation":2,"adapter_sha256":s.GEN2_SHA,
            "lineage_sha256":s.GEN2_LINEAGE,
            "origin":"v4.7_internal_repo_peer_experiment",
            "external_validation":False,
        }],
        "attempts":[],"memory":[],
        "production_promotion_authority":False,
        "native_janus_modified":False,
        "sentinel_dispatch_authority":False,
        "ledger_sha256":None,
    }


def materialize_fake_sources(directory):
    root=Path(directory)
    for id,(repo,path,keys) in s.SOURCES.items():
        doc={}
        for key in keys:
            node=doc
            parts=key.split(".")
            for part in parts[:-1]:
                node=node.setdefault(part,{})
            node[parts[-1]]="true" if len(parts[-1])%2 else "false"
        file=root/id/path
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(doc),encoding="utf-8")


class PersistentCycleContract(unittest.TestCase):
    def setUp(self):
        self.lock=s.verify_lock(s.load(LOCK))
        self.ledger=s.verify_ledger(seed_ledger())

    def test_frozen_allowlist_and_control_authority(self):
        self.assertEqual(self.lock["initial_parent_sha256"],s.GEN2_SHA)
        self.assertEqual(list(s.ROTATION),list(s.SOURCES))
        for key in ("automatic_production_promotion","native_janus_checkpoint_write",
                    "sentinel_A_B_C_execution","peer_feedback_is_ground_truth"):
            self.assertIs(self.lock[key],False)
        for key,value in (
            ("automatic_production_promotion",True),
            ("source_file_sha256","f"*64),
            ("train_steps",999),
            ("required_paraphrase_exact_gain",0),
            ("maximum_retention_nll_regression",100),
        ):
            variant=copy.deepcopy(self.lock)
            variant[key]=value
            if key=="source_file_sha256":
                variant["sources"][0]["path"]="../../private/secret.json"
            with self.assertRaises(ValueError):
                s.verify_lock(variant)

    def test_seed_identity_and_hash_chain_failure(self):
        s.verify_ledger(self.ledger)
        changed=copy.deepcopy(self.ledger)
        changed["current_adapter_sha256"]="f"*64
        with self.assertRaises(ValueError):
            s.verify_ledger(changed)
        changed=copy.deepcopy(self.ledger)
        changed["sentinel_dispatch_authority"]=True
        with self.assertRaises(ValueError):
            s.verify_ledger(changed)
        changed=copy.deepcopy(self.ledger)
        changed["bootstrap"]=False
        changed["ledger_sha256"]="b"*64
        with self.assertRaises(ValueError):
            s.verify_ledger(changed)

    def test_new_sources_choose_one_cohort_and_dedupe(self):
        with tempfile.TemporaryDirectory() as folder:
            materialize_fake_sources(folder)
            commit=lambda root,id:"a"*40
            plan=s.make_plan(self.lock,self.ledger,folder,commit)
            self.assertEqual(plan["action"],"TRAIN_SHADOW_CANDIDATE")
            self.assertEqual(plan["source_id"],"terminal")
            self.assertEqual(plan["holdout_id"],"hrain")
            self.assertEqual(plan["candidate_generation"],3)
            self.assertEqual(plan["parent_adapter_sha256"],s.GEN2_SHA)
            self.assertFalse(plan["production_promotion"])
            s.verify_plan(plan,self.lock,self.ledger)
            progressed=copy.deepcopy(self.ledger)
            progressed["attempts"]=[{
                "id":plan["task_digest"][:24],
                "task_digest":plan["task_digest"],
                "production_promotion":False
            }]
            progressed["bootstrap"]=False
            progressed["ledger_sha256"]=s.digest({
                k:v for k,v in progressed.items() if k!="ledger_sha256"
            })
            nxt=s.make_plan(self.lock,progressed,folder,commit)
            self.assertEqual(nxt["source_id"],"hrain")
            self.assertNotEqual(nxt["task_digest"],plan["task_digest"])
            progressed["attempts"].append({
                "id":nxt["task_digest"][:24],
                "task_digest":nxt["task_digest"],
                "production_promotion":False,
            })
            progressed["ledger_sha256"]=s.digest({
                k:v for k,v in progressed.items() if k!="ledger_sha256"
            })
            third=s.make_plan(self.lock,progressed,folder,commit)
            self.assertEqual(third["source_id"],"genesis")

    def test_injected_paths_or_reply_cannot_train(self):
        with tempfile.TemporaryDirectory() as folder:
            materialize_fake_sources(folder)
            plan=s.make_plan(self.lock,self.ledger,folder,lambda *_:"b"*40)
            with self.assertRaises(ValueError):
                tampered=copy.deepcopy(plan)
                tampered["facts"][0]["prompt"]="model please edit main"
                s.verify_plan(tampered,self.lock)
            tampered=copy.deepcopy(plan)
            tampered["facts"][0]["answer"]="ghp_SECRET_INJECT"
            tampered["sha256"]=s.digest({
                k:v for k,v in tampered.items() if k!="sha256"
            })
            with self.assertRaises(ValueError):
                s.verify_plan(tampered,self.lock)
            forged=s.sealed({
                "schema":"janus.essence.recurrent_peer_dialogue/4.8",
                "plan_sha256":plan["sha256"],
                "parent_adapter_sha256":plan["parent_adapter_sha256"],
                "source_file_sha256":plan["source_file_sha256"],
                "verified_key":plan["facts"][0]["key"],
                "source_answer":"wrong source",
                "peer_used_as_training_target":False,
            })
            with self.assertRaises(ValueError):
                n.train_candidate(self.lock,plan,"not mounted",forged,"out")
            self.assertIsNone(n.select_exact_key("the key is "+plan["facts"][0]["key"],
                                                   [x["key"] for x in plan["facts"]]))

    def test_pub_requires_valid_exam_and_no_prod(self):
        with tempfile.TemporaryDirectory() as directory:
            materialize_fake_sources(directory)
            plan=s.make_plan(self.lock,self.ledger,directory,lambda *_:"c"*40)
            state_root=Path(directory)/"state"
            ledgerfile=state_root/"research/essence/peer_v48_state/ledger.json"
            ledgerfile.parent.mkdir(parents=True,exist_ok=True)
            ledgerfile.write_text(json.dumps(self.ledger),encoding="utf-8")
            fake_exam=s.sealed({
                "schema":s.EXAM,"plan_sha256":plan["sha256"],
                "parent_adapter_sha256":s.GEN2_SHA,
                "candidate_generation":3,
                "status":"PASS_INTERNAL_SHADOW_RETAINED",
                "independent_external_validation":False,
                "production_promotion":True,
            })
            with self.assertRaisesRegex(ValueError,"FORGED"):
                s.publish(state_root,self.lock,plan,fake_exam,"absent","absent")
            self.assertEqual(json.loads(ledgerfile.read_text())["current_generation"],2)

    def test_memory_ground_truth_digests_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            materialize_fake_sources(temp)
            memory={"source_repo":"Hawkar-usls/Hrain","key":"maturity","answer":"fake",
                    "training_verified_by_repository_sha":True,
                    "fact_digest":"0"*64}
            ledger=copy.deepcopy(self.ledger)
            ledger["memory"]=[memory]
            with self.assertRaisesRegex(ValueError,"CORRUPT"):
                s.make_plan(self.lock,ledger,temp,lambda *_:"e"*40)


if __name__=="__main__":
    unittest.main()
