from restored.graph_selection_assessor import assess


def test_isolated_and_high_pain_nodes_are_review_proposals_not_deleted():
    nodes=[
      {"id":"root","type":"root","pain_score":99},
      {"id":"a","type":"concept","pain_score":0},
      {"id":"b","type":"concept","pain_score":4},
      {"id":"c","type":"concept","pain_score":0}
    ]
    links=[{"source":"root","target":"a"},{"source":"a","target":"b"}]
    r=assess(nodes,links,pain_threshold=3.0)
    by_id={x["node_id"]:x for x in r["assessments"]}
    assert by_id["root"]["status"]=="PROTECTED"
    assert by_id["b"]["status"]=="REVIEW" and "HIGH_PAIN" in by_id["b"]["reasons"]
    assert by_id["c"]["status"]=="REVIEW" and "ISOLATED" in by_id["c"]["reasons"]
    assert r["authority"]["deletes_nodes"] is False
    assert r["authority"]["removes_links"] is False


def test_healthy_connected_graph_needs_no_review():
    nodes=[{"id":"root","type":"root"},{"id":"a","type":"concept"}]
    links=[{"source":"root","target":"a"}]
    r=assess(nodes,links)
    assert r["status"]=="NO_REVIEW_REQUIRED"
    assert r["proposals"]==[]
    assert len(r["assessment_sha256"])==64
