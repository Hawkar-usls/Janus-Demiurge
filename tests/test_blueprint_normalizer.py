from restored.blueprint_normalizer import normalize

def test_new_module_blueprint_and_code_generation_share_modern_schema_not_history_claim():
    a=normalize({"type":"NEW_MODULE_BLUEPRINT","title":"ChronoSync","blueprint":"sync clocks"},source_event_id="e1")
    b=normalize({"type":"CODE_GENERATION","title":"ChronoSync","blueprint":"sync clocks"},source_event_id="e2")
    assert a["status"]=="NORMALIZED_CANDIDATE" and b["status"]=="NORMALIZED_CANDIDATE"
    assert a["observed_type"]=="NEW_MODULE_BLUEPRINT"
    assert b["observed_type"]=="CODE_GENERATION"
    assert a["historical_translation_claim"] is False and b["historical_translation_claim"] is False
    assert a["authority"]["writes_module"] is False

def test_unknown_or_incomplete_event_holds():
    assert normalize({"type":"dream","title":"x","content":"y"})["status"]=="HOLD"
    assert normalize({"type":"NEW_MODULE_BLUEPRINT","title":"x"})["status"]=="HOLD"
