from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
PYTHON=sys.executable


def run(*args):
    return subprocess.run([PYTHON,*map(str,args)],cwd=ROOT,text=True,capture_output=True)


def test_director_generates_bounded_spec():
    with tempfile.TemporaryDirectory() as td:
        out=pathlib.Path(td)/"specs"
        r=run("tools/demiurge_rex_director.py","--desires","rex/JANUS_REX_DESIRES.json","--policy","rex/policy.json","--nexus-policy","rex/nexus_policy.json","--out-dir",out)
        assert r.returncode==0,r.stderr
        spec=json.loads((out/"rex_birth_notice.json").read_text())
        assert spec["schema"]=="janus.rex.module_spec.v1"
        assert spec["template"]=="echo"
        assert spec["nexus"]["request_autorun"] is True
        assert spec["provenance"]["desire_grants_admission"] is False
        assert spec["provenance"]["desire_grants_lifecycle"] is False
        assert spec["provenance"]["authority_delta"]==0
        living=json.loads((out/"rex_lifecycle_heartbeat.json").read_text())
        assert living["lifecycle"]["enabled"] is True
        assert living["lifecycle"]["mode"]=="SCHEDULED"
        assert living["lifecycle"]["interval_minutes"]==60
        assert living["provenance"]["desire_grants_lifecycle"] is False


def test_director_refuses_autorun_for_non_allowed_template():
    with tempfile.TemporaryDirectory() as td:
        td=pathlib.Path(td)
        desires=json.loads((ROOT/"rex/JANUS_REX_DESIRES.json").read_text())
        desires["requests"][0]["template"]="not_allowed"
        p=td/"desires.json"; p.write_text(json.dumps(desires))
        r=run("tools/demiurge_rex_director.py","--desires",p,"--policy","rex/policy.json","--nexus-policy","rex/nexus_policy.json","--out-dir",td/"out")
        assert r.returncode!=0


def test_director_refuses_unapproved_lifecycle_interval():
    with tempfile.TemporaryDirectory() as td:
        td=pathlib.Path(td)
        desires=json.loads((ROOT/"rex/JANUS_REX_DESIRES.json").read_text())
        desires["requests"][1]["lifecycle"]["interval_minutes"]=17
        p=td/"desires.json"; p.write_text(json.dumps(desires))
        r=run("tools/demiurge_rex_director.py","--desires",p,"--policy","rex/policy.json","--nexus-policy","rex/nexus_policy.json","--out-dir",td/"out")
        assert r.returncode!=0
        assert "interval" in (r.stdout+r.stderr).lower()
