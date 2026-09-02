import tempfile
import textwrap
import unittest
from pathlib import Path

from janus_model.extensions import trump_shadow_compute as tsc


class FakeCandidate:
    calls = 0

    @staticmethod
    def canon_cnf(clauses):
        return tuple(tuple(c) for c in clauses)

    @staticmethod
    def verify_total_assignment(clauses, assignment):
        return tsc.assignment_satisfies(clauses, assignment)

    @classmethod
    def solve_fail_closed(cls, clauses):
        cls.calls += 1
        baseline = tsc.reference_dpll_baseline(clauses)
        if baseline["status"] == "SAT":
            return {"status": "SAT", "reason": "FAKE", "witness": baseline["witness"]}
        return {"status": "OPEN", "reason": "FAKE_NO_UNSAT_CERTIFICATE"}


class TrumpShadowComputeTests(unittest.TestCase):
    def setUp(self):
        FakeCandidate.calls = 0

    def test_reference_dpll_agrees_with_exhaustive_oracle(self):
        for clauses in (((1,), (2,)), ((1,), (-1,)), ((1, 2), (-1, 2), (1, -2))):
            oracle = tsc.brute_force_oracle(clauses)
            reference = tsc.reference_dpll_baseline(clauses)
            self.assertEqual(reference["status"], oracle["status"])
            if reference["status"] == "SAT":
                self.assertTrue(tsc.assignment_satisfies(clauses, reference["witness"]))

    def test_unlisted_workload_does_not_even_run_candidate(self):
        receipt = {"summary": {"verified_sat_fast_path_workloads": ["PROVEN_CLASS"]}}
        out = tsc.solve_with_verified_sat_fast_path(FakeCandidate, ((1,),), receipt, workload_id="OTHER_CLASS")
        self.assertEqual(out["status"], "SAT")
        self.assertEqual(out["source"], "REFERENCE_DPLL_FALLBACK")
        self.assertEqual(out["proof_scope"], "BASELINE_RESULT_NOT_TRUMP_LADDER_EVIDENCE")
        self.assertEqual(out["candidate_status"], "NOT_RUN_UNLISTED_WORKLOAD")
        self.assertEqual(FakeCandidate.calls, 0)

    def test_speedup_eligible_verified_sat_is_local_fast_path_only(self):
        receipt = {"summary": {"verified_sat_fast_path_workloads": ["PROVEN_CLASS"]}}
        out = tsc.solve_with_verified_sat_fast_path(FakeCandidate, ((1,),), receipt, workload_id="PROVEN_CLASS")
        self.assertEqual(out["status"], "SAT")
        self.assertEqual(out["source"], "TRUMP_VERIFIED_SPEEDUP_ELIGIBLE_SAT_FAST_PATH")
        self.assertEqual(out["proof_scope"], "L1_LOCAL_FINITE_INSTANCE_ONLY")
        self.assertFalse(out["universal_coverage_proved"])
        self.assertFalse(out["uniform_resolver_proved"])
        self.assertFalse(out["polynomial_bound_proved"])
        self.assertEqual(FakeCandidate.calls, 1)

    def test_open_on_eligible_workload_falls_back_to_reference_dpll(self):
        receipt = {"summary": {"verified_sat_fast_path_workloads": ["UNSAT_CLASS"]}}
        out = tsc.solve_with_verified_sat_fast_path(FakeCandidate, ((1,), (-1,)), receipt, workload_id="UNSAT_CLASS")
        self.assertEqual(out["status"], "UNSAT")
        self.assertEqual(out["source"], "REFERENCE_DPLL_FALLBACK")
        self.assertEqual(out["candidate_status"], "OPEN")

    def test_unsat_never_short_circuits_from_candidate(self):
        class UnsafeUnsat(FakeCandidate):
            @classmethod
            def solve_fail_closed(cls, clauses):
                cls.calls += 1
                return {"status": "UNSAT", "reason": "UNVERIFIED"}
        receipt = {"summary": {"verified_sat_fast_path_workloads": ["PROVEN_CLASS"]}}
        out = tsc.solve_with_verified_sat_fast_path(UnsafeUnsat, ((1,),), receipt, workload_id="PROVEN_CLASS")
        self.assertEqual(out["status"], "SAT")
        self.assertEqual(out["source"], "REFERENCE_DPLL_FALLBACK")

    def test_run_shadow_can_only_emit_local_finite_evidence(self):
        source = textwrap.dedent(
            """
            def canon_cnf(clauses):
                return tuple(tuple(c) for c in clauses)
            def verify_total_assignment(clauses, assignment):
                return all(any(assignment.get(abs(int(l))) == int(int(l)>0) for l in c) for c in clauses)
            def solve_fail_closed(clauses):
                assignment={v:1 for v in range(1,17)}
                if verify_total_assignment(clauses, assignment):
                    return {'status':'SAT','reason':'TEST','witness':assignment}
                return {'status':'OPEN','reason':'TEST_OPEN'}
            """
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.py"
            path.write_text(source, encoding="utf-8")
            out = tsc.run_shadow(path, repeats=3)
        self.assertGreaterEqual(out["summary"]["local_finite_exactness_count"], 1)
        self.assertEqual(out["summary"]["highest_proof_scope"], "L1_LOCAL_FINITE_INSTANCE_ONLY")
        self.assertFalse(out["summary"]["universal_coverage_proved"])
        self.assertFalse(out["summary"]["uniform_total_resolver_proved"])
        self.assertFalse(out["summary"]["polynomial_bound_proved"])
        self.assertFalse(out["summary"]["P_equals_NP_proved"])
        for row in out["workloads"]:
            self.assertFalse(row["universal_coverage_proved"])
            self.assertFalse(row["uniform_resolver_proved"])
            self.assertFalse(row["worst_case_polynomial_bound_proved"])

    def test_dynamic_loader_supports_dataclass_candidate(self):
        source = textwrap.dedent(
            """
            from dataclasses import dataclass
            @dataclass
            class Marker:
                x: int = 1
            def solve_fail_closed(clauses):
                return {'status': 'OPEN', 'reason': 'TEST'}
            def verify_total_assignment(clauses, assignment):
                return True
            def canon_cnf(clauses):
                return tuple(tuple(c) for c in clauses)
            """
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "candidate.py"
            path.write_text(source, encoding="utf-8")
            mod = tsc.load_candidate(path)
        self.assertEqual(mod.Marker().x, 1)


if __name__ == "__main__":
    unittest.main()
