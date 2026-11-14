#!/usr/bin/env python3
"""011B no network tests of full Qu Eq4, file constraints and math gates."""
import io
import math
import unittest
import dryad_switch_011b as x

class Qu2026SourceAndTheory(unittest.TestCase):
 def uniform(self):
  rows="\n".join(f"{j:04b},0.0625,0.001" for j in range(16)).encode()
  t={f"{i:04b}":x.decode_csv(rows,f"{i:04b}")[0] for i in range(16)}
  return t

 def test_exact_paper_eq4_on_flat_source(self):
  p=x.inequality(self.uniform())
  self.assertEqual(p["full_source_outcome_rows_used"],256)
  self.assertAlmostEqual(p["term1"],.25)
  self.assertAlmostEqual(p["term2"],.25)
  self.assertAlmostEqual(p["term3"],.5)
  self.assertAlmostEqual(p["S"],1.0)
  self.assertFalse(p["causal_inequality_violation_conditional_on_source_sampling_assumptions"])

 def test_readme_exact_binary_columns(self):
  raw="\n".join(f"{j:04b},{1/16:.5f},0.002" for j in range(16)).encode()
  tab,checks=x.decode_csv(raw,"0000")
  self.assertEqual(checks["row_count"],16)
  self.assertEqual(checks["original_probability_sum"],"1.00000")
  self.assertEqual(len(tab),16)

 def test_bad_probabilities_do_not_renormalize(self):
  raw="\n".join(f"{j:04b},0.05,0.002" for j in range(16)).encode()
  with self.assertRaisesRegex(ValueError,"SOURCE_NOT_NORMALIZED"):
   x.decode_csv(raw,"0100")

 def test_wrong_outcome_mapping_fail_closed(self):
  raw="\n".join(f"{j:04d},.0625,.002" for j in range(16)).encode()
  with self.assertRaisesRegex(ValueError,"UNKNOWN_OUTCOME_ENCODING"):
   x.decode_csv(raw,"0000")

 def test_duplicate_outcome_rejected(self):
  raw=("0000,.1,.02\n"*16).encode()
  with self.assertRaisesRegex(ValueError,"DUPLICATE_OUTCOME"):
   x.decode_csv(raw,"0000")

 def test_incomplete_setting_set_rejected(self):
  tab=self.uniform();del tab["1101"]
  with self.assertRaisesRegex(ValueError,"REQUIRE_ALL_16_SETTINGS"):
   x.inequality(tab)

 def test_all_outcomes_nonlinear_versus_real_CPTP(self):
  p=x.analytical_models()
  self.assertAlmostEqual(p["nonlinear_pure_state_map"]["Z_ensemble_P0_after_assumed_deterministic_map"],.5)
  self.assertAlmostEqual(p["nonlinear_pure_state_map"]["X_ensemble_P0_after_assumed_deterministic_map"],.8)
  self.assertAlmostEqual(p["nonlinear_pure_state_map"]["assumed_potential_operational_delta"],.3)
  self.assertAlmostEqual(p["standard_quantum_filter_all_outcomes"]["Z_unconditional_P0"],.5)
  self.assertAlmostEqual(p["standard_quantum_filter_all_outcomes"]["X_unconditional_P0"],.5)
  self.assertEqual(p["standard_quantum_filter_all_outcomes"]["unconditional_signal_delta"],0)

 def test_coherent_order_vs_mixed_does_not_rewrite_early_record(self):
  p=x.analytical_models()["coherent_quantum_switch"]
  self.assertEqual(p["ideal_control_minus_probability"],1)
  self.assertEqual(p["incoherent_mixture_control_minus_probability"],.5)
  self.assertFalse(p["earlier_already_fixed_A_can_be_rewritten"])

 def test_sigma_claim_is_explicitly_unverified(self):
  p=x.inequality(self.uniform())
  self.assertTrue(p["diagonal_only_sigma_NOT_authoritative"])
  self.assertFalse(p["claimed_24_SD_independently_reproduced"])
  self.assertGreater(p["descriptive_diagonal_only_S_sigma"],0)

 def test_source_pinned_to_frozen_Dryad_version(self):
  self.assertEqual(x.VERSION,448155)
  self.assertEqual(x.VERSION_ZIP_SHA256,"5cf46d27052bcae65ca2f4c58ef5e373a4410c3c4d52c1cfc785b3e169c9054c")
  self.assertEqual(len(x.EXPECTED_NAMES),16)

if __name__=="__main__":unittest.main()
