from __future__ import annotations
import hashlib, json, pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args):
    return subprocess.run([PYTHON, *map(str, args)], cwd=ROOT, text=True, capture_output=True)


def test_end_to_end():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        out = td / "candidates"
        r = run("tools/demiurge_rex.py", "build", "--policy", "rex/policy.json", "--spec", "rex/specs/rex_heartbeat.json", "--out-root", out)
        assert r.returncode == 0, r.stderr
        cdir = out / "rex_heartbeat"
        r = run("tools/demiurge_rex.py", "audit", "--candidate-dir", cdir)
        assert r.returncode == 0, r.stderr
        source_sha = hashlib.sha256((cdir / "module.py").read_bytes()).hexdigest()
        admissions = td / "admissions"
        r = run("tools/demiurge_rex.py", "admit", "--candidate-dir", cdir, "--admissions-dir", admissions,
                "--source-sha256", source_sha, "--authority", "EXPLICIT_EXTERNAL_GATE")
        assert r.returncode == 0, r.stderr
        inp = td / "input.json"
        inp.write_text('{"tick": 1}\n', encoding="utf-8")
        r = run("tools/demiurge_rex.py", "run", "--candidate-dir", cdir, "--admissions-dir", admissions, "--input", inp)
        assert r.returncode == 0, r.stderr
        result = json.loads(r.stdout)
        assert result["status"] == "ALIVE"
        assert result["authority_delta"] == 0


def test_rex_cannot_self_authorize():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        out = td / "candidates"
        assert run("tools/demiurge_rex.py", "build", "--spec", "rex/specs/rex_heartbeat.json", "--out-root", out).returncode == 0
        cdir = out / "rex_heartbeat"
        assert run("tools/demiurge_rex.py", "audit", "--candidate-dir", cdir).returncode == 0
        source_sha = hashlib.sha256((cdir / "module.py").read_bytes()).hexdigest()
        r = run("tools/demiurge_rex.py", "admit", "--candidate-dir", cdir, "--admissions-dir", td / "admissions",
                "--source-sha256", source_sha, "--authority", "REX")
        assert r.returncode != 0
        assert "cannot self-authorize" in (r.stderr + r.stdout)


def test_auditor_rejects_import_and_open():
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        cdir = td / "bad"
        cdir.mkdir()
        source = "import os\nasync def run(context):\n    return open('/tmp/x','w')\n"
        (cdir / "module.py").write_text(source, encoding="utf-8")
        (cdir / "candidate.json").write_text(json.dumps({"module_id":"bad","source_sha256":hashlib.sha256(source.encode()).hexdigest()}), encoding="utf-8")
        r = run("tools/demiurge_rex.py", "audit", "--candidate-dir", cdir)
        assert r.returncode != 0
        receipt = json.loads((cdir / "audit.json").read_text())
        assert receipt["status"] == "FAIL"
