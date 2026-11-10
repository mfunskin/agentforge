from src.config_overlay import merge_config


def test_inputs_are_unchanged():
    defaults = {"service": {"port": 80}, "items": [1]}
    overrides = {"service": {"tls": True}}
    merged = merge_config(defaults, overrides)
    assert defaults == {"service": {"port": 80}, "items": [1]}
    assert overrides == {"service": {"tls": True}}
    merged["service"]["port"] = 443
    merged["items"].append(2)
    assert defaults["service"]["port"] == 80
    assert defaults["items"] == [1]


def test_nested_override_does_not_alias():
    overrides = {"metadata": {"tags": ["prod"]}}
    merged = merge_config({}, overrides)
    merged["metadata"]["tags"].append("new")
    assert overrides == {"metadata": {"tags": ["prod"]}}


def test_deeply_nested_merge():
    result = merge_config(
        {"a": {"b": {"c": 1, "d": 2}}}, {"a": {"b": {"d": 8}}}
    )
    assert result == {"a": {"b": {"c": 1, "d": 8}}}
