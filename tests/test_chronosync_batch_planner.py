from restored.chronosync_batch_planner import plan_batch


def test_priority_and_fifo():
    r = plan_batch([
        {"source": "a", "timestamp": 1, "data": "n"},
        {"source": "b", "timestamp": 2, "data": "c", "critical": True},
        {"source": "c", "timestamp": 3, "data": "n2"},
    ], max_batch=3)
    assert [p["source"] for p in r["selected"]] == ["b", "a", "c"]
    assert r["authority"]["writes_memory"] is False


def test_adaptive_and_deferred():
    rows = [{"source": f"s{i}", "timestamp": i, "data": "x"} for i in range(12)]
    r = plan_batch(rows, current_interval_s=1.0, max_batch=5)
    assert r["rate_state"] == "ACCELERATE"
    assert r["suggested_next_interval_s"] == 0.8
    assert r["selected_count"] == 5
    assert r["deferred_count"] == 7


def test_conflict_is_detected_not_resolved():
    r = plan_batch([
        {"source": "a", "timestamp": 1, "data": 1, "conflict_key": "k"},
        {"source": "CORE", "timestamp": 2, "data": 2, "conflict_key": "k"},
    ])
    assert r["unresolved_conflict_keys"] == ["k"]
    assert r["authority"]["resolves_conflicts"] is False
