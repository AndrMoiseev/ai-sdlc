from pathlib import Path

import pytest

import detekt_audit as audit


@pytest.fixture
def project(monkeypatch):
    root = Path("project").absolute()
    defaults = {"style": {"active": True, "Enabled": {"active": True},
                          "Disabled": {"active": False}, "Renamed": {"active": True}}}
    files = {
        Path("defaults.jar"): defaults,
        audit.ASSETS / "detekt.yml": {"style": {"active": True, "Enabled": {"active": True},
                                                "Disabled": {"active": False}}},
        audit.ASSETS / "detekt-1.yml": {"style": {"Renamed": {"active": True}}},
        audit.ASSETS / "detekt-2.yml": {"style": {"Renamed": {"active": True}}},
        root / "module.yml": {"style": {"Enabled": {"active": False, "severity": "warning"}}},
        root / "shared.yml": {"style": {"Enabled": {"active": True}, "Renamed": {"active": False}}},
    }
    monkeypatch.setattr(audit, "read_config", files.__getitem__)
    monkeypatch.setattr(Path, "resolve", lambda path, strict=False: path)

    def inspect(*configs, accept=(), version="1.23.8", standalone=False, ktlint=False):
        return audit.inspect_detekt(root, version, Path("defaults.jar"), configs, standalone, ktlint, accept)

    return inspect, files, root


@pytest.mark.parametrize("accept,selected", [
    ([], set()), (["style.Enabled.active"], {"Enabled"}), (["all"], {"Enabled", "Renamed"}),
])
def test_pin_matches_and_only_selected_differences(project, accept, selected):
    inspect, files, root = project
    result = inspect("shared.yml", "module.yml", accept=accept)
    assert result["pin"] == {"style.active": True, "style.Disabled.active": False}
    assert result["differences"]["style.Enabled.active"] == {
        "source": str(root / "module.yml"), "current": False, "recommended": True,
    }
    edits = result["yaml_edits"].get("style", {})
    pins = {"active": True, "Disabled": {"active": False}} if accept == ["all"] else {}
    assert edits == pins | {key: {"active": True} for key in selected}
    files[root / "applied.yml"] = result["yaml_edits"]
    repeated = inspect("shared.yml", "module.yml", "applied.yml", accept=accept)
    assert repeated["yaml_edits"] == {}
    assert set(repeated["differences"]) == {f"style.{key}.active" for key in {"Enabled", "Renamed"} - selected}


@pytest.mark.parametrize("version,wrapper", [("1.23.8", "formatting"), ("2.0.0-alpha.6", "ktlint")])
def test_installed_wrapper_is_a_selectable_difference(project, version, wrapper):
    inspect, _, _ = project
    assert not inspect(version=version)["differences"]
    result = inspect(version=version, ktlint=True, accept=[f"{wrapper}.active"])
    assert result["yaml_edits"][wrapper] == {"active": False}
    assert "style" not in result["yaml_edits"]


def test_standalone_config_does_not_inherit_enabled_rules(project):
    inspect, _, _ = project
    result = inspect("module.yml", standalone=True)
    assert result["differences"]["style.Renamed.active"]["current"] is False
    assert result["pin"] == {"style.active": True, "style.Disabled.active": False}
    with pytest.raises(ValueError, match="Unknown detekt setting"):
        inspect("module.yml", accept=["style.Unknown.active"])


def test_other_release_uses_its_own_rule_list(project):
    inspect, files, _ = project
    defaults = files[Path("defaults.jar")]
    defaults["style"]["ReleaseSpecific"] = {"active": True}
    defaults["style"]["Disabled"] = {"active": True}
    defaults["style"]["ForbiddenFutureRule"] = {"active": True}
    defaults["style"]["ModifierOrder"] = {"active": True}
    defaults["coroutines"] = {"active": True, "ReleaseSpecific": {"active": True}}
    defaults["potential-bugs"] = {"PropertyUsedBeforeDeclaration": {"active": False}}
    common = files[audit.ASSETS / "detekt.yml"]
    common["style"]["ModifierOrder"] = {"active": False}
    common["coroutines"] = {"active": False}
    common["potential-bugs"] = {"PropertyUsedBeforeDeclaration": {"active": True},
                                "DontDowncastCollectionTypes": {"active": True}}
    edits = inspect(version="1.22.0", accept=["all"])["yaml_edits"]
    assert edits["style"]["ReleaseSpecific"]["active"] is True
    assert edits["style"]["Disabled"]["active"] is True
    assert edits["style"]["ForbiddenFutureRule"]["active"] is False
    assert edits["style"]["ModifierOrder"]["active"] is False
    assert edits["coroutines"] == {"active": False, "ReleaseSpecific": {"active": False}}
    assert edits["potential-bugs"] == {"PropertyUsedBeforeDeclaration": {"active": True}}


def test_pin_matching_value_from_external_config(project):
    inspect, files, root = project
    external = root.parent / "organization.yml"
    files[external] = {"style": {"Enabled": {"active": True}}}
    assert inspect(external)["pin"]["style.Enabled.active"] is True


def test_variable_name_limit_is_selectable_independently(project):
    inspect, files, root = project
    files[Path("defaults.jar")]["naming"] = {
        "VariableMaxLength": {"active": False, "maximumVariableNameLength": 64}}
    files[audit.ASSETS / "detekt.yml"]["naming"] = {
        "VariableMaxLength": {"active": True, "maximumVariableNameLength": 64}}
    key = "naming.VariableMaxLength.maximumVariableNameLength"
    active = "naming.VariableMaxLength.active"
    assert inspect("module.yml", standalone=True)["pin"][key] == 64

    files[root / "module.yml"]["naming"] = {"VariableMaxLength": {"maximumVariableNameLength": 80}}
    result = inspect("module.yml", accept=[active])
    assert result["differences"][key] == {
        "current": 80, "recommended": 64, "source": str(root / "module.yml")}
    assert result["yaml_edits"]["naming"]["VariableMaxLength"] == {"active": True}
    result = inspect("module.yml", accept=[key])
    assert result["yaml_edits"]["naming"]["VariableMaxLength"] == {"maximumVariableNameLength": 64}
    result = inspect("module.yml", accept=["all"])
    files[root / "applied.yml"] = result["yaml_edits"]
    assert inspect("module.yml", "applied.yml", accept=["all"])["yaml_edits"] == {}
