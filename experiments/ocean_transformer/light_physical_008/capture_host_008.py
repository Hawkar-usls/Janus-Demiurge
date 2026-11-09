#!/usr/bin/env python3
"""Host-side optional serial capture for LIGHT-008.

Operator must physically connect/test hardware and run this script manually.
It never uses a QPU, networking, GitHub write access or user account secrets.
Host UTC is timestamp of serial RECEIVE, not event time and not independent proof.
Requires: pip install pyserial (only on an operator-controlled capture PC).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import physical_light_008 as protocol


def parse_sample(message, phase, seq, expected_led, plan_id):
    if (message.get("type") != "sample" or message.get("phase") != phase
            or message.get("plan_id") != plan_id
            or type(message.get("seq")) is not int or message["seq"] != seq
            or type(message.get("led")) is not int
            or message["led"] != expected_led
            or type(message.get("adc_u16")) is not int
            or not 0 <= message["adc_u16"] <= 65535
            or type(message.get("esp_elapsed_us")) is not int
            or type(message.get("led_switch_elapsed_us")) is not int):
        raise ValueError("DEVICE_MESSAGE_NOT_VALID_FOR_FROZEN_SCHEDULE")
    host_utc = protocol.utc_now()
    host_monotonic = time.monotonic_ns()
    return {
        "seq": seq,
        "led": message["led"],
        "adc_u16": message["adc_u16"],
        "esp_elapsed_us": message["esp_elapsed_us"],
        "led_switch_elapsed_us": message["led_switch_elapsed_us"],
        "host_received_utc": host_utc,
        "host_monotonic_ns": host_monotonic,
    }


def capture_device(schedule, phase, port, baud=115200):
    import serial  # optional dependency; NOT imported for offline CI
    plan = protocol.validate_schedule(schedule)
    if phase not in ("train", "test"):
        raise ValueError("INVALID_PHASE")
    cmd = {
        "type": "capture",
        "phase": phase,
        "plan_id": plan["plan_id"],
        "plan_sha256": schedule["payload_sha256"],
        "bits": plan[phase + "_bits"],
        "period_ms": plan["sampling_period_ms"],
        "settle_ms": plan["settle_ms"],
    }
    captured = {
        "schema": protocol.SCHEMA,
        "phase": phase,
        "plan_id": plan["plan_id"],
        "plan_sha256": schedule["payload_sha256"],
        "source_class": protocol.REAL,
        "collection_utc_first_received": None,
        "capture_software_note": "Host serial receive UTC; device MicroPython elapsed monotonic ticks",
        "rows": [],
        "total_samples": 0,
    }
    with serial.Serial(port, baud, timeout=2) as dev:
        time.sleep(2)
        dev.reset_input_buffer()
        dev.write((json.dumps(cmd, separators=(",", ":")) + "\n").encode("utf-8"))
        dev.flush()
        deadline = time.monotonic() + 35
        acked = False
        finished = False
        while time.monotonic() < deadline:
            line = dev.readline()
            if not line:
                continue
            try:
                message = json.loads(line.decode("utf-8").strip())
            except (UnicodeError, ValueError):
                if acked:
                    raise ValueError("CORRUPT_SERIAL_LINE_AFTER_ACK")
                continue  # Ignore MicroPython boot banner before ACK.
            typ = message.get("type")
            if typ == "error":
                raise ValueError("DEVICE_ERROR:" + str(message.get("message"))[:100])
            if not acked:
                if (typ == "ack" and message.get("plan_id") == plan["plan_id"]
                        and message.get("plan_sha256") == schedule["payload_sha256"]
                        and message.get("phase") == phase
                        and message.get("n") == protocol.N):
                    acked = True
                continue
            if typ == "sample":
                idx = len(captured["rows"])
                if idx >= protocol.N:
                    raise ValueError("TOO_MANY_DEVICE_SAMPLES")
                row = parse_sample(message, phase, idx, cmd["bits"][idx], plan["plan_id"])
                if idx == 0:
                    captured["collection_utc_first_received"] = row["host_received_utc"]
                captured["rows"].append(row)
            elif typ == "done":
                if (message.get("plan_id") != plan["plan_id"]
                        or message.get("count") != protocol.N
                        or len(captured["rows"]) != protocol.N):
                    raise ValueError("DEVICE_DONE_WITH_MISSING_SAMPLES")
                finished = True
                break
            else:
                raise ValueError("UNEXPECTED_DEVICE_MESSAGE_AFTER_ACK")
        if not acked or not finished:
            raise ValueError("DEVICE_ACK_OR_COMPLETE_SEQUENCE_MISSING")
    captured["total_samples"] = len(captured["rows"])
    protocol.validate_capture(captured, schedule, phase, protocol.REAL)
    return captured


def main():
    p = argparse.ArgumentParser(description="Manual opt-in ESP32 USB capture; no cloud/QPU")
    p.add_argument("--plan", required=True)
    p.add_argument("--phase", required=True, choices=("train", "test"))
    p.add_argument("--port", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    schedule = protocol.read_json(args.plan)
    protocol.validate_schedule(schedule)
    # Refuse to initiate hardware if requested output already exists.
    if Path(args.output).exists():
        raise SystemExit("CAPTURE_DESTINATION_ALREADY_EXISTS")
    try:
        capture = capture_device(schedule, args.phase, args.port)
    except Exception as exc:
        # Fail closed. Do not invent missing frames or claim success.
        raise SystemExit("CAPTURE_INCOMPLETE_NO_VERIFIED_OUTPUT: " + str(exc)) from None
    protocol.atomic_new(args.output, capture)
    print(json.dumps({"status": "FULL_DEVICE_CAPTURE_RECORDED_NOT_INDEPENDENTLY_ATTESTED",
                      "phase":args.phase,
                      "samples":capture["total_samples"],
                      "capture_sha256":protocol.sha(capture),
                      "QPU_time_used_minutes":0}, sort_keys=True))


if __name__ == "__main__":
    main()
