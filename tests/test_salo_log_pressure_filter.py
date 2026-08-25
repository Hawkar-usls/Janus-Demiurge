from restored.salo_log_pressure_filter import SaloLogPressureFilter


def test_repeat_pressure_is_suppressed_for_display_not_evidence():
    salo=SaloLogPressureFilter(repeat_window_s=5.0)
    a=salo.observe("ERROR","HRAIN timeout",now=10.0)
    b=salo.observe("ERROR","HRAIN   timeout",now=11.0)
    c=salo.observe("ERROR","HRAIN timeout",now=12.0)
    assert a["decision"]=="EMIT"
    assert b["decision"]=="DISPLAY_SUPPRESS_REPEAT"
    assert c["decision"]=="DISPLAY_SUPPRESS_REPEAT"
    assert c["total_count_for_signature"]==3
    assert c["repeat_count_since_last_emit"]==2
    assert c["evidence_preserved"] is True
    assert c["authority"]["deletes_log_evidence"] is False


def test_window_expiry_emits_repeat_summary_and_severity_stays_distinct():
    salo=SaloLogPressureFilter(repeat_window_s=5.0)
    salo.observe("WARNING","same text",now=0.0)
    salo.observe("WARNING","same text",now=1.0)
    error=salo.observe("ERROR","same text",now=2.0)
    later=salo.observe("WARNING","same text",now=6.0)
    assert error["decision"]=="EMIT"
    assert error["signature_sha256"] != later["signature_sha256"]
    assert later["decision"]=="EMIT_WITH_REPEAT_SUMMARY"
    assert later["repeat_count_since_last_emit"]==1


def test_snapshot_is_bounded_and_deterministic_shape():
    salo=SaloLogPressureFilter(repeat_window_s=1.0,max_signatures=8)
    for i in range(20):
        salo.observe("INFO",f"m{i}",now=float(i))
    snap=salo.snapshot()
    assert len(snap["signatures"])==8
    assert len(snap["snapshot_sha256"])==64
