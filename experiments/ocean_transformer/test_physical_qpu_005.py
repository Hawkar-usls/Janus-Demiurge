#!/usr/bin/env python3
"""QPU 005 protocol tests. All 4096 synthetic rows are NOT lab evidence."""
import json
import math
import random
import tempfile
import unittest
from pathlib import Path

import physical_qpu_005_protocol as p
import physical_qpu_005_ibm as ibm


def mock_job():
    return {
        "provider":"IBM_QUANTUM",
        "backend_name":"synthetic-test-name-not-a-real-job",
        "backend_simulator":False,
        "job_id":"SYNTHETIC_TEST_ONLY",
        "compiled_circuit_sha256":"a"*64,
    }


def mock_data():
    # Clearly labelled synthetic stand-in for the two-setting Bell experiment.
    # Not shuffled; tests analysis formulas only, not physical randomness.
    return [[i%2,0,i%2] for i in range(2048)] + [
        [i%2,1,(i//2)%2] for i in range(2048)]


class QPUProtocolTests(unittest.TestCase):
    def test_predeclared_before_hardware(self):
        pre=p.plan()
        self.assertEqual(p.verify_plan(pre),pre["preregistered_sha256"])
        self.assertFalse(pre["hardware_job_submitted_by_this_plan"])
        self.assertEqual(pre["shots"],4096)
        self.assertEqual(pre["fixed_nominal_significance_threshold"],.001)
        self.assertFalse(pre["spacelike_separation_claimed"])
        self.assertFalse(pre["physical_retrocausality_proven"])

    def test_mutated_plan_is_refused(self):
        plan=p.plan()
        plan["shots"]=8192
        with self.assertRaises(ValueError):
            p.verify_plan(plan)

    def test_expected_controls_and_primary_raw_marginal(self):
        result=p.assess(p.plan(),mock_data(),mock_job())
        self.assertEqual(result["shot_count"],4096)
        self.assertEqual(len(result["all_raw_shots"]),4096)
        self.assertEqual(result["primary"]["setting0_shots"],2048)
        self.assertEqual(result["primary"]["setting1_shots"],2048)
        self.assertAlmostEqual(result["primary"]["a1_given_setting0"],.5)
        self.assertAlmostEqual(result["primary"]["a1_given_setting1"],.5)
        self.assertAlmostEqual(result["primary"]["difference_setting1_minus_setting0"],0)
        self.assertAlmostEqual(result["primary"]["fisher_exact_two_sided_p"],1)
        self.assertEqual(result["diagnostics_not_primary"]["p_a_equals_b_setting_z"],1)
        self.assertAlmostEqual(result["diagnostics_not_primary"]["p_a_equals_b_setting_x"],.5)
        self.assertFalse(result["primary"]["threshold_crossed"])
        self.assertFalse(result["limitations"]["physical_retrocausality_proven"])

    def test_rare_outlier_does_not_allow_physics_claim(self):
        rows=mock_data()
        for record in rows[2048:]:
            record[0]=1
        report=p.assess(p.plan(),rows,mock_job())
        self.assertLess(report["primary"]["fisher_exact_two_sided_p"],.001)
        self.assertTrue(report["primary"]["threshold_crossed"])
        self.assertFalse(report["limitations"]["physical_retrocausality_proven"])
        self.assertTrue(report["primary"]["threshold_crossing_not_proof_of_retrocausality"])

    def test_wrong_number_of_shots_and_invalid_rows_rejected(self):
        data=mock_data()
        with self.assertRaisesRegex(ValueError,"ALL_SHOTS_REQUIRED"):
            p.assess(p.plan(),data[1:],mock_job())
        data[123][2]="2"
        with self.assertRaisesRegex(ValueError,"INVALID_SHOT_BIT"):
            p.assess(p.plan(),data,mock_job())

    def test_missing_physical_backend_metadata_fails(self):
        job=mock_job()
        job["backend_simulator"]=True
        with self.assertRaisesRegex(ValueError,"REAL_QPU_JOB_AND_CIRCUIT_PROVENANCE"):
            p.assess(p.plan(),mock_data(),job)

    def test_quality_failure_keeps_every_raw_shot(self):
        data=[[i%2,0,(i//2)%2] for i in range(3900)]
        data += [[i%2,1,(i//2)%2] for i in range(196)]
        r=p.assess(p.plan(),data,mock_job())
        self.assertEqual(r["status"],"REAL_QPU_SETTING_QUALITY_HOLD")
        self.assertIsNone(r["primary"]["difference_setting1_minus_setting0"])
        self.assertFalse(r["primary"]["threshold_crossed"])
        self.assertEqual(len(r["all_raw_shots"]),4096)

    def test_fisher_small_exact_case(self):
        # [[2,0],[0,2]] has two equally unlikely extreme cases out of 6.
        self.assertAlmostEqual(p.fisher_exact_two_sided(2,0,0,2),1/3)
        self.assertEqual(p.fisher_exact_two_sided(1,1,1,1),1)

    def test_immutable_plan_and_result(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"plan.json"
            p.write_once(path,p.plan())
            self.assertEqual(json.loads(path.read_text()),p.plan())
            with self.assertRaisesRegex(ValueError,"REFUSE_OVERWRITE"):
                p.write_once(path,p.plan())

    def test_qpu_circuit_has_delayed_conditional_without_simulator_fallback(self):
        # If Qiskit is installed, validate the *actual circuit object*.
        try:
            import qiskit
        except ImportError:
            self.skipTest("qiskit is not installed in this environment")
        x=ibm.circuit_structure()
        self.assertEqual(x["gates_in_program_order"][-2:],
                         ["if_else","measure"])
        self.assertTrue(x["conditional_basis_setting_generated_after_early_readout_in_program"])
        self.assertFalse(x["actual_physical_circuit_executed"])

    def test_hardware_without_secrets_has_no_submission(self):
        from unittest.mock import patch
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"MISSING_IBM_QUANTUM_OPEN_CREDENTIALS"):
                ibm.require_credentials()


if __name__ == "__main__":
    unittest.main(verbosity=2)
