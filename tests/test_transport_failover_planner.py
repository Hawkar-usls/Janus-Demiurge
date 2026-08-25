from restored.transport_failover_planner import build_plan, classify_attempt


def test_plan_orders_active_first_and_deduplicates_without_transport_authority():
    plan = build_plan(
        "http://titan-a/",
        ["http://titan-b", "http://titan-a", "http://titan-c/"],
        "heartbeat",
        {"status": "online"},
        "blood-core",
    )
    assert plan["targets"] == ["http://titan-a", "http://titan-b", "http://titan-c"]
    assert plan["request"]["method"] == "POST"
    assert plan["authority"]["sends_network_request"] is False
    assert plan["authority"]["changes_active_target"] is False


def test_ack_classifier_repairs_historical_http_lt_500_bug():
    plan = build_plan("http://a", ["http://b"], "thought", {"x": 1}, "node")
    ok = classify_attempt(plan, "http://a", http_status=204)
    auth = classify_attempt(plan, "http://a", http_status=401)
    server = classify_attempt(plan, "http://a", http_status=503)
    net = classify_attempt(plan, "http://a", network_error="timeout")

    assert ok["outcome"] == "ACK" and ok["next_target"] is None
    assert auth["outcome"] == "TERMINAL_REJECT" and auth["next_target"] is None
    assert server["outcome"] == "RETRY_OR_FAILOVER" and server["next_target"] == "http://b"
    assert net["outcome"] == "RETRY_OR_FAILOVER" and net["next_target"] == "http://b"
