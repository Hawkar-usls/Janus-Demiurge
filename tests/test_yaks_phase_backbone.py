from restored.yaks_phase_backbone import PHASES, phase_policy, transition

def test_all_historical_phases_are_policy_only():
    assert PHASES==("SURVIVAL","STABILITY","MEANING","CREATION","HIBERNATE")
    for phase in PHASES:
        p=phase_policy(phase)
        assert p["status"]=="POLICY_ONLY"
        assert p["authority"]["starts_services"] is False
        assert p["authority"]["stops_services"] is False
        assert p["authority"]["changes_prism_facet"] is False

def test_transition_is_receipt_not_actuation():
    r=transition("STABILITY","SURVIVAL",reason="resource pressure",evidence_sha256="a"*64)
    assert r["status"]=="TRANSITION_PROPOSAL"
    assert r["policy"]["prefer"]==["navigator"]
    assert r["authority"]["applies_transition"] is False
    assert len(r["transition_sha256"])==64
    assert transition("STABILITY","UNKNOWN")["status"]=="HOLD"
