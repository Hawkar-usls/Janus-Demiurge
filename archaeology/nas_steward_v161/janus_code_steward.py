#!/usr/bin/env python3
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

VERSION = "1.6.1-AUTONOMOUS-CODE-STEWARD-BKG"
ROOT = Path(os.environ.get("JANUS_ROOT", "/janus")).resolve()
POLL_SECONDS = max(5, min(3600, int(os.environ.get("JANUS_STEWARD_POLL_SECONDS", "15"))))
COMPATIBILITY_EPOCH = os.environ.get("JANUS_STEWARD_COMPATIBILITY_EPOCH", "HABITAT-1").strip() or "HABITAT-1"
MIN_PROMOTION_SAMPLES_PER_COMPONENT = max(2, int(os.environ.get("JANUS_STEWARD_PROMOTION_SAMPLES", "5")))
MIN_ROLLBACK_SAMPLES_PER_COMPONENT = max(2, int(os.environ.get("JANUS_STEWARD_ROLLBACK_SAMPLES", "3")))
PROMOTION_SCORE = float(os.environ.get("JANUS_STEWARD_PROMOTION_SCORE", "0.90"))
ROLLBACK_HARD_FLOOR = float(os.environ.get("JANUS_STEWARD_ROLLBACK_HARD_FLOOR", "0.65"))
ROLLBACK_REGRESSION_MARGIN = float(os.environ.get("JANUS_STEWARD_ROLLBACK_MARGIN", "0.08"))
MAX_HEALTH_RECORDS_PER_COMPONENT = max(5, int(os.environ.get("JANUS_STEWARD_HEALTH_WINDOW", "20")))

SAFE_RELEASE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SAFE_HEX = re.compile(r"^[0-9a-f]{64}$")
LAUNCHER_MAGIC = "JANUS_CODE_STEWARD_LAUNCHER_V1"

SERVICES = ROOT / "services"
RELEASES = ROOT / "releases"
STEWARD = ROOT / "steward"
ACTIVATIONS = STEWARD / "activations"
PROMOTIONS = STEWARD / "promotions"
QUARANTINE = STEWARD / "quarantine"
HEALTH = STEWARD / "health"
INBOX = STEWARD / "inbox"
PROCESSED = STEWARD / "processed"

GATE_SOURCE = SERVICES / "janus_habitat_gate.py"
TERMINAL_SOURCE = SERVICES / "janus_habitat_terminal.py"

class StewardError(RuntimeError):
    pass

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def verify_self_hash(value: dict[str, Any], key: str) -> bool:
    claimed = value.get(key)
    if not isinstance(claimed, str) or SAFE_HEX.fullmatch(claimed) is None:
        return False
    unsigned = dict(value)
    unsigned.pop(key, None)
    return digest(unsigned) == claimed

def create_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        if path.read_bytes() != data:
            raise StewardError(f"CREATE_ONLY_COLLISION:{path}")

def create_json(path: Path, value: dict[str, Any]) -> None:
    create_bytes(path, (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))

def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StewardError(f"TOP_LEVEL_OBJECT_REQUIRED:{path}")
    return value

def ensure_dirs() -> None:
    for p in (RELEASES, ACTIVATIONS, PROMOTIONS, QUARANTINE, HEALTH, INBOX, PROCESSED):
        p.mkdir(parents=True, exist_ok=True)

def destructive_surface_findings(source: bytes) -> list[str]:
    try:
        tree = ast.parse(source.decode("utf-8"))
    except Exception as exc:
        raise StewardError(f"PYTHON_AST_INVALID:{type(exc).__name__}:{exc}") from exc
    bad = []
    os_bad = {"remove", "unlink", "rmdir", "rename", "replace", "removedirs"}
    shutil_bad = {"move", "rmtree"}
    path_bad = {"unlink", "rmdir", "rename", "replace"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute):
            if isinstance(f.value, ast.Name) and f.value.id == "os" and f.attr in os_bad:
                bad.append(f"os.{f.attr}@{getattr(node, 'lineno', '?')}")
            elif isinstance(f.value, ast.Name) and f.value.id == "shutil" and f.attr in shutil_bad:
                bad.append(f"shutil.{f.attr}@{getattr(node, 'lineno', '?')}")
            elif f.attr in path_bad:
                bad.append(f"*.{f.attr}@{getattr(node, 'lineno', '?')}")
    return sorted(set(bad))

def validate_python_payload(data: bytes, component: str) -> str:
    compile(data, f"<{component}>", "exec")
    findings = destructive_surface_findings(data)
    if findings:
        raise StewardError(f"NOHAND_DESTRUCTIVE_SURFACE:{component}:{','.join(findings)}")
    return sha256_bytes(data)

def manifest_for(release_id: str, gate: bytes, terminal: bytes, *, parent_release: str | None,
                 compatibility_epoch: str, source: str, gates: dict[str, bool]) -> dict[str, Any]:
    gate_sha = validate_python_payload(gate, "gate")
    terminal_sha = validate_python_payload(terminal, "terminal")
    value = {
        "schema": "janus.code_steward.release_manifest.v1",
        "release_id": release_id,
        "compatibility_epoch": compatibility_epoch,
        "parent_release": parent_release,
        "source": source,
        "components": {
            "gate": {"path": "gate.py", "sha256": gate_sha, "bytes": len(gate)},
            "terminal": {"path": "terminal.py", "sha256": terminal_sha, "bytes": len(terminal)},
        },
        "gates": gates,
        "laws": {"delete": False, "move": False, "rename": False},
        "activation_is_append_only": True,
        "rollback_policy": "BEST_KNOWN_GOOD_SAME_COMPATIBILITY_EPOCH",
    }
    value["manifest_receipt_sha256"] = digest(value)
    return value

def validate_manifest(value: dict[str, Any]) -> None:
    if value.get("schema") != "janus.code_steward.release_manifest.v1" or not verify_self_hash(value, "manifest_receipt_sha256"):
        raise StewardError("MANIFEST_SCHEMA_OR_HASH_INVALID")
    if SAFE_RELEASE.fullmatch(str(value.get("release_id", ""))) is None:
        raise StewardError("RELEASE_ID_INVALID")
    laws = value.get("laws") or {}
    if laws.get("delete") is not False or laws.get("move") is not False or laws.get("rename") is not False:
        raise StewardError("NOHAND_LAWS_REQUIRED")

def install_release(manifest: dict[str, Any], gate: bytes, terminal: bytes) -> None:
    validate_manifest(manifest)
    rid = str(manifest["release_id"])
    if sha256_bytes(gate) != manifest["components"]["gate"]["sha256"]:
        raise StewardError("GATE_SHA_MISMATCH")
    if sha256_bytes(terminal) != manifest["components"]["terminal"]["sha256"]:
        raise StewardError("TERMINAL_SHA_MISMATCH")
    validate_python_payload(gate, "gate")
    validate_python_payload(terminal, "terminal")
    target = RELEASES / rid
    create_bytes(target / "gate.py", gate)
    create_bytes(target / "terminal.py", terminal)
    create_json(target / "manifest.json", manifest)

def release_manifests() -> list[dict[str, Any]]:
    rows = []
    if not RELEASES.exists():
        return rows
    for p in sorted(RELEASES.glob("*/manifest.json")):
        try:
            v = read_json(p); validate_manifest(v); rows.append(v)
        except Exception:
            continue
    return rows

def activation_record(sequence: int, target_release: str, previous_release: str | None, reason: str) -> dict[str, Any]:
    v = {
        "schema": "janus.code_steward.activation.v1",
        "sequence": sequence,
        "target_release": target_release,
        "previous_release": previous_release,
        "reason": reason,
        "created_unix_ns": time.time_ns(),
        "delete": False,
        "move": False,
        "rename": False,
        "activation_is_append_only": True,
    }
    v["activation_receipt_sha256"] = digest(v)
    return v

def valid_activations() -> list[dict[str, Any]]:
    rows = []
    for p in sorted(ACTIVATIONS.glob("*.json")):
        try:
            v = read_json(p)
            if v.get("schema") == "janus.code_steward.activation.v1" and verify_self_hash(v, "activation_receipt_sha256"):
                rows.append(v)
        except Exception:
            pass
    return sorted(rows, key=lambda x: int(x.get("sequence", 0)))

def latest_activation() -> dict[str, Any] | None:
    rows = valid_activations()
    return rows[-1] if rows else None

def append_activation(target: str, reason: str) -> dict[str, Any]:
    prev = latest_activation()
    seq = int(prev["sequence"]) + 1 if prev else 1
    v = activation_record(seq, target, prev.get("target_release") if prev else None, reason)
    name = f"{seq:020d}-{v['activation_receipt_sha256']}.json"
    create_json(ACTIVATIONS / name, v)
    return v

def bootstrap_if_needed() -> dict[str, Any]:
    manifests = release_manifests()
    if manifests:
        if latest_activation() is None:
            rid = sorted(str(x["release_id"]) for x in manifests)[0]
            append_activation(rid, "RECOVER_MISSING_ACTIVATION")
        return {"status": "ALREADY_BOOTSTRAPPED", "release_id": latest_activation()["target_release"]}
    if not GATE_SOURCE.is_file() or not TERMINAL_SOURCE.is_file():
        raise StewardError("BOOTSTRAP_SOURCE_MISSING")
    gate = GATE_SOURCE.read_bytes(); terminal = TERMINAL_SOURCE.read_bytes()
    if LAUNCHER_MAGIC.encode() in gate or LAUNCHER_MAGIC.encode() in terminal:
        raise StewardError("BOOTSTRAP_REFUSES_TO_SNAPSHOT_LAUNCHER_RUN_STEWARD_BEFORE_REPLACING_GATE_TERMINAL")
    rid = "000001"
    m = manifest_for(
        rid, gate, terminal, parent_release=None, compatibility_epoch=COMPATIBILITY_EPOCH,
        source="LIVE_NAS_BOOTSTRAP_SNAPSHOT",
        gates={"bootstrap_live_observed": True, "ci": False, "demihead": False, "guardian": True},
    )
    install_release(m, gate, terminal)
    act = append_activation(rid, "BOOTSTRAP_CURRENT_LIVE_PAIR")
    return {"status": "BOOTSTRAP_READY", "release_id": rid, "manifest_sha256": m["manifest_receipt_sha256"],
            "gate_sha256": m["components"]["gate"]["sha256"],
            "terminal_sha256": m["components"]["terminal"]["sha256"], "activation": act}

def candidate_files() -> list[Path]:
    return sorted(INBOX.glob("*.json"))

def processed_marker(candidate_sha: str) -> Path:
    return PROCESSED / f"{candidate_sha}.json"

def process_candidate(path: Path) -> dict[str, Any] | None:
    raw = path.read_bytes(); candidate_sha = sha256_bytes(raw)
    if processed_marker(candidate_sha).exists():
        return None
    v = json.loads(raw.decode("utf-8"))
    if not isinstance(v, dict) or v.get("schema") != "janus.code_steward.candidate_bundle.v1" or not verify_self_hash(v, "candidate_receipt_sha256"):
        raise StewardError(f"CANDIDATE_SCHEMA_OR_HASH_INVALID:{path.name}")
    rid = str(v.get("release_id", ""))
    if SAFE_RELEASE.fullmatch(rid) is None:
        raise StewardError("CANDIDATE_RELEASE_ID_INVALID")
    if (RELEASES / rid / "manifest.json").exists():
        raise StewardError("CANDIDATE_RELEASE_ID_ALREADY_EXISTS")
    gates = v.get("gates") or {}
    if not all(gates.get(k) is True for k in ("ci", "demihead", "guardian")):
        raise StewardError("CANDIDATE_APPROVAL_GATES_NOT_ALL_PASS")
    gate = base64.b64decode(v["gate_b64"], validate=True)
    terminal = base64.b64decode(v["terminal_b64"], validate=True)
    current = latest_activation()
    parent = current.get("target_release") if current else None
    epoch = str(v.get("compatibility_epoch") or COMPATIBILITY_EPOCH)
    m = manifest_for(rid, gate, terminal, parent_release=parent, compatibility_epoch=epoch,
                     source=str(v.get("source", "STEWARD_INBOX")), gates={"bootstrap_live_observed": False, "ci": True, "demihead": True, "guardian": True})
    install_release(m, gate, terminal)
    receipt = {"schema": "janus.code_steward.processed_candidate.v1", "candidate_sha256": candidate_sha,
               "release_id": rid, "manifest_sha256": m["manifest_receipt_sha256"], "installed": True,
               "auto_activate": v.get("auto_activate") is True, "created_unix_ns": time.time_ns()}
    receipt["receipt_sha256"] = digest(receipt)
    create_json(processed_marker(candidate_sha), receipt)
    if v.get("auto_activate") is True:
        append_activation(rid, "APPROVED_CANDIDATE_PROBATION")
    return receipt

def health_rows(release_id: str, component: str) -> list[dict[str, Any]]:
    folder = HEALTH / release_id / component
    rows = []
    if not folder.exists():
        return rows
    for p in sorted(folder.glob("*.json"))[-MAX_HEALTH_RECORDS_PER_COMPONENT:]:
        try:
            v = read_json(p)
            if v.get("schema") == "janus.code_steward.launcher_health.v1" and verify_self_hash(v, "health_receipt_sha256"):
                rows.append(v)
        except Exception:
            pass
    return rows

def release_health(release_id: str) -> dict[str, Any]:
    components = {}
    all_rows = []
    for c in ("gate", "terminal"):
        rows = health_rows(release_id, c)
        all_rows.extend(rows)
        if rows:
            alive = sum(1 for x in rows if x.get("child_alive") is True) / len(rows)
            startup = sum(1 for x in rows if x.get("startup_ok") is True) / len(rows)
            restart_quality = sum(max(0.0, 1.0 - min(3, int(x.get("exit_count", 0))) / 3.0) for x in rows) / len(rows)
            score = 0.55 * alive + 0.35 * startup + 0.10 * restart_quality
        else:
            alive = startup = restart_quality = score = 0.0
        components[c] = {"samples": len(rows), "availability": alive, "startup": startup,
                         "restart_quality": restart_quality, "score": score}
    if not all_rows:
        total = 0.0
    else:
        total = min(components["gate"]["score"], components["terminal"]["score"])
    return {"release_id": release_id, "score": total, "components": components,
            "samples": len(all_rows), "both_components_present": all(components[c]["samples"] > 0 for c in components)}

def promotion_records() -> list[dict[str, Any]]:
    rows = []
    for p in sorted(PROMOTIONS.glob("*.json")):
        try:
            v = read_json(p)
            if v.get("schema") == "janus.code_steward.promotion.v1" and verify_self_hash(v, "promotion_receipt_sha256"):
                rows.append(v)
        except Exception:
            pass
    return rows

def promoted_release_ids() -> set[str]:
    return {str(x["release_id"]) for x in promotion_records()}

def is_quarantined(release_id: str) -> bool:
    return any(str(x.get("release_id")) == release_id for x in quarantine_records())

def quarantine_records() -> list[dict[str, Any]]:
    rows=[]
    for p in sorted(QUARANTINE.glob("*.json")):
        try:
            v=read_json(p)
            if v.get("schema") == "janus.code_steward.quarantine.v1" and verify_self_hash(v,"quarantine_receipt_sha256"):
                rows.append(v)
        except Exception:
            pass
    return rows

def append_quarantine(release_id: str, reason: str, health: dict[str, Any]) -> dict[str, Any]:
    v={"schema":"janus.code_steward.quarantine.v1","release_id":release_id,"reason":reason,
       "health":health,"created_unix_ns":time.time_ns(),"delete":False,"move":False,"rename":False}
    v["quarantine_receipt_sha256"]=digest(v)
    create_json(QUARANTINE / f"{time.time_ns()}-{v['quarantine_receipt_sha256']}.json",v)
    return v

def manifest_by_id(release_id: str) -> dict[str, Any]:
    p=RELEASES/release_id/"manifest.json"
    v=read_json(p); validate_manifest(v); return v

def append_promotion(release_id: str, health: dict[str, Any]) -> dict[str, Any]:
    if release_id in promoted_release_ids():
        return {"status":"ALREADY_PROMOTED","release_id":release_id}
    v={"schema":"janus.code_steward.promotion.v1","release_id":release_id,"health":health,
       "created_unix_ns":time.time_ns(),"policy":"PROBATION_TO_STABLE","delete":False,"move":False,"rename":False}
    v["promotion_receipt_sha256"]=digest(v)
    create_json(PROMOTIONS / f"{time.time_ns()}-{v['promotion_receipt_sha256']}.json",v)
    return v

def bootstrap_release_for_epoch(epoch: str) -> str | None:
    rows=[]
    for m in release_manifests():
        if m.get("compatibility_epoch") == epoch and m.get("source") == "LIVE_NAS_BOOTSTRAP_SNAPSHOT":
            rows.append(str(m["release_id"]))
    return sorted(rows)[0] if rows else None

def choose_best_known_good(epoch: str, exclude: set[str] | None=None) -> dict[str, Any]:
    exclude=exclude or set(); candidates=[]
    promoted=promoted_release_ids()
    for m in release_manifests():
        rid=str(m["release_id"])
        if rid in exclude or rid not in promoted or is_quarantined(rid) or m.get("compatibility_epoch") != epoch:
            continue
        h=release_health(rid)
        if all(h["components"][c]["samples"] >= MIN_PROMOTION_SAMPLES_PER_COMPONENT for c in ("gate","terminal")):
            candidates.append((h["score"], h["samples"], rid, h))
    candidates.sort(key=lambda x:(x[0],x[1],x[2]), reverse=True)
    if candidates:
        s,n,r,h=candidates[0]; return {"release_id":r,"score":s,"samples":n,"health":h,"policy":"BEST_KNOWN_GOOD"}
    fallback=bootstrap_release_for_epoch(epoch)
    if fallback and fallback not in exclude:
        return {"release_id":fallback,"score":release_health(fallback)["score"],"samples":release_health(fallback)["samples"],
                "health":release_health(fallback),"policy":"EMERGENCY_BOOTSTRAP_FALLBACK"}
    raise StewardError("NO_COMPATIBLE_FALLBACK")

def evaluate_current() -> dict[str, Any]:
    act=latest_activation()
    if not act:
        return {"status":"NO_ACTIVATION"}
    rid=str(act["target_release"]); m=manifest_by_id(rid); h=release_health(rid)
    if is_quarantined(rid):
        return {"status":"CURRENT_QUARANTINED_WAITING_LAUNCHER_SWITCH","release_id":rid}
    enough_promotion=all(h["components"][c]["samples"] >= MIN_PROMOTION_SAMPLES_PER_COMPONENT for c in ("gate","terminal"))
    if enough_promotion and h["score"] >= PROMOTION_SCORE:
        append_promotion(rid,h)
    enough_rollback=all(h["components"][c]["samples"] >= MIN_ROLLBACK_SAMPLES_PER_COMPONENT for c in ("gate","terminal"))
    if not enough_rollback:
        return {"status":"PROBATION","release_id":rid,"health":h}
    try:
        bkg=choose_best_known_good(str(m["compatibility_epoch"]), exclude={rid})
    except StewardError as exc:
        if str(exc) != "NO_COMPATIBLE_FALLBACK":
            raise
        bkg={"release_id":rid,"score":h["score"],"samples":h["samples"],"health":h,"policy":"CURRENT_IS_ONLY_COMPATIBLE_RELEASE"}
    reasons=[]
    if h["score"] < ROLLBACK_HARD_FLOOR and bkg["release_id"] != rid:
        reasons.append("CURRENT_BELOW_HARD_FLOOR")
    if bkg["release_id"] != rid and bkg["samples"] and bkg["score"] - h["score"] >= ROLLBACK_REGRESSION_MARGIN:
        reasons.append("CURRENT_REGRESSED_VS_BEST_KNOWN_GOOD")
    if any(h["components"][c]["startup"] < 1.0 for c in ("gate","terminal")):
        reasons.append("STARTUP_FAILURE_OBSERVED")
    if reasons and bkg["release_id"] != rid:
        append_quarantine(rid, "+".join(reasons), h)
        rollback=append_activation(str(bkg["release_id"]), "AUTO_ROLLBACK_BEST_KNOWN_GOOD")
        return {"status":"AUTO_ROLLBACK","from":rid,"to":bkg["release_id"],"reasons":reasons,"health":h,"bkg":bkg,"activation":rollback}
    return {"status":"HEALTHY","release_id":rid,"health":h,"best_known_good":bkg}

def tick() -> dict[str, Any]:
    ensure_dirs()
    boot=bootstrap_if_needed()
    processed=[]
    for p in candidate_files():
        try:
            r=process_candidate(p)
            if r: processed.append(r)
        except Exception as exc:
            print(json.dumps({"event":"JANUS_CODE_STEWARD_CANDIDATE_HOLD","file":p.name,"error":f"{type(exc).__name__}:{exc}"},sort_keys=True),flush=True)
    evaluation=evaluate_current()
    return {"event":"JANUS_CODE_STEWARD_TICK","version":VERSION,"bootstrap":boot,"processed_candidates":len(processed),
            "evaluation":evaluation,"no_delete":True,"no_move":True,"no_rename":True}

def self_test() -> dict[str, Any]:
    sample=b"print('ok')\n"
    assert validate_python_payload(sample,"sample") == sha256_bytes(sample)
    bad=b"import os\nos.remove('x')\n"
    rejected=False
    try: validate_python_payload(bad,"bad")
    except StewardError: rejected=True
    assert rejected
    a=activation_record(1,"000001",None,"TEST")
    assert verify_self_hash(a,"activation_receipt_sha256")
    return {"status":"PASS","version":VERSION,"nohand_ast_rejects_delete":rejected,
            "append_only_activation":True,"best_known_good_policy":True,"bootstrap_snapshot_before_launchers":True}

def main() -> int:
    if "--self-test" in sys.argv:
        print(json.dumps(self_test(),ensure_ascii=False,sort_keys=True)); return 0
    once="--once" in sys.argv
    print(json.dumps({"event":"JANUS_CODE_STEWARD_STARTED","version":VERSION,"root":str(ROOT),"poll_seconds":POLL_SECONDS},sort_keys=True),flush=True)
    while True:
        try:
            result=tick(); print(json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
            if result.get("bootstrap",{}).get("status") == "BOOTSTRAP_READY":
                print(json.dumps({"event":"JANUS_CODE_STEWARD_BOOTSTRAP_READY","release_id":result["bootstrap"]["release_id"],
                                  "manifest_sha256":result["bootstrap"].get("manifest_sha256"),
                                  "gate_sha256":result["bootstrap"].get("gate_sha256"),
                                  "terminal_sha256":result["bootstrap"].get("terminal_sha256"),
                                  "safe_to_replace_gate_terminal_with_launchers":True},sort_keys=True),flush=True)
        except Exception as exc:
            print(json.dumps({"event":"JANUS_CODE_STEWARD_HOLD","version":VERSION,"error":f"{type(exc).__name__}:{exc}",
                              "nas_code_activation":False,"no_delete":True,"no_move":True,"no_rename":True},sort_keys=True),flush=True)
        if once: return 0
        time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    raise SystemExit(main())
