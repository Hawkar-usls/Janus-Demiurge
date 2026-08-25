from restored.hrain_event_outbox import append, verify, active_window, transport_batch

def test_outbox_is_append_only_deduplicated_and_offline(tmp_path):
    p=tmp_path/"hrain.jsonl"
    a=append(p,{"type":"cycle","cycle":1,"score":0.1})
    b=append(p,{"type":"cycle","cycle":1,"score":0.1})
    append(p,{"type":"record","cycle":1,"score":0.1})
    append(p,{"type":"collapse","cycle":2,"config":{"lr":0.1}})
    assert a["appended"] is True and b["appended"] is False
    assert verify(p)["valid"] is True and verify(p)["records"]==3
    batch=transport_batch(p)
    assert batch["authority"]["network_io"] is False
    assert batch["authority"]["deletes_ledger"] is False

def test_critical_history_survives_bounded_cycle_view(tmp_path):
    p=tmp_path/"hrain.jsonl"
    append(p,{"type":"record","cycle":0,"score":9})
    for i in range(10): append(p,{"type":"cycle","cycle":i,"score":i})
    append(p,{"type":"collapse","cycle":11})
    view=active_window(p,max_cycle_events=2)
    types=[r["event_type"] for r in view]
    cycles=[r["payload"].get("cycle") for r in view]
    assert types.count("record")==1 and types.count("collapse")==1
    assert 8 in cycles and 9 in cycles
