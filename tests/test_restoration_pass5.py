import json
from restored.dream_bus_router import route_file
from restored.mnemosyne_sensor import scan, compare
from restored.failure_ledger import append, verify

def test_dream_bus_non_destructive(tmp_path):
    src=tmp_path/"dreams.json"; dst=tmp_path/"routed.json"
    events=[{"type":"dream","x":1},{"type":"NEW_MODULE_BLUEPRINT","x":2},{"type":"weird","x":3}]
    src.write_text(json.dumps(events),encoding="utf-8")
    before=src.read_bytes()
    r=route_file(src,dst)
    assert src.read_bytes()==before
    assert r["lane_counts"]=={"MEMORY":1,"BLUEPRINT":1,"EXPERIENCE":0,"QUARANTINE":1}

def test_mnemosyne_deterministic_and_diff(tmp_path):
    (tmp_path/"a.py").write_text("x=1\n")
    a=scan(tmp_path); b=scan(tmp_path)
    assert a["manifest_sha256"]==b["manifest_sha256"]
    (tmp_path/"a.py").write_text("x=2\n"); (tmp_path/"b.json").write_text("{}")
    c=scan(tmp_path); d=compare(a,c)
    assert d["changed"]==["a.py"] and d["added"]==["b.json"]

def test_failure_ledger_hash_chain_and_dedupe(tmp_path):
    p=tmp_path/"failures.jsonl"
    a=append(p,kind="IMPORT_FAIL",subject_sha256="a"*64,status="QUARANTINE",detail={"why":"NameError"})
    b=append(p,kind="IMPORT_FAIL",subject_sha256="a"*64,status="QUARANTINE",detail={"why":"NameError"})
    c=append(p,kind="TEST_FAIL",subject_sha256="b"*64,status="PRESERVE",detail={})
    assert a["appended"] is True and b["appended"] is False and c["appended"] is True
    assert verify(p)["valid"] is True and verify(p)["records"]==2

def test_static_integration_planner():
    from restored.module_integration_planner import plan
    m=[{"id":"memory","dependencies":[]},{"id":"rex","dependencies":["auditor","memory"]},{"id":"auditor","dependencies":[]}]
    r=plan(m)
    assert r["status"]=="PLAN_ONLY"
    assert r["order"].index("auditor") < r["order"].index("rex")
    cyc=plan([{"id":"a","dependencies":["b"]},{"id":"b","dependencies":["a"]}])
    assert cyc["status"]=="HOLD"

def test_module_auditor_catches_historical_failure_class():
    from restored.module_auditor import audit_source
    good="async def run(core):\n    return None\n"
    bad="python\nasync def run(core):\n    return None\n"
    assert audit_source(good)["status"]=="PASS_STATIC"
    r=audit_source(bad)
    assert r["status"]=="REJECT"
    assert any(x["kind"]=="BARE_LANGUAGE_MARKER" for x in r["findings"])
