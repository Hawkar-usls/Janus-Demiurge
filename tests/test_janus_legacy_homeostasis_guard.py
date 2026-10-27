"""Tests for side-effect-free legacy All Star Genesis telemetry triage."""
import importlib.util
import math
import pathlib
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools/janus_legacy_homeostasis_guard.py"
spec=importlib.util.spec_from_file_location("homeostasis_probe",SOURCE)
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

def sample(**changes):
    d={"score":1.0,"loss":0.7,"val_loss":0.9,"diversity":0.4,
       "mutual_information":0.15,"grad_mean":4.0,"grad_max":7.0}
    d.update(changes)
    return d

class GenesisHomeostasisProbe(unittest.TestCase):
    def test_finite_snapshot_is_not_science_pass(self):
        result=guard.assess_legacy_metric_frame(sample())
        self.assertEqual(result["status"],"FINITE_VALUES_ONLY")
        self.assertEqual(result["reasonCodes"],[])
        self.assertEqual(result["scientificVerdict"],"NOT_TOPA_ADJUDICATED")
        self.assertFalse(result["pEqualsNpProof"])
        self.assertFalse(result["autonomousGraphMutationAllowed"])

    def test_original_nan_score_and_bad_gradients_are_rejected(self):
        for name,value in [
            ("score",float("nan")),("grad_max",float("nan")),
            ("grad_max",float("-inf")),("grad_mean",float("inf")),
            ("loss",float("nan")),("val_loss",float("inf")),
            ("diversity",float("-inf")),("mutual_information",float("nan")),
            ("grad_mean",-1.0),("grad_max",-3.0),
        ]:
            with self.subTest(name=name,value=str(value)):
                r=guard.assess_legacy_metric_frame(sample(**{name:value}))
                self.assertEqual(r["status"],"INVALID_METRIC_FRAME")
                self.assertTrue(r["reasonCodes"])

    def test_threshold_is_only_heuristic(self):
        x=guard.assess_legacy_metric_frame(sample(grad_max=101))
        self.assertEqual(x["status"],"HEURISTIC_GRADIENT_ALERT")
        self.assertIn("LEGACY_GRADIENT_CEILING_EXCEEDED",x["reasonCodes"])
        self.assertEqual(x["hypothesis"],"UNTESTED_HEURISTIC_ONLY")
        self.assertEqual(guard.assess_legacy_metric_frame(sample(grad_max=100))["status"],
                         "FINITE_VALUES_ONLY")

    def test_type_and_consistency_fail_closed(self):
        for frame in (sample(score=True),sample(grad_mean=12,grad_max=7),
                      sample(grad_max="99"),sample(grad_mean=None)):
            self.assertEqual(guard.assess_legacy_metric_frame(frame)["status"],
                             "INVALID_METRIC_FRAME")
        with self.assertRaises(TypeError):
            guard.assess_legacy_metric_frame([])
        for bound in (-1, 0, float("inf"),float("nan"),True,"100"):
            with self.assertRaises(ValueError):
                guard.assess_legacy_metric_frame(sample(),gradient_ceiling=bound)

    def test_private_extra_fields_are_never_emitted_or_used(self):
        a=sample(device_id="PRIVATE_SERIAL_DO_NOT_PRINT",notes="PRIVATE_RESEARCH")
        self.assertNotIn("PRIVATE_SERIAL",str(guard.assess_legacy_metric_frame(a)))
        self.assertEqual(guard.assess_legacy_metric_frame(a),
                         guard.assess_legacy_metric_frame(sample()))

if __name__=="__main__":unittest.main()
