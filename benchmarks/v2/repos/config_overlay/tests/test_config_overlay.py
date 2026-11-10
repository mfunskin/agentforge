from src.config_overlay import merge_config


def test_recursive_merge_preserves_default_settings():
    defaults = {"service": {"port": 80, "tls": False}, "region": "us"}
    overrides = {"service": {"tls": True}}
    assert merge_config(defaults, overrides) == {
        "service": {"port": 80, "tls": True}, "region": "us",
    }


def test_explicit_null_replaces_value():
    assert merge_config({"cache": {"ttl": 30}}, {"cache": None}) == {"cache": None}


def test_list_override_replaces_instead_of_appending():
    assert merge_config({"hosts": ["a", "b"]}, {"hosts": ["c"]}) == {"hosts": ["c"]}
