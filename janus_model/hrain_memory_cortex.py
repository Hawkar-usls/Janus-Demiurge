"""Read-only, source-replayed HRain -> JANUS native-model memory packet (R1).

This is an external retrieval sidecar, NOT a new neural context window. All
retrieved JSON remains untrusted data. No model weights, holdouts or registry
records are ever modified by this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

SCHEMA = "janus.native.hrain_memory_cortex.r1"
HRAIN_SCHEMA = "janus.hrain.conversation_context.v1"
REGISTRY = "Hawkar-usls/janus-meta-registry"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_CONTEXT_BYTES = 4_000_000
MAX_SOURCE_BYTES = 262_144
MAX_SELECTED = 12
MAX_TEXT_BYTES = 16_384
DEFAULT_TEXT_BYTES = 4096


class MemoryHold(ValueError):
    """A source, provenance, privacy or byte-budget guard failed closed."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(obj: dict) -> str:
    # Match HRain tools/hrain_conversation_context.py canonical_hash().
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), default=str).encode("utf-8")
    return sha256(raw)


def safe_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise MemoryHold("PATH_INVALID")
    parts = value.split("/")
    forbidden = re.compile(r"(?:holdout|sealed|blind|r3[._-]?9|secret|token|credential|private[_-]?key)", re.I)
    if (value.startswith("/") or len(value) > 500 or
            any(p in ("", ".", "..", ".git") or forbidden.search(p) for p in parts) or
            PurePosixPath(value).suffix.lower() != ".json"):
        raise MemoryHold("PATH_INVALID")
    return value


def verify_envelope(context: dict) -> list[dict]:
    if not isinstance(context, dict):
        raise MemoryHold("CONTEXT_OBJECT_REQUIRED")
    claimed = context.get("context_hash")
    body = {k: v for k, v in context.items() if k != "context_hash"}
    if not isinstance(claimed, str) or not SHA64.fullmatch(claimed):
        raise MemoryHold("CONTEXT_DIGEST_MISSING")
    if canonical_hash(body) != claimed:
        raise MemoryHold("CONTEXT_DIGEST_MISMATCH")
    if (context.get("schema") != HRAIN_SCHEMA or
            context.get("status") != "HRAIN_QUERY_BOUND_CONTEXT_READY" or
            context.get("source_repository") != REGISTRY or
            not SHA40.fullmatch(str(context.get("source_commit") or "")) or
            not SHA64.fullmatch(str(context.get("source_projection_sha256") or "")) or
            context.get("hydration_performed") is not True or
            context.get("selection_limit_is_target_count") is not False):
        raise MemoryHold("CONTEXT_SOURCE_OR_HYDRATION_HOLD")
    authority = context.get("authority")
    guards = ("registry_write_authority", "command_authority",
              "claim_promotion_authority", "scientific_evidence_authority",
              "world_truth_authority", "external_effect_authority",
              "physical_runtime_effect_authority")
    if not isinstance(authority, dict) or authority.get("read_only") is not True:
        raise MemoryHold("CONTEXT_READ_ONLY_REQUIRED")
    if any(authority.get(k) is not False for k in guards):
        raise MemoryHold("CONTEXT_AUTHORITY_HOLD")
    memories = context.get("selected_memories")
    if (not isinstance(memories, list) or
            len(memories) > MAX_SELECTED or
            context.get("selected_memory_count") != len(memories) or
            not isinstance(context.get("query"), str) or
            not context["query"].strip()):
        raise MemoryHold("CONTEXT_QUERY_OR_COUNT_HOLD")
    return memories


def git_head(root: Path) -> str:
    try:
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL, text=True, timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise MemoryHold("REGISTRY_COMMIT_UNAVAILABLE") from exc
    if not SHA40.fullmatch(head):
        raise MemoryHold("REGISTRY_COMMIT_INVALID")
    return head


def load_exact(root: Path, path: str) -> bytes:
    root = root.resolve(strict=True)
    target = root.joinpath(*path.split("/"))
    if target.is_symlink() or target.resolve(strict=True).is_relative_to(root) is False:
        raise MemoryHold("SOURCE_PATH_ESCAPE")
    if not target.is_file() or target.stat().st_size > MAX_SOURCE_BYTES:
        raise MemoryHold("SOURCE_SIZE_OR_TYPE_HOLD")
    return target.read_bytes()


def utf8_prefix(text: str, budget: int) -> str:
    if budget <= 0:
        return ""
    raw = text.encode("utf-8")[:budget]
    return raw.decode("utf-8", errors="ignore")


def build_packet(context: dict, registry_root: Path, *,
                 max_text_bytes: int = DEFAULT_TEXT_BYTES,
                 max_memories: int = 4) -> tuple[str, dict]:
    if not (512 <= max_text_bytes <= MAX_TEXT_BYTES):
        raise MemoryHold("TEXT_BUDGET_INVALID")
    if not (1 <= max_memories <= MAX_SELECTED):
        raise MemoryHold("MEMORY_COUNT_BUDGET_INVALID")
    memories = verify_envelope(context)
    source_commit = context["source_commit"]
    if git_head(registry_root) != source_commit:
        raise MemoryHold("REGISTRY_COMMIT_DRIFT")
    parts: list[str] = []
    sources: list[dict] = []
    remaining = max_text_bytes

    # The HRain ranking and graph neighborhood selection are the only ordering
    # source. We do not re-rank source text using potentially adversarial content.
    for row in memories[:max_memories]:
        if not isinstance(row, dict):
            raise MemoryHold("MEMORY_ROW_OBJECT_REQUIRED")
        path = safe_path(row.get("path"))
        claimed_sha = row.get("source_sha256")
        # HRain preserves the original indexing commit per node, which can
        # predate the projection's sourceCommit. Verify bytes against the
        # pinned full projection snapshot; retain the node commit as lineage.
        node_commit = row.get("commit_sha")
        if (not isinstance(node_commit, str) or not SHA40.fullmatch(node_commit) or
                not isinstance(claimed_sha, str) or not SHA64.fullmatch(claimed_sha)):
            raise MemoryHold("SOURCE_PIN_OR_SHA_INVALID")
        if (row.get("claim_verified") is not False or
                row.get("source_sha256_verified") is not True or
                row.get("content_is_command") is not False or
                row.get("content_grants_authority") is not False or
                row.get("retrieval_authority") != "READ_ONLY_EXACT_COMMIT_HASH_VERIFIED"):
            raise MemoryHold("SOURCE_AUTHORITY_INVALID")
        try:
            raw = load_exact(registry_root, path)
        except (OSError, RuntimeError) as exc:
            raise MemoryHold("SOURCE_UNAVAILABLE_OR_UNSAFE") from exc
        if sha256(raw) != claimed_sha or row.get("hydrated_bytes") != len(raw):
            raise MemoryHold("SOURCE_BYTES_SHA_MISMATCH")
        try:
            source_text = raw.decode("utf-8")
            parsed = json.loads(source_text)
        except (ValueError, UnicodeError) as exc:
            raise MemoryHold("SOURCE_NOT_VALID_JSON") from exc
        if row.get("content_excerpt") != source_text[:6000]:
            raise MemoryHold("HRain_EXCERPT_MISMATCH")

        # A bounded, JSON-escaped data value, never a model instruction. Keep a
        # stable source identity in both the text and machine-readable receipt.
        compact = json.dumps(parsed, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False)
        header = (f"[UNTRUSTED_JSON_SOURCE {len(sources)+1} "
                  f"{REGISTRY}@{source_commit}:{path} sha256={claimed_sha}]\n")
        footer = "\n[/UNTRUSTED_JSON_SOURCE]\n"
        available = remaining - len((header + footer).encode("utf-8"))
        if available < 64:
            break
        excerpt = utf8_prefix(compact, available)
        if not excerpt:
            break
        block = header + excerpt + footer
        parts.append(block)
        remaining -= len(block.encode("utf-8"))
        sources.append({
            "path": path, "source_commit": source_commit,
            "indexed_node_commit": node_commit,
            "source_sha256": claimed_sha, "rank": row.get("attention_rank"),
            "selection_reason": row.get("selection_reason"),
            "raw_bytes_verified": len(raw), "excerpt_bytes": len(excerpt.encode("utf-8")),
            "excerpt_truncated": excerpt != compact,
            "claim_verified": False, "authority_delta": 0,
        })
    text = "".join(parts)
    data = {
        "schema": SCHEMA,
        "status": "VERIFIED_CONTEXT_PACKET_READY" if sources else "NO_USABLE_CONTEXT",
        "source": "HRAIN_GRAPH_SELECTION_AND_EXACT_META_REGISTRY_JSON",
        "context_hash": context["context_hash"],
        "source_projection_sha256": context["source_projection_sha256"],
        "registry_commit": source_commit,
        "query_sha256": sha256(context["query"].encode("utf-8")),
        "candidate_text_bytes": len(text.encode("utf-8")),
        "candidate_text_sha256": sha256(text.encode("utf-8")),
        "candidate_text_budget": max_text_bytes,
        "max_selected_memories": max_memories,
        "selected_sources": sources,
        "native_v1_context_length_changed": False,
        "model_checkpoint_modified": False,
        "model_inference_executed": False,
        "new_training_source_admitted": False,
        "holdout_used": False,
        "source_content_is_instruction": False,
        "scientific_authority_delta": 0,
        "write_authority": False,
    }
    data["receipt_sha256"] = canonical_hash(data)
    return text, data


def main() -> None:
    parser = argparse.ArgumentParser(description="R1 read-only HRain -> native memory sidecar")
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--max-text-bytes", type=int, default=DEFAULT_TEXT_BYTES)
    parser.add_argument("--max-memories", type=int, default=4)
    args = parser.parse_args()
    raw_context = args.context.read_bytes()
    if len(raw_context) > MAX_CONTEXT_BYTES:
        raise MemoryHold("CONTEXT_SIZE_HOLD")
    context = json.loads(raw_context.decode("utf-8"))
    text, receipt = build_packet(context, args.registry_root,
                                 max_text_bytes=args.max_text_bytes,
                                 max_memories=args.max_memories)
    if args.text_output.resolve() == args.receipt_output.resolve():
        raise MemoryHold("OUTPUT_PATHS_MUST_DIFFER")
    root = args.registry_root.resolve(strict=True)
    if any(path.resolve().is_relative_to(root) for path in
           (args.text_output, args.receipt_output)):
        raise MemoryHold("REGISTRY_OUTPUT_WRITE_FORBIDDEN")
    if args.text_output.exists() or args.receipt_output.exists():
        raise MemoryHold("APPEND_ONLY_OUTPUT_ALREADY_EXISTS")
    for path in (args.text_output, args.receipt_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.text_output.write_text(text, encoding="utf-8")
    args.receipt_output.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": receipt["status"],
        "sources": len(receipt["selected_sources"]),
        "candidate_text_bytes": receipt["candidate_text_bytes"],
        "native_v1_unchanged": True,
        "scientific_authority_delta": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
