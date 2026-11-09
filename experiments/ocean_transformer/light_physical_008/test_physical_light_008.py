#!/usr/bin/env python3
"""LIGHT-008 unit fixtures are all SYNTHETIC and never physical evidence."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import tempfile
import unittest
import sys
import builtins

import physical_light_008 as m
import capture_host_008 as host


def iso(base, shift_ms):
    return (base + timedelta(milliseconds=shift_ms)).isoformat(
        timespec="microseconds").replace("+00:00", "Z")


def plan():
    return m.make_schedule(
        rng=random.Random(137), timestamp="2026-11-09T12:00:00.000000Z",
        plan_id="synthetic-training-only-0001")


def captured(schedule, phase, true_lag=2, start="2026-11-09T12:01:00Z",
             offset=0, synthetic=True, noise_seed=3):
    bits = schedule["payload"][phase + "_bits"]
    rng = random.Random(noise_seed)
    start_time = m.parse_utc(start)
    rows = []
    for i in range(m.N):
        source = bits[i-true_lag] if i >= true_lag else 0
        adc = 9000 + source * 24000 + rng.randint(-32, 32)
        rows.append({
            "seq": i,
            "led": bits[i],
            "adc_u16": adc,
            "esp_elapsed_us": i * 50000 + 5300,
            "led_switch_elapsed_us": i * 50000 + 100,
            "host_received_utc": iso(start_time, i*50 + 7),
            "host_monotonic_ns": 8_000_000_000 + offset + i*50_000_000,
        })
    return {"schema": m.SCHEMA, "phase": phase,
            "plan_id": schedule["payload"]["plan_id"],
            "plan_sha256": schedule["payload_sha256"],
            "source_class": m.SYNTHETIC if synthetic else m.REAL,
            "total_samples": len(rows), "rows": rows}


class ScheduleTests(unittest.TestCase):
    def test_schedule_is_balanced_and_deterministic_in_unit_fixture(self):
        s = plan()
        self.assertEqual(s, plan())
        self.assertEqual(m.validate_schedule(s)["samples_per_phase"], 256)
        self.assertEqual(sum(s["payload"]["train_bits"]), 128)
        self.assertEqual(sum(s["payload"]["test_bits"]), 128)

    def test_altered_schedule_hash_is_rejected(self):
        s = plan()
        s["payload"]["test_bits"][0] ^= 1
        with self.assertRaisesRegex(ValueError, "SOURCE_SCHEDULE_SHA_MISMATCH"):
            m.validate_schedule(s)

    def test_invalid_utc_schedule_is_rejected(self):
        s = plan()
        s["payload"]["created_utc"] = "2026-11-09 12:00"
        s["payload_sha256"] = m.sha(s["payload"])
        with self.assertRaisesRegex(ValueError, "UTC_TIMESTAMP_WITH_Z_REQUIRED"):
            m.validate_schedule(s)

    def test_forecast_output_write_once(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.json"
            m.atomic_new(p, plan())
            with self.assertRaises(FileExistsError):
                m.atomic_new(p, plan())


class RawLightValidationTests(unittest.TestCase):
    def test_256_samples_are_required(self):
        s = plan()
        c = captured(s, "train")
        c["rows"].pop()
        with self.assertRaisesRegex(ValueError, "ALL_256_UNFILTERED_SAMPLES_REQUIRED"):
            m.validate_capture(c, s, "train")

    def test_wrong_led_schedule_fails(self):
        s = plan()
        c = captured(s, "train")
        c["rows"][3]["led"] ^= 1
        with self.assertRaisesRegex(ValueError, "ROW_ORDER_OR_LED_SCHEDULE_MISMATCH"):
            m.validate_capture(c, s, "train")

    def test_synthetic_is_distinct_from_physical(self):
        s = plan()
        c = captured(s, "train")
        with self.assertRaisesRegex(ValueError, "MIXED_REAL_AND_SYNTHETIC_DATA_REFUSED"):
            m.validate_capture(c, s, "train", m.REAL)

    def test_monotonic_clock_rollback_fails(self):
        s = plan()
        c = captured(s, "train")
        c["rows"][5]["host_monotonic_ns"] = 0
        with self.assertRaisesRegex(ValueError, "NONMONOTONIC_DEVICE_OR_HOST_CLOCK"):
            m.validate_capture(c, s, "train")

    def test_utc_rollback_fails(self):
        s = plan()
        c = captured(s, "train")
        c["rows"][6]["host_received_utc"] = "2026-11-09T11:58:00.000000Z"
        with self.assertRaisesRegex(ValueError, "UTC_CLOCK_MOVED_BACKWARDS"):
            m.validate_capture(c, s, "train")

    def test_invalid_device_timing_fails(self):
        s = plan()
        c = captured(s, "train")
        c["rows"][4]["led_switch_elapsed_us"] = c["rows"][4]["esp_elapsed_us"] + 1
        with self.assertRaisesRegex(ValueError, "DEVICE_LED_TO_ADC_TIMING_INVALID"):
            m.validate_capture(c, s, "train")

    def test_adc_range_fails_closed(self):
        s = plan()
        c = captured(s, "train")
        c["rows"][5]["adc_u16"] = 65536
        with self.assertRaisesRegex(ValueError, "INVALID_ADC_U16"):
            m.validate_capture(c, s, "train")

    def test_capture_phase_not_interchangeable(self):
        s = plan()
        c = captured(s, "train")
        with self.assertRaisesRegex(ValueError, "CAPTURE_PLAN_OR_PHASE_MISMATCH"):
            m.validate_capture(c, s, "test")


class PrecommitAndScoreTests(unittest.TestCase):
    def setUp(self):
        self.s = plan()
        self.train = captured(self.s, "train", start="2026-11-09T12:01:00Z")
        self.test = captured(self.s, "test", start="2026-11-09T12:04:00Z")
        self.precommit = m.make_precommit(
            self.s, self.train, timestamp="2026-11-09T12:03:00.000000Z")

    def test_training_recovers_known_synthetic_lag(self):
        fitted = m.fit_model(self.train, self.s)
        self.assertEqual(fitted["lag_bins"], 2)
        self.assertGreater(fitted["mu_on"] - fitted["mu_off"], 20000)

    def test_precommit_does_not_read_future_test_measurements(self):
        self.assertEqual(self.precommit["payload"]["n_predictions"], 256)
        self.assertFalse(self.precommit["payload"]["real_test_measurements_accessed"])
        self.assertFalse(self.precommit["external_precommit_witness_verified"])
        self.assertNotIn("test_capture_sha256", self.precommit["payload"])
        self.assertTrue(all("adc_actual" not in x
                            for x in self.precommit["payload"]["predictions"]))

    def test_real_benchmark_formally_synthetic(self):
        score = m.score(self.s, self.train, self.precommit, self.test)
        self.assertEqual(score["status"], "SYNTHETIC_TEST_ONLY")
        self.assertTrue(score["beats_baseline"])
        self.assertEqual(score["n_unfiltered_samples"], 256)
        self.assertEqual(score["selected_lag_bins_from_train_only"], 2)
        self.assertFalse(score["precommit_preceded_test_verified_externally"])
        self.assertFalse(score["physical_retrocausality_proven"])
        self.assertEqual(score["QPU_minutes_used"], 0)

    def test_modified_forecast_is_refused(self):
        broken = copy.deepcopy(self.precommit)
        broken["payload"]["predictions"][10]["adc_prediction"] += 5
        broken["payload_sha256"] = m.sha(broken["payload"])
        with self.assertRaisesRegex(ValueError, "PRECOMMIT_CHANGED_AFTER_CALIBRATION"):
            m.score(self.s, self.train, broken, self.test)

    def test_unfrozen_future_data_cannot_be_passed_to_prepare(self):
        with self.assertRaisesRegex(ValueError, "UTC_TIMESTAMP_WITH_Z_REQUIRED"):
            m.make_precommit(self.s, self.train, self.test)

    def test_wrong_chronology_rejected(self):
        self.test["rows"][0]["host_received_utc"] = "2026-11-09T12:02:00.000000Z"
        with self.assertRaisesRegex(ValueError, "FORECAST_WAS_NOT_BEFORE_TEST_CAPTURE"):
            m.score(self.s, self.train, self.precommit, self.test)

    def test_incomplete_test_capture_rejected_without_scoring(self):
        self.test["rows"].pop()
        with self.assertRaisesRegex(ValueError, "ALL_256_UNFILTERED_SAMPLES_REQUIRED"):
            m.score(self.s, self.train, self.precommit, self.test)

    def test_synthetic_vs_real_mixing_refused(self):
        self.test["source_class"] = m.REAL
        with self.assertRaisesRegex(ValueError, "MIXED_REAL_AND_SYNTHETIC_DATA_REFUSED"):
            m.score(self.s, self.train, self.precommit, self.test)

    def test_self_labelled_real_still_unwitnessed(self):
        real_train = copy.deepcopy(self.train)
        real_test = copy.deepcopy(self.test)
        real_train["source_class"] = m.REAL
        real_test["source_class"] = m.REAL
        real_commit = m.make_precommit(
            self.s, real_train, timestamp="2026-11-09T12:03:00.000000Z")
        result = m.score(self.s, real_train, real_commit, real_test)
        self.assertEqual(result["status"], "REAL_RECORDING_SCORED_WITH_SELF_REPORTED_TIMES")
        self.assertFalse(result["time_sync_verified_by_independent_custodian"])
        self.assertFalse(result["hardware_lineage_independently_verified"])


class HostCaptureParserTests(unittest.TestCase):
    def test_valid_host_parser_receives_no_network(self):
        d = {"type":"sample","phase":"test","plan_id":"opaque-plan","seq":0,
             "led":1,"adc_u16":13000,"esp_elapsed_us":5900,
             "led_switch_elapsed_us":100}
        row = host.parse_sample(d, "test", 0, 1, "opaque-plan")
        self.assertEqual(row["adc_u16"], 13000)
        self.assertTrue(row["host_received_utc"].endswith("Z"))

    def test_host_parser_refuses_wrong_led_and_missing_sample(self):
        d = {"type":"sample","phase":"test","plan_id":"opaque-plan","seq":0,
             "led":1,"adc_u16":13000,"esp_elapsed_us":5900,
             "led_switch_elapsed_us":100}
        with self.assertRaisesRegex(ValueError, "DEVICE_MESSAGE_NOT_VALID"):
            host.parse_sample(d, "test", 0, 0, "opaque-plan")

    def test_no_optional_serial_dependency_in_offline_tests(self):
        # Importing host code must never attempt to access USB on CI.
        self.assertIn("capture_device", dir(host))


if __name__ == "__main__":
    unittest.main(verbosity=2)
