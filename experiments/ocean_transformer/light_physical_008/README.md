# JANUS-LIGHT-PHYSICAL-008 — prospective real LED/photodetector capture

**Status: HARDWARE-READY DESIGN; NO LIVE DEVICE DATA YET.**
No photon measurements, independent timestamp witness, QPU use, or retrocausality result are claimed. This is a new protocol distinct from original QPU-005, banana-006 and LIGHT-007.

## Objective and scientific boundary

Test conventional forward-time predictability of actual LED/photodetector response. Measure whether a model fitted on the first 256 raw ADC readings beats the calibration mean as a baseline across every one of 256 later readings. The experiment uses 50-ms modulation bins with 5-ms device-settling delay. The model chooses a delay of 0–4 bins using training data ONLY; no future sensor values enter the precommitted forecast.

This is a sensor/firmware response experiment. An ADC observed 5ms after LED command does NOT measure the optical speed of light. A predefined LED schedule makes later readings predictable through ordinary forward causation, not retrocausality.

## Physical equipment

Classic ESP32 + MicroPython, low-power visible LED with correct series resistor/current-limited driver, safe 0–3.3-V analog-output light sensor (or properly amplified photodiode). Common GND. The firmware assumes GPIO25 for LED output and GPIO34/ADC1 input on the original ESP32. These pins may be wrong on ESP32-S2/S3/C3 or other boards.

Verify voltage, current, pinout, attenuation, and maximum analog input before connecting anything. GPIO34 is input-only. Do not connect a bare photodiode directly without a suitable front-end, a laser, high-power LED, or mains. The MicroPython ESP32 ADC is nonlinear and not a calibrated fast time-tagger.

Official docs:
https://micropython.org/resources/docs/en/latest/esp32/quickref.html
https://docs.micropython.org/en/latest/library/time.html

## Manual physical workflow — CI NEVER operates devices

From the Janus-Demiurge repository root, on your authorized capture PC with Python 3.11+:

1. Create an unpredictable, balanced 256+256 LED schedule with a unique ID:

       python experiments/ocean_transformer/light_physical_008/physical_light_008.py schedule --output private_light008_schedule.json

   Freeze its bytes and SHA before physical acquisition; preserve its Git revision. This is a real proposed schedule, NOT an observed measurement.

2. Review hardware wiring and separately authorize manually flashing the MicroPython device file esp32_led_photodetector_008.py as main.py on a compatible classic ESP32. The device waits on USB serial for an explicit command; there is no Wi-Fi or automatic acquisition.

3. Install the optional serial library on the capture PC only:

       python -m pip install pyserial

   Collect all 256 training readings:

       python experiments/ocean_transformer/light_physical_008/capture_host_008.py --plan private_light008_schedule.json --phase train --port /dev/ttyUSB0 --output private_light008_train_raw.json

   Replace /dev/ttyUSB0 with the real port (e.g. COM3 on Windows).

4. Train and freeze the prospective 256-test-reading forecast:

       python experiments/ocean_transformer/light_physical_008/physical_light_008.py prepare --plan private_light008_schedule.json --train private_light008_train_raw.json --output private_light008_precommit.json

   **Mandatory stop before test:** publish precommit SHA and original forecast bytes (or a public SHA with separately escrowed bytes) in a new GitHub commit or externally signed record. An independent custodian must verify the provider commit time is BEFORE any TEST capture. The local UTC prepared_at time is NOT independent verification.

5. After that external commitment is visible, collect the whole TEST stream:

       python experiments/ocean_transformer/light_physical_008/capture_host_008.py --plan private_light008_schedule.json --phase test --port /dev/ttyUSB0 --output private_light008_test_raw.json

6. Score without modifying the fixed model:

       python experiments/ocean_transformer/light_physical_008/physical_light_008.py score --plan private_light008_schedule.json --train private_light008_train_raw.json --precommit private_light008_precommit.json --test private_light008_test_raw.json --output private_light008_score.json

Raw captures are write-once. Missing, reordered, wrong-LED or corrupt device frames FAIL CLOSED; incomplete captures are retained separately with a .rejected.json suffix and must never be scored. No selective reruns or omitted failed attempts. A retry needs a separate ID and public attempt history.

The scorer deliberately reports REAL_RECORDING_SCORED_WITH_SELF_REPORTED_TIMES until the raw sensor provenance, GitHub timing, time-sync error, and independent witness have been checked. Any JSON field claiming physical data is not itself evidence that a device was connected.

## Time and measurement limits

The device records elapsed microseconds after start, not universal time. The host records UTC AFTER serial receipt and its monotonic receive time. USB transport/scheduling/ADC reaction dominate any fine timing, so this cannot establish photon transit time or free-choice spacelike separation. The resulting model may measure sensor latency and correlated noise in 50-ms time bins; no relativistic or retrocausal conclusion is possible.

Future reverse-causality work requires a distinct externally preregistered study with independently chosen late settings, a sealed early stream, separately verified clock/causal geometry, no postselection, and external replication. The original JANUS QPU-005 is not modified or launched.

## Verification

The new GitHub Actions workflow janus-ocean-light-physical-008-offline-ci.yml checks 24 adversarial deterministic synthetic-only tests and fixed source blob SHA values. It installs no serial drivers and makes no IBM calls. Artifacts explicitly declare zero real LED measurements and no hardware execution.

The distinct LIGHT-008 preregistration must be in Meta Registry before any genuine future TEST recording. Real data should be stored securely and only a privacy-reviewed evidence manifest and cryptographic digests need be public.
