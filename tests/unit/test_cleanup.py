from scripts.cleanup import _collect_paths


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("generated", encoding="utf-8")


def test_cleanup_removes_top_level_venv_by_default(tmp_path):
    _touch(tmp_path / ".venv" / "Lib" / "site-packages" / "native.pyd")
    _touch(tmp_path / ".venv" / "Lib" / "site-packages" / "module.pyc")

    targets = {
        path.relative_to(tmp_path).as_posix()
        for path in _collect_paths(tmp_path, keep_venvs=False)
    }

    assert ".venv" in targets
    assert ".venv/Lib/site-packages/native.pyd" not in targets
    assert ".venv/Lib/site-packages/module.pyc" not in targets


def test_cleanup_removes_named_venv_and_deps_by_default(tmp_path):
    _touch(tmp_path / ".venv-dev" / "Scripts" / "tool.exe")
    _touch(tmp_path / ".deps" / "colosseum-core" / "pyproject.toml")

    targets = {
        path.relative_to(tmp_path).as_posix()
        for path in _collect_paths(tmp_path, keep_venvs=False)
    }

    assert ".venv-dev" in targets
    assert ".deps" in targets
    assert ".deps/colosseum-core/pyproject.toml" not in targets


def test_cleanup_keep_venvs_only_scrubs_caches(tmp_path):
    _touch(tmp_path / ".venv" / "Lib" / "site-packages" / "native.pyd")
    _touch(tmp_path / ".venv" / "Lib" / "site-packages" / "module.pyc")

    targets = {
        path.relative_to(tmp_path).as_posix()
        for path in _collect_paths(tmp_path, keep_venvs=True)
    }

    assert ".venv" not in targets
    assert ".venv/Lib/site-packages/native.pyd" not in targets
    assert ".venv/Lib/site-packages/module.pyc" in targets


def test_cleanup_matches_share_ignore_policy(tmp_path):
    _touch(tmp_path / "share" / "notes.txt")
    _touch(tmp_path / "share" / "python-wheels" / "package.whl")

    targets = {
        path.relative_to(tmp_path).as_posix()
        for path in _collect_paths(tmp_path, keep_venvs=False)
    }

    assert "share" not in targets
    assert "share/notes.txt" not in targets
    assert "share/python-wheels" in targets


def test_cleanup_removes_offline_wheelhouse_and_pytest_cache(tmp_path):
    _touch(tmp_path / "wheelhouse" / "pkg.whl")
    _touch(tmp_path / ".pytest_cache" / "v" / "cache")
    (tmp_path / "pkg-offline-windows-py3.12.zip").write_bytes(b"zip")

    targets = {
        path.relative_to(tmp_path).as_posix()
        for path in _collect_paths(tmp_path, keep_venvs=False)
    }

    assert "wheelhouse" in targets
    assert ".pytest_cache" in targets
    assert "pkg-offline-windows-py3.12.zip" in targets
