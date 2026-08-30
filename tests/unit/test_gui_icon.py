from __future__ import annotations

from pathlib import Path

from colosseum.gui._icon import _ASSETS, init_windows_taskbar


def test_gui_icon_assets_exist() -> None:
    assert (_ASSETS / "colosseum.ico").is_file()
    assert (_ASSETS / "colosseum-512.png").is_file()
    assert Path(__file__).resolve().parents[2] / "colosseum" / "gui" / "assets" == _ASSETS


def test_init_windows_taskbar_is_safe_off_windows(monkeypatch) -> None:
    monkeypatch.setattr("colosseum.gui._icon.sys.platform", "linux")
    init_windows_taskbar()
