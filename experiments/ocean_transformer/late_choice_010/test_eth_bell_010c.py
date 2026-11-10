#!/usr/bin/env python3
"""Unit tests for original ETH Bell 2023 source-independent counting and null."""
import unittest
import eth_bell_010c as q


class ETHBellReplayTests(unittest.TestCase):
    def test_rows_all_included(self):
        data=("Title of data\nInput Alice, Output Alice, Input Bob, Output Bob\n"
              "0,1,0,-1\n1,-1,1,1\n")
        old=q.EXPECTED_N
        try:
            q.EXPECTED_N=2
            c,n=q.audit_rows(data.encode())
        finally:
            q.EXPECTED_N=old
        self.assertEqual(n,2)
        self.assertEqual(c[(0,0)][(1,-1)],1)
        self.assertEqual(c[(1,1)][(-1,1)],1)

    def test_reject_bad_value(self):
        with self.assertRaisesRegex(ValueError,"INVALID_SETTING_OR_OUTCOME"):
            q.audit_rows(b"title\ncolumns\n0,0,1,1\n")

    def test_reject_missing_records(self):
        with self.assertRaisesRegex(ValueError,"ETH_TRIAL_COUNT_CHANGED"):
            q.audit_rows(b"title\ncolumns\n0,1,1,-1\n")

    def test_known_chsh(self):
        c={(a,b):{(A,B):0 for A in (-1,1) for B in (-1,1)}
                 for a in (0,1) for b in (0,1)}
        for a in (0,1):
            for b in (0,1):
                # Idealized PR-box control: strong CHSH, unbiased marginals.
                sign=-1 if (a,b)==(1,1) else 1
                for A in (-1,1):
                    c[(a,b)][(A,A*sign)]=25
        s=q.summarize(c,200)
        self.assertEqual(s["CHSH_S_max_four_orientations"],4.0)

    def test_unconditional_no_signalling_control(self):
        c={(a,b):{(A,B):25 for A in (-1,1) for B in (-1,1)}
                 for a in (0,1) for b in (0,1)}
        stats=q.summarize(c,400)
        self.assertTrue(all(v["p_two_sided_normal"]==1 for v in stats["marginal_no_signalling_tests"]))
        self.assertTrue(all(v["p_holm_familywise"]==1 for v in stats["marginal_no_signalling_tests"]))

    def test_normal_tail(self):
        self.assertAlmostEqual(q.two_sided_normal_p(0),1)
        self.assertLess(q.two_sided_normal_p(5),1e-5)


if __name__=="__main__":
    unittest.main()
