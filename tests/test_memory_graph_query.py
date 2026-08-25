from restored.memory_graph_query import shortest_path, related_subgraph


def _graph():
    return {
        "nodes": [
            {"id":"A","label":"A"},
            {"id":"B","label":"B"},
            {"id":"C","label":"C"},
            {"id":"D","label":"D"},
        ],
        "edges": [
            {"source":"A","target":"B","weight":1.0},
            {"source":"B","target":"C","weight":1.0},
            {"source":"D","target":"B","weight":1.0},
        ],
    }


def test_shortest_path_is_directed_bfs_and_read_only():
    g=_graph(); before=repr(g)
    r=shortest_path(g,"A","C",max_edges=6)
    assert r["found"] is True
    assert r["path"]==["A","B","C"]
    assert shortest_path(g,"C","A")["found"] is False
    assert repr(g)==before
    assert r["authority"]["mutates_graph"] is False


def test_context_cloud_uses_incoming_and_outgoing_neighbors():
    r=related_subgraph(_graph(),"B",depth=1)
    assert [n["id"] for n in r["nodes"]]==["A","B","C","D"]
    assert len(r["edges"])==3
    assert r["authority"]["loads_or_saves_graph"] is False


def test_invalid_snapshot_fails_closed():
    bad={"nodes":[{"id":"A"}],"edges":[{"source":"A","target":"MISSING"}]}
    try:
        shortest_path(bad,"A","MISSING")
    except ValueError:
        pass
    else:
        raise AssertionError("dangling edge must fail closed")
