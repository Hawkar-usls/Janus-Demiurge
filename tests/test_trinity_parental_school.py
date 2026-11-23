"""Safety and contract tests for the GitHub-native Trinity parental school.

Synthetic tests verify contracts ONLY; they are not evidence of trained
JANUS gain or that Qwen/SmolLM performed inference on this runner.
"""
import copy
import json
import unittest
from tools import trinity_parental_contract as c
from tools import trinity_parental_cpu as cpu

class TrinityParentSchoolContracts(unittest.TestCase):
    def test_original_computational_role_map_not_theology(self):
        self.assertEqual(set(c.ROLES),{
            "father_strategist","son_seer","spirit_executor","sovereign_gate"})
        self.assertIn("Qwen",c.ROLES["father_strategist"])
        self.assertIn("JANUS",c.ROLES["son_seer"])

    def test_both_cpu_parent_revisions_are_fixed_and_different(self):
        self.assertEqual(c.QWEN["revision"],"7ae557604adf67be50417f59c2c2f167def9a775")
        self.assertEqual(c.SMOL["revision"],"12fd25f77366fa6b3b4b768ec3050bf629380bac")
        self.assertNotEqual(c.QWEN["repo"],c.SMOL["repo"])

    def test_curriculum_is_train_only_and_deterministic(self):
        t=c.curriculum()
        self.assertEqual(t,c.curriculum())
        self.assertEqual(len(t),24)
        self.assertEqual(len({v["id"] for v in t}),24)
        self.assertEqual(set(x["partition"] for x in t),{"TRAIN_ONLY"})
        for x in t:
            self.assertIn("Compute",x["prompt"])
            self.assertEqual(x["source"],"DETERMINISTIC_SYMBOLIC_ORACLE")

    def test_oracle_rejects_wrong_qwen_outputs_even_if_critic_agrees(self):
        t=c.curriculum()
        rows=[{"id":x["id"],"teacher_text":"99999","critic_text":"YES"} for x in t]
        r=c.teach_gate(rows)
        self.assertEqual(sum(x["eligible_for_train"] for x in r),0)
        self.assertTrue(all(not x["teacher_proposed_correct"] for x in r))

    def test_smol_critic_veto_over_correct_teacher(self):
        t=c.curriculum()
        rows=[{"id":x["id"],"teacher_text":x["expected"],"critic_text":"NO"} for x in t]
        self.assertEqual(sum(r["eligible_for_train"] for r in c.teach_gate(rows)),0)

    def test_verified_teacher_proposals_are_train_only(self):
        t=c.curriculum()
        rows=[{"id":x["id"],"teacher_text":x["expected"],"critic_text":"YES"} for x in t]
        self.assertEqual(sum(r["eligible_for_train"] for r in c.teach_gate(rows)),24)

    def test_teacher_extra_prose_is_not_mathematical_truth(self):
        self.assertIsNone(c.answer("The answer is 12"))
        self.assertIsNone(c.answer("-4"))
        self.assertIsNone(c.answer("0004"))
        self.assertEqual(c.answer("14\n"),"14")

    def test_synthetic_success_is_review_only_not_auto_promotion(self):
        base={n:[False]*64 for n in ("qwen","smollm","janus_incumbent","janus_candidate")}
        base["qwen"][:5]=[True]*5
        base["smollm"][5:8]=[True]*3
        base["janus_incumbent"][8:10]=[True]*2
        base["janus_candidate"][:12]=[True]*12
        result=c.decide(base,candidate_sha="b"*64,checkpoint_sha="a"*64,first_look=True)
        self.assertEqual(result["new_beyond_all_parents"],2)
        self.assertTrue(result["eligible_for_review"])
        self.assertFalse(result["may_promote_native_model"])
        self.assertFalse(result["automatic_self_training_enabled"])
        self.assertEqual(result["status"],"ELIGIBLE_FOR_HUMAN_REVIEW_NOT_PRODUCTION")

    def test_student_loses_any_solved_case_fails_even_if_many_new_correct(self):
        base={n:[False]*64 for n in ("qwen","smollm","janus_incumbent","janus_candidate")}
        base["qwen"][0]=True
        base["janus_candidate"][1:25]=[True]*24
        result=c.decide(base,candidate_sha="b"*64,checkpoint_sha="a"*64,first_look=True)
        self.assertEqual(result["previously_solved_lost"],1)
        self.assertFalse(result["eligible_for_review"])

    def test_no_real_first_look_no_review(self):
        base={n:[False]*64 for n in ("qwen","smollm","janus_incumbent","janus_candidate")}
        base["janus_candidate"][:10]=[True]*10
        result=c.decide(base,candidate_sha="b"*64,checkpoint_sha="a"*64,first_look=False)
        self.assertFalse(result["eligible_for_review"])

    def test_incomplete_parent_votes_and_unsigned_weights_fail(self):
        base={n:[False]*64 for n in ("qwen","smollm","janus_incumbent","janus_candidate")}
        with self.assertRaisesRegex(ValueError,"TRINITY_MISSING_PARENT"):
            c.decide({k:v for k,v in base.items() if k!="smollm"},
                     candidate_sha="b"*64,checkpoint_sha="a"*64,first_look=True)
        with self.assertRaisesRegex(ValueError,"TRINITY_CANDIDATE_NOT_NEW"):
            c.decide(base,candidate_sha="a"*64,checkpoint_sha="a"*64,first_look=True)

    def test_receipt_digest_tampering_fail_closed(self):
        doc=c.sealed({"status":"HOLD","production_promotion":False})
        c.checked_seal(doc)
        altered=copy.deepcopy(doc)
        altered["production_promotion"]=True
        with self.assertRaisesRegex(ValueError,"TRINITY_RECEIPT_DIGEST_MISMATCH"):
            c.checked_seal(altered)

    def test_atomic_output_will_not_overwrite(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"receipt.json"
            cpu.save_new(p,{"proof":False})
            with self.assertRaisesRegex(ValueError,"TRINITY_OUTPUT_MUST_BE_NEW"):
                cpu.save_new(p,{"proof":True})

if __name__=="__main__":
    unittest.main()
