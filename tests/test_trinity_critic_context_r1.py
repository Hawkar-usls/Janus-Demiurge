"""Trinity R1 critic and context fail-closed contracts (no model calls here)."""
import unittest
from tools import trinity_parental_contract as c
from tools import trinity_critic_probe as critic
from tools import trinity_context_probe as context


class TrinityR1Safety(unittest.TestCase):
    def test_critic_only_exact_yes_can_approve(self):
        for value in ("YES"," yes ","\nYES\n"):
            self.assertEqual(c.critic_decision(value),"APPROVE")
        for value in ("NO"," no ","\nNO\n"):
            self.assertEqual(c.critic_decision(value),"VETO")

    def test_ambiguous_critic_never_approves(self):
        for value in ("YES, probably","YES/NO","NO because 2+2=4",
                      "I think YES","", "42","uncertain",None, "YES\nNO", "YES "*50):
            self.assertEqual(c.critic_decision(value),"ABSTAIN")

    def test_bad_critic_cannot_pass_correct_teacher(self):
        tasks=c.curriculum()
        rows=[{"id":t["id"],"teacher_text":t["expected"],
               "critic_text":"YES but not sure"} for t in tasks]
        result=c.teach_gate(rows)
        self.assertEqual(sum(r["eligible_for_train"] for r in result),0)
        self.assertTrue(all(r["critic_abstained"] and r["critic_veto"] for r in result))
        self.assertTrue(all(r["critic_decision"]=="ABSTAIN" for r in result))

    def test_bad_teacher_never_passes_even_with_yes(self):
        tasks=c.curriculum()
        rows=[{"id":t["id"],"teacher_text":"99999","critic_text":"YES"}
              for t in tasks]
        self.assertEqual(sum(r["eligible_for_train"] for r in c.teach_gate(rows)),0)

    def test_critic_probe_has_three_disjoint_types(self):
        rows=critic.cases()
        self.assertEqual(len(rows),36)
        self.assertEqual({r["kind"] for r in rows},{"CORRECT","INCORRECT","AMBIGUOUS"})
        self.assertEqual(len({r["id"] for r in rows}),36)
        self.assertFalse({r["problem"] for r in rows} & {x["prompt"] for x in c.curriculum()})
        self.assertTrue(all(r["partition"]=="PUBLIC_CRITIC_DIAGNOSTIC_NOT_STUDENT_EXAM"
                            for r in rows))

    def test_perfect_probe_still_cannot_certify_learning(self):
        rows=critic.cases()
        answers=["YES" if r["kind"]=="CORRECT" else "NO" for r in rows]
        result=critic.evaluate(rows,answers)
        self.assertEqual(result["qualification"],
                         "PUBLIC_DIAGNOSTIC_PASS_STILL_NEEDS_UNSEEN_CRITIC_HOLDOUT")
        self.assertFalse(result["eligible_to_certify_student_training"])
        self.assertFalse(result["independent_external_exam"])

    def test_sycophantic_critic_is_hold_even_with_safe_oracle(self):
        rows=critic.cases()
        r=critic.evaluate(rows,["YES"]*len(rows))
        self.assertEqual(r["qualification"],"HOLD_CRITIC_NOT_QUALIFIED")
        self.assertFalse(r["criteria"]["wrong_detection"])

    def test_abstentions_are_safe_not_evidence_of_skill(self):
        rows=critic.cases()
        r=critic.evaluate(rows,["maybe"]*len(rows))
        self.assertEqual(r["qualification"],"HOLD_CRITIC_NOT_QUALIFIED")
        self.assertEqual(r["metrics"]["INCORRECT"]["VETO"],0)
        self.assertTrue(r["criteria"]["ambiguous_rejection"])
        self.assertFalse(r["criteria"]["correct_approval"])

    def test_critic_probe_modification_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"TRINITY_CRITIC_DIAGNOSTIC_MODIFIED"):
            critic.evaluate(list(reversed(critic.cases())),["NO"]*36)

    def test_context_probes_never_use_genesis_exam(self):
        rows=context.probes()
        self.assertEqual(len(rows),36)
        self.assertEqual(len({r["id"] for r in rows}),36)
        self.assertEqual(sum(r["group"]=="TRAIN_ONLY_SHORT" for r in rows),24)
        self.assertEqual(sum(r["group"]=="PUBLIC_PADDED_MEDIUM" for r in rows),6)
        self.assertEqual(sum(r["group"]=="PUBLIC_PADDED_LONG" for r in rows),6)
        self.assertTrue(all("expected" in r for r in rows))

    def test_context_allowlist_only(self):
        self.assertEqual(context.LENGTHS,(128,256,512))


if __name__=="__main__":
    unittest.main()
