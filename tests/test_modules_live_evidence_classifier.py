from restored.modules_live_evidence_classifier import build_roster


def test_truth_ladder_does_not_promote_selection_to_success():
    r = build_roster([
        {"module":"hephaestus.py","kind":"INDEX_OR_HASH_PRESENCE"},
        {"module":"hephaestus.py","kind":"MIGRATION_SELECTED"},
    ])
    m=r["modules"][0]
    assert m["state"]=="MIGRATION_SELECTED_ONLY"
    assert m["highest_positive_tier"]==2
    assert r["authority"]["promotes_modules"] is False


def test_online_success_and_failure_are_distinct():
    r=build_roster([
        {"module":"mod_x.py","kind":"LIVE_DIRECTORY_FILE_PRESENCE"},
        {"module":"mod_x.py","kind":"BOOT_ATTEMPTED"},
        {"module":"mod_x.py","kind":"LIVE_MODULE_ONLINE"},
        {"module":"mod_x.py","kind":"LIVE_MODULE_ERROR","detail":"boom"},
    ])
    m=r["modules"][0]
    assert m["state"]=="RUNTIME_FAILURE_CONFIRMED"
    assert m["failure_evidence_count"]==1

    r2=build_roster([
        {"module":"mod_x.py","kind":"LIVE_MODULE_ONLINE"},
        {"module":"mod_x.py","kind":"LIVE_MODULE_ERROR"},
        {"module":"mod_x.py","kind":"LIVE_MODULE_SUCCESS"},
    ])
    m2=r2["modules"][0]
    assert m2["state"]=="LIVE_SUCCESS_CONFIRMED"
    assert m2["failure_evidence_count"]==1


def test_module_identity_normalization_and_invalid_kind():
    r=build_roster([
        {"module":"J\\mod_rex.py","kind":"REGISTRY_LABEL"},
        {"module":"mod_rex","kind":"INDEX_OR_HASH_PRESENCE"},
    ])
    assert r["module_count"]==1
    assert r["modules"][0]["module"]=="mod_rex"
    try:
        build_roster([{"module":"x","kind":"MAGIC_SUCCESS"}])
    except ValueError:
        pass
    else:
        raise AssertionError("unknown evidence kind must fail")
