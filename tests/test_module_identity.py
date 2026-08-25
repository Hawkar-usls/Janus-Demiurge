from restored.module_identity import canonical_module_key, protected, collision_groups

def test_stem_filename_and_path_are_same_identity():
    assert canonical_module_key("mod_auditor")=="mod_auditor"
    assert canonical_module_key("mod_auditor.py")=="mod_auditor"
    assert canonical_module_key("services/modules/mod_auditor.py")=="mod_auditor"
    assert protected("services/modules/mod_auditor.py", {"mod_auditor"}) is True

def test_case_and_extension_collision_is_visible():
    groups=collision_groups(["Mod_Rex.py","mod_rex","services/modules/MOD_REX.PY","other.py"])
    assert groups["mod_rex"]==["Mod_Rex.py","mod_rex","services/modules/MOD_REX.PY"]
