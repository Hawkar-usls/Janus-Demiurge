#!/usr/bin/env python3
"""JANUS R2 blinded addressed-vs-sham handshake tests (all synthetic)."""
import copy
import unittest

import janus_addressed_handshake_cpu_r2 as j


class AddressedHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.early=j.create_early("43210001234", nonce="0"*64)
        self.late=j.create_future("43210001234")
        self.late["generated_epoch_utc"]=self.early["created_epoch_utc"]+120.

    def test_early_only_has_request_and_guesses_no_future(self):
        self.assertEqual(len(self.early["records"]),64)
        self.assertFalse(any("future_target_bit" in row for row in self.early["records"]))
        self.assertTrue(self.early["future_target_not_generated"])

    def test_real_secrets_future_has_no_request_or_guesses(self):
        self.assertEqual(len(self.late["records"]),64)
        self.assertFalse(any("guess_addressed" in r or "request_key_sha256" in r
                             for r in self.late["records"]))
        self.assertFalse(self.late["early_predictions_or_request_keys_loaded"])

    def test_four_cells_exactly_balanced(self):
        self.assertTrue(j.verify(self.early,self.late))
        self.assertEqual(set(r["request_type"] for r in self.early["records"]),
                         set(j.LABELS))

    def test_actual_independent_rng_pilot_never_claims_physical_channel(self):
        s=j.score(self.early,self.late,permutations=199)
        self.assertEqual(s["trials"],64)
        self.assertTrue(s["all_64_trials_included"])
        self.assertEqual(sum(s["four_cells_n"].values()),64)
        self.assertFalse(s["physical_retrocausal_signal_proven"])
        self.assertFalse(s["external_late_entropy_attested"])
        self.assertTrue(s["no_postselection"])
        self.assertTrue(0<s["routing_label_permutation_p"]<=1)

    def test_paired_exact_tail_boundaries(self):
        self.assertEqual(j.exact_onesided_fair_tail(0,0),1)
        self.assertEqual(j.exact_onesided_fair_tail(8,8),1/256)
        self.assertEqual(j.exact_onesided_fair_tail(8,0),1)

    def test_bad_future_field_fails_even_if_digest_recomputed(self):
        late=copy.deepcopy(self.late)
        late["records"][0]["early_prediction"]="leaked"
        late["records_sha256"]=j.sha(j.canonical(late["records"]))
        with self.assertRaisesRegex(ValueError,"UNEXPECTED_OR_MISSING_FIELD"):
            j.verify(self.early,late)

    def test_changed_early_guess_digest_fails(self):
        early=copy.deepcopy(self.early)
        early["records"][0]["guess_addressed"] ^= 1
        with self.assertRaisesRegex(ValueError,"RECORD_DIGEST_CONTRADICTION"):
            j.verify(early,self.late)

    def test_bad_route_balance_fails_if_digest_recomputed(self):
        late=copy.deepcopy(self.late)
        late["records"][0]["route_mode"]="addressed" if (
            late["records"][0]["route_mode"]=="sham") else "sham"
        late["records_sha256"]=j.sha(j.canonical(late["records"]))
        with self.assertRaisesRegex(ValueError,"UNBALANCED_FOUR_CELLS"):
            j.verify(self.early,late)

    def test_late_clock_backdated_refused(self):
        late=copy.deepcopy(self.late)
        late["generated_epoch_utc"]=self.early["created_epoch_utc"]-1.
        with self.assertRaisesRegex(ValueError,"INTERNAL_CLOCK_ORDER_FAILED"):
            j.verify(self.early,late)

    def test_missing_trial_refused_not_filtered(self):
        late=copy.deepcopy(self.late)
        late["records"].pop()
        late["records_sha256"]=j.sha(j.canonical(late["records"]))
        with self.assertRaisesRegex(ValueError,"MISSING_TRIAL_RECORD"):
            j.verify(self.early,late)

    def test_planted_address_dependent_message_is_detectable_but_fake(self):
        # A deliberately forward-leaked SYNTHETIC target. NEVER physical.
        late=copy.deepcopy(self.late)
        for a,b in zip(self.early["records"],late["records"]):
            if a["request_type"]=="matched_request":
                b["future_target_bit"]=(
                    a["guess_addressed"] if b["route_mode"]=="addressed"
                    else a["guess_unaddressed"])
            else:
                b["future_target_bit"]=(
                    a["guess_unaddressed"] if b["route_mode"]=="addressed"
                    else a["guess_addressed"])
        late["records_sha256"]=j.sha(j.canonical(late["records"]))
        s=j.score(self.early,late,permutations=999,seed=71)
        self.assertGreater(s["addressing_interaction_difference_in_differences"],0.4)
        self.assertLess(s["routing_label_permutation_p"],0.05)
        self.assertFalse(s["physical_retrocausal_signal_proven"])

    def test_reproducible_permutation_given_frozen_rows(self):
        a=j.score(self.early,self.late,permutations=199,seed=14)
        b=j.score(self.early,self.late,permutations=199,seed=14)
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main(verbosity=2)
