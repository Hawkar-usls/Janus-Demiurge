#!/usr/bin/env python3
"""Unit checks for 4-date historical exploration, no external HTTP."""
import datetime as dt
import unittest

import retrospective_noaa_009_exploratory as back
import noaa_009a as n


def make(day):
    """Fully populated artificial hourly GHI; not a real NOAA recording."""
    return {"date":day.isoformat(),"url":"https://example.invalid/noaa-history",
            "raw_sha256":"a"*64,
            "latitude":40.05,"longitude":-88.37,
            "hourly_ghi":[0.0 if h<12 else 100.0+h for h in range(24)]}


class BacktestControls(unittest.TestCase):
    def test_four_targets_and_96_slots(self):
        self.assertEqual([x.isoformat() for x in back.DATES],
                         ["2026-11-02","2026-11-03","2026-11-04","2026-11-05"])

    def test_history_is_strictly_before_target_and_glow_not_measured(self):
        date=back.DATES[0]
        history=[make(date-dt.timedelta(days=i)) for i in (9,8,7,6)]
        x=back.assess_day(history,make(date))
        self.assertEqual(x["n_hours"],24)
        self.assertFalse(x["forecast_has_independent_time_witness"])
        self.assertFalse(x["glow_observed_by_real_sensor"])
        self.assertEqual(len(x["mae_w_m2"]),4)

    def test_same_day_future_contamination_rejected(self):
        date=back.DATES[0]
        history=[make(date-dt.timedelta(days=i)) for i in (9,8,7,6)]
        history[-1]["date"]=date.isoformat()
        with self.assertRaisesRegex(ValueError,"NOAA_HISTORY_NOT_CHRONOLOGICALLY_PRIOR_TO_TARGET"):
            back.assess_day(history,make(date))

    def test_missing_actual_hour_fails_instead_of_imputing(self):
        date=back.DATES[0]
        history=[make(date-dt.timedelta(days=i)) for i in (9,8,7,6)]
        measured=make(date)
        measured["hourly_ghi"][12]=None
        with self.assertRaisesRegex(ValueError,"NOAA_INCOMPLETE_TARGET_NO_POSTHOC_IMPUTATION"):
            back.assess_day(history,measured)


if __name__=="__main__":
    unittest.main()
