# MicroPython (CLASSIC ESP32 ONLY) — deploy manually as main.py after wiring review.
# No Wi-Fi, QPU, GitHub, secrets, autonomous launch or scheduled background actions.
# GPIO25 DIGITAL output -> low-current LED via appropriate series resistor/driver.
# GPIO34 ADC1 input <- 0..3.3V-output sensor module with common ground.
# Never connect raw high voltage or a bare reverse-biased diode without proper
# photodiode amplifier; validate power and pinout before enabling.
#
# USB serial protocol: one JSON request line {"type":"capture", "phase": ...,
# "plan_id": ..., "plan_sha256":...,"bits":[0,1,...],
# "period_ms":50,"settle_ms":5}; ack -> 256 samples -> done.
# LED is forced off even on an exception. Sample timestamps are only MCU
# relative ticks, not UTC or photon event timestamps.
import sys
import time
import ujson
from machine import ADC, Pin

LED = Pin(25, Pin.OUT, value=0)
PHOTO = ADC(Pin(34), atten=ADC.ATTN_11DB)
N = 256
PERIOD_MS = 50
SETTLE_MS = 5


def reply(value):
    sys.stdout.write(ujson.dumps(value) + "\n")
    try:
        sys.stdout.flush()
    except AttributeError:
        pass


def capture(cmd):
    if (cmd.get("type") != "capture" or
            cmd.get("phase") not in ("train", "test") or
            cmd.get("period_ms") != PERIOD_MS or
            cmd.get("settle_ms") != SETTLE_MS):
        raise ValueError("PHYSICAL_PROTOCOL_MISMATCH")
    bits = cmd.get("bits")
    if (not isinstance(bits, list) or len(bits) != N or
            any(type(v) is not int or v not in (0, 1) for v in bits) or
            sum(bits) != 128):
        raise ValueError("INVALID_LED_SCHEDULE")
    plan_id = cmd.get("plan_id")
    plan_sha = cmd.get("plan_sha256")
    if not isinstance(plan_id, str) or not isinstance(plan_sha, str):
        raise ValueError("INVALID_SCHEDULE_ID")
    LED.value(0)
    time.sleep_ms(100)
    initial = time.ticks_us()
    reply({"type":"ack", "phase":cmd["phase"],
           "plan_id":plan_id, "plan_sha256":plan_sha,
           "n":N, "period_ms":PERIOD_MS})
    try:
        for index, bit in enumerate(bits):
            deadline = time.ticks_add(initial, index * PERIOD_MS * 1000)
            while time.ticks_diff(deadline, time.ticks_us()) > 0:
                time.sleep_us(200)
            LED.value(bit)
            switched = time.ticks_us()
            time.sleep_ms(SETTLE_MS)
            sampled = time.ticks_us()
            adc = PHOTO.read_u16()
            reply({
                "type":"sample", "seq":index, "led":bit, "adc_u16":adc,
                "esp_elapsed_us":time.ticks_diff(sampled, initial),
                "led_switch_elapsed_us":time.ticks_diff(switched, initial),
                "phase":cmd["phase"], "plan_id":plan_id
            })
        reply({"type":"done", "phase":cmd["phase"], "count":N,
               "plan_id":plan_id})
    finally:
        LED.value(0)


reply({"type":"ready", "protocol":"JANUS-LIGHT-PHYSICAL-008",
       "board":"CLASSIC_ESP32_ADCI_GPIO34_GPIO25"})
while True:
    try:
        raw = sys.stdin.readline()
        if not raw:
            time.sleep_ms(10)
            continue
        command = ujson.loads(raw)
        capture(command)
    except Exception as exc:
        LED.value(0)
        reply({"type":"error", "message":str(exc)})
