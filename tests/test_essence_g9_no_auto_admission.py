"""G9 reject-before-independent-first-look proof. This is NOT an empirical model test."""
import unittest
from tools import essence_v55_neural_loop as v55


class G9NoAutoAdmission(unittest.TestCase):
    def test_prior_shadow_generations_keep_original_internal_policy(self):
        for generation in range(3, 8):
            self.assertTrue(v55.g9_internal_admission_allowed(generation, True))
            self.assertFalse(v55.g9_internal_admission_allowed(generation, False))

    def test_g9_and_later_cannot_self_promote_even_with_internal_pass(self):
        self.assertFalse(v55.g9_internal_admission_allowed(8, True))
        self.assertFalse(v55.g9_internal_admission_allowed(8, False))
        self.assertFalse(v55.g9_internal_admission_allowed(9, True))

    def test_bad_generation_and_booleans_fail_closed(self):
        for args in ((True, True), (2, True), (10, True),
                     (8, 1), (8, "PASS_INTERNAL_SHADOW")):
            with self.subTest(args=args),self.assertRaises(ValueError):
                v55.g9_internal_admission_allowed(*args)

    def test_original_v55_shadow_promotion_authority_still_false(self):
        self.assertFalse(v55.LOCK["production_promotion"])
        self.assertFalse(v55.LOCK["sentinel_dispatch"])
        self.assertFalse(v55.LOCK["external_validation"])


if __name__=="__main__":
    unittest.main()
