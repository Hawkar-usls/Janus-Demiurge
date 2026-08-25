from restored.hrain_action_scorer import score_actions


def test_scores_direct_and_edge_evidence_without_mutation_authority():
    nodes={
      "n1":{"type":"memory","energy":2.0,"data":{"action":"EXPLORE"}},
      "n2":{"type":"memory","energy":1.0,"data":{}},
      "a_exploit":{"type":"action","energy":0.1,"data":{"action":"EXPLOIT"}}
    }
    edges={"n2->a_exploit":{"weight":0.8}}
    r=score_actions(nodes=nodes,edges=edges,available_actions=["EXPLORE","EXPLOIT"])
    assert r["status"]=="PROPOSAL"
    assert r["selected_action"]=="EXPLORE"
    assert r["scores"]["EXPLORE"]==2.0
    assert r["scores"]["EXPLOIT"]==0.9
    assert len(r["evidence"]["EXPLOIT"])==2
    assert r["authority"]["executes_action"] is False
    assert r["authority"]["mutates_graph"] is False


def test_no_signal_is_not_random_fallback_and_tie_is_explicit():
    empty=score_actions(nodes={},edges={},available_actions=["A","B"])
    assert empty["status"]=="NO_SIGNAL"
    assert empty["selected_action"] is None
    nodes={"x":{"type":"memory","energy":1.0,"data":{"action":"A"}},"y":{"type":"memory","energy":1.0,"data":{"action":"B"}}}
    tied=score_actions(nodes=nodes,edges={},available_actions=["A","B"])
    assert tied["status"]=="PROPOSAL"
    assert tied["selected_action"] is None
    assert tied["tied_actions"]==["A","B"]
