from restored.hrain_similarity_planner import similarity, plan


def test_missing_agent_ids_do_not_create_false_identity_bonus():
    a={"data":{"purity":90,"temp":50}}
    b={"data":{"purity":90,"temp":50}}
    c={"data":{"purity":90,"temp":50,"agent_id":"x"}}
    d={"data":{"purity":90,"temp":50,"agent_id":"x"}}
    assert abs(similarity(a,b)-0.8)<1e-12
    assert abs(similarity(c,d)-1.0)<1e-12


def test_plan_is_deterministic_and_proposal_only():
    nodes={
      "b":{"energy":2,"data":{"purity":91,"temp":51,"agent_id":"x","loss":0.2}},
      "a":{"energy":1,"data":{"purity":90,"temp":50,"agent_id":"x","loss":0.1}},
      "c":{"energy":3,"data":{"purity":10,"temp":90,"agent_id":"y","loss":0.9}}
    }
    r1=plan(nodes=nodes,edges={},similarity_threshold=0.9,cluster_similarity=0.9)
    r2=plan(nodes=dict(reversed(list(nodes.items()))),edges={},similarity_threshold=0.9,cluster_similarity=0.9)
    assert r1["plan_sha256"]==r2["plan_sha256"]
    assert r1["link_proposals"][0]["source"]=="a" and r1["link_proposals"][0]["target"]=="b"
    assert r1["cluster_proposals"][0]["members"]==["a","b"]
    assert r1["authority"]["adds_edges"] is False
    assert r1["authority"]["removes_nodes"] is False


def test_existing_edge_is_not_proposed_again_and_large_graph_holds():
    nodes={"a":{"data":{"purity":100,"temp":0,"agent_id":"z"}},"b":{"data":{"purity":100,"temp":0,"agent_id":"z"}}}
    r=plan(nodes=nodes,edges={"a->b":{"weight":1}},similarity_threshold=0.5)
    assert r["link_proposals"]==[]
    huge={str(i):{"data":{}} for i in range(4)}
    assert plan(nodes=huge,max_nodes=3)["status"]=="HOLD"
