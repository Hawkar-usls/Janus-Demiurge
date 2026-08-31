#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "scout_swarm" / "missions" / "HA10_REVERSE_SPIRAL_COUNCIL-v1.json"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"NOT_JSON_OBJECT:{path}")
    return value


def load_mission() -> dict[str, Any]:
    mission = load_json(MISSION)
    if mission.get("status") != "AUTHORIZED_TO_RUN":
        raise ValueError("MISSION_NOT_AUTHORIZED")
    roles = mission.get("roles") or []
    if len(roles) != 17 or len({r.get('id') for r in roles}) != 17:
        raise ValueError("MISSION_MUST_HAVE_17_UNIQUE_ROLES")
    return mission


def input_verdict(payload: dict[str, Any]) -> str:
    for key_path in (
        ("new_result", "verdict"),
        ("result", "verdict"),
        ("verdict",),
    ):
        cur: Any = payload
        ok = True
        for key in key_path:
            if not isinstance(cur, dict) or key not in cur:
                ok = False
                break
            cur = cur[key]
        if ok and isinstance(cur, str):
            return cur
    return "UNSPECIFIED"


BASE_BY_VERDICT: dict[str, dict[str, float]] = {
    "PUBLIC_STATIONXML_DOES_NOT_ENCODE_KNOWN_FAULT_ERA_CHANGE": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 100,
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 86,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 84,
        "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1": 74,
        "COUSTEAU_HA10_WAIT_FOR_CUSTODIAN_CALIBRATION_REPLY": 32,
        "COUSTEAU_HA10_119HZ_REINTERPRETATION": -1000,
    },
    "PUBLIC_STATIONXML_ENCODES_FAULT_ERA_RESPONSE_CHANGE": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 100,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 93,
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 82,
        "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1": 72,
        "COUSTEAU_HA10_WAIT_FOR_CUSTODIAN_CALIBRATION_REPLY": 35,
        "COUSTEAU_HA10_119HZ_REINTERPRETATION": -1000,
    },
    "MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 100,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 96,
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 84,
        "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1": 73,
        "COUSTEAU_HA10_WAIT_FOR_CUSTODIAN_CALIBRATION_REPLY": 36,
        "COUSTEAU_HA10_119HZ_REINTERPRETATION": -1000,
    },
    "BLOCKED_PUBLIC_RESPONSE_EPOCH_AUDIT": {
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 100,
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 94,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 92,
        "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1": 74,
        "COUSTEAU_HA10_WAIT_FOR_CUSTODIAN_CALIBRATION_REPLY": 48,
        "COUSTEAU_HA10_119HZ_REINTERPRETATION": -1000,
    },
}

ROLE_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "SCOUT_AURA_ORACLE_01": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 4,
        "COUSTEAU_HA10_119HZ_REINTERPRETATION": -1000,
    },
    "SCOUT_HRAIN_02": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 8},
    "SCOUT_INAIHR_03": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 10,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 5,
    },
    "SCOUT_COSMOS_04": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 10,
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 4,
    },
    "SCOUT_META_REGISTRY_05": {"COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 5},
    "SCOUT_DISTRIBUTED_SWARM_06": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 9},
    "SCOUT_TERMINAL_07": {
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 7,
        "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 6,
    },
    "SCOUT_DEMIHEAD_08": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 12},
    "SCOUT_FUNDAMENTUM_09": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 10},
    "SCOUT_CAT_10": {"COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 8},
    "SCOUT_SCOBY_11": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 7},
    "SCOUT_LAPIS_12": {"COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1": 10},
    "SCOUT_VOICE_13": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 9},
    "SCOUT_ECHO_PYRAMID_14": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 8,
        "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1": 5,
    },
    "SCOUT_TRANCEPTION_15": {
        "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 8,
        "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1": 4,
    },
    "SCOUT_AIFC_16": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 12},
    "SCOUT_GENESIS_17": {"COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1": 8},
}


def role_reason(role_id: str, gate_id: str, verdict: str, lens: str) -> str:
    if gate_id == "COUSTEAU_HA10_119HZ_REINTERPRETATION":
        return "VETO: frozen 119-Hz negative has zero authority delta and cannot be rescued by this branch."
    if gate_id == "COUSTEAU_HA10_PRE_POST_2013_CROSSTALK_TRIPLET_GATE_V1":
        return f"{lens}: direct six-channel raw-first pre/post comparison best separates a documented south-triplet fault/cross-talk parent from persistent site physics after result {verdict}."
    if gate_id == "COUSTEAU_HA10_FIRST_AVAILABLE_SIX_CHANNEL_BASELINE_V1":
        return f"{lens}: earliest simultaneously available six-channel data provide an independent backcast against the later 2013-2015 morphology."
    if gate_id == "COUSTEAU_HA10_CALIBRATION_SEQUENCE_PUBLIC_RECOVERY_V1":
        return f"{lens}: calibration provenance can test what changed in the measurement representation, but public absence cannot imply custodian absence."
    if gate_id == "COUSTEAU_HA10_NATIVE_BATHYMETRY_SWATH_INTERSECTION_V1":
        return f"{lens}: independent seabed geometry must remain a separate evidence lane because electronics cannot erase physical bathymetry."
    return f"{lens}: custodian waiting is a fallback only when current public evidence cannot discriminate further."


def run_role(role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    mission = load_mission()
    roles = {r["id"]: r for r in mission["roles"]}
    if role_id not in roles:
        raise ValueError(f"UNKNOWN_ROLE:{role_id}")
    candidates = {c["gate_id"]: c for c in mission["candidate_gates"]}
    verdict = input_verdict(payload)
    base = dict(BASE_BY_VERDICT.get(verdict, BASE_BY_VERDICT["MIXED_OR_PARTIAL_PUBLIC_RESPONSE_EPOCH_ENCODING"]))
    for gate_id, delta in ROLE_ADJUSTMENTS.get(role_id, {}).items():
        base[gate_id] = base.get(gate_id, 0.0) + delta
    base["COUSTEAU_HA10_119HZ_REINTERPRETATION"] = -1000.0
    ranked = sorted(base.items(), key=lambda kv: (-kv[1], kv[0]))
    role = roles[role_id]
    return {
        "schema": "janus.demiurge.reverse_spiral_role_vote.v1",
        "mission_id": mission["mission_id"],
        "input_sha256": canonical_hash(payload),
        "mode": "DETERMINISTIC_ROLE_LENS__MODEL_OUTPUT_NOT_EVIDENCE",
        "role_id": role_id,
        "lens": role["lens"],
        "input_verdict": verdict,
        "ranked_candidates": [
            {
                "rank": idx + 1,
                "gate_id": gate_id,
                "score": score,
                "reason": role_reason(role_id, gate_id, verdict, role["lens"]),
                "promotion_ceiling": candidates[gate_id]["promotion_ceiling"],
            }
            for idx, (gate_id, score) in enumerate(ranked)
        ],
        "vetoes": ["COUSTEAU_HA10_119HZ_REINTERPRETATION"],
        "authority": {"target_identity": "UNCONFIRMED", "authority_delta_for_119hz": 0},
    }


def aggregate(votes: list[dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    mission = load_mission()
    if len(votes) != 17 or len({v.get("role_id") for v in votes}) != 17:
        raise ValueError("AGGREGATE_REQUIRES_17_UNIQUE_ROLE_VOTES")
    expected_input_hash = canonical_hash(payload)
    if any(v.get("input_sha256") != expected_input_hash for v in votes):
        raise ValueError("VOTES_DO_NOT_BIND_TO_SAME_INPUT")
    all_gate_ids = [c["gate_id"] for c in mission["candidate_gates"]]
    stats: dict[str, Any] = {}
    for gate_id in all_gate_ids:
        scores: list[float] = []
        ranks: list[int] = []
        top1 = 0
        for vote in votes:
            row = next(r for r in vote["ranked_candidates"] if r["gate_id"] == gate_id)
            scores.append(float(row["score"]))
            ranks.append(int(row["rank"]))
            if int(row["rank"]) == 1:
                top1 += 1
        stats[gate_id] = {
            "mean_score": mean(scores),
            "mean_rank": mean(ranks),
            "top1_votes": top1,
            "min_score": min(scores),
            "max_score": max(scores),
        }
    allowed = [g for g in all_gate_ids if g != "COUSTEAU_HA10_119HZ_REINTERPRETATION"]
    selected = sorted(
        allowed,
        key=lambda g: (-stats[g]["top1_votes"], -stats[g]["mean_score"], stats[g]["mean_rank"], g),
    )[0]
    ordered = sorted(
        allowed,
        key=lambda g: (-stats[g]["top1_votes"], -stats[g]["mean_score"], stats[g]["mean_rank"], g),
    )
    return {
        "schema": "janus.demiurge.reverse_spiral_council_result.v1",
        "mission_id": mission["mission_id"],
        "status": "COUNCIL_COMPLETE__ADVISORY_NEXT_GATE_ONLY",
        "input_sha256": expected_input_hash,
        "input_verdict": input_verdict(payload),
        "roles_expected": 17,
        "roles_observed": 17,
        "selected_next_gate": selected,
        "ordered_next_gates": ordered,
        "gate_stats": stats,
        "vetoed_gate": "COUSTEAU_HA10_119HZ_REINTERPRETATION",
        "authority": {
            "council_output_is_scientific_evidence": False,
            "target_identity": "UNCONFIRMED",
            "authority_delta_for_119hz": 0,
            "frozen_negative_results_persist": True,
        },
        "canonical_answer": f"Run {selected} next; preserve all frozen results and keep bathymetry as an independent evidence lane.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--role")
    parser.add_argument("--votes-dir")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = load_json(Path(args.input))
    if args.role:
        result = run_role(args.role, payload)
    elif args.votes_dir:
        votes = [load_json(p) for p in sorted(Path(args.votes_dir).glob("*.json"))]
        result = aggregate(votes, payload)
    else:
        raise SystemExit("REQUIRE_ROLE_OR_VOTES_DIR")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS_APPEND_ONLY_REQUIRED")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result.get("status", "ROLE_VOTE"), "selected_next_gate": result.get("selected_next_gate")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
