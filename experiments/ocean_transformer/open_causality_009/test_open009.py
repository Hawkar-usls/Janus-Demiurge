#!/usr/bin/env python3
"""Synthetic-only adversarial admission tests for prospective public beacons."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import open009 as m


def frozen():
    return json.loads(m.PLAN.read_text(encoding="utf8"))


def surfrad_day(mode="normal"):
    # NOAA-format stub only; this is NOT real light data.
    rows=["Bondville fixture", "40.05 -88.37 213 2026 1"]
    for minute in m.TARGET_MINUTES:
        hour=minute//60
        within=minute%60
        qc=1 if (mode=="qc" and minute==m.TARGET_MINUTES[17]) else 0
        cols=[2026,316,11,12,hour,within,round(minute/60,3),35,
              330.0,qc]+[0]*36
        rows.append(" ".join(map(str,cols)))
    if mode=="missing":
        rows.pop()
    if mode=="wrong_day":
        rows[2]=rows[2].replace("2026 316 11 12","2026 315 11 11",1)
    if mode=="duplicate":
        rows.append(rows[2])
    return ("\n".join(rows)+"\n").encode()


def beacon_for_index(i):
    sig=(i.to_bytes(4,"big")*12).hex()
    raw_hash=hashlib.sha256(bytes.fromhex(sig)).hexdigest()
    return {"index":i,"round":m.round_for(i),"bit":int(raw_hash[:2],16)>>7,
            "signature":sig,"randomness":raw_hash,
            "two_relays_agree":True}


class SealedPlanTest(unittest.TestCase):
    def test_01_frozen_plan_equals_protocol(self):
        self.assertEqual(m.validate_plan(frozen()),frozen())

    def test_02_starts_in_prospective_future(self):
        self.assertEqual(m.utc(m.START).isoformat(),"2026-11-12T00:00:00+00:00")
        self.assertEqual(m.first_round(),33879412)
        self.assertEqual(m.round_for(1023),33899872)

    def test_03_sample_spacing_one_minute(self):
        self.assertEqual(m.round_for(1)-m.round_for(0),20)

    def test_04_fixed_baseline_1024_bits(self):
        self.assertEqual(len(m.xorshift_bits()),1024)
        self.assertEqual(m.hex_to_bits(frozen()["drand"]["forecast_bits_hex"]),
                         m.xorshift_bits())

    def test_05_future_values_not_in_forecast(self):
        p=frozen()
        self.assertFalse(p["future_values_seen_before_forecast"])
        self.assertFalse(p["trained_transformer_present"])
        self.assertFalse(p["QPU_run"])
        self.assertEqual(len(p["noaa"]["forecast_W_m2"]),60)

    def test_06_tampered_prediction_refused(self):
        p=frozen()
        p["drand"]["forecast_bits_hex"]="0"*256
        with self.assertRaisesRegex(ValueError,"PLAN_CHANGED_FROM_FROZEN_PROTOCOL"):
            m.validate_plan(p)

    def test_07_tampered_noaa_forecast_refused(self):
        p=frozen()
        p["noaa"]["forecast_W_m2"][10]+=30
        with self.assertRaisesRegex(ValueError,"PLAN_CHANGED_FROM_FROZEN_PROTOCOL"):
            m.validate_plan(p)

    def test_08_binary_round_trip(self):
        self.assertEqual(m.hex_to_bits(m.bits_to_hex(m.xorshift_bits())),
                         m.xorshift_bits())

    def test_09_noaa_date_and_url(self):
        self.assertEqual(m.noaa_url(),
          "https://gml.noaa.gov/aftp/data/radiation/surfrad/bon/2026/bon26316.dat")

    def test_10_write_once(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"report.json"
            m.write_new(path,frozen())
            with self.assertRaises(FileExistsError):
                m.write_new(path,frozen())


class BeaconsTest(unittest.TestCase):
    def test_11_future_beacon_access_refused(self):
        with self.assertRaisesRegex(ValueError,"FUTURE_BEACONS_NOT_RELEASED"):
            m.score_drand(frozen(),fetcher=beacon_for_index,
              now_utc=m.utc("2026-11-11T00:00:00Z"))

    def test_12_1024_complete_mock_beacons_scored(self):
        r=m.score_drand(frozen(),fetcher=beacon_for_index,
                        now_utc=m.utc("2026-11-13T20:00:00Z"))
        self.assertEqual(r["status"],"FULL_BEACON_OBSERVATIONS__BLS_VERIFICATION_PENDING")
        self.assertEqual(r["observed_n"],1024)
        self.assertFalse(r["external_signature_BLS_verified"])
        self.assertFalse(r["experimental_retrocausality_proven"])
        self.assertEqual(r["source_class"],"TEST_FIXTURE")

    def test_13_missing_index_no_score_and_not_dropped(self):
        def bad_fetch(i):
            if i==51:
                raise TimeoutError("TEST_ONLY_NO_BEACON")
            return beacon_for_index(i)
        r=m.score_drand(frozen(),fetcher=bad_fetch,
                        now_utc=m.utc("2026-11-13T20:00:00Z"))
        self.assertEqual(r["status"],"INCOMPLETE_NO_SCORE")
        self.assertEqual(r["unavailable_count"],1)
        self.assertNotIn("accuracy",r)

    def test_14_wrong_round_no_score(self):
        def bad_fetch(i):
            row=beacon_for_index(i)
            if i==0: row["round"]+=1
            return row
        r=m.score_drand(frozen(),fetcher=bad_fetch,
                        now_utc=m.utc("2026-11-13T20:00:00Z"))
        self.assertEqual(r["status"],"INCOMPLETE_NO_SCORE")
        self.assertEqual(r["unavailable_count"],1)

    def test_15_fisher_not_claimed_or_used(self):
        self.assertLess(m.binomial_tail(1024,562),0.001)
        self.assertGreater(m.binomial_tail(1024,512),0.4)

    def test_16_wrong_relay_signature_refused(self):
        with patch.object(m,"fetch_http",return_value=b'{"round":123,"signature":"zz"}'):
            with self.assertRaisesRegex(ValueError,"MALFORMED_SIGNATURE"):
                m.fetch_drand_single(m.RELAY_BASES[0],123)
        sig="00"*48
        blob={"round":123,"signature":sig,"randomness":"ff"*32}
        with patch.object(m,"fetch_http",return_value=json.dumps(blob).encode()):
            with self.assertRaisesRegex(ValueError,"SIGNATURE_RANDOMNESS_HASH_MISMATCH"):
                m.fetch_drand_single(m.RELAY_BASES[0],123)


class NoaaTest(unittest.TestCase):
    def test_17_day_not_over_refused(self):
        with self.assertRaisesRegex(ValueError,"TARGET_DAY_IS_NOT_YET_OVER"):
            m.score_noaa(frozen(),fetcher=lambda _:surfrad_day(),
                 now_utc=m.utc("2026-11-12T20:00:00Z"))

    def test_18_all_sixty_noaa_samples_scored(self):
        r=m.score_noaa(frozen(),fetcher=lambda _:surfrad_day(),
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"COMPLETE_PUBLIC_SURFRAD_WINDOW_SCORED")
        self.assertEqual(r["valid_n"],60)
        self.assertEqual(r["mae_baseline_constant250_Wm2"],80.0)
        self.assertEqual(len(r["actual_irradiance_Wm2"]),60)

    def test_19_quality_flag_fail_closed(self):
        r=m.score_noaa(frozen(),fetcher=lambda _:surfrad_day("qc"),
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"QC_OR_MISSING_ROWS_NO_SCORE")
        self.assertEqual(len(r["bad_or_missing_minute_indices"]),1)
        self.assertNotIn("mae_solar_proxy_Wm2",r)

    def test_20_missing_row_fail_closed(self):
        r=m.score_noaa(frozen(),fetcher=lambda _:surfrad_day("missing"),
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"QC_OR_MISSING_ROWS_NO_SCORE")

    def test_21_wrong_date_fails(self):
        r=m.score_noaa(frozen(),fetcher=lambda _:surfrad_day("wrong_day"),
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"REJECTED_SOURCE_FORMAT_NO_SCORE")

    def test_22_duplicate_minute_fails(self):
        r=m.score_noaa(frozen(),fetcher=lambda _:surfrad_day("duplicate"),
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"REJECTED_SOURCE_FORMAT_NO_SCORE")

    def test_23_unpublished_noaa_no_made_up_data(self):
        def missing(_):
            raise TimeoutError("NOT_AVAILABLE_IN_FIXTURE")
        r=m.score_noaa(frozen(),fetcher=missing,
                 now_utc=m.utc("2026-11-14T00:00:00Z"))
        self.assertEqual(r["status"],"PENDING_NOAA_PUBLICATION_NO_SCORE")
        self.assertNotIn("actual_irradiance_Wm2",r)


if __name__=="__main__":
    unittest.main(verbosity=2)
