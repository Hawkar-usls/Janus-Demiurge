from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

AUTHORITY = "SCOPED_OUTPUT_ARTIFACT_WRITE_ONLY"


def _resolved(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def atomic_write_text(
    output_path: str | os.PathLike[str],
    text: str,
    *,
    immutable_sources: Iterable[str | os.PathLike[str]] = (),
    encoding: str = "utf-8",
) -> Path:
    """Atomically write one explicitly named output artifact.

    The caller must provide immutable source paths when the output is derived
    from source material. The helper refuses to target any of those sources.
    It owns only the temporary file that it creates next to the output.
    """
    dst = _resolved(output_path)
    immutable = {_resolved(path) for path in immutable_sources}
    if dst in immutable:
        raise ValueError("output artifact must not overwrite an immutable source")

    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{dst.name}.", suffix=".tmp", dir=str(dst.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            os.unlink(tmp)
    return dst
