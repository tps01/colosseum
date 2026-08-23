"""U-SUITE-01: suite TOML loading."""

from __future__ import annotations

import pytest

from colosseum.runner.suite import SuiteError, load_suite_toml


def test_load_happy_suite(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "happy.toml")
    assert suite.name == "fixture_happy"
    assert len(suite.tests) == 1
    assert suite.setup[0].name == "setup_ok.py"
    assert suite.fail_fast is False


def test_missing_name_raises(tmp_path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('tests = ["../scripts/pass_test.py"]\n', encoding="utf-8")
    with pytest.raises(SuiteError, match="requires string field `name`"):
        load_suite_toml(path)


def test_empty_tests_raises(tmp_path) -> None:
    path = tmp_path / "empty.toml"
    path.write_text('name = "x"\ntests = []\n', encoding="utf-8")
    with pytest.raises(SuiteError, match="non-empty `tests`"):
        load_suite_toml(path)


def test_paths_resolve_relative_to_suite_file(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "happy.toml")
    assert suite.tests[0].is_file()
    assert "fixtures" in str(suite.tests[0])


def test_fail_fast_true_loads(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "multi_test_fail_fast_crash.toml")
    assert suite.fail_fast is True
    assert len(suite.tests) == 2


def test_fail_fast_non_bool_raises(tmp_path, fixtures_dir) -> None:
    script = fixtures_dir / "scripts" / "pass_test.py"
    path = tmp_path / "bad_fail_fast.toml"
    path.write_text(
        f'name = "x"\nfail_fast = "yes"\ntests = ["{script.as_posix()}"]\n',
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="fail_fast.*boolean"):
        load_suite_toml(path)
