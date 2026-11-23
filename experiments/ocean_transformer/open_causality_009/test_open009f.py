#!/usr/bin/env python3
"""Offline checks for model equations, chronology and exact null tests."""
import datetime as dt
import math
import unittest

import noaa_009a as noaa
import physical_mle_009f as m
import no_signalling_009f as s


class ScientificContractTests(unittest.TestCase):
    def test_train_only_past(self):
        t=dt.date(2025,12,1)
        ds=m.training_days(t)
        self.assertEqual(len(ds),28)
        self.assertEqual(ds[0],t-dt.timedelta(days=33))
        self.assertEqual(ds[-1],t-dt.timedelta(days=6))
        self.assertTrue(all(x<t for x in ds))
        self.assertEqual(len(set(ds)),28)

    def test_mle_known_physical_transmission(self):
        day=dt.date(2025,10,10)
        lat,lon=40.05,-88.37
        x=[m.physical_toa_horizontal(day,h,lat,lon) for h in range(24)]
        y=[0.42*v for v in x]
        sample={"date":day.isoformat(),"latitude":lat,"longitude":lon,"hourly_ghi":y}
        result=m.mle_fit([sample]*28)
        self.assertAlmostEqual(result["tau"],0.42,places=11)
        self.assertAlmostEqual(result["sigma2"],0,places=15)
        preds=m.predict(result,day)
        for observed,guess in zip(y,preds["prediction_w_m2"]):
            self.assertAlmostEqual(observed,guess,places=10)

    def test_invalid_training_rejected(self):
        day=dt.date(2025,10,10)
        data={"date":day.isoformat(),"latitude":40.05,"longitude":-88.37,
              "hourly_ghi":[None]*24}
        with self.assertRaises(ValueError):
            m.mle_fit([data])

    def test_physical_night_irradiance_zero(self):
        day=dt.date(2025,12,1)
        self.assertEqual(m.physical_toa_horizontal(day,0,40.05,-88.37),0.0)

    def test_exact_sign_flip_distribution(self):
        self.assertEqual(m.exact_sign_flip_p([1.0]*8),1/256)
        self.assertEqual(m.exact_sign_flip_p([-1.0]*8),1.0)

    def test_conditional_markov_mle_from_counts(self):
        bits=[0,0,1,1,0,1,0,0,1,1,0,0,1]
        counts,p=s.mle_conditional_markov(bits)
        self.assertEqual(sum(sum(row) for row in counts),len(bits)-1)
        self.assertTrue(all(0<v<1 for v in p))
        self.assertEqual(p[0],counts[0][1]/sum(counts[0]))

    def test_exact_null_eprocess_fair_model(self):
        r=s.evaluate([0.5]*1024,[0,1]*512)
        self.assertEqual(r["matches"],512)
        self.assertAlmostEqual(r["brier"],0.25)
        self.assertAlmostEqual(r["log_e_final"],0)
        self.assertEqual(r["anytime_valid_p_upper_bound"],1)
        self.assertFalse(r["threshold_crossed"])

    def test_eprocess_can_detect_strong_realized_dependency(self):
        r=s.evaluate([0.9]*1024,[1]*1024)
        self.assertTrue(r["threshold_crossed"])
        self.assertGreater(r["log_e_final"],math.log(1000))

    def test_invalid_probability_rejected(self):
        with self.assertRaises(ValueError):
            s.evaluate([0.0],[1])


if __name__ == "__main__":
    unittest.main()
