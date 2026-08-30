from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Any, Literal

from ._browser import (
    RunBrowserRow,
    RunBrowserSnapshot,
    RunSnapshot,
    format_summary_text,
    load_run_browser_snapshot,
    load_run_snapshot,
)
from ._icon import apply_window_icon, init_windows_taskbar
from .run_worker import RunFinished, RunKind, RunRequest, RunWorker

_STATUS_BUTTON_COLORS: dict[str, tuple[str, str]] = {
    "PASS": ("#1a7f37", "#3fb950"),
    "FAIL": ("#cf222e", "#f85149"),
    "ERROR": ("#cf222e", "#f85149"),
    "NO TEST": ("#8250df", "#a371f7"),
    "INVALID": ("#bc4c00", "#db6d28"),
}


def _normalize_status(status: str) -> str:
    key = status.strip().upper().replace("-", " ").replace("_", " ")
    if key in {"NO TEST", "NOTEST"}:
        return "NO TEST"
    if key in {"FAILED", "FAIL"}:
        return "FAIL"
    return key


def _pane_bg(root: Any, ctk: Any) -> str:  # noqa: ANN401
    try:
        return str(root._apply_appearance_mode(root.cget("fg_color")))
    except (AttributeError, tk.TclError, TypeError, ValueError):
        return "#2b2b2b" if str(ctk.get_appearance_mode()).lower() == "dark" else "#ebebeb"


def _make_paned(
    parent: Any,
    orient: Literal["horizontal", "vertical"],
    bg: str,
) -> tk.PanedWindow:
    return tk.PanedWindow(
        parent, orient=orient, sashwidth=6, sashrelief=tk.FLAT, sashpad=0,
        bd=0, relief=tk.FLAT, bg=bg, background=bg, borderwidth=0,
    )


def _set_initial_sashes(body: tk.PanedWindow, results: tk.PanedWindow) -> None:
    try:
        body.update_idletasks()
        body.sash_place(0, int(max(body.winfo_width(), 1) * 0.62), 1)
        results.sash_place(0, 1, int(max(results.winfo_height(), 1) * 0.45))
    except tk.TclError:
        pass


def ensure_display_available() -> None:
    if sys.platform == "win32":
        return
    if not os.environ.get("DISPLAY"):
        print(
            "Colosseum GUI requires a display. Set DISPLAY or use SSH X11 forwarding (ssh -X).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
    except tk.TclError as exc:
        print(f"Colosseum GUI cannot open a display: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _browse_file(title: str, filetypes: list[tuple[str, str]]) -> str:
    return filedialog.askopenfilename(title=title, filetypes=filetypes) or ""


class ColosseumApp:
    def __init__(self, ctk: Any) -> None:  # noqa: ANN401
        self._ctk = ctk
        self._root = ctk.CTk()
        self._root.title("Colosseum")
        apply_window_icon(self._root)
        self._root.geometry("1000x700")
        self._root.minsize(800, 500)
        self._cwd = Path.cwd()
        self._worker = RunWorker(cwd=self._cwd)
        self._ui_events: queue.Queue[Any] = queue.Queue()
        self._test_path = ctk.StringVar(value="")
        self._suite_path = ctk.StringVar(value="")
        self._config_path = ctk.StringVar(value=os.environ.get("COLOSSEUM_BENCH_CONFIG", ""))
        self._metadata_path = ctk.StringVar(value=os.environ.get("COLOSSEUM_METADATA_PATH", ""))
        self._debug = ctk.BooleanVar(value=False)
        self._status = ctk.StringVar(value="Ready")
        self._run_widgets: dict[tuple[str, Path], Any] = {}
        self._browser_snapshot = RunBrowserSnapshot(rows=[])
        self._browser_generation = 0
        self._detail_generation = 0
        self._expanded_output_dirs: set[Path] = set()
        self._selected_run_dir: Path | None = None
        self._build_layout()
        self._refresh_runs()
        self._root.after(200, self._poll_worker)

    def run(self) -> None:
        self._root.mainloop()

    def _build_layout(self) -> None:
        ctk, root = self._ctk, self._root
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        pane_bg = _pane_bg(root, ctk)

        form = ctk.CTkFrame(root)
        form.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        form.grid_columnconfigure(1, weight=1)
        rows = (
            ("Test (.py)", self._test_path, [("Python", "*.py")]),
            ("Suite (.toml)", self._suite_path, [("TOML", "*.toml")]),
            ("Config", self._config_path, [("TOML", "*.toml"), ("All", "*.*")]),
            ("Metadata", self._metadata_path, [("YAML", "*.yaml;*.yml"), ("All", "*.*")]),
        )
        for i, (label, var, fts) in enumerate(rows):
            ctk.CTkLabel(form, text=label).grid(row=i, column=0, padx=4, pady=2, sticky="w")
            ctk.CTkEntry(form, textvariable=var).grid(row=i, column=1, padx=4, pady=2, sticky="ew")
            ctk.CTkButton(
                form, text="Browse", width=80,
                command=lambda ft=fts, v=var: v.set(_browse_file("Select file", ft)),
            ).grid(row=i, column=2, padx=4)
        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=len(rows), column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ctk.CTkButton(actions, text="Run test", command=self._run_test).grid(row=0, column=0, padx=4)
        ctk.CTkButton(actions, text="Run suite", command=self._run_suite).grid(row=0, column=1, padx=4)
        self._stop_btn = ctk.CTkButton(actions, text="Stop", state="disabled", command=self._stop_run)
        self._stop_btn.grid(row=0, column=2, padx=4)
        ctk.CTkCheckBox(actions, text="Debug", variable=self._debug).grid(row=0, column=3, padx=8)

        body = _make_paned(root, tk.HORIZONTAL, pane_bg)
        body.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        log_frame = ctk.CTkFrame(body, width=620)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self._log_text = ctk.CTkTextbox(log_frame, state="disabled", wrap="none")
        self._log_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        results = _make_paned(body, tk.VERTICAL, pane_bg)
        runs_panel = ctk.CTkFrame(results, height=160)
        runs_panel.grid_rowconfigure(1, weight=1)
        runs_panel.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(runs_panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Runs").grid(row=0, column=0, sticky="w")
        ctrls = ctk.CTkFrame(header, fg_color="transparent")
        ctrls.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(ctrls, text="Refresh", width=70, command=self._refresh_runs).grid(row=0, column=0, padx=2)
        ctk.CTkButton(ctrls, text="Expand", width=70, command=self._expand_all_output_dirs).grid(row=0, column=1, padx=2)
        ctk.CTkButton(ctrls, text="Collapse", width=70, command=self._collapse_all_output_dirs).grid(row=0, column=2, padx=2)
        self._run_list = ctk.CTkScrollableFrame(runs_panel)
        self._run_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))

        detail = ctk.CTkFrame(results)
        detail.grid_rowconfigure(0, weight=1)
        detail.grid_columnconfigure(0, weight=1)
        tabs = ctk.CTkTabview(detail)
        tabs.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        tabs.add("Summary")
        self._summary_text = ctk.CTkTextbox(tabs.tab("Summary"), state="disabled")
        self._summary_text.pack(fill="both", expand=True)

        log_frame.grid_propagate(False)
        runs_panel.grid_propagate(False)
        detail.grid_propagate(False)
        body.add(log_frame, minsize=260, stretch="always")
        body.add(results, minsize=220, stretch="always")
        results.add(runs_panel, minsize=90, stretch="always")
        results.add(detail, minsize=120, stretch="always")
        self._root.after(100, lambda: _set_initial_sashes(body, results))

        ctk.CTkLabel(root, textvariable=self._status).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

    @staticmethod
    def _set_text(textbox: Any, text: str) -> None:  # noqa: ANN401
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        if text:
            textbox.insert("end", text)
            textbox.see("1.0")
        textbox.configure(state="disabled")

    def _config_value(self) -> str | None:
        v = self._config_path.get().strip()
        return v or None

    def _metadata_value(self) -> str | None:
        v = self._metadata_path.get().strip()
        return v or None

    def _run_test(self) -> None:
        p = self._test_path.get().strip()
        if not p:
            return
        path = Path(p).resolve()
        if path.is_file():
            self._start_run(RunRequest(RunKind.TEST, path, self._config_value(), self._metadata_value(), self._debug.get()))

    def _run_suite(self) -> None:
        p = self._suite_path.get().strip()
        if not p:
            return
        path = Path(p).resolve()
        if path.is_file():
            self._start_run(RunRequest(RunKind.SUITE, path, self._config_value(), self._metadata_value(), self._debug.get()))

    def _start_run(self, request: RunRequest) -> None:
        if self._worker.is_running():
            return
        self._selected_run_dir = None
        self._set_text(self._log_text, "")
        self._set_text(self._summary_text, "")
        self._stop_btn.configure(state="normal")
        try:
            self._worker.start(request)
        except RuntimeError:
            self._stop_btn.configure(state="disabled")

    def _stop_run(self) -> None:
        self._worker.stop()

    def _append_log(self, line: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", line + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _status_button_color(self, status: str) -> tuple[str, str] | str:
        return _STATUS_BUTTON_COLORS.get(_normalize_status(status), "gray40")

    def _outputs_dir_label(self, outputs_dir: Path) -> str:
        try:
            return str(outputs_dir.relative_to(self._cwd))
        except ValueError:
            return str(outputs_dir)

    def _run_list_label(self, row: RunBrowserRow) -> str:
        return f"{row.entry.path.name}  [{row.status}]"

    def _refresh_runs(self) -> None:
        self._browser_generation += 1
        gen = self._browser_generation
        threading.Thread(target=lambda: self._ui_events.put(("browser", gen, load_run_browser_snapshot(self._cwd))), daemon=True).start()

    def _expand_all_output_dirs(self) -> None:
        self._expanded_output_dirs = set(self._browser_snapshot.output_dirs)
        self._render_run_list()

    def _collapse_all_output_dirs(self) -> None:
        self._expanded_output_dirs.clear()
        self._render_run_list()

    def _toggle_outputs_dir(self, outputs_dir: Path) -> None:
        if outputs_dir in self._expanded_output_dirs:
            self._expanded_output_dirs.remove(outputs_dir)
        else:
            self._expanded_output_dirs.add(outputs_dir)
        self._render_run_list()

    def _render_run_list(self) -> None:
        for w in self._run_widgets.values():
            w.pack_forget()
        ctk, rows = self._ctk, self._browser_snapshot.rows
        grouped = len(self._browser_snapshot.output_dirs) > 1
        active: set[tuple[str, Path]] = set()
        if grouped:
            by_dir: dict[Path, list[RunBrowserRow]] = {}
            for row in rows:
                by_dir.setdefault(row.entry.outputs_dir, []).append(row)
            for outputs_dir in sorted(by_dir, key=lambda d: max(r.mtime for r in by_dir[d]), reverse=True):
                exp = outputs_dir in self._expanded_output_dirs
                key = ("outputs", outputs_dir)
                active.add(key)
                hdr = self._run_widgets.get(key) or ctk.CTkButton(
                    self._run_list, anchor="w", fg_color="transparent", hover_color=("gray85", "gray25"),
                    command=lambda od=outputs_dir: self._toggle_outputs_dir(od),
                )
                self._run_widgets[key] = hdr
                hdr.configure(text=f"{'[-]' if exp else '[+]'} {self._outputs_dir_label(outputs_dir)}")
                hdr.pack(fill="x", pady=(3, 1))
                if exp:
                    for row in by_dir[outputs_dir]:
                        active.add(("run", row.entry.path))
                        self._add_run_button(row, indent=True)
        else:
            for row in rows:
                active.add(("run", row.entry.path))
                self._add_run_button(row, indent=False)
        for key, w in list(self._run_widgets.items()):
            if key not in active:
                w.destroy()
                del self._run_widgets[key]

    def _add_run_button(self, row: RunBrowserRow, *, indent: bool) -> None:
        run_dir = row.entry.path
        key = ("run", run_dir)
        btn = self._run_widgets.get(key) or self._ctk.CTkButton(
            self._run_list, anchor="w", fg_color="transparent", hover_color=("gray85", "gray25"),
            command=lambda rd=run_dir: self._select_run(rd),
        )
        self._run_widgets[key] = btn
        btn.configure(text=self._run_list_label(row), text_color=self._status_button_color(row.status))
        btn.pack(fill="x", padx=(18, 0) if indent else 0, pady=1)

    def _select_run(self, run_dir: Path) -> None:
        self._selected_run_dir = run_dir
        self._detail_generation += 1
        gen = self._detail_generation
        self._set_text(self._log_text, f"Loading debug.log for {run_dir.name}...")
        self._set_text(self._summary_text, f"Loading summary for {run_dir.name}...")
        threading.Thread(
            target=lambda: self._ui_events.put(("run", gen, load_run_snapshot(run_dir))), daemon=True,
        ).start()

    def _apply_run_snapshot(self, snap: RunSnapshot) -> None:
        if self._selected_run_dir != snap.run_dir:
            return
        if snap.log_error:
            log = snap.log_error
        elif not snap.log_text:
            log = "debug.log is empty."
        else:
            log = snap.log_text if snap.log_text.endswith("\n") else snap.log_text + "\n"
        self._set_text(self._log_text, log)
        self._set_text(self._summary_text, format_summary_text(snap.summary))

    def _poll_worker(self) -> None:
        while True:
            try:
                kind, *payload = self._worker.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log" and self._selected_run_dir is None and self._worker.is_running():
                self._append_log(payload[0])
            elif kind == "started":
                self._selected_run_dir = None
                self._append_log(f"--- Run started: {payload[0]} ---")
                self._status.set(f"Running: {payload[0]}")
            elif kind == "error":
                self._append_log(f"ERROR: {payload[0]}")
                self._stop_btn.configure(state="disabled")
                self._status.set("Run failed to start")
            elif kind == "finished":
                finished: RunFinished = payload[0]
                self._append_log(f"--- Run finished (exit {finished.exit_code}) ---")
                self._stop_btn.configure(state="disabled")
                self._status.set(f"Last run: {finished.run_dir}" if finished.run_dir else f"Finished (exit {finished.exit_code})")
                self._refresh_runs()
        while True:
            try:
                kind, *payload = self._ui_events.get_nowait()
            except queue.Empty:
                break
            if kind == "browser" and payload[0] == self._browser_generation:
                self._browser_snapshot = payload[1]
                self._render_run_list()
            elif kind == "run" and payload[0] == self._detail_generation:
                self._apply_run_snapshot(payload[1])
        self._root.after(200, self._poll_worker)


def main() -> None:
    ensure_display_available()
    try:
        import customtkinter as ctk
    except ImportError as exc:
        print("Colosseum GUI requires customtkinter. Reinstall with: pip install --force-reinstall colosseum-core", file=sys.stderr)
        raise SystemExit(1) from exc
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    init_windows_taskbar()
    ColosseumApp(ctk).run()
