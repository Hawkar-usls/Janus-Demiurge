"""TRINITY R1.3: balance is verifiable; a one-class critic cannot graduate."""
import unittest

from tools import trinity_parental_contract as c
from tools import trinity_critic_probe as r1
from tools import trinity_r11_critic_eval as r11
from tools import trinity_r12_critic_eval as r12
from tools import trinity_r13_balanced_critic_train as train
from tools import trinity_r13_fourth_critic_eval as exam


class TrinityR13BalancedCriticContracts(unittest.TestCase):
    def test_training_data_has_192_unique_train_only_rows(self):
        rows=train.train_rows()
        self.assertEqual(len(rows),192)
        self.assertEqual(len({r["prompt"] for r in rows}),192)
        self.assertTrue(all(r["partition"]=="TRAIN_ONLY_SYMBOLIC_TRUTH" for r in rows))
        self.assertEqual(c.digest(rows),train.verify_train_rows(rows))

    def test_labels_exactly_balanced(self):
        rows=train.train_rows()
        self.assertEqual(sum(r["answer"]=="YES" for r in rows),96)
        self.assertEqual(sum(r["answer"]=="NO" for r in rows),96)
        self.assertEqual(sum(r["kind"].endswith("_CORRECT") for r in rows),96)

    def test_both_problem_phrasings_have_both_labels(self):
        rows=train.train_rows()
        self.assertEqual([sum(r["kind"]==k for r in rows) for k in
                          ("A_CORRECT","A_INCORRECT","B_CORRECT","B_AMBIGUOUS")],
                         [48,48,48,48])

    def test_stratified_training_never_starts_with_a_negative_only_prefix(self):
        rows=train.train_rows()
        indices=train.balanced_indices(rows)
        self.assertEqual(len(indices),192)
        self.assertEqual(len(set(indices)),192)
        self.assertEqual(indices,train.balanced_indices(rows))
        for steps in (2,16,48,96,192):
            subset=[rows[i]["answer"] for i in indices[:steps]]
            self.assertEqual(subset.count("YES"),steps//2)
            self.assertEqual(subset.count("NO"),steps//2)

    def test_modified_train_source_or_label_is_blocked(self):
        rows=train.train_rows()
        rows[0]["answer"]="NO"
        with self.assertRaisesRegex(ValueError,"R13_TRAIN_SET_DRIFT"):
            train.verify_train_rows(rows)
        with self.assertRaisesRegex(ValueError,"R13_UNTRUSTED_SAMPLING_DATA"):
            train.balanced_indices(rows)

    def test_fourth_firstlook_is_disjoint_from_all_known_prior_critic_exams(self):
        current=exam.rows()
        self.assertEqual(len(current),36)
        self.assertEqual(len({x["prompt"] for x in current}),36)
        prior={x["prompt"] for x in train.train_rows()}
        prior.update(r11.rows()[i]["prompt"] for i in range(36))
        prior.update(x["prompt"] for x in r12.rows())
        prior.update(r1.prompt(x) for x in r1.cases())
        self.assertFalse({x["prompt"] for x in current}&prior)
        self.assertEqual({x["partition"] for x in current},
                         {"FOURTH_INTERNAL_FIRST_LOOK_NOT_EXTERNAL_BLIND"})

    def test_train_packed_labels_are_not_preshifted(self):
        ids,labels=train.pack_hf_causal_labels([15,18,20],[22,23])
        self.assertEqual(ids,[15,18,20,22,23])
        self.assertEqual(labels,[-100,-100,-100,22,23])

    def test_every_correct_and_wrong_verdict_is_needed(self):
        rows=exam.rows()
        perfect=["YES" if r["expected"]=="YES" else "NO" for r in rows]
        outcome=exam.evaluate_predictions(rows,["maybe"]*36,perfect,"a"*64)
        self.assertEqual(outcome["status"],
                         "INTERNAL_CRITIC_IMPROVEMENT_OBSERVED__EXTERNAL_HOLD")
        self.assertFalse(outcome["external_independent_exam"])
        self.assertFalse(outcome["may_replace_parent_critic"])
        self.assertTrue(outcome["first_look_only"])

    def test_always_no_is_vetoed(self):
        rows=exam.rows()
        outcome=exam.evaluate_predictions(rows,["maybe"]*36,["NO"]*36,"a"*64)
        self.assertEqual(outcome["status"],"HOLD_CRITIC_GENERALIZATION_NOT_PROVEN")
        self.assertEqual(outcome["metrics"]["CANDIDATE"]["CORRECT"]["APPROVE"],0)
        self.assertTrue(outcome["criterion"]["all_veto_strategy_rejected"])

    def test_always_yes_and_abstention_are_vetoed(self):
        rows=exam.rows()
        for votes in (["YES"]*36,["maybe"]*36):
            with self.subTest(votes=votes[0]):
                outcome=exam.evaluate_predictions(rows,["maybe"]*36,votes,"a"*64)
                self.assertEqual(outcome["status"],
                                 "HOLD_CRITIC_GENERALIZATION_NOT_PROVEN")
                self.assertFalse(outcome["may_graduate_trinity"])

    def test_no_subsets_or_overwrites_can_be_scored(self):
        rows=exam.rows()
        with self.assertRaisesRegex(ValueError,"R13_INCOMPLETE_MODEL_RESPONSES"):
            exam.evaluate_predictions(rows,[],[],"a"*64)
        with self.assertRaisesRegex(ValueError,"R13_EVAL_CASES_CHANGED"):
            exam.evaluate_predictions(list(reversed(rows)),["YES"]*36,["NO"]*36,"a"*64)


if __name__=="__main__":
    unittest.main()
