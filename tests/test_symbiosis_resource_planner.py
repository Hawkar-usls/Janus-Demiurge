from restored.symbiosis_resource_planner import propose


def test_low_pressure_keeps_base_plan_without_actuation():
    r=propose(base_batch=128,gpu_load=20,cpu_load=10,gpu_temp_c=50,igpu_load=10,cache_ratio=1.0,gaming_mode=False)
    assert r["status"]=="PLAN_ONLY"
    assert r["reason"]=="LOW_PRESSURE"
    assert r["proposal"]=={"batch_size":128,"pause_seconds":0.0}
    assert r["authority"]["changes_batch"] is False
    assert r["authority"]["sleeps_process"] is False


def test_pressure_reduces_batch_as_power_of_two_and_only_proposes_pause():
    r=propose(base_batch=128,gpu_load=80,cpu_load=50,gpu_temp_c=75,igpu_load=20,cache_ratio=1.0,gaming_mode=False)
    assert r["reason"]=="PRESSURE_ADAPTATION"
    assert r["proposal"]["batch_size"]==16
    assert r["proposal"]["pause_seconds"]==2.0
    assert r["authority"]["changes_power_limit"] is False


def test_gaming_mode_is_conservative_plan_not_game_control():
    r=propose(base_batch=128,gpu_load=0,cpu_load=0,gpu_temp_c=30,gaming_mode=True)
    assert r["reason"]=="GAMING_MODE"
    assert r["proposal"]=={"batch_size":32,"pause_seconds":3.0}
    assert r["authority"]["controls_game"] is False
