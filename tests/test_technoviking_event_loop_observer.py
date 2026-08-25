from restored.technoviking_event_loop_observer import observe_lag


def test_normal_warn_severe_classification():
    normal = observe_lag([5, 10, 15, 20])
    assert normal["state"] == "NORMAL"
    assert normal["suggested_backoff_ms"] == 0.0

    warn = observe_lag([10, 20, 120, 40], warn_ms=100, severe_ms=500)
    assert warn["state"] == "WARN"
    assert warn["warn_or_worse_count"] == 1
    assert warn["authority"]["changes_event_loop"] is False

    severe = observe_lag([10, 600, 20], warn_ms=100, severe_ms=500)
    assert severe["state"] == "SEVERE"
    assert severe["severe_count"] == 1


def test_no_data_and_provenance_boundary():
    r = observe_lag([])
    assert r["state"] == "NO_DATA"
    assert r["provenance"]["exact_historical_bytes_recovered"] is False
    assert r["provenance"]["relationship"] == "ROLE_BACKED_RECONSTRUCTION_NOT_BYTE_DESCENDANT"
    assert r["authority"]["calls_gc_collect"] is False
    assert r["authority"]["starts_or_stops_services"] is False


def test_invalid_thresholds_fail_closed():
    try:
        observe_lag([1], warn_ms=500, severe_ms=100)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid threshold order must fail")
