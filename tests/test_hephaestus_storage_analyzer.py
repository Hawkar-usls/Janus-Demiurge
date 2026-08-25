from restored.hephaestus_storage_analyzer import analyze_sizes, scan_metadata


def test_fixed_block_slack_is_explicit_estimate_not_pnp_claim():
    r=analyze_sizes([1,4096,4097],block_size=4096)
    assert r["logical_bytes"]==8194
    assert r["estimated_block_allocated_bytes"]==16384
    assert r["estimated_block_slack_bytes"]==8190
    assert r["interpretation"]["slack_is_estimate"] is True
    assert r["interpretation"]["proves_p_equals_np"] is False
    assert r["authority"]["moves_files"] is False


def test_metadata_scan_does_not_read_or_mutate_content(tmp_path):
    a=tmp_path/"a.bin"; b=tmp_path/"b.txt"
    a.write_bytes(b"x"*5); b.write_text("hello",encoding="utf-8")
    before={p.name:p.read_bytes() for p in (a,b)}
    r1=scan_metadata(tmp_path,block_size=8)
    r2=scan_metadata(tmp_path,block_size=8)
    assert r1["manifest_sha256"]==r2["manifest_sha256"]
    assert r1["summary"]["file_count"]==2
    assert r1["authority"]["reads_file_content"] is False
    assert r1["authority"]["mutates_filesystem"] is False
    assert {p.name:p.read_bytes() for p in (a,b)}==before
