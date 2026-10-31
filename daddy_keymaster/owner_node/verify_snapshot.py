"""JANUS owner-local read-only archive verifier; Python standard library only."""
import hashlib
import json
import pathlib
import re
import sys
import zipfile

PREFIX = "state/"
SEG = re.compile(r"state/archive_segments/([0-9]{8})\.json$")
MARK = re.compile(r"state/processed_sources/([a-f0-9]{64})\.json$")
SHA = re.compile(r"[a-f0-9]{64}$")
HEAD_SHA = re.compile(r"[a-f0-9]{40}$")
ZERO = "0" * 64

def need(x, message):
    if not x:
        raise ValueError(message)

def digest(obj):
    b = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()

def verify_receipt(doc, schema):
    need(isinstance(doc, dict) and doc.get("schema") == schema, "BAD_RECEIPT_SCHEMA")
    given = doc.get("receipt_sha256")
    need(isinstance(given, str) and SHA.fullmatch(given), "BAD_RECEIPT_SHA")
    need(digest({k:v for k,v in doc.items() if k != "receipt_sha256"}) == given, "RECEIPT_TAMPER")
    return given

def verify_queue(s):
    need(isinstance(s, dict) and s.get("schema") == "janus.daddy_keymaster.git_cas_queue.v1", "BAD_QUEUE_SCHEMA")
    events = s.get("events")
    need(isinstance(events, list) and isinstance(s.get("tasks"), dict), "BAD_QUEUE_SHAPE")
    need(type(s.get("epoch")) is int and s["epoch"] == len(events) and len(events) <= 256, "BAD_QUEUE_EPOCH")
    rows = {}
    tip = ZERO
    for seq, ev in enumerate(events, start=1):
        need(type(ev.get("seq")) is int and ev["seq"] == seq and ev.get("previous_sha256") == tip, "BAD_EVENT_SEQUENCE")
        body = {k:ev[k] for k in ("seq","kind","task_id","detail","previous_sha256")}
        need(ev.get("event_sha256") == digest(body), "BAD_EVENT_CHAIN")
        tid, kind, d = ev["task_id"], ev["kind"], ev["detail"]
        if kind == "ENQUEUE":
            need(tid not in rows and len(rows) < 32 and isinstance(d,dict), "BAD_ENQUEUE_DUPLICATE")
            need(d.get("kind") in ("contract_test","readonly_index","pure_module_eval"), "UNAUTHORIZED_KIND")
            need(isinstance(d.get("source_sha256"), str) and SHA.fullmatch(d["source_sha256"]), "BAD_SOURCE_SHA")
            rows[tid] = dict(d, state="QUEUED", generation=0, holder=None,
                             lease_until=None, checkpoint_sha256=None, result_sha256=None)
        else:
            need(tid in rows, "EVENT_WITHOUT_TASK")
            row = rows[tid]
            if kind == "CLAIM":
                need(row["state"] == "QUEUED" and type(d.get("generation")) is int
                     and d["generation"] == row["generation"] + 1, "BAD_CLAIM")
                row.update(state="LEASED",generation=d["generation"],
                           holder=d["holder"],lease_until=d["lease_until"])
            elif kind == "CHECKPOINT":
                need(row["state"] == "LEASED" and d.get("generation") == row["generation"]
                     and d.get("holder") == row["holder"], "BAD_CHECKPOINT_HOLDER")
                need(isinstance(d.get("content_sha256"), str) and SHA.fullmatch(d["content_sha256"]), "BAD_CHECKPOINT_SHA")
                row["checkpoint_sha256"] = d["content_sha256"]
            elif kind == "COMPLETE":
                need(row["state"] == "LEASED" and d.get("generation") == row["generation"]
                     and d.get("holder") == row["holder"]
                     and row["checkpoint_sha256"] is not None
                     and d.get("checkpoint_sha256") == row["checkpoint_sha256"], "BAD_COMPLETE")
                need(isinstance(d.get("result_sha256"), str) and SHA.fullmatch(d["result_sha256"]), "BAD_RESULT_SHA")
                row.update(state="COMPLETE",result_sha256=d["result_sha256"])
            elif kind == "HOLD":
                need(row["state"] == "LEASED" and d.get("generation") == row["generation"]
                     and d.get("reason") == "EXPIRED_OUTCOME_UNCERTAIN", "BAD_HOLD")
                row["state"] = "HOLD"
            elif kind == "SKIP_SUPERSEDED":
                need(row["state"] == "QUEUED"
                     and d.get("source_sha256") == row["source_sha256"]
                     and d.get("reason") == "UNCLAIMED_OLD_MAIN_VERSION", "BAD_SKIP")
                row["state"] = "SKIPPED"
            else:
                raise ValueError("UNKNOWN_EVENT")
        tip = ev["event_sha256"]
    need(tip == s.get("tip_sha256") and rows == s["tasks"], "TASK_PROJECTION_MISMATCH")
    return {"epoch":len(events),"tip":tip,"tasks":len(rows),
            "complete":sum(x["state"]=="COMPLETE" for x in rows.values())}

def validate(zip_path, receipt_path):
    zpath = pathlib.Path(zip_path)
    record = json.loads(pathlib.Path(receipt_path).read_text(encoding="utf-8-sig"))
    need(record.get("schema") == "janus.daddy_keymaster.physical_backup_receipt.v1", "BAD_LOCAL_RECEIPT")
    need(HEAD_SHA.fullmatch(record.get("head_sha","")) is not None, "BAD_HEAD")
    need(hashlib.sha256(zpath.read_bytes()).hexdigest() == record.get("zip_sha256"), "ZIP_SHA_MISMATCH")
    with zipfile.ZipFile(zpath,"r") as z:
        files = {}
        need(len(z.infolist()) <= 4096, "ZIP_ENTRY_LIMIT")
        for info in z.infolist():
            name = info.filename
            need(name == "state/relay_queue.json" or name == "state/relay_archive_head.json"
                 or SEG.fullmatch(name) or MARK.fullmatch(name), "UNAUTHORIZED_ZIP_PATH")
            need(name not in files and info.file_size <= 200000, "ZIP_DUP_OR_SIZE")
            files[name] = json.loads(z.read(info).decode("utf-8"))
    need("state/relay_queue.json" in files, "QUEUE_MISSING")
    current = verify_queue(files["state/relay_queue.json"])
    need(record.get("queue_epoch") == current["epoch"]
         and record.get("queue_tip_sha256") == current["tip"], "LOCAL_RECEIPT_STATE_MISMATCH")
    archives = sorted((int(SEG.fullmatch(k).group(1)),v) for k,v in files.items() if SEG.fullmatch(k))
    if archives:
        need("state/relay_archive_head.json" in files, "ARCHIVE_HEAD_MISSING")
        head = files["state/relay_archive_head.json"]
        verify_receipt(head, "janus.daddy_keymaster.archive_head.v1")
        need(head.get("serial") == len(archives), "ARCHIVE_COUNT_GAP")
        previous = ZERO
        covered = {}
        for index,(serial,segment) in enumerate(archives, start=1):
            need(serial == index and segment.get("serial") == serial, "ARCHIVE_SERIAL_GAP")
            sd = verify_receipt(segment,"janus.daddy_keymaster.archive_segment.v1")
            need(segment.get("previous_segment_digest_sha256") == previous, "ARCHIVE_CHAIN_BROKEN")
            archive_state = verify_queue(segment["queue"])
            need(archive_state["tip"] == segment.get("queue_tip_sha256"), "ARCHIVE_QUEUE_SHA_MISMATCH")
            for tid,row in segment["queue"]["tasks"].items():
                need(row["state"] in ("COMPLETE","SKIPPED"), "ARCHIVE_NONTERMINAL")
                covered.setdefault(row["source_sha256"],(serial,sd,[]))[2].append((tid,row["state"]))
            previous = sd
        need(head.get("segment_digest_sha256") == previous and
             head.get("segment_path") == "state/archive_segments/%08d.json"%len(archives),
             "ARCHIVE_HEAD_TIP_MISMATCH")
        markers = {MARK.fullmatch(k).group(1):v for k,v in files.items() if MARK.fullmatch(k)}
        need(set(markers) == set(covered), "SOURCE_MARKER_COVERAGE")
        for source,(serial,sha256,rows) in covered.items():
            marker=markers[source]
            verify_receipt(marker,"janus.daddy_keymaster.retired_source.v1")
            need(marker.get("source_sha256") == source and marker.get("segment") == serial
                 and marker.get("segment_digest_sha256") == sha256, "SOURCE_MARKER_BINDING")
            need(sorted(zip(marker.get("task_ids",[]),marker.get("terminal_states",[]))) == sorted(rows),
                 "SOURCE_MARKER_TASKS")
    else:
        need("state/relay_archive_head.json" not in files, "ORPHAN_ARCHIVE_HEAD")
        need(not any(MARK.fullmatch(k) for k in files), "ORPHAN_SOURCE_MARKER")
    return {"status":"JANUS_INDEPENDENT_LOCAL_REPLAY_PASS",
            "source_head":record["head_sha"],
            "queue_epoch":current["epoch"],"completed":current["complete"],
            "archive_segments":len(archives),"zip_sha256":record["zip_sha256"]}

if __name__ == "__main__":
    try:
        result = validate(sys.argv[1],sys.argv[2])
        print(json.dumps(result,sort_keys=True))
    except Exception as ex:
        print("JANUS_LOCAL_REPLAY_REJECTED: "+str(ex),file=sys.stderr)
        sys.exit(2)
