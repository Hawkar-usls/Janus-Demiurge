#!/usr/bin/env python3
"""010M standalone tests: validate no-signalling versus postselection illusion."""
import unittest
import causal_falsification_010m as q


def toy(n=128):
    # All four setting cells and A outcomes balanced within every 8 rows.
    # B selection forces A sign from setting b while raw A and b independent.
    rows=["Original ETH-style title","Input Alice, Output Alice, Input Bob, Output Bob"]
    for i in range(n):
        a=(i//4)%2
        b=(i//2)%2
        A=1 if (i%2) else -1
        B=1 if ((A==1)==(b==1)) else -1
        rows.append(f"{a},{A},{b},{B}")
    return ("\n".join(rows)+"\n").encode()


class RealDataFalsificationContracts(unittest.TestCase):
    def test_predeclared_all_rows_and_holdout(self):
        train,hold,post,blocks,n=q.parse(toy(),expected_n=128,block_size=16)
        self.assertEqual(n,128)
        self.assertEqual(len(blocks),4)
        self.assertEqual(sum(q.sample(train,w,o,b)["n"] for o in q.OWN for b in q.REMOTE),64)
        self.assertEqual(sum(q.sample(hold,"Alice",o,b)["n"] for o in q.OWN for b in q.REMOTE),64)
        self.assertEqual(sum(q.sample(hold,"Bob",o,b)["n"] for o in q.OWN for b in q.REMOTE),64)

    def test_synthetic_perfect_fake_retro_without_raw_signal(self):
        train,hold,post,blocks,n=q.parse(toy(),expected_n=128,block_size=16)
        for o in q.OWN:
            s=q.score_test(hold,"Alice",o)
            self.assertEqual(s["delta_plus_remote1_minus0"],0)
            self.assertEqual(s["iid_approx_two_sided_p"],1)
            self.assertAlmostEqual(q.delta(post,"Alice",o),1.0)
        sc=q.predict(train,hold)
        self.assertLess(abs(sc["Alice"]["Mjanus_minus_M0_bits_per_event"]),0.0001)

    def test_holm_familywise(self):
        vals=[{"iid_approx_two_sided_p":p} for p in [0.04,0.0001,0.3,0.02]]
        q.holm(vals)
        self.assertAlmostEqual(vals[1]["p_holm_4_tests"],0.0004)
        self.assertTrue(vals[1]["passes_familywise_alpha_0_001"])
        self.assertFalse(vals[0]["passes_familywise_alpha_0_001"])

    def test_missing_rows_refused(self):
        with self.assertRaisesRegex(ValueError,"ETH_TRIAL_COUNT_MISMATCH"):
            q.parse(toy(120),expected_n=128,block_size=16)

    def test_duplicate_rows_refused(self):
        with self.assertRaisesRegex(ValueError,"MORE_ROWS_THAN_EXPECTED"):
            q.parse(toy(136),expected_n=128,block_size=16)

    def test_source_format_refusal(self):
        s=toy(128).decode().replace("0,-1,0,1","0,0,0,1",1)
        with self.assertRaisesRegex(ValueError,"INVALID_QUBIT_SETTING_OR_OUTCOME"):
            q.parse(s.encode(),expected_n=128,block_size=16)

    def test_empty_cell_refuses_test(self):
        table=q.empty()
        q.add(table,"Alice",0,0,True)
        with self.assertRaisesRegex(ValueError,"EMPTY_CELL_FOR_TEST"):
            q.score_test(table,"Alice",0)

    def test_no_time_order_claim_is_in_proof(self):
        p=q.physics_proof()
        self.assertIn("not establish such timing",p["Mjanus_proxy"])
        self.assertEqual(p["JANUS_predeclared_exploratory_effect_abs_delta"],0.01)
        self.assertEqual(p["family_alpha"],0.001)

    def test_source_digest_locked(self):
        self.assertEqual(q.ZIP_SHA256,"2d39d1b6898480d3de0134e2d55ac3faee87af32c8db5bc6fdf6fa6997296909")
        self.assertEqual(q.EXPECTED_N,1_048_576)
        self.assertEqual(q.HALF_N,524_288)

if __name__=="__main__":unittest.main()
