from restored.synapse_graph_integrity import analyze


def test_chain_is_reachable_without_forcing_star_topology():
    graph={
      "nodes":[{"id":"CORE"},{"id":"a"},{"id":"b"}],
      "links":[{"source":"CORE","target":"a"},{"source":"a","target":"b"}]
    }
    r=analyze(graph)
    assert r["status"]=="CLEAN"
    assert r["unreachable_from_core"]==[]
    assert r["direct_core_neighbors"]==["a"]
    assert r["authority"]["mutates_graph"] is False


def test_missing_core_duplicates_invalid_links_and_unreachable_are_findings():
    graph={
      "nodes":[{"id":"a"},{"id":"a"},{"id":"b"}],
      "links":[
        {"source":"a","target":"a"},
        {"source":"a","target":"missing"},
        {"source":"a","target":"b"},
        {"source":"b","target":"a"}
      ]
    }
    r=analyze(graph)
    kinds=[x["kind"] for x in r["findings"]]
    assert r["status"]=="REPAIR_PROPOSAL"
    assert "MISSING_CORE" in kinds
    assert "DUPLICATE_NODE_ID" in kinds
    assert "SELF_LOOP" in kinds
    assert "LINK_TO_MISSING_NODE" in kinds
    assert "DUPLICATE_UNDIRECTED_LINK" in kinds
    assert set(r["unreachable_from_core"])=={"a","b"}
    assert r["authority"]["saves_graph"] is False
