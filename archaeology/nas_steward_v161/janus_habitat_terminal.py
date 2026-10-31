#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

VERSION = "1.6.2-STABLE-RELEASE-LAUNCHER"
LAUNCHER_MAGIC = "JANUS_CODE_STEWARD_LAUNCHER_V1"
COMPONENT = "terminal"
ROOT = Path(os.environ.get("JANUS_ROOT", "/janus")).resolve()
POLL_SECONDS = max(2, min(300, int(os.environ.get("JANUS_LAUNCHER_POLL_SECONDS", "5"))))
HEALTH_SECONDS = max(10, min(3600, int(os.environ.get("JANUS_LAUNCHER_HEALTH_SECONDS", "30"))))
RESTART_BACKOFF = max(1, min(300, int(os.environ.get("JANUS_LAUNCHER_RESTART_BACKOFF", "3"))))
STOP_TIMEOUT = max(2, min(120, int(os.environ.get("JANUS_LAUNCHER_STOP_TIMEOUT", "15"))))

ACTIVATIONS = ROOT / "steward" / "activations"
RELEASES = ROOT / "releases"
HEALTH = Path(os.environ.get("JANUS_LAUNCHER_HEALTH_ROOT", str(ROOT / "steward" / "health"))).resolve()

class LauncherError(RuntimeError): pass

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value: Any) -> str: return hashlib.sha256(canonical_bytes(value)).hexdigest()
def sha256_bytes(data: bytes) -> str: return hashlib.sha256(data).hexdigest()

def verify_hash(value: dict[str, Any], key: str) -> bool:
    claimed=value.get(key)
    if not isinstance(claimed,str) or len(claimed)!=64: return False
    u=dict(value); u.pop(key,None)
    return digest(u)==claimed

def read_json(p: Path) -> dict[str, Any]:
    v=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(v,dict): raise LauncherError(f"OBJECT_REQUIRED:{p}")
    return v

def create_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    try:
        with path.open("xb") as h:
            h.write(data); h.flush(); os.fsync(h.fileno())
    except FileExistsError:
        if path.read_bytes()!=data: raise LauncherError(f"CREATE_ONLY_COLLISION:{path}")

def latest_activation() -> dict[str, Any]:
    rows=[]
    for p in sorted(ACTIVATIONS.glob("*.json")):
        try:
            v=read_json(p)
            if v.get("schema")=="janus.code_steward.activation.v1" and verify_hash(v,"activation_receipt_sha256"):
                rows.append(v)
        except Exception: pass
    if not rows: raise LauncherError("NO_VALID_ACTIVATION")
    return sorted(rows,key=lambda x:int(x.get("sequence",0)))[-1]

def resolve_payload(release_id: str) -> tuple[Path,dict[str,Any]]:
    mp=RELEASES/release_id/"manifest.json"
    m=read_json(mp)
    if m.get("schema")!="janus.code_steward.release_manifest.v1" or not verify_hash(m,"manifest_receipt_sha256"):
        raise LauncherError("MANIFEST_INVALID")
    comp=(m.get("components") or {}).get(COMPONENT) or {}
    rel=str(comp.get("path", COMPONENT+".py"))
    if rel not in {"gate.py","terminal.py"}: raise LauncherError("PAYLOAD_PATH_INVALID")
    p=(RELEASES/release_id/rel).resolve()
    if RELEASES not in p.parents: raise LauncherError("PAYLOAD_ESCAPES_RELEASE_ROOT")
    data=p.read_bytes()
    if sha256_bytes(data)!=comp.get("sha256"): raise LauncherError("PAYLOAD_SHA_MISMATCH")
    if LAUNCHER_MAGIC.encode() in data: raise LauncherError("RECURSIVE_LAUNCHER_PAYLOAD_FORBIDDEN")
    return p,m

def health_record(release_id: str, child_alive: bool, startup_ok: bool, exit_count: int, started_mono: float | None) -> dict[str,Any]:
    v={"schema":"janus.code_steward.launcher_health.v1","release_id":release_id,"component":COMPONENT,
       "child_alive":bool(child_alive),"startup_ok":bool(startup_ok),"exit_count":int(exit_count),
       "uptime_seconds":max(0.0,time.monotonic()-started_mono) if started_mono is not None else 0.0,
       "observed_unix_ns":time.time_ns(),"launcher_version":VERSION,"delete":False,"move":False,"rename":False}
    v["health_receipt_sha256"]=digest(v); return v

def write_health(v: dict[str,Any]) -> None:
    rid=str(v["release_id"]); folder=HEALTH/rid/COMPONENT
    create_json(folder/f"{v['observed_unix_ns']}-{os.getpid()}-{v['health_receipt_sha256']}.json",v)

def child_env(release_id: str, payload: Path, manifest: dict[str,Any]) -> dict[str,str]:
    env=dict(os.environ)
    env["JANUS_ACTIVE_RELEASE_ID"]=release_id
    env["JANUS_ACTIVE_RELEASE_MANIFEST_SHA256"]=str(manifest["manifest_receipt_sha256"])
    env["JANUS_LAUNCHER_PARENT"]="1"
    env["PYTHONDONTWRITEBYTECODE"]="1"
    if COMPONENT=="terminal":
        env["JANUS_TERMINAL_SELF_REL"]=payload.relative_to(ROOT).as_posix()
    return env

def stop_child(child: subprocess.Popen[Any] | None) -> None:
    if child is None or child.poll() is not None: return
    child.terminate()
    deadline=time.monotonic()+STOP_TIMEOUT
    while time.monotonic()<deadline and child.poll() is None: time.sleep(0.2)
    if child.poll() is None:
        child.kill(); child.wait(timeout=5)

def self_test() -> dict[str,Any]:
    v={"schema":"janus.code_steward.activation.v1","sequence":1,"target_release":"000001","previous_release":None,
       "reason":"TEST","created_unix_ns":1,"delete":False,"move":False,"rename":False,"activation_is_append_only":True}
    v["activation_receipt_sha256"]=digest(v)
    return {"status":"PASS","version":VERSION,"component":COMPONENT,"activation_hash":verify_hash(v,"activation_receipt_sha256"),
            "launcher_magic":LAUNCHER_MAGIC,"no_file_delete_move_rename":True}

def main() -> int:
    if "--self-test" in sys.argv:
        print(json.dumps(self_test(),sort_keys=True)); return 0
    child=None; active=None; started=None; exit_count=0; startup_ok=False; last_health=0.0
    print(json.dumps({"event":"JANUS_RELEASE_LAUNCHER_STARTED","component":COMPONENT,"version":VERSION,"root":str(ROOT)},sort_keys=True),flush=True)
    try:
        while True:
            try:
                act=latest_activation(); target=str(act["target_release"])
                payload,manifest=resolve_payload(target)
                changed=(target!=active)
                if changed:
                    stop_child(child); child=None; active=target; started=None; startup_ok=False; exit_count=0
                    print(json.dumps({"event":"JANUS_RELEASE_SWITCH","component":COMPONENT,"target_release":target,
                                      "reason":act.get("reason"),"payload":str(payload)},sort_keys=True),flush=True)
                if child is None or child.poll() is not None:
                    if child is not None and child.poll() is not None:
                        exit_count+=1
                        write_health(health_record(active,False,startup_ok,exit_count,started))
                        time.sleep(RESTART_BACKOFF)
                    child=subprocess.Popen([sys.executable,"-u",str(payload)],env=child_env(active,payload,manifest))
                    started=time.monotonic(); startup_ok=True
                    print(json.dumps({"event":"JANUS_RELEASE_CHILD_STARTED","component":COMPONENT,"release_id":active,
                                      "pid":child.pid,"sha256":manifest["components"][COMPONENT]["sha256"]},sort_keys=True),flush=True)
                now=time.monotonic()
                if now-last_health>=HEALTH_SECONDS:
                    write_health(health_record(active,child.poll() is None,startup_ok,exit_count,started)); last_health=now
            except Exception as exc:
                print(json.dumps({"event":"JANUS_RELEASE_LAUNCHER_HOLD","component":COMPONENT,"error":f"{type(exc).__name__}:{exc}",
                                  "current_child_preserved":child is not None and child.poll() is None},sort_keys=True),flush=True)
            time.sleep(POLL_SECONDS)
    finally:
        stop_child(child)

if __name__=="__main__": raise SystemExit(main())
