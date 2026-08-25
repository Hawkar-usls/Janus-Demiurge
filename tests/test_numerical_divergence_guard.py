from restored.numerical_divergence_guard import assess, sanitize_state


def test_blackhole_threshold_yields_proposal_without_mutation_authority():
    r = assess({"a": 26.0, "b": -2.0}, 4.0, current_lr_scale=1.0)
    assert r["status"] == "STABILIZATION_PROPOSAL"
    assert r["candidate"]["weights"] == {"a": 3.0, "b": -2.0}
    assert r["candidate"]["bias"] == 3.0
    assert r["candidate"]["lr_scale"] == 0.6
    assert r["authority"]["mutates_weights"] is False
    assert r["authority"]["changes_learning_rate"] is False


def test_nonfinite_weights_are_explicit_trigger_and_not_preserved():
    r = assess({"ok": 1.0, "nan": float("nan")}, float("inf"))
    assert r["status"] == "STABILIZATION_PROPOSAL"
    assert r["observed"]["nonfinite_weight_keys"] == ["nan"]
    assert r["observed"]["bias_nonfinite"] is True
    assert r["candidate"]["weights"] == {"ok": 1.0}
    assert r["candidate"]["bias"] == 0.0


def test_state_sanitizer_is_bounded_and_proposal_only():
    payload = {
        "input_keys": [f"k{i}" for i in range(70)],
        "weights": {"x": 99.0, "y": float("nan"), "z": -4.0},
        "bias": float("nan"),
        "best_score": float("inf"),
        "history_tail": list(range(80)),
    }
    r = sanitize_state(payload)
    assert len(r["input_keys"]) == 64
    assert r["weights"] == {"x": 10.0, "z": -4.0}
    assert r["bias"] == 0.0
    assert r["best_score"] == -1e9
    assert len(r["history_tail"]) == 64
    assert r["authority"]["writes_model_state"] is False
