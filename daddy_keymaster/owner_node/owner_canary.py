"""JANUS owner-local bounded compute canary: verified snapshot -> one CPU proof.

No untrusted task execution, networking, model writes, credentials or daemon.
Uses only Python stdlib, a single short CPU calculation, and local receipts.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parent
SNAPSHOTS = ROOT / "snapshots"
RECEIPTS = ROOT / "node_receipts"
SCHEMA = "janus.daddy_keymaster.owner_node_canary.v1"

def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha(data):
    return hashlib.sha256(canonical(data)).hexdigest()

def need(condition, why):
    if not condition:
        raise ValueError(why)

def main():
    verify_file = ROOT / "Verify-Snapshot.py"
    if not verify_file.exists():
        verify_file = ROOT / "verify_snapshot.py"
    verify = runpy.run_path(str(verify_file))["validate"]
    snapshots = ROOT / "snapshots"
    receipts_dir = ROOT / "node_receipts"
    candidates = sorted(snapshots.glob("*.receipt.json"),
                        key=lambda p: p.stat().st_mtime_ns, reverse=True)
    need(candidates, "OWNER_NODE_NO_BACKUP_AVAILABLE")
    chosen = None
    for rec in candidates:
        doc = json.loads(rec.read_text(encoding="utf-8-sig"))
        head = doc["head_sha"]
        zip_path = snapshots / (head + ".zip")
        if zip_path.exists():
            chosen = (head, zip_path, rec)
            break
    need(chosen is not None, "OWNER_NODE_NO_VERIFIABLE_BACKUP")
    head, zip_path, rec_path = chosen
    verification = verify(str(zip_path), str(rec_path))
    need(verification["status"]=="JANUS_INDEPENDENT_LOCAL_REPLAY_PASS",
         "OWNER_NODE_VERIFICATION_FAILED")
    receipts_dir.mkdir(parents=True,exist_ok=True)
    target = receipts_dir / (head+".json")
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8-sig"))
        signature = existing.get("receipt_sha256")
        body = {k:v for k,v in existing.items() if k!="receipt_sha256"}
        need(signature == sha(body) and existing.get("source_head")==head
             and existing.get("source_zip_sha256")==verification["zip_sha256"]
             and existing.get("status")=="OWNER_NODE_BOUNDED_CANARY_PASS",
             "OWNER_NODE_EXISTING_PROOF_TAMPERED")
        print("OWNER_NODE_CANARY_ALREADY_VERIFIED head="+head)
        return
    # One core, no model or downloaded source code; strictly 40,000 small
    # SHA calculations, independent of user prompts or queue task envelopes.
    # Safe even on low-spec hardware and never repeats for the same HEAD.
    started = time.monotonic()
    item = hashlib.sha256((head+verification["zip_sha256"]).encode()).digest()
    for _ in range(40000):
        item = hashlib.sha256(item).digest()
    elapsed = round((time.monotonic()-started)*1000,2)
    record = {
        "schema":SCHEMA,
        "status":"OWNER_NODE_BOUNDED_CANARY_PASS",
        "captured_utc":dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),
        "source_head":head,
        "source_zip_sha256":verification["zip_sha256"],
        "archive_segments_verified":verification["archive_segments"],
        "queue_epoch_verified":verification["queue_epoch"],
        "work_kind":"pure_module_eval_synthetic_sha256",
        "iterations":40000,
        "output_sha256":item.hex(),
        "elapsed_ms":elapsed,
        "owner_node_availability":"OBSERVED_ONCE_NOT_24_7",
        "remote_dispatches":0,
        "external_model_claims":0,
        "champion_promotions":0,
        "authority_delta":0
    }
    record["receipt_sha256"]=sha(record)
    staging = target.with_suffix(".partial")
    staging.write_bytes(canonical(record)+b"\n")
    os.replace(staging,target)
    need(sha({k:v for k,v in json.loads(target.read_text()).items()
              if k != "receipt_sha256"}) == record["receipt_sha256"],
         "OWNER_NODE_POSTWRITE_TAMPER")
    print("OWNER_NODE_CANARY_NEW_VERIFIED head="+head+" elapsed_ms="+str(elapsed)+
          " result_sha256="+item.hex())

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("OWNER_NODE_CANARY_HOLD: "+str(exc),file=sys.stderr)
        sys.exit(2)
