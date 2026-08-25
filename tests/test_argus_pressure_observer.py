from restored.argus_pressure_observer import parse_loadavg, parse_meminfo, observe_from_text

LOAD="0.25 0.50 0.75 1/100 123\n"
MEM="MemTotal:       1000000 kB\nMemAvailable:    750000 kB\nMemFree:         700000 kB\n"


def test_argus_parses_nominal_resource_snapshot_without_actuation():
    assert parse_loadavg(LOAD)["load_1m"]==0.25
    mem=parse_meminfo(MEM)
    assert mem["mem_used_kib"]==250000
    assert mem["mem_percent"]==25.0
    r=observe_from_text(LOAD,MEM,cpu_warn=2.0,mem_warn=90.0)
    assert r["pressure"]["state"]=="NOMINAL"
    assert r["authority"]["adjusts_entropy"] is False
    assert r["authority"]["runs_gc"] is False


def test_argus_reports_cpu_and_memory_pressure_but_does_not_react():
    high_load="5.5 4.0 3.0 2/100 1\n"
    low_mem="MemTotal: 1000 kB\nMemAvailable: 50 kB\n"
    r=observe_from_text(high_load,low_mem,cpu_warn=2.0,mem_warn=90.0)
    assert r["pressure"]["state"]=="PRESSURE"
    assert set(r["pressure"]["findings"])=={"CPU_LOAD_HIGH","MEMORY_PRESSURE_HIGH"}
    assert r["authority"]["kills_services"] is False
    assert len(r["observation_sha256"])==64
