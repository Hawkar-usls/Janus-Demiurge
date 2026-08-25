from restored.config_neighborhood_estimator import ConfigNeighborhoodEstimator


def test_insufficient_history_is_not_magic_numeric_prediction():
    est = ConfigNeighborhoodEstimator(min_history=3)
    est.observe({"lr": 0.01, "gain": 1.0}, 0.4)
    r = est.estimate({"lr": 0.01, "temp": 1.0})
    assert r["status"] == "INSUFFICIENT_HISTORY"
    assert r["estimate"] is None
    assert r["authority"]["claims_improvement_probability"] is False


def test_source_faithful_lr_neighborhood_mean_and_ignored_dimensions():
    est = ConfigNeighborhoodEstimator(min_history=3, lr_tolerance=0.005)
    est.observe({"lr": 0.010, "gain": 0.5, "temp": 0.5}, 0.2)
    est.observe({"lr": 0.012, "gain": 2.0, "temp": 2.0}, 0.6)
    est.observe({"lr": 0.030, "gain": 1.0, "temp": 1.0}, 0.9)
    r = est.estimate({"lr": 0.011, "gain": 99.0, "temp": 99.0})
    assert r["status"] == "EMPIRICAL_ESTIMATE"
    assert r["method"] == "LR_NEIGHBOR_MEAN"
    assert abs(r["estimate"] - 0.4) < 1e-12
    assert r["sample_count"] == 2
    assert r["ignored_dimensions_by_historical_design"] == ["gain", "temp"]


def test_recent_mean_fallback_is_descriptive_only():
    est = ConfigNeighborhoodEstimator(min_history=3, fallback_window=2)
    est.observe({"lr": 0.01}, 0.1)
    est.observe({"lr": 0.02}, 0.3)
    est.observe({"lr": 0.03}, 0.5)
    r = est.estimate({"lr": 0.90})
    assert r["method"] == "RECENT_MEAN_FALLBACK"
    assert abs(r["estimate"] - 0.4) < 1e-12
    assert r["authority"]["claims_future_information"] is False
    assert "ESTIMATOR_MUST_BE_SCORED_PROSPECTIVELY" in r["laws"]
