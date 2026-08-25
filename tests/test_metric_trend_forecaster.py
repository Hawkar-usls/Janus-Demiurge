from restored.metric_trend_forecaster import MetricTrendForecaster


def test_warmup_and_source_faithful_velocity_acceleration_forecast():
    f=MetricTrendForecaster(lead_factor=1.8)
    a=f.step(1.0,0.10)
    b=f.step(2.0,0.20)
    c=f.step(4.0,0.50)
    assert a["phase"]=="WARMUP" and a["predicted_score"]==1.0
    assert b["velocity"]==1.0 and b["acceleration"]==1.0
    assert b["predicted_score"]==4.3
    assert c["velocity"]==2.0 and c["acceleration"]==1.0
    assert c["predicted_score"]==8.1
    assert c["predicted_aux_metric"]==1.04


def test_forecast_has_no_future_information_or_action_authority():
    r=MetricTrendForecaster().step(1.0,0.0)
    assert r["authority"]["claims_future_information"] is False
    assert r["authority"]["chooses_action"] is False
    assert "TREND_EXTRAPOLATION_NE_PRECOGNITION" in r["laws"]
