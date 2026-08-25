import json
import pytest
from restored.homeostasis_guard import evaluate_metrics, build_state, verify_state, write_state_atomic, load_state


def test_healthy_metrics_are_continue_eligible_without_actuation():
    r=evaluate_metrics(score=1.0,val_loss=0.5,diversity=0.7,mutual_information=0.02,grad_norm_mean=1.5,train_loss=0.4,grad_norm_max=3.0)
    assert r["status"]=="HEALTHY"
    assert r["recommendation"]=="CONTINUE_ELIGIBLE"
    assert r["authority"]["rolls_back_model"] is False


def test_nonfinite_or_exploding_metrics_hold():
    r=evaluate_metrics(score=1.0,val_loss=float("nan"),diversity=0.7,mutual_information=0.02,grad_norm_mean=1.5,grad_norm_max=101.0)
    kinds=[x["kind"] for x in r["findings"]]
    assert r["status"]=="HOLD"
    assert "NONFINITE_OR_MISSING_METRIC" in kinds
    assert "GRADIENT_EXPLOSION_RISK" in kinds
    assert r["recommendation"]=="ROLLBACK_OR_DIAGNOSE_PROPOSAL"


def test_state_is_hash_bound_atomic_and_tamper_detected(tmp_path):
    state=build_state(cycle=7,last_score=1.0,last_mi=0.1,best_score=1.2,failed_config_hashes=["a"*64],predicted_score=1.1,velocity=0.1,acceleration=0.0,purity_score=0.9)
    assert verify_state(state) is True
    p=tmp_path/"homeostasis.json"
    write_state_atomic(p,state)
    assert load_state(p)==state
    broken=json.loads(p.read_text())
    broken["cycle"]=8
    p.write_text(json.dumps(broken),encoding="utf-8")
    with pytest.raises(ValueError): load_state(p)
