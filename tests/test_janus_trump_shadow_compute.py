import unittest

from janus_model.extensions import trump_shadow_compute as tsc


class FakeCandidate:
    @staticmethod
    def canon_cnf(clauses):
        return tuple(tuple(c) for c in clauses)

    @staticmethod
    def verify_total_assignment(clauses, assignment):
        return tsc.assignment_satisfies(clauses, assignment)

    @staticmethod
    def solve_fail_closed(clauses):
        baseline = tsc.brute_force_baseline(clauses)
        if baseline["status"] == "SAT":
            return {"status": "SAT", "reason": "FAKE", "witness": baseline["witness"]}
        return {"status": "OPEN", "reason": "FAKE_NO_UNSAT_CERTIFICATE"}


class TrumpShadowComputeTests(unittest.TestCase):
    def test_baseline_is_exact_on_sat_and_unsat(self):
        sat = tsc.brute_force_baseline(((1,), (2,)))
        unsat = tsc.brute_force_baseline(((1,), (-1,)))
        self.assertEqual(sat["status"], "SAT")
        self.assertTrue(tsc.assignment_satisfies(((1,), (2,)), sat["witness"]))
        self.assertEqual(unsat["status"], "UNSAT")

    def test_verified_sat_may_fast_path_but_open_falls_back(self):
        receipt = {"summary": {"verified_sat_fast_path_workloads": ["X"]}}
        sat = tsc.solve_with_verified_sat_fast_path(FakeCandidate, ((1,),), receipt)
        self.assertEqual(sat["status"], "SAT")
        self.assertEqual(sat["source"], "TRUMP_VERIFIED_SAT_FAST_PATH")
        unsat = tsc.solve_with_verified_sat_fast_path(FakeCandidate, ((1,), (-1,)), receipt)
        self.assertEqual(unsat["status"], "UNSAT")
        self.assertEqual(unsat["source"], "INDEPENDENT_BASELINE_FALLBACK")
        self.assertEqual(unsat["candidate_status"], "OPEN")

    def test_unsat_never_short_circuits_from_candidate_without_baseline(self):
        class UnsafeUnsat(FakeCandidate):
            @staticmethod
            def solve_fail_closed(clauses):
                return {"status": "UNSAT", "reason": "UNVERIFIED"}
        out = tsc.solve_with_verified_sat_fast_path(UnsafeUnsat, ((1,),), {"summary": {}})
        self.assertEqual(out["status"], "SAT")
        self.assertEqual(out["source"], "INDEPENDENT_BASELINE_FALLBACK")


if __name__ == "__main__":
    unittest.main()
