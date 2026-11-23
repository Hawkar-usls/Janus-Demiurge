"""Trinity R1.1 safety: train-only vs internal first-look separation and no promotion."""
import unittest
from tools import trinity_parental_contract as c
from tools import trinity_critic_probe as old_critic
from tools import trinity_r11_critic_train as critic_train
from tools import trinity_r11_critic_eval as critic_eval
from tools import trinity_r11_student_train as janus_train
from tools import trinity_r11_student_eval as janus_eval


class TrinityR11Tests(unittest.TestCase):
    def test_critic_train_split_is_exact_and_verified(self):
        rows=critic_train.train_rows()
        self.assertEqual(len(rows),144)
        self.assertEqual(critic_train.verify_train_rows(rows),c.digest(rows))
        self.assertEqual({x["partition"] for x in rows},{"TRAIN_ONLY_SYMBOLIC_TRUTH"})
        self.assertEqual({k:sum(x["kind"]==k for x in rows) for k in
                          ("CORRECT","INCORRECT","AMBIGUOUS")},
                          {"CORRECT":48,"INCORRECT":48,"AMBIGUOUS":48})

    def test_critic_internal_firstlook_disjoint_from_train_and_r1_public(self):
        rows=critic_eval.rows()
        seen={x["prompt"] for x in critic_train.train_rows()}
        published={old_critic.prompt(x) for x in old_critic.cases()}
        self.assertEqual(len(rows),36)
        self.assertFalse(seen & {x["prompt"] for x in rows})
        self.assertFalse(published & {x["prompt"] for x in rows})
        self.assertEqual(len({x["prompt"] for x in rows}),36)
        self.assertEqual({x["partition"] for x in rows},
                         {"INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND"})

    def test_critic_perfect_synthetic_predictions_still_no_approval(self):
        rows=critic_eval.rows()
        texts=["YES" if x["kind"]=="CORRECT" else "NO" for x in rows]
        result=critic_eval.evaluate_predictions(rows,["YES"]*len(rows),texts,"f"*64)
        self.assertEqual(result["status"],"INTERNAL_CRITIC_IMPROVEMENT_OBSERVED__EXTERNAL_HOLD")
        self.assertFalse(result["may_replace_parent_critic"])
        self.assertFalse(result["may_graduate_trinity"])
        self.assertFalse(result["external_independent_exam"])

    def test_critic_sycophant_fails_even_with_many_yes(self):
        rows=critic_eval.rows()
        result=critic_eval.evaluate_predictions(rows,["NO"]*len(rows),
                                                ["YES"]*len(rows),"f"*64)
        self.assertEqual(result["status"],"HOLD_CRITIC_GENERALIZATION_NOT_PROVEN")
        self.assertEqual(result["metrics"]["CANDIDATE"]["INCORRECT"]["APPROVE"],12)

    def test_critic_abstentions_not_counted_as_solved(self):
        rows=critic_eval.rows()
        result=critic_eval.evaluate_predictions(rows,["maybe"]*len(rows),
                                                ["maybe"]*len(rows),"f"*64)
        self.assertEqual(result["status"],"HOLD_CRITIC_GENERALIZATION_NOT_PROVEN")
        self.assertEqual(result["metrics"]["CANDIDATE"]["INCORRECT"]["VETO"],0)

    def test_critic_incomplete_firstlook_rejected(self):
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            critic_eval.evaluate_predictions(critic_eval.rows(),[],[],"f"*64)

    def test_janus_context_train_dataset_is_train_only(self):
        data=janus_train.train_rows()
        self.assertEqual(len(data),48)
        self.assertEqual({x["partition"] for x in data},{"TRAIN_ONLY"})
        self.assertEqual([sum(x["group"]==k for x in data) for k in
                          ("TRAIN_SHORT","TRAIN_MEDIUM","TRAIN_LONG")],[24,12,12])

    def test_janus_fresh_firstlook_separated_from_train_and_public_r1(self):
        data=janus_eval.cases()
        self.assertEqual(len(data),36)
        self.assertFalse({x["prompt"] for x in data}&
                         {x["prompt"] for x in janus_train.train_rows()})
        self.assertEqual([sum(x["group"]==k for x in data) for k in
                          ("SHORT","MEDIUM","LONG")],[12,12,12])
        self.assertTrue(all(x["partition"]=="INTERNAL_FIRSTLOOK_NOT_EXTERNAL_BLIND" for x in data))

    def test_no_student_eval_as_training(self):
        train_ids={x["id"] for x in janus_train.train_rows()}
        exam_ids={x["id"] for x in janus_eval.cases()}
        self.assertFalse(train_ids&exam_ids)
        self.assertFalse({x["prompt"] for x in janus_eval.cases()}&
                         {x["prompt"] for x in c.curriculum()})

    def test_training_functions_reject_out_of_scope_configs(self):
        self.assertEqual(janus_train.context_probe.LENGTHS,(128,256,512))
        self.assertNotEqual(c.QWEN,c.SMOL)


if __name__=="__main__":
    unittest.main()
