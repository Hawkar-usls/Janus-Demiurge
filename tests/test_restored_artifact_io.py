from pathlib import Path

import pytest

from restored.artifact_io import atomic_write_text


def test_atomic_writer_refuses_immutable_source(tmp_path: Path):
    source = tmp_path / "source.json"
    source.write_text("original\n", encoding="utf-8")
    with pytest.raises(ValueError):
        atomic_write_text(source, "replacement\n", immutable_sources=[source])
    assert source.read_text(encoding="utf-8") == "original\n"


def test_atomic_writer_writes_explicit_output_and_preserves_source(tmp_path: Path):
    source = tmp_path / "source.json"
    output = tmp_path / "out" / "receipt.json"
    source.write_text("source\n", encoding="utf-8")
    result = atomic_write_text(output, "receipt\n", immutable_sources=[source])
    assert result == output.resolve()
    assert output.read_text(encoding="utf-8") == "receipt\n"
    assert source.read_text(encoding="utf-8") == "source\n"
    assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


def test_atomic_writer_cleans_temp_on_replace_failure(tmp_path: Path, monkeypatch):
    output = tmp_path / "receipt.json"

    def boom(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("restored.artifact_io.os.replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(output, "receipt\n")
    assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []
