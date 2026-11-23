"""Trinity R1.2: exact HF causal label alignment, new no-leakage firstlook."""
import unittest

from tools import trinity_parental_contract as c
from tools import trinity_r11_critic_eval as previous
from tools import trinity_r12_critic_train as train
from tools import trinity_r12_critic_eval as evaluation


class TrinityR12LabelRescue(unittest.TestCase):
    def test_hf_causal_input_includes_full_prompt_and_target(self):
        input_ids,labels=train.pack_hf_causal_labels([10,11,12],[20,21])
        self.assertEqual(input_ids,[10,11,12,20,21])
        self.assertEqual(labels,[-100,-100,-100,20,21])
        self.assertEqual(len(input_ids),len(labels))
        # HF shifts internally; input token index 2 predicts first answer at 3.
        self.assertEqual(labels[3],20)

    def test_no_preshifted_labels(self):
        ids,labels=train.pack_hf_causal_labels([3,4,5,6],[7,8,9])
        self.assertEqual(ids[-3:],[7,8,9])
        self.assertEqual(labels[:4],[-100]*4)
        self.assertEqual(labels[4:],[7,8,9])

    def test_incomplete_or_invalid_training_pack_fails(self):
        for p,t in (([],[1]),([1],[]),([1.0],[2]),([1],[-1]),("1",[2])):
            with self.subTest((p,t)),self.assertRaisesRegex(ValueError,"R12_INVALID_CAUSAL_PACK"):
                train.pack_hf_causal_labels(p,t)

    def test_new_model_still_uses_only_symbolically_verified_training_set(self):
        self.assertEqual(train.verify_train_rows(train.train_rows()),
                         c.digest(train.train_rows()))
        self.assertEqual(len(train.train_rows()),144)

    def test_r12_exam_is_not_reused_r11_or_train_data(self):
        cases=evaluation.rows()
        self.assertEqual(len(cases),36)
        self.assertEqual(len({r["prompt"] for r in cases}),36)
        self.assertFalse({r["prompt"] for r in cases}&
                         {r["prompt"] for r in train.train_rows()})
        self.assertFalse({r["prompt"] for r in cases}&
                         {r["prompt"] for r in previous.rows()})
        self.assertTrue(all(r["partition"]=="NEW_INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND"
                            for r in cases))

    def test_no_new_physics_or_student_graduation_through_critic(self):
        rows=evaluation.rows()
        expected=["YES" if x["kind"]=="CORRECT" else "NO" for x in rows]
        result=evaluation.evaluate_predictions(rows,["YES"]*36,expected,"a"*64)
        self.assertTrue(result["status"].endswith("EXTERNAL_HOLD"))
        self.assertFalse(result["may_replace_parent_critic"])
        self.assertFalse(result["may_graduate_trinity"])
        self.assertFalse(result["external_independent_exam"])

    def test_all_yes_cannot_be_promoted(self):
        rows=evaluation.rows()
        result=evaluation.evaluate_predictions(rows,["YES"]*36,["YES"]*36,"a"*64)
        self.assertEqual(result["status"],"HOLD_CRITIC_GENERALIZATION_NOT_PROVEN")


if __name__=="__main__":
    unittest.main()
