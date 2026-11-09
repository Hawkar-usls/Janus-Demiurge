import math
import unittest
import numpy as np

import fit_real_lab_decay_010 as f


class RealDecayFittingSafety(unittest.TestCase):
    def test_three_distinct_compositions_declared(self):
        self.assertEqual(f.SAMPLES, {1:"Eu_only",2:"Eu_plus_B",3:"Eu_plus_Dy"})
        self.assertEqual(f.N_TRAIN + (f.N_EXPECTED - f.N_TRAIN), 441)

    def test_no_source_data_leakage_from_held_out_samples(self):
        x=np.arange(441,dtype=float)*15+105
        observed=np.exp(-x/1000.0)*10000
        corrupted=np.copy(observed)
        corrupted[264:]=1e9  # May NOT affect fitted parameters.
        # Only use model 1 for this negative control.
        a=f.fit_one(x,observed,"mono")
        b=f.fit_one(x,corrupted,"mono")
        self.assertEqual(a["parameters"],b["parameters"])
        self.assertNotEqual(a["holdout_mae_original_units"],b["holdout_mae_original_units"])
        self.assertEqual(a["n_test"],177)

    def test_expected_model_shapes_and_negative_background_allowed(self):
        x=np.array([0.,100.])
        self.assertAlmostEqual(f.model("mono",[0,20,100],x)[1],20/math.e)
        self.assertEqual(len(f.model("bi",[0,10,20,10,200],x)),2)
        self.assertEqual(len(f.model("power",[0,10,20,2],x)),2)
        with self.assertRaisesRegex(ValueError,"UNSUPPORTED_MODEL_KIND"):
            f.model("not_a_model",[0],x)

    def test_bad_training_row_count_rejected(self):
        with self.assertRaisesRegex(ValueError,"CHRONOLOGICAL_441_ROWS_REQUIRED"):
            f.fit_one(np.array([1.]),np.array([10.]),"mono")

    def test_bootstrap_only_fixed_177_late_points(self):
        with self.assertRaisesRegex(ValueError,"HOLDOUT_LENGTH_CHANGED"):
            f.paired_block_bootstrap_bi_minus_power(
                np.array([1.,2.,3.]),np.array([1.,1.,1.]),1)


if __name__=="__main__":
    unittest.main()
