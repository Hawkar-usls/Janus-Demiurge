#!/usr/bin/env python3
"""Offline contract tests: no data needed and no untrusted external downloads."""
import unittest
import public_bell_010a as b


class HistoricalBellReplayTests(unittest.TestCase):
    def test_exact_fisher_independence(self):
        self.assertEqual(b.two_sided_fisher([[20,20],[20,20]]),1.0)

    def test_exact_fisher_extreme(self):
        self.assertLess(b.two_sided_fisher([[45,0],[0,45]]),1e-20)

    def test_fisher_symmetric_row_exchange(self):
        tab=[[13,24],[31,14]]
        self.assertAlmostEqual(b.two_sided_fisher(tab),b.two_sided_fisher(tab[::-1]))

    def row(self):
        # Timestamp, day, run, C1 time/channel, C2 time/channel, settings,
        # setting time tags, readout times, exclusion times, veto ages.
        return ["2015-09-18T00:00:00",18,1,5426350,0,5675700,1,0,0,
                10500,10500,12000,10000,0,0,0,0]

    def test_author_herald_gate(self):
        self.assertTrue(b.strict_predefined_herald(tuple(self.row())))

    def test_failed_herald_not_selected(self):
        r=self.row()
        r[5]=0
        self.assertFalse(b.strict_predefined_herald(tuple(r)))

    def test_veto_excludes_exceptions(self):
        r=self.row()
        r[13]=1
        self.assertFalse(b.strict_predefined_herald(tuple(r)))

    def test_readout_boundary(self):
        self.assertEqual(b.spin_outcome(10620),-1)
        self.assertEqual(b.spin_outcome(10621),1)
        self.assertEqual(b.spin_outcome(14320),1)
        self.assertEqual(b.spin_outcome(14321),-1)

    def test_max_chsh_on_known_theoretical_construct(self):
        rows=[]
        for a in (0,1):
            for c in (0,1):
                for _ in range(16):
                    rows.append({"setting_alice":a,"setting_bob":c,
                                 "outcome_alice":1,
                                 "outcome_bob":-1 if (a==1 and c==1) else 1})
        result=b.correlations_and_signalling(rows)
        self.assertAlmostEqual(result["CHSH_S"],4.0)
        self.assertEqual(sum(result["CHSH_cell_counts"].values()),64)
        for stat in result["marginal_no_signalling_exploratory"]:
            self.assertGreaterEqual(stat["p_holm_familywise"],stat["p_two_sided_fisher"]-1e-12)
            self.assertLessEqual(stat["p_holm_familywise"],1.0)


if __name__=="__main__":
    unittest.main()
