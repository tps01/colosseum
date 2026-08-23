"""No-artifacts utility mode: console-only logging and in-memory SQLite."""

from __future__ import annotations

import pytest

import colosseum as col
import colosseum.context as context_module
from colosseum.config.loader import load_config
from colosseum.context import apply_no_artifacts, init_context, get_context
from colosseum.output.artifacts import resolve_artifact_path
from colosseum.output.paths import ensure_output_dir, ensure_runtime_ready

from tests.support.core_api import measure_value
from tests.support.helpers import run_endex_expect_code


@pytest.fixture(autouse=True)
def _reset_context() -> None:
    context_module._ACTIVE_CONTEXT = None
    yield
    context_module._ACTIVE_CONTEXT = None


def test_load_config_no_artifacts_skips_outputs(core_config, isolated_cwd, capsys) -> None:
    load_config(core_config, no_artifacts=True)
    measure_value(key="rail", value=3.3)

    assert not (isolated_cwd / "outputs").exists()
    captured = capsys.readouterr()
    assert "Colosseum version:" in captured.out
    assert "no-artifacts mode" in captured.out

    measurements = col.database.read_measurements()
    assert [row.key for row in measurements] == ["rail"]


def test_ensure_output_dir_raises_in_no_artifacts_mode(core_config) -> None:
    load_config(core_config, no_artifacts=True)
    ctx = get_context()
    ensure_runtime_ready(ctx)

    with pytest.raises(RuntimeError, match="no-artifacts mode"):
        ensure_output_dir(ctx)


def test_resolve_artifact_path_raises_in_no_artifacts_mode(core_config) -> None:
    load_config(core_config, no_artifacts=True)
    measure_value(key="rail", value=3.3)

    with pytest.raises(RuntimeError, match="no-artifacts mode"):
        resolve_artifact_path("traces/foo.csv")


def test_late_no_artifacts_toggle_raises(core_config) -> None:
    load_config(core_config)
    ctx = get_context()
    ensure_runtime_ready(ctx)

    with pytest.raises(RuntimeError, match="before the runtime is bootstrapped"):
        apply_no_artifacts(ctx, no_artifacts=True)


def test_endex_no_artifacts_skips_summary(core_config, isolated_cwd) -> None:
    load_config(core_config, no_artifacts=True)
    measure_value(key="rail", value=3.3)

    run_endex_expect_code(0)

    assert not (isolated_cwd / "outputs").exists()


def test_init_context_honors_env_no_artifacts(core_config, isolated_cwd, monkeypatch) -> None:
    monkeypatch.setenv("COLOSSEUM_NO_ARTIFACTS", "1")
    init_context(test_case_name="env_flag")
    load_config(core_config)
    measure_value(key="rail", value=3.3)

    assert get_context().no_artifacts is True
    assert not (isolated_cwd / "outputs").exists()
