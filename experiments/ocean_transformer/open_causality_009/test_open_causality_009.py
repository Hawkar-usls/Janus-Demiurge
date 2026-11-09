#!/usr/bin/env python3
"""Offline no-network unit tests for public-data 009A and 009B."""
import datetime as dt
import json
import math
import random
import tempfile
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch

import noaa_009a as a
import future_009b as b

UTC=dt.timezone.utc
TODAY=dt.datetime(2026,11,9,4,15,tzinfo=UTC)

def fixture_day(day,offset=0):
    raw=(f"Bondville\n40.05 -88.37 213 1\n"+"".join(
        f"{day.year} {day.timetuple().tm_yday} {day.month} {day.day} {h} {m} 0 50 {100+offset+h} 0\n"
        for h in range(24) for m in range(60))).encode()
    return a.parse_day(raw,day,a.url_for(day))

def history(now=TODAY):
    return [fixture_day(now.date()-dt.timedelta(days=i),0) for i in (7,6,5,4)]

class NoaaTests(TestCase):
    def test_strict_official_column_mapping(self):
        x=fixture_day(TODAY.date()-dt.timedelta(days=7))
        self.assertEqual(len(x["hourly_ghi"]),24)
        self.assertEqual(x["hourly_ghi"][3],103)
        self.assertEqual(x["minute_valid_count"][3],60)

    def test_duplicate_or_missing_minute_fails(self):
        day=TODAY.date()-dt.timedelta(days=7)
        x=fixture_day(day)
        raw=(f"Bondville\n40.05 -88.37 213 1\n"+"".join(
            f"{day.year} {day.timetuple().tm_yday} {day.month} {day.day} {h} {m} 0 50 100 0\n"
            for h in range(24) for m in range(60) if not(h==3 and m==1))).encode()
        with self.assertRaisesRegex(ValueError,"NOAA_MISSING_MINUTE_ROWS"):
            a.parse_day(raw,day,x["url"])

    def test_zenith_and_nighttime_clear_sky(self):
        d=dt.date(2026,11,11)
        self.assertGreater(max(a.haurwitz(d,h,40.05,-88.37) for h in range(24)),400)
        self.assertEqual(min(a.haurwitz(d,h,40.05,-88.37) for h in range(24)),0)

    def test_no_fetched_future_data_when_preparing(self):
        target=TODAY.date()+dt.timedelta(days=2)
        x=a.prepare(target,TODAY,history())
        self.assertEqual(x["sha256"],a.sha(x["payload"]))
        self.assertFalse(x["payload"]["target_data_seen"])
        self.assertEqual(len(x["payload"]["predictions_w_m2"]),24)
        self.assertEqual(x["payload"]["training_dates"][-1],"2026-11-05")
        self.assertTrue(all("target_ghi" not in k for k in x["payload"]))

    def test_future_limit_forced(self):
        with self.assertRaisesRegex(ValueError,"TARGET_MUST_BE_TWO_DAYS_AHEAD"):
            a.prepare(TODAY.date(),TODAY,history())

    def test_all_physical_hours_scored(self):
        early=a.prepare(TODAY.date()+dt.timedelta(days=2),TODAY,history())
        d=dt.date.fromisoformat(early["payload"]["target_date_utc"])
        target=fixture_day(d)
        result=a.assess(early,target,"2026-11-09T04:20:00Z",
                        dt.datetime(2026,11,15,tzinfo=UTC))
        self.assertEqual(result["n_hours"],24)
        self.assertEqual(len(result["mae_w_m2"]),4)
        self.assertFalse(result["retrocausality_proven"])

    def test_refuse_late_commitment(self):
        early=a.prepare(TODAY.date()+dt.timedelta(days=2),TODAY,history())
        with self.assertRaisesRegex(ValueError,"NO_EARLY_GITHUB_WITNESS_BEFORE_TARGET"):
            a.assess(early,fixture_day(dt.date(2026,11,11)),
                     "2026-11-11T03:00:00Z",dt.datetime(2026,11,15,tzinfo=UTC))

    def test_missing_target_flag_refused(self):
        early=a.prepare(TODAY.date()+dt.timedelta(days=2),TODAY,history())
        target=fixture_day(dt.date(2026,11,11))
        target["hourly_ghi"][5]=None
        with self.assertRaisesRegex(ValueError,"NOAA_TARGET_INCOMPLETE"):
            a.assess(early,target,"2026-11-09T04:20:00Z",dt.datetime(2026,11,15,tzinfo=UTC))

    def test_new_file_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"early.json"
            a.store(p,{"x":1})
            with self.assertRaises(FileExistsError):a.store(p,{"x":2})

class FutureTests(TestCase):
    def prior(self):
        return {"chain_hash":b.CHAIN,"genesis_time":b.GENESIS,"period":3,
                "round":b.round_at_or_after(TODAY.timestamp())-5,
                "signature_verified_by_pinned_client":True}

    def early(self):
        future_date=TODAY.date()+dt.timedelta(days=2)
        fake_probs=[.49,.51]*64
        with patch.object(b,"predict",return_value=fake_probs):
            return b.prepare(future_date,self.prior(),object(),
                   "a"*64,"b"*64,TODAY)

    def test_distinct_future_rounds(self):
        x=self.early()["payload"]
        self.assertEqual(x["n_distinct_rounds"],128)
        self.assertEqual(len(set(x["target_rounds"])),128)
        self.assertTrue(all(v-u==20 for u,v in zip(x["target_rounds"],x["target_rounds"][1:])))
        self.assertTrue(x["first_release_unix"]>TODAY.timestamp()+24*3600)

    def test_future_bits_not_read_during_precommit(self):
        x=self.early()
        self.assertEqual(x["sha256"],b.digest(x["payload"]))
        self.assertFalse(x["payload"]["future_results_seen"])
        self.assertFalse(x["payload"]["training_after_precommit"])
        self.assertEqual(len(x["payload"]["probability_1"]),128)

    def signed(self,early):
        rounds=early["payload"]["target_rounds"]
        return {"chain_hash":b.CHAIN,"signature_verification":"DRAND_CLIENT_BLS_PINNED",
                "target_rounds":rounds,
                "beacons":[{"round":r,"randomness":"0"*64,
                           "signature_verified_by_pinned_client":True} for r in rounds]}

    def test_distinct_rounds_scored_no_selection(self):
        x=self.early()
        score=b.assess(x,self.signed(x),"2026-11-09T04:23:00Z",
                       dt.datetime(2026,11,13,tzinfo=UTC))
        self.assertEqual(score["n_distinct_rounds"],128)
        self.assertEqual(score["matches"],64)
        self.assertTrue(score["no_late_outcomes_filtered"])
        self.assertFalse(score["retrocausality_proven"])

    def test_wrong_or_missing_round_fails(self):
        x=self.early()
        bad=self.signed(x)
        bad["beacons"].pop()
        with self.assertRaisesRegex(ValueError,"MISSING_FUTURE_ROUNDS"):
            b.assess(x,bad,"2026-11-09T04:23:00Z",dt.datetime(2026,11,13,tzinfo=UTC))

    def test_late_witness_fails(self):
        x=self.early()
        with self.assertRaisesRegex(ValueError,"INDEPENDENT_GITHUB_ARTIFACT_NOT_BEFORE"):
            b.assess(x,self.signed(x),"2026-11-11T08:00:00Z",
                     dt.datetime(2026,11,13,tzinfo=UTC))

    def test_prediction_tampering_fails(self):
        x=self.early()
        x["payload"]["probability_1"][3]=.99
        with self.assertRaisesRegex(ValueError,"FROZEN_MODEL_FORECAST_HASH_MISMATCH"):
            b.assess(x,self.signed(x),"2026-11-09T04:23:00Z",
                     dt.datetime(2026,11,13,tzinfo=UTC))

    def test_unreleased_beacon_fails(self):
        x=self.early()
        with self.assertRaisesRegex(ValueError,"ALL_FUTURE_ROUNDS_NOT_YET_PUBLISHED"):
            b.assess(x,self.signed(x),"2026-11-09T04:23:00Z",TODAY)

if __name__=="__main__":main(verbosity=2)
