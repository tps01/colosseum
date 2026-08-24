"""U-SUITE-01: suite TOML loading."""

from __future__ import annotations

from datetime import timedelta

import pytest

from colosseum.runner.suite import (
    SuiteError,
    expand_test_schedule,
    load_suite_toml,
    parse_repeat_duration,
)


def test_load_happy_suite(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "happy.toml")
    assert suite.name == "fixture_happy"
    assert len(suite.tests) == 1
    assert suite.tests[0].path.name == "pass_test.py"
    assert suite.tests[0].repeat_count == 1
    assert suite.tests[0].repeat_for is None
    assert suite.between_tests == []
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
    assert suite.tests[0].path.is_file()
    assert "fixtures" in str(suite.tests[0].path)


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


def test_load_between_tests(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "between_two_tests.toml")
    assert len(suite.between_tests) == 1
    assert suite.between_tests[0].name == "count_between.py"


def test_load_repeat_count_table(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "repeat_count.toml")
    assert len(suite.tests) == 1
    assert suite.tests[0].repeat_count == 3
    assert suite.tests[0].repeat_for is None


def test_load_repeat_for_table(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "repeat_for.toml")
    assert suite.tests[0].repeat_for == timedelta(seconds=1)


def test_load_repeat_for_table(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "repeat_for.toml")
    assert suite.tests[0].repeat_for == timedelta(seconds=1)


def test_load_rip_cord(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "setup_fail_rip_cord.toml")
    assert suite.rip_cord is True


def test_rip_cord_non_bool_raises(tmp_path, fixtures_dir) -> None:
    script = fixtures_dir / "scripts" / "pass_test.py"
    path = tmp_path / "bad_rip_cord.toml"
    path.write_text(
        f'name = "x"\nrip_cord = "yes"\ntests = ["{script.as_posix()}"]\n',
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="rip_cord.*boolean"):
        load_suite_toml(path)


def test_repeat_count_and_repeat_for_rejected(tmp_path, fixtures_dir) -> None:
    script = fixtures_dir / "scripts" / "pass_test.py"
    path = tmp_path / "both.toml"
    path.write_text(
        f'name = "x"\ntests = [{{ path = "{script.as_posix()}", repeat_count = 2, repeat_for = "1s" }}]\n',
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="cannot set both repeat_count and repeat_for"):
        load_suite_toml(path)


def test_repeat_count_zero_rejected(tmp_path, fixtures_dir) -> None:
    script = fixtures_dir / "scripts" / "pass_test.py"
    path = tmp_path / "zero.toml"
    path.write_text(
        f'name = "x"\ntests = [{{ path = "{script.as_posix()}", repeat_count = 0 }}]\n',
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="repeat_count must be >= 1"):
        load_suite_toml(path)


def test_invalid_repeat_for_duration(tmp_path, fixtures_dir) -> None:
    script = fixtures_dir / "scripts" / "pass_test.py"
    path = tmp_path / "bad_duration.toml"
    path.write_text(
        f'name = "x"\ntests = [{{ path = "{script.as_posix()}", repeat_for = "bad" }}]\n',
        encoding="utf-8",
    )
    with pytest.raises(SuiteError, match="Invalid repeat_for duration"):
        load_suite_toml(path)


@pytest.mark.parametrize(
    ("value", "expected_seconds"),
    [
        ("30s", 30),
        ("90m", 90 * 60),
        ("24h", 24 * 3600),
        ("1d", 86400),
        ("1d12h", 86400 + 12 * 3600),
    ],
)
def test_parse_repeat_duration(value: str, expected_seconds: int) -> None:
    assert parse_repeat_duration(value).total_seconds() == expected_seconds


def test_expand_test_schedule_count_mode(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "repeat_count.toml")
    schedule = expand_test_schedule(suite.tests)
    assert len(schedule) == 3
    assert [run.repeat_index for run in schedule] == [0, 1, 2]
    assert all(run.path.name == "count_repeat.py" for run in schedule)


def test_expand_test_schedule_rejects_duration_mode(fixtures_dir) -> None:
    suite = load_suite_toml(fixtures_dir / "suites" / "repeat_for.toml")
    with pytest.raises(SuiteError, match="does not support repeat_for"):
        expand_test_schedule(suite.tests)
