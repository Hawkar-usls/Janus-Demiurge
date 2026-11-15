"""ESSENCE v4.9 zero-network contracts for prospective continual-learning trial."""
import copy
import re
import unittest
from unittest.mock import patch

from tools import essence_v46_oracle_descendant as v46
from tools import essence_v48_recurrent_state as state
from tools import essence_v49_continual as v49


class ProspectiveContinualTests(unittest.TestCase):
    def setUp(self):
        self.lock=v49.validate_lock(v49.read_locked(v49.LOCK_PATH))

    def test_fixed_parent_sources_and_immutable_exam_gates(self):
        self.assertEqual(self.lock["parent_tensor_sha256"],state.GEN2_SHA)
        self.assertEqual(self.lock["max_steps_per_candidate"],40)
        self.assertNotEqual(self.lock["new_train_source"]["repo"],
                            self.lock["prospective_holdout_source"]["repo"])
        for key in ("automatic_research_model_acceptance","production_model_updates",
                    "native_janus_weight_changes","sentinel_A_B_C_execution",
                    "human_independent_custodian","retune_after_exam"):
            self.assertIs(self.lock[key],False)
        for key,value in (
            ("learning_rate",0.008),
            ("max_steps_per_candidate",100),
            ("retune_after_exam",True),
            ("automated_research_model_acceptance",True),
        ):
            changed=copy.deepcopy(self.lock)
            changed[key]=value
            with self.assertRaises(ValueError):
                v49.validate_lock(changed)
        source=copy.deepcopy(self.lock)
        source["prospective_holdout_source"]["commit"]="0"*40
        with self.assertRaises(ValueError):
            v49.validate_lock(source)
        threshold=copy.deepcopy(self.lock)
        threshold["exam"]["legacy_exact_allowed_drop"]=8
        with self.assertRaises(ValueError):
            v49.validate_lock(threshold)

    def test_replay_and_naive_have_exact_equal_step_cost(self):
        new=[{"key":str(i),"prompt":"new-"+str(i),"answer":"X"} for i in range(6)]
        old=[{"key":str(i),"prompt":"old-"+str(i),"answer":"NORTH"} for i in range(8)]
        mem=[{"key":str(i),"prompt":"memory-"+str(i),"answer":"value"} for i in range(8)]
        naive=v49.make_schedule("naive",new,mem,old,self.lock)
        replay=v49.make_schedule("replay",new,mem,old,self.lock)
        self.assertEqual(len(naive),len(replay))
        self.assertEqual(len(naive),40)
        self.assertEqual({x["source_lane"] for x in naive},{"new"})
        self.assertEqual({x["source_lane"]:sum(y["source_lane"]==x["source_lane"]
                                             for y in replay) for x in replay},
                         {"new":20,"old":10,"memory":10})
        self.assertTrue(any(row["source_lane"]=="old" for row in replay))
        with self.assertRaises(ValueError):
            v49.make_schedule("unknown",new,mem,old,self.lock)

    def test_future_route_cases_are_new_oracle_correct(self):
        rows=v49.new_route_questions(self.lock["legacy_eval_fresh_count"])
        self.assertEqual(len(rows),16)
        tags=[]
        for row in rows:
            match=re.search(r"Decode tag ([KL]-[a-f0-9]{8})\.",row["prompt"])
            self.assertIsNotNone(match)
            tag=match.group(1)
            tags.append(tag)
            self.assertEqual(v46.oracle_a(tag),v46.oracle_b(tag))
            self.assertEqual(v46.oracle_a(tag),row["answer"])
        self.assertEqual(len(set(tags)),16)
        original=v46.sample_set(v46.lock_check(
            v46.read("research/essence/peer_v46/oracle_lock.json")),"train")
        self.assertTrue(set(tags).isdisjoint({x["code"] for x in original}))

    def test_freeze_payload_hash_binds_new_source_and_new_cases(self):
        def fake_source(directory,spec):
            keys=spec["keys"]
            data=[{"key":k,"prompt":state.question(spec["repo"],k),
                   "answer":"value-"+str(i)} for i,k in enumerate(keys)]
            return "a"*64 if "lapis" in spec["repo"] else "b"*64,data
        with patch.object(v49,"frozen_source",side_effect=fake_source):
            payload,commitment=v49.prepare_exam(self.lock,"lapis","cosmos")
        v49.validate_commitment(self.lock,payload,commitment)
        self.assertEqual(commitment["cohort_sizes"],
                         {"new_rephrased":6,"other_repo":6,"fresh_old_family":16})
        self.assertFalse(payload["training_job_access_authorized"])
        self.assertFalse(commitment["not_externally_independent"] is False)
        bad=copy.deepcopy(payload)
        bad["fresh_legacy_routes"][0]["answer"]="FALSE"
        with self.assertRaisesRegex(ValueError,"RECEIPT_TAMPER"):
            v49.validate_commitment(self.lock,bad,commitment)
        forged=copy.deepcopy(bad)
        forged["sha256"]=state.digest({k:v for k,v in forged.items() if k!="sha256"})
        with self.assertRaisesRegex(ValueError,"FROZEN_EXAM_PAYLOAD"):
            v49.validate_commitment(self.lock,forged,commitment)

    def test_replay_memory_source_authenticity(self):
        ledger={
            "schema":state.LEDGER,
            "bootstrap":False,
            "current_generation":2,
            "current_adapter_sha256":state.GEN2_SHA,
            "current_lineage_sha256":state.GEN2_LINEAGE,
            "accepted_generations":[{"generation":2,"adapter_sha256":state.GEN2_SHA}],
            "attempts":[],"memory":[],
            "production_promotion_authority":False,"native_janus_modified":False,
            "sentinel_dispatch_authority":False,
        }
        for repo in ("Hawkar-usls/Hrain","Hawkar-usls/Janus_Genesis"):
            for key in ("schema_id","project","portfolio_class","last_reviewed"):
                fact={
                    "source_repo":repo,"key":key,"answer":"verified",
                    "training_verified_by_repository_sha":True
                }
                ledger["memory"].append(dict(fact,fact_digest=state.digest(fact)))
        ledger["ledger_sha256"]=state.digest(ledger)
        self.assertEqual(len(v49.approved_memory(ledger)),8)
        poisoned=copy.deepcopy(ledger)
        poisoned["memory"][0]["answer"]="unknown"
        poisoned["ledger_sha256"]=state.digest({
            k:v for k,v in poisoned.items() if k!="ledger_sha256"})
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_G2_MEMORY"):
            v49.approved_memory(poisoned)

    def test_no_naive_tuning_to_old_examination(self):
        self.assertEqual(self.lock["exam"]["legacy_replay_must_beat_baseline_by"],1)
        self.assertEqual(self.lock["exam"]["source_paraphrase_exact_gain_min"],1)
        self.assertFalse(self.lock["human_independent_custodian"])


if __name__=="__main__":
    unittest.main()
