"""Bounded, SHA-bound JANUS checkpoint admission before PyTorch deserialization.

Hash binding is not independent protection against rewriting both Git history
and model state. Custom in-process training candidates can be unpinned at this
library boundary; the user-facing CLI must require an explicit SHA-256 for them.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import zipfile

PROMOTED = Path(__file__).resolve().parent / "checkpoints" / "promoted.pt"
PROMOTED_STATE = Path(__file__).resolve().parent / "state" / "JANUS_MODEL_STATE.json"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
MAX_CHECKPOINT_BYTES = 100_000_000
MAX_UNCOMPRESSED_BYTES = 100_000_000
MAX_ARCHIVE_FILES = 4096
MAX_PARAMETERS = 30_000_000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_canonical_promoted(path: Path) -> bool:
    return Path(path).resolve() == PROMOTED.resolve()


def preflight(path: Path, *, expected_sha256: str | None = None) -> str:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("JANUS_CHECKPOINT_PATH_HOLD")
    size = path.stat().st_size
    if not 1 <= size <= MAX_CHECKPOINT_BYTES:
        raise RuntimeError("JANUS_CHECKPOINT_SIZE_HOLD")
    if expected_sha256 is not None and (not isinstance(expected_sha256, str)
                                       or SHA_PATTERN.fullmatch(expected_sha256) is None):
        raise RuntimeError("JANUS_CHECKPOINT_DIGEST_FORMAT_HOLD")
    if is_canonical_promoted(path):
        try:
            state = json.loads(PROMOTED_STATE.read_text(encoding="utf-8"))
            committed = state["checkpoint_sha256"]
        except (OSError, KeyError, ValueError, TypeError) as exc:
            raise RuntimeError("JANUS_PROMOTED_STATE_MISSING_HOLD") from exc
        if not isinstance(committed, str) or SHA_PATTERN.fullmatch(committed) is None:
            raise RuntimeError("JANUS_PROMOTED_STATE_DIGEST_INVALID_HOLD")
        if expected_sha256 is not None and not hmac.compare_digest(expected_sha256, committed):
            raise RuntimeError("JANUS_CHECKPOINT_EXPECTED_STATE_CONFLICT_HOLD")
        expected_sha256 = committed
    digest = sha256_file(path)
    if expected_sha256 is not None and not hmac.compare_digest(digest, expected_sha256):
        raise RuntimeError("JANUS_CHECKPOINT_SHA_MISMATCH_HOLD")
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if not members or len(members) > MAX_ARCHIVE_FILES:
                raise RuntimeError("JANUS_CHECKPOINT_ZIP_MEMBERS_HOLD")
            if sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES:
                raise RuntimeError("JANUS_CHECKPOINT_ZIP_UNCOMPRESSED_HOLD")
            if not any(m.filename.endswith("/data.pkl") for m in members):
                raise RuntimeError("JANUS_CHECKPOINT_ZIP_STRUCTURE_HOLD")
            if any(m.file_size < 0 or m.compress_size < 0
                   or m.file_size > MAX_UNCOMPRESSED_BYTES for m in members):
                raise RuntimeError("JANUS_CHECKPOINT_ZIP_MEMBER_SIZE_HOLD")
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise RuntimeError("JANUS_CHECKPOINT_ZIP_INVALID_HOLD") from exc
    return digest


def checked_config(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_TYPE_HOLD")
    bounds = {
        "vocab_size": (258, 258),
        "context_length": (32, 8192),
        "d_model": (16, 1024),
        "n_heads": (1, 64),
        "n_layers": (1, 16),
        "ff_mult": (1, 8),
    }
    clean = {}
    if set(raw) != set(bounds) | {"dropout"}:
        raise RuntimeError("JANUS_CHECKPOINT_CONFIG_FIELDS_HOLD")
    for field, (minimum, maximum) in bounds.items():
        value = raw.get(field)
        if type(value) is not int or not minimum <= value <= maximum:
            raise RuntimeError("JANUS_CHECKPOINT_CONFIG_BOUND_HOLD:" + field)
        clean[field] = value
    if clean["d_model"] % clean["n_heads"] != 0:
        raise RuntimeError("JANUS_CHECKPOINT_HEAD_DIVISIBILITY_HOLD")
    dropout = raw.get("dropout")
    if type(dropout) not in (int, float) or not math.isfinite(float(dropout)) or not 0 <= dropout < 1:
        raise RuntimeError("JANUS_CHECKPOINT_DROPOUT_HOLD")
    clean["dropout"] = float(dropout)
    d = clean["d_model"]
    rough_parameters = (clean["vocab_size"] + clean["context_length"]) * d + (
        clean["n_layers"] * (4 * d * d + 2 * d * d * clean["ff_mult"] + 16 * d)
    )
    if rough_parameters > MAX_PARAMETERS:
        raise RuntimeError("JANUS_CHECKPOINT_PARAMETERS_BUDGET_HOLD")
    return clean
