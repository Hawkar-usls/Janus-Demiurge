#!/usr/bin/env python3
"""JANUS OPEN-CAUSALITY-009: sealed prospective public-source baseline experiment.

This is an independently time-indexed forecast control, NOT a retrocausal
communication experiment. The forecast is a frozen source file on GitHub
before drand / NOAA target times. No hidden tuning, filtering or resampling.
No QPU, ESP32, local hardware, secrets or write access.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from urllib import request

HERE = Path(__file__).resolve().parent
PLAN = HERE / "precommit_009.json"
CHAIN = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
GENESIS = 1692803367
PERIOD = 3
START = "2026-11-12T00:00:00Z"
NOAA_DATE = "2026-11-12"
NOAA_STATION = "bon"
TARGET_MINUTES = list(range(16*60, 17*60))
BEACONS = 1024
SPACING_ROUNDS = 20
RELAY_BASES = (
    "https://api.drand.sh",
    "https://api2.drand.sh",
)
NOAA_BASE = "https://gml.noaa.gov/aftp/data/radiation/surfrad/"
MAX_RESPONSE_BYTES = 650_000


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def utc(s):
    if not isinstance(s, str) or not s.endswith("Z"):
        raise ValueError("UTC_Z_REQUIRED")
    return datetime.fromisoformat(s[:-1] + "+00:00")


def now():
    return datetime.now(timezone.utc)


def write_new(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf8") as f:
        f.write(json.dumps(obj, sort_keys=True, indent=2,
                           ensure_ascii=False, allow_nan=False) + "\n")


def solar_prediction(minute):
    # Fixed solar-geometry proxy for Bondville, NOT a trained ML forecast or
    # calibrated clear-sky model. Published before target readings.
    lat = math.radians(40.05192)
    longitude = -88.37309
    doy = 316  # 2026-11-12 nonleap year
    dec = math.radians(23.44 * math.sin(2*math.pi*(doy - 81) / 365))
    utc_hour = minute / 60
    hourangle = math.radians(15 * (utc_hour + longitude / 15 - 12))
    cosz = (math.sin(lat)*math.sin(dec)
            + math.cos(lat)*math.cos(dec)*math.cos(hourangle))
    return round(700 * max(0.0, cosz), 6)


def xorshift_bits():
    x = 0x4A414E55  # Public deterministic negative-control seed.
    bits = []
    for _ in range(BEACONS):
        x ^= (x << 13) & 0xffffffff
        x ^= x >> 17
        x ^= (x << 5) & 0xffffffff
        x &= 0xffffffff
        bits.append(x & 1)
    return bits


def first_round():
    return 1 + (int(utc(START).timestamp()) - GENESIS) // PERIOD


def round_for(i):
    return first_round() + i * SPACING_ROUNDS


def end_time():
    return datetime.fromtimestamp(
        GENESIS + (round_for(BEACONS-1)-1)*PERIOD, timezone.utc)


def bits_to_hex(bits):
    if len(bits) % 4:
        raise ValueError("NOT_FULL_NIBBLES")
    return "".join(format(sum(bits[i+j] << (3-j) for j in range(4)), "x")
                   for i in range(0, len(bits), 4))


def hex_to_bits(s):
    return [int(bit) for c in s for bit in f"{int(c, 16):04b}"]


def expected_plan():
    return {
        "schema": "janus.ocean.open_causality_009.precommit.v1",
        "status": "FROZEN_PROSPECTIVE_BASELINES_NO_ACTUAL_OUTCOMES",
        "scope": "EXTERNAL_NOAA_AND_DRAND_PUBLIC_DATA",
        "precommit_basis": "GitHub commit publication before all designated target times",
        "causal_interpretation": "CONTROL_ONLY_NOT_RETROCAUSAL_EVIDENCE",
        "drand": {
            "chain": "quicknet", "chain_hash": CHAIN,
            "genesis_unix_s": GENESIS, "period_seconds": PERIOD,
            "target_start_utc": START,
            "first_round": first_round(),
            "round_step": SPACING_ROUNDS,
            "n": BEACONS,
            "bit_rule": "msb_sha256(signature_bytes)",
            "model": "xorshift32_fixed_seed_zero_knowledge_negative_control",
            "forecast_bits_hex": bits_to_hex(xorshift_bits()),
            "significance_test": "one-sided exact binomial tail under iid fair bits; predeclared alpha 0.001",
            "alpha": 0.001,
            "beacon_signature_policy": "two-relay equality and SHA256(signature) checking; BLS pairing NOT independently verified",
        },
        "noaa": {
            "archive": "NOAA_SURFRAD_BONDVILLE",
            "date_utc": NOAA_DATE,
            "station": NOAA_STATION,
            "source_base": NOAA_BASE,
            "variable": "dw_solar",
            "qc_variable": "dw_solar_flag",
            "minutes_utc": TARGET_MINUTES,
            "n": len(TARGET_MINUTES),
            "forecast_W_m2": [solar_prediction(i) for i in TARGET_MINUTES],
            "model": "fixed_solar_zenith_proxy_scale700",
            "baseline_zero_W_m2": 0,
            "baseline_constant_W_m2": 250,
            "metric": "mean absolute error on all sixty 1-minute records, no postselection",
            "missing_policy": "REFUSE_SCORE_IF_ANY_MISSING_OR_NONZERO_QC",
        },
        "physical_measurements_collected_by_janus": False,
        "trained_transformer_present": False,
        "QPU_run": False,
        "future_values_seen_before_forecast": False,
    }


def validate_plan(plan):
    if plan != expected_plan():
        raise ValueError("PLAN_CHANGED_FROM_FROZEN_PROTOCOL")
    if len(hex_to_bits(plan["drand"]["forecast_bits_hex"])) != BEACONS:
        raise ValueError("WRONG_N_BITS")
    return plan


def fetch_http(url, max_bytes=MAX_RESPONSE_BYTES):
    req = request.Request(url, headers={
        "User-Agent":"JANUS-OPEN-CAUSALITY-009/1.0 (public research)",
        "Accept":"application/json,text/plain",
    })
    with request.urlopen(req, timeout=15) as resp:
        body = resp.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise ValueError("UNBOUNDED_SOURCE_RESPONSE")
    return body


def fetch_drand_single(base, r):
    url = f"{base}/{CHAIN}/public/{r}"
    response = json.loads(fetch_http(url))
    if response.get("round") != r:
        raise ValueError("WRONG_BEACON_ROUND")
    sig = response.get("signature")
    if (not isinstance(sig, str) or len(sig) != 96 or
            any(c not in "0123456789abcdefABCDEF" for c in sig)):
        raise ValueError("MALFORMED_SIGNATURE")
    signed_random = hashlib.sha256(bytes.fromhex(sig)).hexdigest()
    if response.get("randomness") != signed_random:
        raise ValueError("SIGNATURE_RANDOMNESS_HASH_MISMATCH")
    return {"round":r,"signature":sig.lower(),"randomness":signed_random,
            "source":url}


def one_drand(i):
    r = round_for(i)
    a = fetch_drand_single(RELAY_BASES[0], r)
    b = fetch_drand_single(RELAY_BASES[1], r)
    if a["signature"] != b["signature"]:
        raise ValueError("RELAYS_DISAGREE")
    return {"index":i, "round":r,"signature":a["signature"],
            "randomness":a["randomness"],
            "bit":int(a["randomness"][:2], 16) >> 7,
            "two_relays_agree":True,
            "bls_signature_independently_verified":False,
            "relay_sources":[a["source"],b["source"]]}


def binomial_tail(n, k):
    if not 0 <= k <= n:
        raise ValueError("INVALID_BINOMIAL_COUNT")
    return sum(math.comb(n, t) for t in range(k, n+1))/2**n


def score_drand(plan, fetcher=one_drand, now_utc=None):
    validate_plan(plan)
    clock = now_utc if now_utc is not None else now()
    if clock <= end_time():
        raise ValueError("FUTURE_BEACONS_NOT_RELEASED")
    pred = hex_to_bits(plan["drand"]["forecast_bits_hex"])
    observations = [None]*BEACONS
    problems = []
    # Bound public API use. Do not substitute missing bits.
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = {pool.submit(fetcher,i):i for i in range(BEACONS)}
        for done in as_completed(tasks):
            i=tasks[done]
            try:
                row=done.result()
                if (row["index"]!=i or row["round"]!=round_for(i)
                        or row.get("bit") not in (0,1)
                        or row.get("two_relays_agree") is not True):
                    raise ValueError("UNVERIFIED_OR_MISORDERED_BEACON")
                observations[i]=row
            except Exception as ex:
                problems.append({"index":i,"reason":str(ex)[:120]})
    present=sum(row is not None for row in observations)
    result={
        "schema":"janus.ocean.open009.drand_score.v1",
        "source_class":"ACTUAL_PUBLIC_BEACONS" if fetcher is one_drand else "TEST_FIXTURE",
        "forecast_sha256":digest(plan),
        "expected_n":BEACONS,
        "observed_n":present,
        "unavailable_count":BEACONS-present,
        "problems":sorted(problems,key=lambda x:x["index"]),
        "raw_observations_sha256":digest(observations),
        "raw_observations":observations,
        "retrieved_utc":clock.isoformat(),
        "external_signature_BLS_verified":False,
        "cryptographic_trust_gate":"NOT_PASSED_BLS_UNVERIFIED",
        "experimental_retrocausality_proven":False,
    }
    if present != BEACONS:
        result["status"]="INCOMPLETE_NO_SCORE"
    else:
        matches=sum(pred[i]==row["bit"] for i,row in enumerate(observations))
        result.update({
          "status":"FULL_BEACON_OBSERVATIONS__BLS_VERIFICATION_PENDING",
          "matches":matches, "accuracy":matches/BEACONS,
          "one_sided_binomial_p":binomial_tail(BEACONS,matches),
          "alpha":0.001,
          "passes_nominal_statistical_gate":binomial_tail(BEACONS,matches)<0.001,
          "interpretation":"Control predicts randomness; nominal statistical outlier is not retrocausal evidence"
        })
    return result


def noaa_url():
    day=utc(NOAA_DATE+"T00:00:00Z")
    jday=day.timetuple().tm_yday
    return f"{NOAA_BASE}bon/{day.year}/bon{day.strftime('%y')}{jday:03}.dat"


def parse_surfrad(raw):
    text=raw.decode("utf-8")
    lines=text.splitlines()
    if len(lines)<62:
        raise ValueError("SURFRAD_FILE_TOO_SHORT")
    # First two SURFRAD lines are site name and station metadata.
    result={}
    for line in lines[2:]:
        cols=line.split()
        if len(cols)<10:
            raise ValueError("SURFRAD_ROW_MALFORMED")
        year,jday,month,day,hour,minute=map(int,cols[:6])
        if (year,month,day)!=(2026,11,12) or jday!=316:
            raise ValueError("WRONG_SURFRAD_DAY")
        minute_of_day=hour*60+minute
        if minute_of_day in result:
            raise ValueError("SURFRAD_DUPLICATE_MINUTE")
        if minute_of_day in TARGET_MINUTES:
            val=float(cols[8])
            qc=int(float(cols[9]))
            if not math.isfinite(val):
                raise ValueError("SURFRAD_NONFINITE")
            result[minute_of_day]={"minute":minute_of_day,"dw_solar":val,
                "dw_solar_flag":qc}
    return result


def score_noaa(plan, fetcher=fetch_http, now_utc=None):
    validate_plan(plan)
    clock=now_utc if now_utc is not None else now()
    if clock <= utc("2026-11-13T00:00:00Z"):
        raise ValueError("TARGET_DAY_IS_NOT_YET_OVER")
    url=noaa_url()
    try:
        raw=fetcher(url)
    except Exception as ex:
        return {"schema":"janus.ocean.open009.noaa_score.v1",
                "status":"PENDING_NOAA_PUBLICATION_NO_SCORE",
                "source_url":url,"error":str(ex)[:150],
                "forecast_sha256":digest(plan)}
    try:
        rows=parse_surfrad(raw)
    except Exception as ex:
        return {"schema":"janus.ocean.open009.noaa_score.v1",
                "status":"REJECTED_SOURCE_FORMAT_NO_SCORE",
                "source_url":url,
                "source_raw_sha256":hashlib.sha256(raw).hexdigest(),
                "error":str(ex)[:150]}
    bad=[i for i in TARGET_MINUTES if i not in rows
         or rows[i]["dw_solar"]<=-999 or rows[i]["dw_solar_flag"]!=0]
    result={
      "schema":"janus.ocean.open009.noaa_score.v1",
      "source_url":url,"source_raw_sha256":hashlib.sha256(raw).hexdigest(),
      "expected_n":60,
      "valid_n":60-len(bad),
      "bad_or_missing_minute_indices":bad,
      "forecast_sha256":digest(plan),
      "retrieved_utc":clock.isoformat(),
      "physical_retrocausality_proven":False,
    }
    if bad:
        result["status"]="QC_OR_MISSING_ROWS_NO_SCORE"
        return result
    actual=[rows[i]["dw_solar"] for i in TARGET_MINUTES]
    pred=plan["noaa"]["forecast_W_m2"]
    def mae(forecast):
        return sum(abs(a-b) for a,b in zip(actual,forecast))/len(actual)
    result.update({
      "status":"COMPLETE_PUBLIC_SURFRAD_WINDOW_SCORED",
      "mae_solar_proxy_Wm2":round(mae(pred),6),
      "mae_baseline_zero_Wm2":round(mae([0.0]*60),6),
      "mae_baseline_constant250_Wm2":round(mae([250.0]*60),6),
      "solar_proxy_beats_both_baselines":(
        mae(pred)<min(mae([0.0]*60),mae([250.0]*60))),
      "actual_irradiance_Wm2":actual,
      "note":"Observational irradiance, not free choice or photon time-of-flight"
    })
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["validate","score-drand","score-noaa"])
    p.add_argument("--plan",default=str(PLAN))
    p.add_argument("--output")
    args=p.parse_args()
    plan=json.loads(Path(args.plan).read_text())
    validate_plan(plan)
    if args.mode=="validate":
        result={"status":"PRECOMMIT_PROTOCOL_MATCHES_SOURCE",
                "forecast_sha256":digest(plan),
                "drand_n":BEACONS,"noaa_n":60,
                "future_drand_first_round":first_round(),
                "target_end_utc":end_time().isoformat(),
                "qpu_minutes":0,"physical_retrocausality_proven":False}
    elif args.mode=="score-drand":
        result=score_drand(plan)
    else:
        result=score_noaa(plan)
    if args.output:
        write_new(args.output,result)
    print(json.dumps({k:v for k,v in result.items()
                      if k!="raw_observations" and k!="actual_irradiance_Wm2"},
                     sort_keys=True))
    if result.get("status") in ("INCOMPLETE_NO_SCORE",
                                "REJECTED_SOURCE_FORMAT_NO_SCORE",
                                "QC_OR_MISSING_ROWS_NO_SCORE"):
        raise SystemExit(2)


if __name__=="__main__":
    main()
