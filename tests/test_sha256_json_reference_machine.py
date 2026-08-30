from pathlib import Path
import importlib.util
import sys


MODULE = Path(__file__).resolve().parents[1] / "trump" / "sha256_json_reference_machine.py"
SPEC = importlib.util.spec_from_file_location("sha256_json_reference_machine", MODULE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def test_published_vectors_and_hashlib_replay():
    result = MOD.selftest()
    assert result["terminal"] == "SHA256_JSON_REFERENCE_MACHINE_SELFTEST_PASS"
    assert result["vectors_passed"] == 3
    assert result["scientific_boundary"] == "P_VS_NP_OPEN"


def test_rank_is_exactly_round_count_and_ends_at_zero():
    receipt = MOD.execute(b"abc")
    assert receipt["initial_rank"] == receipt["rounds_executed"]
    assert receipt["final_rank"] == 0
    assert receipt["rank_strict_unit_descent"] is True


def test_working_state_respects_frozen_json_bound():
    for n in (0, 1, 55, 56, 63, 64, 65, 1024):
        receipt = MOD.execute(b"x" * n)
        assert receipt["max_working_words_observed"] <= receipt["declared_working_words_upper_bound"]


def test_candidate_next_action_is_unique():
    receipt = MOD.execute(b"route-law")
    assert receipt["candidate_next_action_count_per_round"] == 1
    assert receipt["pcner_axes"]["POLY_FIND"] == "PASS_FOR_SHA256_CONTROL"


def test_sat_boundary_is_never_promoted():
    receipt = MOD.execute(b"not-a-sat-proof")
    b = receipt["scientific_boundary"]
    assert b["SAT_transfer_claimed"] is False
    assert b["universal_GPEI_for_SAT_proved"] is False
    assert b["P_equals_NP_proved"] is False
    assert b["P_VS_NP"] == "OPEN"
