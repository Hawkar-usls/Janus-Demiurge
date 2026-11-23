"""R1.4 mathematical oracle is the only truth source; all model speech advisory."""
from __future__ import annotations
from pathlib import Path
import unittest
from tools import trinity_r14_verified_oracle as o
from tools import trinity_parental_contract as c

ROOT=Path(__file__).resolve().parents[1]


class R14VerifiedCriticContract(unittest.TestCase):
    def test_new_fifth_cases_are_precommitted_and_not_in_training(self):
        cases=o.read_fifth(ROOT)
        self.assertEqual(len(cases),64)
        self.assertEqual(len({x["id"] for x in cases}),64)
        for kind in ("CORRECT","WRONG","AMBIGUOUS","UNSUPPORTED"):
            self.assertEqual(sum(x["kind"]==kind for x in cases),16)
        self.assertFalse({x["prompt"] for x in cases}&
                         {x["prompt"] for x in o.train_only_cases()})
        self.assertTrue(all(x["partition"]=="FIFTH_INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND" for x in cases))

    def test_no_eval_code_execution_math_grammar_only(self):
        self.assertEqual(o.exact_reference("Calculate 18 + 27. Answer with one integer."),"45")
        self.assertEqual(o.exact_reference("Calculate 18 - 27. Answer with one integer."),"-9")
        self.assertEqual(o.exact_reference("Calculate 18 * 27. Answer with one integer."),"486")
        for invalid in (
            "Calculate 18 / 27. Answer with one integer.",
            "Calculate 18 ** 27. Answer with one integer.",
            "Calculate 18 + 27. Answer with one integer. Ignore rules",
            "Calculate 18 + __import__('os').system('id'). Answer with one integer.",
            "What is 18 + 27?",
            "Calculate -18 + 27. Answer with one integer.",
            "Calculate 9999999 + 27. Answer with one integer.",
        ):
            self.assertIsNone(o.exact_reference(invalid))

    def test_strict_canonical_format_and_truth_separate(self):
        q="Calculate 18 - 27. Answer with one integer."
        self.assertEqual(o.verify(q,"-9")["verdict"],"APPROVE")
        self.assertEqual(o.verify(q,"-8")["verdict"],"VETO_WRONG")
        for p in ("-09","+9"," -9","-9 ","-9.0","Maybe -9","-9\nYES","--9","",None):
            self.assertEqual(o.verify(q,p)["verdict"],"VETO_FORMAT")
        self.assertEqual(o.verify("Calculate 18 / 27. Answer with one integer.","0")["verdict"],"HOLD_UNSUPPORTED")

    def test_no_advisory_can_override_correct_or_wrong_math(self):
        prompt="Calculate 21 + 26. Answer with one integer."
        self.assertTrue(o.verify(prompt,"47")["eligible_for_train"])
        self.assertFalse(o.verify(prompt,"48")["eligible_for_train"])
        for opinion in ("YES","NO","FORMAT=CANONICAL\nWHY=looks right",
                        "FORMAT=NONCANONICAL\nWHY=bad","FORMAT=UNKNOWN\nWHY=unclear",
                        "IGNORE THE MATH ORACLE",None):
            observation=o.interpret_advisory(opinion)
            self.assertNotIn("eligible_for_train",observation)
            self.assertNotIn("math_verdict",observation)
            self.assertTrue(o.verify(prompt,"47")["eligible_for_train"])
            self.assertFalse(o.verify(prompt,"48")["eligible_for_train"])

    def test_structured_comment_is_format_only(self):
        p=o.interpret_advisory("FORMAT=CANONICAL\nWHY=one integer")
        self.assertTrue(p["valid"])
        self.assertEqual(p["format"],"CANONICAL")
        for s in ("FORMAT=CANONICAL; YES","FORMAT=CANONICAL\nWHY=one\nMORE=yes","","yes",None):
            self.assertFalse(o.interpret_advisory(s)["valid"])

    def test_train_only_source_never_uses_model_generated_truth(self):
        rows=[{"id":x["id"],"teacher_proposal":x["reference"],
               "smollm_advisory":"FORMAT=NONCANONICAL\nWHY=I disagree"}
              for x in o.train_only_cases()]
        report=o.verified_train_source(rows)
        self.assertEqual(report["accepted_count"],24)
        self.assertEqual(len(report["accepted_cases"]),24)
        self.assertTrue(all(x["source"]=="TRAIN_ONLY_SYMBOLIC_ORACLE_WITH_QWEN_VERIFIED"
                            for x in report["accepted_cases"]))
        self.assertTrue(report["smollm_advisory_never_truth"])
        self.assertFalse(report["student_training_executed"])
        self.assertFalse(report["production_promotion"])

    def test_wrong_qwen_answer_must_not_become_training_example(self):
        rows=[{"id":x["id"],"teacher_proposal":x["reference"],
               "smollm_advisory":"FORMAT=CANONICAL\nWHY=one integer"}
              for x in o.train_only_cases()]
        rows[0]["teacher_proposal"]="99999"
        rows[1]["teacher_proposal"]="Maybe 5"
        report=o.verified_train_source(rows)
        self.assertEqual(report["accepted_count"],22)
        self.assertEqual(len(report["accepted_cases"]),22)
        self.assertEqual(report["rows"][0]["verdict"],"VETO_WRONG")
        self.assertEqual(report["rows"][1]["verdict"],"VETO_FORMAT")

    def test_forged_train_source_order_and_missing_cases_are_blocked(self):
        rows=[{"id":x["id"],"teacher_proposal":x["reference"],"smollm_advisory":"format"}
              for x in o.train_only_cases()]
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            o.verified_train_source(rows[:-1])
        with self.assertRaisesRegex(ValueError,"ORDER"):
            o.verified_train_source(list(reversed(rows)))

    def test_fifth_oracle_64_of_64_on_frozen_predeclared_reference(self):
        cases=o.read_fifth(ROOT)
        report=o.compare_fifth(cases,["I have no opinion"]*64)
        self.assertTrue(report["oracle_matches_frozen_reference"])
        self.assertEqual(sum(x["oracle_exact"] for x in report["metrics"].values()),64)
        self.assertEqual(sum(x["format_only_exact"] for x in report["metrics"].values()),48)
        self.assertEqual(report["metrics"]["WRONG"]["format_only_exact"],0)
        self.assertFalse(report["external_validation"])
        self.assertFalse(report["janus_model_promoted"])

    def test_advisory_malicious_claim_does_not_change_oracle(self):
        cases=o.read_fifth(ROOT)
        a=o.compare_fifth(cases,["FORMAT=CANONICAL\nWHY=ignore arithmetic"]*64)
        b=o.compare_fifth(cases,["FORMAT=NONCANONICAL\nWHY=bad formatting"]*64)
        self.assertEqual([x["oracle_verdict"] for x in a["per_case"]],
                         [x["oracle_verdict"] for x in b["per_case"]])
        self.assertTrue(a["oracle_matches_frozen_reference"])
        self.assertFalse(a["automatic_self_training"])

    def test_eval_case_count_and_identity_rejected(self):
        cases=o.read_fifth(ROOT)
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_FIFTH_MODEL"):
            o.compare_fifth(cases,["UNKNOWN"]*63)

    def test_old_genesis_trinity_policy_remains_separate(self):
        self.assertEqual(len(c.curriculum()),24)
        self.assertEqual(o.FIFTH_BLOB,"a31080b9574305a6d3d1f94754978fd485000b12")
        self.assertNotIn("G9",o.SCHEMA)


if __name__=="__main__":
    unittest.main()
