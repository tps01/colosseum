"""U-CFG-04: ConfigStore lookups."""

from __future__ import annotations

import pytest

import colosseum as col
from colosseum.config.loader import ConfigError, ConfigStore, load_config
from colosseum.config.sections import ConfigSectionSpec
from colosseum.context import init_context, get_context
from colosseum.runner.runtime import ensure_output_dir


SPEC = ConfigSectionSpec(
    dotted_path="acme.device",
    id_field="device_id",
    required_keys=("driver", "resource"),
)


def _store() -> ConfigStore:
    normalized = {
        "acme.device": {
            1: {"device_id": 1, "driver": "sim", "resource": "SIM::1"},
        }
    }
    return ConfigStore({}, normalized, {SPEC.dotted_path: SPEC})


def _register_spec() -> None:
    ctx = init_context(test_case_name="config")
    ctx.plugin_registry.register_config_section(SPEC)
    ctx.plugin_registry.loaded = True


def test_get_item_returns_row() -> None:
    row = _store().get_item("acme.device", 1)
    assert row["resource"] == "SIM::1"


def test_unknown_id_raises_config_error() -> None:
    with pytest.raises(ConfigError, match="Unknown id"):
        _store().get_item("acme.device", 99)


def test_require_item_checks_required_keys() -> None:
    store = ConfigStore(
        {},
        {"acme.device": {1: {"device_id": 1, "driver": "sim"}}},
        {SPEC.dotted_path: SPEC},
    )
    with pytest.raises(ConfigError, match="missing required keys"):
        store.require_item("acme.device", 1)


def test_load_config_wraps_normalization_errors(tmp_path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        "[[acme.device]]\n"
        "device_id = 1\n"
        "driver = \"sim\"\n"
        "resource = \"A\"\n"
        "\n"
        "[[acme.device]]\n"
        "device_id = 1\n"
        "driver = \"sim\"\n"
        "resource = \"B\"\n",
        encoding="utf-8",
    )
    _register_spec()
    with pytest.raises(ConfigError, match="Duplicate id"):
        load_config(config_path)


def test_load_config_accepts_utf8_bom(tmp_path) -> None:
    config_path = tmp_path / "bom.toml"
    config_path.write_bytes(
        b"\xef\xbb\xbf"
        b"[[acme.device]]\n"
        b"device_id = 1\n"
        b"driver = \"sim\"\n"
        b"resource = \"SIM::1\"\n"
    )

    _register_spec()
    store = load_config(config_path)

    assert store.require_item("acme.device", 1)["resource"] == "SIM::1"


def test_config_is_loaded_reports_runtime_state(core_config) -> None:
    assert col.config.is_loaded() is False

    load_config(core_config)

    assert col.config.is_loaded() is True


def test_apply_raw_config_attaches_store() -> None:
    from colosseum.config.loader import apply_raw_config
    from colosseum.context import init_context, get_context
    import colosseum.context as context_module

    context_module._ACTIVE_CONTEXT = None
    ctx = init_context(test_case_name="apply_raw")
    ctx.plugin_registry.register_config_section(SPEC)
    ctx.plugin_registry.loaded = True
    raw = {
        "acme": {
            "device": [
                {"device_id": 1, "driver": "serial", "resource": "COM1"},
            ]
        }
    }
    store = apply_raw_config(ctx, raw, source_label="(test)")
    assert get_context().config_path == "(test)"
    assert store.require_item("acme.device", 1)["resource"] == "COM1"


def test_load_config_reload_updates_run_metadata(core_config, isolated_cwd, tmp_path) -> None:
    load_config(core_config)
    ctx = get_context()
    ensure_output_dir(ctx)
    replacement = tmp_path / "replacement.toml"
    replacement.write_text(
        "[runtime]\n"
        "label = \"replacement\"\n",
        encoding="utf-8",
    )

    load_config(replacement)

    metadata = {row.key: row.value for row in ctx.db.fetch_run_metadata()}
    assert metadata["config_path"] == str(replacement.resolve())
