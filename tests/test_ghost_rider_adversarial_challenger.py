from restored.ghost_rider_adversarial_challenger import prepare_challenge, seal_candidate


def test_prepare_is_deterministic_and_has_no_truth_authority():
    a = prepare_challenge("The signal is artificial.", source_ref="obs:42")
    b = prepare_challenge("The signal is artificial.", source_ref="obs:42")
    assert a["challenge_sha256"] == b["challenge_sha256"]
    assert a["status"] == "ADVERSARIAL_TASK"
    assert len(a["lanes"]) == 4
    assert a["authority"]["synthetic_output_is_evidence"] is False
    assert a["authority"]["writes_truth_memory"] is False


def test_candidate_stays_synthetic_and_requires_independent_evidence():
    challenge = prepare_challenge("A caused B")
    r = seal_candidate(challenge, "ALTERNATIVE_CAUSAL_STORY", "C could explain both A and B")
    assert r["status"] == "ADVERSARIAL_CANDIDATE_NOT_EVIDENCE"
    assert r["authority"]["candidate_is_fact"] is False
    assert r["authority"]["candidate_is_refutation"] is False
    assert r["next_gate"] == "TEST_CANDIDATE_AGAINST_INDEPENDENT_EVIDENCE"
