import json
from restored.dream_bus_router import route_file
from restored.mnemosyne_sensor import scan, compare, classify_stability
from restored.failure_ledger import append, verify

def test_dream_bus_non_destructive(tmp_path):
    src=tmp_path/"dreams.json"; dst=tmp_path/"routed.json"
    events=[{"type":"dream","x":1},{"type":"NEW_MODULE_BLUEPRINT","x":2},{"type":"weird","x":3}]
    src.write_text(json.dumps(events),encoding="utf-8")
    before=src.read_bytes()
    r=route_file(src,dst)
    assert src.read_bytes()==before
    assert r["lane_counts"]=={"MEMORY":1,"BLUEPRINT":1,"EXPERIENCE":0,"QUARANTINE":1}

def test_mnemosyne_deterministic_diff_and_safe_hot_start(tmp_path):
    (tmp_path/"a.py").write_text("x=1\n")
    a=scan(tmp_path); b=scan(tmp_path)
    assert a["manifest_sha256"]==b["manifest_sha256"]
    stable=classify_stability(a,b)
    assert stable["hot_start_hint"] is True
    assert stable["authority"]["skip_security_checks"] is False
    assert stable["authority"]["skip_integrity_checks"] is False
    (tmp_path/"a.py").write_text("x=2\n"); (tmp_path/"b.json").write_text("{}")
    c=scan(tmp_path); d=compare(a,c); drift=classify_stability(a,c)
    assert d["changed"]==["a.py"] and d["added"]==["b.json"]
    assert drift["dirty"]==["a.py"] and drift["new"]==["b.json"]
    assert drift["hot_start_hint"] is False

def test_failure_ledger_hash_chain_and_dedupe(tmp_path):
    p=tmp_path/"failures.jsonl"
    a=append(p,kind="IMPORT_FAIL",subject_sha256="a"*64,status="QUARANTINE",detail={"why":"NameError"})
    b=append(p,kind="IMPORT_FAIL",subject_sha256="a"*64,status="QUARANTINE",detail={"why":"NameError"})
    c=append(p,kind="TEST_FAIL",subject_sha256="b"*64,status="PRESERVE",detail={})
    assert a["appended"] is True and b["appended"] is False and c["appended"] is True
    assert verify(p)["valid"] is True and verify(p)["records"]==2

def test_static_integration_planner_is_hash_bound_and_fail_closed():
    from restored.module_integration_planner import plan
    m=[{"id":"memory","dependencies":[],"source_sha256":"a"*64},
       {"id":"rex","dependencies":["auditor","memory"],"source_sha256":"b"*64},
       {"id":"auditor","dependencies":[],"source_sha256":"c"*64}]
    r=plan(m); r2=plan(list(reversed(m)))
    assert r["status"]=="PLAN_ONLY" and r["plan_sha256"]==r2["plan_sha256"]
    assert r["order"].index("auditor") < r["order"].index("rex")
    assert r["authority"]["executes_code"] is False
    cyc=plan([{"id":"a","dependencies":["b"]},{"id":"b","dependencies":["a"]}])
    assert cyc["status"]=="HOLD" and "CYCLE -> HOLD" in cyc["law"]

def test_module_auditor_catches_historical_and_destructive_classes():
    from restored.module_auditor import audit_source
    good="async def run(core):\n    return None\n"
    bare="python\nasync def run(core):\n    return None\n"
    destructive="import shutil\nasync def run(core):\n    shutil.rmtree('x')\n"
    interactive="async def run(core):\n    input('x')\n"
    assert audit_source(good)["status"]=="PASS_STATIC"
    r=audit_source(bare)
    assert r["status"]=="REJECT" and any(x["kind"]=="BARE_LANGUAGE_MARKER" for x in r["findings"])
    r=audit_source(destructive)
    assert r["status"]=="REJECT" and any(x.get("name")=="shutil.rmtree" for x in r["findings"])
    r=audit_source(interactive)
    assert r["status"]=="REJECT" and any(x.get("name")=="input" for x in r["findings"])
