#!/usr/bin/env python3
"""JANUS Retro Byte Probe: operational vs postselected 8-bit channels.

Implements exact computational-basis probabilities of eight Bell pairs.
For each attempt:
 t0: record eight early outcomes A; irrevocably fixed.
 t1: independently choose a future byte M.
 t2: apply X^M to the late halves, add bit-flip noise, measure late B.
 t3: optionally *postselect* B == 0x00.

This reproduces one simple PCTC-inspired conditioning statistic, but NOT
the four-qubit Huang et al. protocol, nor a real CTC, nor quantum hardware.
The audit explicitly distinguishes:
 - raw early A versus late M: operationally available at t0
 - A versus M after accepting only trials with B==0: available only at t3
A future-chosen byte cannot be known at t0 from the latter result.

No production JANUS checkpoint is modified; no secret key is read.
References: Ji/Lloyd/Wilde PRL 136 230801 (2026), Huang et al. PRR 8
023084 (2026), Nature Reviews Physics review DOI 10.1038/s42254-024-00739-8.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random

BITS = 8
ALPHABET = 256
DEFAULT_SHOTS = 65536
VERSION = "janus.retro.byte_channel_probe.v1"
NOISE_LEVELS = (0.0, 0.05, 0.20)


def output(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        raise RuntimeError("REFUSE_REWRITE_EXPERIMENT_RESULT")
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def bit_errors(a, b):
    return (a ^ b).bit_count()


def noisy_mask(rng, epsilon):
    # Independent noise source for each of the 8 Bell branches.
    mask = 0
    for k in range(BITS):
        if rng.random() < epsilon:
            mask |= 1 << k
    return mask


def exact_model(epsilon):
    if not 0. <= epsilon <= 0.5:
        raise RuntimeError("NOISE_OUTSIDE_VALID_RANGE")
    return {
        "P_early_byte_equals_independent_future_byte_unconditional": 1 / ALPHABET,
        "P_early_bit_equals_independent_future_bit_unconditional": 0.5,
        "P_late_zero_byte_success": 1 / ALPHABET,
        "P_early_byte_equals_future_byte_conditioned_on_late_zero": (1-epsilon)**BITS,
        "P_early_bit_equals_future_bit_conditioned_on_late_zero": 1-epsilon,
        "preselection_operational_information_bits": 0.,
        "conditional_binary_mutual_information_per_bit": (
            1 - (0 if epsilon in (0,1) else
                 -epsilon * math.log2(epsilon) - (1-epsilon)*math.log2(1-epsilon))
        ),
    }


def simulate_byte_lane(shots, epsilon, seed):
    if not 256 <= shots <= 1000000:
        raise RuntimeError("SHOT_BUDGET_OUT_OF_BOUND")
    # Separate seed streams: earlier outcomes, later choices, measurement noise.
    early_rng = random.Random(seed ^ 0xA5199E)
    late_rng = random.Random(seed ^ 0xB22A0F)
    noise_rng = random.Random(seed ^ 0xC88D3D)
    early_exact = early_bits_correct = 0
    selected = selected_exact = selected_bits_correct = 0
    early_a_digest = hashlib.sha256()
    future_m_digest = hashlib.sha256()
    for _ in range(shots):
        # t0 - receiver record is fixed before any future byte is sampled.
        a = early_rng.getrandbits(BITS)
        early_a_digest.update(bytes([a]))
        # t1 - future user choice is sampled only after the earlier observation.
        m = late_rng.getrandbits(BITS)
        future_m_digest.update(bytes([m]))
        # t2 - late-half Bell measurement with independent bit-flip noise.
        late_b = a ^ m ^ noisy_mask(noise_rng, epsilon)
        equal = BITS - bit_errors(a, m)
        early_bits_correct += equal
        if a == m:
            early_exact += 1
        # t3 - this *conditional* sample was unavailable at t0.
        if late_b == 0:
            selected += 1
            selected_bits_correct += equal
            if a == m:
                selected_exact += 1
    if selected == 0:
        raise RuntimeError("ZERO_POSTSELECTED_SAMPLES")
    theory = exact_model(epsilon)
    return {
        "model": "EIGHT_INDEPENDENT_BELL_PAIRS_WITH_LATE_X_AND_Z_MEASUREMENT",
        "state_preparation": "Each Bell pair |Phi+> = (|00> + |11>)/sqrt(2)",
        "noise_bit_flip_probability": epsilon,
        "raw_attempts": shots,
        "raw_early_equals_future_full_byte_count": early_exact,
        "raw_early_equals_future_full_byte_rate": round(early_exact / shots, 8),
        "raw_early_equals_future_bit_count": early_bits_correct,
        "raw_early_equals_future_bit_rate": round(early_bits_correct / (BITS * shots), 8),
        "late_postselection_predicate": "late measurement of all 8 B halves equals 0x00",
        "selected_attempts": selected,
        "postselection_acceptance_rate": round(selected / shots, 8),
        "selected_early_equals_future_byte_count": selected_exact,
        "selected_early_equals_future_byte_rate": round(selected_exact / selected, 8),
        "selected_early_equals_future_bit_rate": round(selected_bits_correct / (BITS * selected), 8),
        "early_bytes_stream_sha256": early_a_digest.hexdigest(),
        "future_bytes_stream_sha256": future_m_digest.hexdigest(),
        "analytical_probabilities": theory,
        "operational_future_byte_decoded_before_sender_chose_byte": False,
        "early_receiver_has_access_to_late_selection_flag": False,
        "late_conditioning_can_be_used_for_future_to_past_operational_communication": False,
        "hardware_run": False,
        "scientific_status": "SIMULATED_STANDARD_QM_Z_BASIS_CORRELATIONS_NOT_PCTC_CHANNEL",
    }


def switch_exact():
    # Controlled superposition of order of Pauli operators X and Z.
    # XZ|0> = |1>, ZX|0> = -|1>, so the control is |->,
    # and the coherent minus-port click probability is 1.
    # This is the *correct* quantum-switch interference signature,
    # but even if a hardware switch realizes it, it is not a message from
    # an arbitrary later user choice to a previously measured classical bit.
    sqrt2 = math.sqrt(2)
    xp = complex(1,0)
    zx0 = -xp
    xz0 = xp
    plus_port = abs((xz0+zx0)/2)**2
    minus_port = abs((xz0-zx0)/2)**2
    assert abs(plus_port)<1e-15 and abs(minus_port-1)<1e-15
    return {
        "route": "QUANTUM_SWITCH_XZ_ZX_PROCESS_ORDER_WITNESS",
        "input_target": "|0>",
        "gate_order_amplitudes": {"XZ_0_to_1": 1, "ZX_0_to_1": -1},
        "coherent_control_plus_probability": round(plus_port,12),
        "coherent_control_minus_probability": round(minus_port,12),
        "correct_switch_signature_mathematically_reproduced": True,
        "future_to_past_single_byte_capacity_demonstrated": False,
        "physical_hardware_used": False,
        "why_not_a_backward_channel": "The relative phase depends on coherent control of operations within the physical switch, not on an independently chosen classical message after its earlier detector result.",
    }


def guard(candidate, physically_implemented=False):
    """A candidate may enter JANUS production only with *real* early data.

    Mathematically exact conditional results are never accepted as the
    output of a physical backwards-time interface.
    """
    if not physically_implemented:
        return {"promote": False, "reason": "NO_AUTHENTICATED_PHYSICAL_BACKWARD_TIME_INTERFACE"}
    # Any future physical implementation would additionally require a
    # separately audited prospective, preregistered protocol.
    return {"promote": False, "reason": "NO_PROSPECTIVE_HARDWARE_EARLY_BYTE_DATA_OR_INDEPENDENT_REPLICATION"}


def run(shots, seed):
    lanes = [simulate_byte_lane(shots, noise, seed+round(noise*100000))
             for noise in NOISE_LEVELS]
    switch = switch_exact()
    # Positive test of the detector (NOT an actual chronological run): the
    # early record is explicitly assigned the *later* byte, a leakage oracle.
    # It gets 100% agreement but is not a genuine backward channel.
    positive_control = {
        "label": "INJECTED_DATA_LEAKAGE_POSITIVE_CONTROL",
        "design": "fake early = later message; intentionally violates early-before-late rule",
        "raw_exact_byte_accuracy": 1.,
        "leakage_violation_flag": True,
        "promotable": False,
    }
    result = {
        "schema": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_code": "experiments/ocean_transformer/retro_byte_channel_probe.py",
        "scope": "Pure-Python reproducible analytic and Monte Carlo tests, not live quantum hardware",
        "attempts_per_noise_level": shots,
        "seed_for_reproducible_nonphysical_simulation": seed,
        "requested_payload_bits": 8,
        "candidate_methods": [
            "PCTC_INSPIRED_EIGHT_BELL_PAIR_LATE_POSTSELECTION",
            "NOISY_BELL_BRANCHES",
            "QUANTUM_SWITCH_XZ_ZX_CAUSAL_ORDER_WITNESS",
            "INTENTIONAL_DATA_LEAKAGE_CONTROL"
        ],
        "noise_experiments": lanes,
        "quantum_switch_mathematical_control": switch,
        "deliberate_leakage_detector_positive_control": positive_control,
        "gates": {
            "postselected_byte_lane": guard(lanes[0]),
            "noisy_channel_lane": guard(lanes[-1]),
            "quantum_switch_lane": guard(switch)
        },
        "observed_actual_physical_backward_bit_channel": False,
        "janus_production_promoted": False,
        "next_real_world_requirement": "Independent late random byte selected only after earlier physical measurement is sealed; validate early raw statistics before ANY postselection with third-party timestamp and full shot logs. Requires genuine lab hardware to test.",
        "no_signalling_diagnostic": "The unconditional early data's distribution is independent of future byte. Postselection flag is not available until the later operation; selected correlations are retrospective, not early received messages.",
    }
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--shots", type=int, default=DEFAULT_SHOTS)
    parser.add_argument("--seed", type=int, default=2026110611)
    args=parser.parse_args()
    output(args.output, run(args.shots,args.seed))


if __name__ == "__main__":
    main()
