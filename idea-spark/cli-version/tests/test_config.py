import json

from idea_spark.config import config_path, load_config, set_tools_enabled, tools_enabled


def test_tools_disabled_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    assert config_path() == tmp_path / "idea-spark" / "config.json"
    assert load_config()["tools"]["enabled"] is False
    assert tools_enabled() is False


def test_tools_enabled_only_by_explicit_profile_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"tools": {"enabled": True}}), encoding="utf-8")

    assert tools_enabled() is True


def test_invalid_config_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")

    assert load_config()["tools"]["enabled"] is False
    assert tools_enabled() is False


def test_non_object_config_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")

    assert tools_enabled() is False


def test_set_tools_enabled_writes_stable_json(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))

    path = set_tools_enabled(True)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert path == config_path()
    assert data == {"tools": {"enabled": True}}
    assert tools_enabled() is True


def test_empty_hermes_home_is_treated_as_unset(monkeypatch):
    monkeypatch.setenv("HERMES_HOME", "")

    assert config_path() == config_path().home() / ".hermes" / "idea-spark" / "config.json"


def test_set_tools_enabled_preserves_future_config_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"tools": {"enabled": False, "future": "keep"}, "dashboard": {"port": 8765}}),
        encoding="utf-8",
    )

    set_tools_enabled(True)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data == {"dashboard": {"port": 8765}, "tools": {"enabled": True, "future": "keep"}}


def test_boolean_like_non_true_values_do_not_enable_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    path = config_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"tools": {"enabled": "true"}}), encoding="utf-8")

    assert tools_enabled() is False
