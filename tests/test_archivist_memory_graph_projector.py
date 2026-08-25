from restored.archivist_memory_graph_projector import project_rows, derive_checkpoint


def test_digest_tombstone_overrides_source_class_and_preserves_boundary():
    r = project_rows([{"id": 7, "source": "JANUS", "content": "deleted but remembered payload", "tags": ["DIGESTED"]}])
    node = r["nodes_to_append"][0]
    assert node["id"] == "MEM_7"
    assert node["class"] == "TOMBSTONE"
    assert node["tombstone"] is True
    assert node["desc"].startswith("[GHOST] ")
    assert r["authority"]["writes_graph"] is False
    assert r["authority"]["deletes_source_memory"] is False


def test_existing_and_trivial_rows_are_skipped_and_checkpoint_advances():
    r = project_rows([
        (1, "USER", "hello", ""),
        (2, "AI", "x", ""),
        (3, "FILE:test", "file memory", ""),
    ], existing_node_ids=["MEM_1"])
    assert r["checkpoint_max_memory_id"] == 3
    assert r["existing_checkpoint"]["checkpoint_max_memory_id"] == 1
    assert [x["id"] for x in r["skipped"]] == [1, 2]
    assert [x["id"] for x in r["nodes_to_append"]] == ["MEM_3"]


def test_reply_edge_is_explicit_and_projection_is_deterministic():
    rows = [
        {"id": 11, "source": "JANUS", "content": "answer", "tags": [], "reply_to": "MEM_10"},
        {"id": 10, "source": "USER", "content": "question", "tags": []},
    ]
    a = project_rows(rows)
    b = project_rows(list(reversed(rows)))
    assert a["projection_sha256"] == b["projection_sha256"]
    links = {x["target"]: x["source"] for x in a["links_to_append"]}
    assert links["MEM_10"] == "CORE"
    assert links["MEM_11"] == "MEM_10"
    assert "EXPLICIT_REPLY_EDGE_NE_POSITIONAL_PREVIOUS_NODE_HEURISTIC" in a["laws"]


def test_checkpoint_derivation_recognizes_only_mem_numeric_ids():
    r = derive_checkpoint(["MEM_2", "MEM_19", "MEM_x", "CORE", "mem_99", "MEM_0007"])
    assert r["checkpoint_max_memory_id"] == 19
    assert r["recognized_node_ids"] == ["MEM_0007", "MEM_19", "MEM_2"]
    assert r["ignored_node_ids"] == ["CORE", "MEM_x", "mem_99"]
    assert r["authority"]["reads_database"] is False
    assert r["authority"]["writes_graph"] is False
