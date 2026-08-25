from __future__ import annotations
import hashlib, json, os, tempfile
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "janus.dream_bus.envelope.v1"
BLUEPRINT_TYPES = {"NEW_MODULE_BLUEPRINT","NEW_MODULE_IDEA","CODE_GENERATION"}
MEMORY_TYPES = {"dream","DREAM"}
EXPERIENCE_TYPES = {"game_event","artifact","lore","path_choice","SYSTEM_BUFF","EVOLVED_BUFF","Genesis"}

def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def classify_lane(observed_type: str) -> str:
    if observed_type in BLUEPRINT_TYPES: return "BLUEPRINT"
    if observed_type in MEMORY_TYPES: return "MEMORY"
    if observed_type in EXPERIENCE_TYPES: return "EXPERIENCE"
    return "QUARANTINE"

def normalize_event(event: Any, source: str = "unknown") -> dict[str, Any]:
    payload = event if isinstance(event, dict) else {"value": event}
    observed_type = str(payload.get("type", "UNKNOWN"))
    seed = {"source": source, "observed_type": observed_type, "payload": payload}
    event_id = hashlib.sha256(_canonical(seed)).hexdigest()
    return {
        "schema": SCHEMA,
        "event_id": event_id,
        "source": source,
        "observed_type": observed_type,
        "lane": classify_lane(observed_type),
        "payload": payload,
        "acknowledged": False,
    }

def route_events(events: Iterable[Any], source: str = "unknown") -> dict[str, list[dict[str, Any]]]:
    lanes = {"MEMORY": [], "BLUEPRINT": [], "EXPERIENCE": [], "QUARANTINE": []}
    for event in events:
        env = normalize_event(event, source)
        lanes[env["lane"]].append(env)
    return lanes

def route_file(input_path: str | os.PathLike[str], output_path: str | os.PathLike[str], source: str = "legacy_dreams_json") -> dict[str, Any]:
    src, dst = Path(input_path), Path(output_path)
    if src.resolve() == dst.resolve():
        raise ValueError("output must differ from input; source bus is immutable")
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("dream bus input must be a JSON array")
    lanes = route_events(data, source)
    receipt = {
        "schema": "janus.dream_bus.route_receipt.v1",
        "source_path": src.name,
        "source_sha256": before,
        "event_count": len(data),
        "lane_counts": {k: len(v) for k, v in lanes.items()},
        "lanes": lanes,
        "destructive_consume": False,
    }
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=dst.name+".", dir=str(dst.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(receipt, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write("\n")
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    after = hashlib.sha256(src.read_bytes()).hexdigest()
    if before != after: raise RuntimeError("source bus changed during routing")
    return receipt
