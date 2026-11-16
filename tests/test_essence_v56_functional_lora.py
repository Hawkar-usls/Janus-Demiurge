"""ESSENCE v5.6 independent mathematical oracle and functional admission gates."""
from __future__ import annotations
import copy
from pathlib import Path
import unittest
from tools import essence_v56_functional_lora as v
from tools import essence_v48_recurrent_state as state


class FunctionalV56Tests(unittest.TestCase):
    def memory(self):
        return [{"source_repo":"Hawkar-usls/Hrain","answer":"sample",
                 "fact_digest":"a"*64,
                 "training_verified_by_repository_sha":True,
                 "prompt":"test"} for _ in range(4)]

    def fake_plan(self):
        train=v.rows(v.LOCK["training_seed"],96,"train")
        return v.sealed({"schema":v.PLAN,"action":"TRAIN_SHADOW",
            "lock_sha256":state.digest(v.LOCK),
            "parent_generation":3,"parent_adapter_sha256":v.PARENT_SHA,
            "parent_lineage_sha256":v.PARENT_LINEAGE,
            "parent_path":v.PARENT_PATH,
            "training_rows_sha256":state.digest(train),
            "training_seed":v.LOCK["training_seed"],"training_count":96,
            "heldout_seed":v.LOCK["heldout_seed"],"heldout_count":36,
            "memory_replay":self.memory(),
            "production_promotion":False,"sentinel_dispatch":False,
            "holdout_rows_not_generated":True,"external_validation":False})

    def test_frozen_rules_before_first_exam(self):
        self.assertEqual(v.locked(),v.LOCK)
        self.assertEqual(v.LOCK["parent_generation"],3)
        self.assertEqual(v.LOCK["parent_adapter_sha256"],v.PARENT_SHA)
        self.assertEqual(v.LOCK["steps"],160)
        self.assertEqual(v.LOCK["minimum_new_heldout_exact_answers"],2)
        self.assertEqual(v.LOCK["attempt_budget"],1)
        self.assertFalse(v.LOCK["production_promotion"])
        self.assertFalse(v.LOCK["sentinel_dispatch"])

    def test_math_oracle_is_deterministic_and_split_disjoint(self):
        a=v.rows(56011,96,"train")
        b=v.rows(56071,36,"heldout")
        self.assertEqual(a,v.rows(56011,96,"train"))
        self.assertEqual(b,v.rows(56071,36,"heldout"))
        self.assertEqual(len({x["prompt"] for x in a}),96)
        self.assertEqual(len({x["prompt"] for x in b}),36)
        self.assertFalse({x["prompt"] for x in a}&{x["prompt"] for x in b})
        self.assertEqual(set(x["category"] for x in a),
                         {"addition","subtraction","multiplication",
                          "modulus","gcd","shortest_path"})
        self.assertEqual(set(x["category"] for x in b),
                         {"addition","subtraction","multiplication",
                          "modulus","gcd","shortest_path"})
        self.assertEqual(sum(x["category"]=="shortest_path" for x in b),6)

    def test_oracle_cannot_inject_new_seed_or_heldout_during_training(self):
        for bad in ((1,36,"heldout"),(56011,36,"heldout"),
                    (56071,96,"train"),(56072,36,"heldout")):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError,"UNREGISTERED_ORACLE_SEED"):
                    v.rows(*bad)

    def test_task_signatures_not_provided_by_model(self):
        p=self.fake_plan()
        self.assertEqual(v.verify_plan(p),p)
        for k,value in (
           ("parent_generation",8),("parent_adapter_sha256","f"*64),
           ("training_rows_sha256","a"*64),("heldout_seed",0),
           ("heldout_count",999),("holdout_rows_not_generated",False),
           ("production_promotion",True),("sentinel_dispatch",True),
           ("external_validation",True)):
            bad=copy.deepcopy(p)
            bad[k]=value
            bad=v.sealed({x:y for x,y in bad.items() if x!="sha256"})
            with self.subTest(field=k):
                with self.assertRaises(ValueError):
                    v.verify_plan(bad)

    def test_no_disallowed_memory_as_ground_truth(self):
        p=self.fake_plan()
        p["memory_replay"][0]["source_repo"]="Hawkar-usls/unknown-untrusted"
        bad=v.sealed({k:x for k,x in p.items() if k!="sha256"})
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_MEMORY"):
            v.verify_plan(bad)

    def test_hold_if_functional_answers_not_new_or_retention_regresses(self):
        def metric(p,c,pp,cc):
            return {"parent_exact":p,"child_exact":c,"parent_nll":pp,
                    "child_nll":cc,"paired_nll_gain":round(pp-cc,7)}
        good={"fresh_functional":metric(8,10,2.1,1.7),
              "old_skill_retention":metric(5,5,1.4,1.45)}
        self.assertTrue(v.gate(good,2,0))
        self.assertFalse(v.gate(good,1,0))
        self.assertFalse(v.gate(good,2,1))
        bad=copy.deepcopy(good)
        bad["old_skill_retention"]["child_exact"]=4
        self.assertFalse(v.gate(bad,2,0))
        bad=copy.deepcopy(good)
        bad["fresh_functional"]["paired_nll_gain"]=-0.5
        self.assertFalse(v.gate(bad,2,0))

    def test_only_research_neural_proposal_not_production(self):
        script=(Path(__file__).resolve().parents[1]/
               "tools/essence_v56_functional_lora.py").read_text()
        self.assertIn('"heldout_rows_used_in_training":False',script)
        self.assertIn('"parent_restored_after_exam":True',script)
        self.assertIn('state.check_model(parent,PARENT_SHA,PARENT_LINEAGE)',script)
        self.assertIn('is_trainable=False',script)
        self.assertIn('"production_promotion":False',script)
        self.assertNotIn("exec(model_output)",script)


if __name__=="__main__":
    unittest.main()
