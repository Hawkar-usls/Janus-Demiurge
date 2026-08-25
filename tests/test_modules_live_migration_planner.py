from restored.modules_live_migration_planner import classify_roster


def test_elite_goes_to_probation_only():
    result = classify_roster(["genesis.py", "hephaestus.py", "random_old.py"])
    rows = {x["module"]: x for x in result["entries"]}
    assert rows["genesis.py"]["classification"] == "SELECT_FOR_PROBATION"
    assert rows["hephaestus.py"]["classification"] == "SELECT_FOR_PROBATION"
    assert rows["random_old.py"]["classification"] == "HOLD_REVIEW"
    assert result["authority"]["promotes_to_live"] is False


def test_generated_candidates_are_separate():
    result = classify_roster(["gen_alpha.py", "plugin_gen_beta.py", "ordinary.py"])
    rows = {x["module"]: x for x in result["entries"]}
    assert rows["gen_alpha.py"]["classification"] == "GENERATED_QUARANTINE"
    assert rows["plugin_gen_beta.py"]["classification"] == "GENERATED_QUARANTINE"
    assert rows["ordinary.py"]["classification"] == "HOLD_REVIEW"
    assert result["authority"]["copies_files"] is False
    assert result["authority"]["promotes_to_live"] is False


def test_deterministic_and_path_agnostic():
    a = classify_roster(["J\\genesis.py", "/tmp/GENESIS.PY", "README.md", "_private.py"])
    b = classify_roster(["J/genesis.py", "README.md", "_private.py"])
    assert a["plan_sha256"] == b["plan_sha256"]
    assert len([x for x in a["entries"] if x["module"].lower() == "genesis.py"]) == 1
