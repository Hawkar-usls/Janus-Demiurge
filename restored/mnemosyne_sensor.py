from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Iterable, Any

SCHEMA="janus.mnemosyne.manifest.v1"
STABILITY_SCHEMA="janus.mnemosyne.stability.v1"
DEFAULT_SUFFIXES=(".py",".json",".md",".txt",".yml",".yaml")

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024), b""): h.update(block)
    return h.hexdigest()

def scan(root: str|Path, suffixes: Iterable[str]=DEFAULT_SUFFIXES) -> dict[str,Any]:
    base=Path(root).resolve()
    allowed={s.lower() for s in suffixes}
    files=[]
    for p in sorted(base.rglob("*"), key=lambda x:x.as_posix()):
        if p.is_file() and p.suffix.lower() in allowed:
            rel=p.resolve().relative_to(base).as_posix()
            files.append({"path":rel,"size":p.stat().st_size,"sha256":sha256_file(p)})
    body={"schema":SCHEMA,"root_label":base.name,"files":files}
    body["manifest_sha256"]=hashlib.sha256(
        json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    ).hexdigest()
    return body

def compare(old: dict[str,Any], new: dict[str,Any]) -> dict[str,list[str]]:
    a={x["path"]:x["sha256"] for x in old.get("files",[])}
    b={x["path"]:x["sha256"] for x in new.get("files",[])}
    return {
      "added":sorted(set(b)-set(a)),
      "removed_observed":sorted(set(a)-set(b)),
      "changed":sorted(p for p in set(a)&set(b) if a[p]!=b[p]),
      "unchanged":sorted(p for p in set(a)&set(b) if a[p]==b[p]),
    }

def classify_stability(old: dict[str,Any], new: dict[str,Any], hot_start_threshold: float=0.80) -> dict[str,Any]:
    diff=compare(old,new)
    current_count=len(new.get("files",[]))
    stable_count=len(diff["unchanged"])
    stability=(stable_count/current_count) if current_count else 1.0
    drift=bool(diff["added"] or diff["removed_observed"] or diff["changed"])
    hot_hint=(stability>hot_start_threshold and not diff["changed"] and not diff["added"])
    return {
      "schema":STABILITY_SCHEMA,
      "old_manifest_sha256":old.get("manifest_sha256"),
      "new_manifest_sha256":new.get("manifest_sha256"),
      "trusted":diff["unchanged"],
      "dirty":diff["changed"],
      "new":diff["added"],
      "removed_observed":diff["removed_observed"],
      "stability_fraction":round(stability,12),
      "drift_observed":drift,
      "hot_start_hint":hot_hint,
      "authority":{
        "skip_security_checks":False,
        "skip_integrity_checks":False,
        "auto_trust_changed_code":False,
        "schedule_expensive_reanalysis_hint_only":True
      },
      "law":"HOT_START_HINT != PERMISSION_TO_SKIP_SECURITY_OR_INTEGRITY_GATES"
    }

def write_manifest(manifest: dict[str,Any], path: str|Path) -> None:
    Path(path).write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
