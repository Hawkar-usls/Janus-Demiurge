#!/usr/bin/env python3
"""JANUS gull spatial cognition: measured FOV constraints + two toy observers.

This is a FAIR comparative *computational* benchmark, NOT an empirical
model comparison of gull brains. The published Cantlay et al. (2024) data
constrain optics only: 3 species, 10 gulls, group maxima/means. The actual
per-bird retinal tables and behavior/action/fitness labels are NOT ingested.

The models receive identical synthetic visual inputs Y=(bearing, object type).
One 1-bit representation minimizes metric angular reconstruction error;
the other maximizes expected action utility. Both may choose an optimal
action given their compressed representation. Exhaustive 2^7 partitions
avoid optimization randomness and fit/p-value theater. An uncompressed
observer with the same raw input is an exact upper bound on fitness.

One-slice optical proxy (peak frontal binocular field and midline dorsal
blind onset) is a transparent approximation, not a calibrated 3D retinal
map. No bird's eyes/brain connectome or bird behavior was emulated.

Source gull optics: Cantlay, Portugal & Martin (2024), Ibis,
DOI 10.1111/ibi.13360.
Hoffman et al. (2015), DOI 10.3758/s13423-015-0890-8.
Critical comparison: Mattes (2026), DOI 10.1007/s13752-026-00531-0.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import product
import hashlib
import json
from pathlib import Path

SOURCE_DOI = "10.1111/ibi.13360"
ANGLE_GRID = (-12, -4, 4, 12)  # °: invented experimental toy scene bearings
KIND_GRID = ("prey", "hazard")  # invented visual classification, NOT measured
ACTION_GRID = ("left", "right", "evade")
FROZEN_STATES = tuple((kind, bearing) for kind in KIND_GRID
                      for bearing in ANGLE_GRID)
FROZEN_CAPACITY_BITS = 1
UNIFORM_STATE_PROB = F(1, len(FROZEN_STATES))
FIELD_METRICS = {
    "max_binocular_width_degrees": (35.1, 1.2),
    "vertical_binocular_extent_degrees": (111., 5.7),
    "lateral_monocular_field_width_each_degrees": (142., 2.0),
    "anterior_dorsal_blind_sector_starts_above_horizontal_degrees": (46., 1.3),
    "binocular_peak_above_eye_bill_axis_degrees": (11.7, 1.7),
    "dorsal_blind_width_degrees": (32.1, 5.5),
    "rear_blind_width_degrees": (40.7, 2.3),
}
EXPECTED_SAMPLE_COUNTS = {
    "Larus argentatus": 4, "Larus fuscus": 3, "Rissa tridactyla": 3
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def source_data(path: Path):
    raw = path.read_bytes()
    obj = json.loads(raw)
    check(obj.get("schema") == "janus.gull_visual_field.literature_summary.v1",
          "BAD_SOURCE_SCHEMA")
    p = obj.get("provenance", {})
    check(p.get("source_doi") == SOURCE_DOI and
          p.get("individual_measurement_table_verified_and_imported") is False
          and p.get("individual_measurement_rows_reconstructed") is False,
          "MISSING_PUBLISHED_ORIGINAL_DATA_LIMIT")
    species = obj.get("studied_species", [])
    counts = {x["scientific_name"]:x["sample_size_individuals"]
              for x in species}
    check(counts == EXPECTED_SAMPLE_COUNTS and sum(counts.values()) == 10,
          "SPECIES_SAMPLE_SIZES_NOT_GROUNDED")
    measurements = obj.get("published_cross_species_summaries", {})
    check(set(measurements) == set(FIELD_METRICS),
          "PUBLISHED_FIELD_LIST_CHANGED")
    for key, (mean, se) in FIELD_METRICS.items():
        given = measurements[key]
        check(given == {"mean": mean, "standard_error": se},
              "PUBLISHED_FIELD_VALUE_CHANGED_"+key)
    check("no measured choice-action-reward data" in
          " ".join(obj.get("measurement_limitations", [])),
          "BEHAVIOR_DATA_LIMITATION_OMITTED")
    return obj, hashlib.sha256(raw).hexdigest()


def frontal_binocular_peak_proxy(bearing_deg: float, source: dict):
    """Approximate azimuth at the elevation of maximal overlap ONLY."""
    width = source["published_cross_species_summaries"][
        "max_binocular_width_degrees"]["mean"]
    return abs(bearing_deg) <= width / 2


def sagittal_midline_flight_proxy(world_elev_deg: float,
                                  pitch_down_deg: float, source: dict):
    """Simplified 1D projection: head-down pitch rotates horizontal ray up.

    Return a proxy, not a prediction of a full retinal boundary. In
    particular the vertical extent DOES NOT specify the full 3D mask.
    """
    blind_start = source["published_cross_species_summaries"][
        "anterior_dorsal_blind_sector_starts_above_horizontal_degrees"]["mean"]
    local_elev = world_elev_deg + pitch_down_deg
    return {
        "world_elevation_deg": world_elev_deg,
        "head_pitch_down_deg": pitch_down_deg,
        "head_relative_elevation_deg": local_elev,
        "anterior_midline_blind_sector_proxy": local_elev >= blind_start,
        "assumes_static_head_and_1d_projection": True,
    }


def payoff(state, action, reward_world):
    """Invented action/reward table, NEVER claimed to be gull behavior."""
    kind, angle = state
    check(reward_world in ("hazard_costly", "all_safe"),
          "UNKNOWN_SYNTHETIC_REWARD_WORLD")
    check(action in ACTION_GRID, "UNKNOWN_ACTION")
    if reward_world == "all_safe" or kind == "prey":
        if action == "evade":
            return F(1, 10)
        correct = (angle < 0 and action == "left") or (
                    angle > 0 and action == "right")
        return F(3) if correct else F(-1)
    return F(2) if action == "evade" else F(-4)


def partitions():
    """All two-symbol encoders, modulo global code-label swaps, 127 total."""
    for mask in range(1, 1 << (len(FROZEN_STATES)-1)):
        codes = tuple([0] + [(mask >> (i-1)) & 1
                            for i in range(1, len(FROZEN_STATES))])
        yield codes


def score_encoder(codes, reward_world):
    check(len(codes) == len(FROZEN_STATES) and set(codes) == {0,1},
          "ENCODER_NOT_TWO_NONEMPTY_SYMBOLS")
    expected_angle_mse = F(0)
    expected_reward = F(0)
    codebook = {}
    for code in (0,1):
        members = [s for s, encoded in zip(FROZEN_STATES, codes)
                   if encoded == code]
        mean = sum((F(angle) for kind,angle in members),F(0))/len(members)
        expected_angle_mse += sum(((F(angle)-mean)**2 for kind,angle
                                   in members),F(0))*UNIFORM_STATE_PROB
        ranked = [(sum((payoff(s,a,reward_world) for s in members),F(0))
                    *UNIFORM_STATE_PROB, a) for a in ACTION_GRID]
        best_pay = max(p for p,a in ranked)
        # Frozen deterministic tie-breaking.
        action = next(a for a in ACTION_GRID if
                      any(a == b and best_pay == p for p,b in ranked))
        expected_reward += best_pay
        codebook[str(code)] = {"mean_bearing_degrees":str(mean),
                               "optimal_action":action,
                               "world_states":[f"{k}:{a}" for k,a in members]}
    return expected_angle_mse, expected_reward, codebook


def exhaustive_comparison(reward_world):
    scored = [(score_encoder(c, reward_world), c) for c in partitions()]
    check(len(scored) == 127, "PARTITION_ENUMERATION_INCOMPLETE")
    # Both codes use the same two symbols. Geometry compression is optimized
    # for truth-of-angle reconstruction, then gets the BEST action policy
    # possible from its own 1-bit code. Interface compression optimizes
    # reward directly, then is ALSO scored on angular truth reconstruction.
    geometry_result, geometry_codes = min(scored, key=lambda t:(
        t[0][0],-t[0][1],t[1]))
    interface_result, interface_codes = min(scored, key=lambda t:(
        -t[0][1],t[0][0],t[1]))
    full_input_max = sum((max(payoff(s,a,reward_world)
                               for a in ACTION_GRID)*UNIFORM_STATE_PROB
                          for s in FROZEN_STATES), F(0))
    check(full_input_max >= interface_result[1] >= geometry_result[1],
          "DATA_PROCESSING_BOUND_VIOLATED")
    check(geometry_result[0] <= interface_result[0],
          "GEOMETRIC_OPTIMUM_CONTRADICTED")
    def record(result, codes):
        mse, reward, book = result
        return {
           "codes":list(codes),
           "angle_mse_deg2_exact":str(mse),
           "action_expected_reward_exact":str(reward),
           "codebook":book,
        }
    return {
        "reward_environment":reward_world,
        "toy_states":len(FROZEN_STATES),
        "available_input":"perfect synthetic (object_kind, bearing_degrees) for both",
        "prior":"uniform 1/8 over each of eight invented scenes",
        "representation_capacity_bits":FROZEN_CAPACITY_BITS,
        "possible_encoders_exhaustively_checked":len(scored),
        "geometry_angle_MSE_optimized":record(geometry_result,geometry_codes),
        "fitness_action_reward_optimized":record(interface_result,interface_codes),
        "full_input_optimal_action_reward_upper_bound":str(full_input_max),
        "interface_minus_geometry_reward_exact":str(interface_result[1]-
                                                     geometry_result[1]),
        "interface_minus_geometry_angle_MSE_exact":str(interface_result[0]-
                                                        geometry_result[0]),
        "theoretical_result":"Under a frozen one-bit bottleneck, a code optimized for angle reconstruction need not maximize action reward. This is a resource/tradeoff effect, not proof of Hoffman's ontology.",
        "no_empirical_gull_action_labels":True
    }


def report(source:dict, sha: str):
    fov = source["published_cross_species_summaries"]
    normal = sagittal_midline_flight_proxy(0,0,source)
    pitched = sagittal_midline_flight_proxy(0,50,source)
    check(not normal["anterior_midline_blind_sector_proxy"] and
          pitched["anterior_midline_blind_sector_proxy"],
          "PUBLISHED_HEAD_PITCH_CONSISTENCY_FAILED")
    check(all(frontal_binocular_peak_proxy(angle,source)
              for kind,angle in FROZEN_STATES),
          "TOY_STATES_OUTSIDE_PUBLISHED_MAXIMUM_BINOCULAR_CONSTRAINT")
    hazard=exhaustive_comparison("hazard_costly")
    safe=exhaustive_comparison("all_safe")
    check(hazard["geometry_angle_MSE_optimized"][
               "angle_mse_deg2_exact"] ==
          safe["geometry_angle_MSE_optimized"][
               "angle_mse_deg2_exact"],
          "OPTICAL_GEOMETRY_SHOULD_BE_INDEPENDENT_OF_REWARD_ASSUMPTION")
    return {
      "schema":"janus.gull_geometry_vs_interface.comparison.v1",
      "source_doi":SOURCE_DOI,
      "source_file_sha256":sha,
      "real_birds_total":sum(x["sample_size_individuals"]
                             for x in source["studied_species"]),
      "studied_species":source["studied_species"],
      "empirical_calibration":{
        "published_summary":fov,
        "max_binocular_reference_half_angle_deg":
            fov["max_binocular_width_degrees"]["mean"]/2,
        "forward_ray_rest":normal,
        "forward_ray_at_50deg_head_down":pitched,
        "qualitative_source_pitched_blind_consistency_pass":True,
        "source_is_3_species_aggregate_not_individual_trials":True,
        "complete_retinal_sphere_reconstructed_from_source":False,
        "independent_species_holdout_available":False,
        "actual_gull_behavior_or_fitness_measured":False
      },
      "synthetic_exhaustive_worlds":[hazard,safe],
      "theorem":"An unrestricted observer with Y and arbitrary decision policy can emulate any interface C=f(Y). Therefore max_a E[U|Y] >= max_a E[U|C] by conditional optimization. A capacity bottleneck can reverse the ranking of two restricted encoders optimized for different loss functions, but cannot establish which biological perceptual theory is true.",
      "theorem_checked_in_finite_worlds":True,
      "physical_vision_theory_identification":"NOT_IDENTIFIABLE_FROM_VISUAL_FIELD_GEOMETRY_ONLY",
      "higher_level_experimental_data_needed":["individual 3D retinal field boundary tables or equivalent",
          "measured fixation/head pitch during controlled tasks",
          "identical stimulus sets with known bearings/types",
          "trial-wise choices, response times and fitness/foraging/collision outcomes",
          "predeclared competing loss/reward functions and matched representation capacities",
          "out-of-sample species or individual validation"],
      "model_is_real_seagull_neural_connectome":False,
      "trained_transformer_or_production_model_modified":False,
      "research_only":True,
      "verdict":"PUBLISHED_GULL_FOV_CONSTRAINTS_PASS__SYNTHETIC_REPRESENTATION_TRADEOFF_PROVEN__NO_EMPIRICAL_HOFFMAN_VS_GEOMETRY_WINNER"
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=Path(__file__).with_name(
        "laridae_visual_measurements_v1.json"))
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    check(not args.out.exists(), "REFUSE_TO_OVERWRITE_RESEARCH_EVIDENCE")
    source,sha=source_data(args.source)
    result=report(source,sha)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,
                                    indent=2)+"\n",encoding="utf8")
    print(json.dumps({
        "birds":result["real_birds_total"],
        "synthetic_world_rewards":[
            {"mode":x["reward_environment"],
             "geometry":x["geometry_angle_MSE_optimized"][
                 "action_expected_reward_exact"],
             "interface":x["fitness_action_reward_optimized"][
                 "action_expected_reward_exact"],
             "difference":x["interface_minus_geometry_reward_exact"]}
            for x in result["synthetic_exhaustive_worlds"]],
        "real_behavior_theory_winner":None
    },sort_keys=True))


if __name__ == "__main__":
    main()
