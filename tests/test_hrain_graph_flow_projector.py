from restored.hrain_graph_flow_projector import project


def test_historical_decay_flow_order_is_projected_without_mutation_authority():
    nodes={"a":{"energy":1.0},"b":{"energy":0.6}}
    edges={"a->b":{"weight":0.5}}
    r=project(nodes=nodes,edges=edges,edge_decay=1.0,energy_decay=1.0,energy_flow_rate=0.1,edge_reinforce=0.02)
    assert r["status"]=="PROJECTION_ONLY"
    assert abs(r["nodes"]["a"]["energy_after_flow"]-0.95)<1e-12
    assert abs(r["nodes"]["b"]["energy_after_flow"]-0.65)<1e-12
    assert abs(r["transfers"][0]["flow"]-0.05)<1e-12
    assert len(r["reinforcement_proposals"])==1
    assert abs(r["reinforcement_proposals"][0]["proposed_reinforced_weight"]-0.51)<1e-12
    assert r["authority"]["mutates_graph"] is False
    assert r["authority"]["deletes_nodes"] is False


def test_historical_drop_is_diagnostic_only_and_missing_endpoint_is_visible():
    nodes={"a":{"energy":0.001}}
    edges={"a->missing":{"weight":0.001}}
    r=project(nodes=nodes,edges=edges,edge_decay=0.5,energy_decay=0.5,node_energy_threshold=0.01,edge_drop_threshold=0.01)
    assert r["nodes"]["a"]["historical_drop_candidate"] is True
    assert r["edges"]["a->missing"]["historical_drop_candidate"] is True
    assert any(x["kind"]=="MISSING_EDGE_ENDPOINT" for x in r["findings"])
    assert r["authority"]["deletes_edges"] is False
    assert r["authority"]["adds_random_edges"] is False
