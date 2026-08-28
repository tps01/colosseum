from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Any, Literal

from .loaders import (
    DetailSnapshot,
    RunBrowserRow,
    RunBrowserSnapshot,
    load_detail_snapshot,
    load_run_browser_snapshot,
)
from .run_worker import RunFinished, RunKind, RunRequest, RunWorker

_CORE_DB_TABLES = (
    "measurements",
    "verifications",
    "commands",
    "events",
    "artifacts",
    "run_metadata",
)
_DB_CELL_MAX = 200

# Light/dark pairs for CTkButton ``text_color``.
_STATUS_BUTTON_COLORS: dict[str, tuple[str, str]] = {
    "PASS": ("#1a7f37", "#3fb950"),
    "FAIL": ("#cf222e", "#f85149"),
    "ERROR": ("#cf222e", "#f85149"),
    "NO TEST": ("#8250df", "#a371f7"),
    "INVALID": ("#bc4c00", "#db6d28"),
}

# Single foregrounds for CTkTextbox tags (readable on light and dark themes).
_STATUS_TAG_COLORS: dict[str, str] = {
    "PASS": "#2da44e",
    "FAIL": "#e5534b",
    "ERROR": "#e5534b",
    "NO TEST": "#8957e5",
    "INVALID": "#e16f24",
}


def _normalize_status(status: str) -> str:
    """Map stored status strings onto the GUI color vocabulary."""
    key = status.strip().upper().replace("-", " ").replace("_", " ")
    if key in {"NO TEST", "NOTEST"}:
        return "NO TEST"
    if key in {"FAILED", "FAIL"}:
        return "FAIL"
    return key


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
        import tkinter as tk
    except ImportError as exc:
        print(
            "Colosseum GUI requires tkinter (install the OS python3-tk package).",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    try:
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
    except tk.TclError as exc:
        print(f"Colosseum GUI cannot open a display: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> None:
    ensure_display_available()
    try:
        import customtkinter as ctk
    except ImportError as exc:
        print(
            "Colosseum GUI requires customtkinter, which should come with colosseum-core. "
            "Reinstall with: pip install --force-reinstall colosseum-core",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = ColosseumApp(ctk)
    app.run()


class ColosseumApp:
    def __init__(self, ctk: Any) -> None:  # noqa: ANN401
        self._ctk = ctk
        self._root = ctk.CTk()
        self._root.title("Colosseum")
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
        self._run_widgets: dict[tuple[str, Path], Any] = {}
        self._browser_snapshot = RunBrowserSnapshot(rows=[])
        self._browser_generation = 0
        self._detail_generation = 0
        self._expanded_output_dirs: set[Path] = set()
        self._selected_run_dir: Path | None = None
        self._db_table = ctk.StringVar(value=_CORE_DB_TABLES[0])

        self._build_layout()
        self._refresh_run_list()
        self._root.after(200, self._poll_worker)

    def run(self) -> None:
        self._root.mainloop()

    def _build_layout(self) -> None:
        ctk = self._ctk
        root = self._root

        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1)

        run_frame = ctk.CTkFrame(root)
        run_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        run_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(run_frame, text="Test (.py)").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        ctk.CTkEntry(run_frame, textvariable=self._test_path).grid(
            row=0, column=1, padx=4, pady=2, sticky="ew"
        )
        ctk.CTkButton(run_frame, text="Browse", width=80, command=self._browse_test).grid(
            row=0, column=2, padx=4
        )
        ctk.CTkButton(run_frame, text="Run test", width=90, command=self._run_test).grid(
            row=0, column=3, padx=4
        )

        ctk.CTkLabel(run_frame, text="Suite (.toml)").grid(
            row=1, column=0, padx=4, pady=2, sticky="w"
        )
        ctk.CTkEntry(run_frame, textvariable=self._suite_path).grid(
            row=1, column=1, padx=4, pady=2, sticky="ew"
        )
        ctk.CTkButton(run_frame, text="Browse", width=80, command=self._browse_suite).grid(
            row=1, column=2, padx=4
        )
        ctk.CTkButton(run_frame, text="Run suite", width=90, command=self._run_suite).grid(
            row=1, column=3, padx=4
        )

        ctk.CTkLabel(run_frame, text="Config").grid(row=2, column=0, padx=4, pady=2, sticky="w")
        ctk.CTkEntry(run_frame, textvariable=self._config_path).grid(
            row=2, column=1, padx=4, pady=2, sticky="ew"
        )
        ctk.CTkButton(run_frame, text="Browse", width=80, command=self._browse_config).grid(
            row=2, column=2, padx=4
        )
        ctk.CTkCheckBox(run_frame, text="Debug", variable=self._debug).grid(
            row=2, column=3, padx=4, sticky="w"
        )

        ctk.CTkLabel(run_frame, text="Metadata").grid(row=3, column=0, padx=4, pady=2, sticky="w")
        ctk.CTkEntry(run_frame, textvariable=self._metadata_path).grid(
            row=3, column=1, padx=4, pady=2, sticky="ew"
        )
        ctk.CTkButton(run_frame, text="Browse", width=80, command=self._browse_metadata).grid(
            row=3, column=2, padx=4
        )

        self._stop_btn = ctk.CTkButton(
            run_frame, text="Stop", width=90, state="disabled", command=self._stop_run
        )
        self._stop_btn.grid(row=3, column=3, padx=4, pady=4, sticky="e")

        # Horizontal sash: log | results (user-resizable).
        body = self._make_paned(root, tk.HORIZONTAL)
        body.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=8, pady=(0, 8))
        self._body_paned = body

        log_frame = ctk.CTkFrame(body, width=640)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        self._left_tabs = ctk.CTkTabview(log_frame)
        self._left_tabs.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._left_tabs.add("Log")
        self._left_tabs.add("Database")

        log_tab = self._left_tabs.tab("Log")
        log_tab.grid_rowconfigure(0, weight=1)
        log_tab.grid_columnconfigure(0, weight=1)
        self._log_text = ctk.CTkTextbox(log_tab, state="disabled", wrap="none")
        self._log_text.grid(row=0, column=0, sticky="nsew")

        db_tab = self._left_tabs.tab("Database")
        db_tab.grid_rowconfigure(1, weight=1)
        db_tab.grid_columnconfigure(0, weight=1)
        db_controls = ctk.CTkFrame(db_tab, fg_color="transparent")
        db_controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        db_controls.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(db_controls, text="Table").grid(row=0, column=0, padx=(0, 4), sticky="w")
        self._db_table_menu = ctk.CTkOptionMenu(
            db_controls,
            variable=self._db_table,
            values=list(_CORE_DB_TABLES),
            command=self._on_db_table_changed,
        )
        self._db_table_menu.grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(db_controls, text="Reload", width=80, command=self._reload_database).grid(
            row=0, column=2, padx=(4, 0)
        )
        self._db_text = ctk.CTkTextbox(db_tab, state="disabled", wrap="none")
        self._db_text.grid(row=1, column=0, sticky="nsew")
        self._configure_status_tags(self._db_text)
        self._db_text.configure(state="normal")
        self._db_text.insert("end", "Select a run to inspect execution.sqlite.")
        self._db_text.configure(state="disabled")

        # Vertical sash: run list | summary/verifications.
        results = self._make_paned(body, tk.VERTICAL)
        self._results_paned = results

        runs_frame = ctk.CTkFrame(results, height=140)
        runs_frame.grid_rowconfigure(1, weight=1)
        runs_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(runs_frame, text="Runs").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self._run_list = ctk.CTkScrollableFrame(runs_frame)
        self._run_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        run_controls = ctk.CTkFrame(runs_frame, fg_color="transparent")
        run_controls.grid(row=2, column=0, padx=4, pady=4, sticky="ew")
        for column in range(3):
            run_controls.grid_columnconfigure(column, weight=1)
        ctk.CTkButton(run_controls, text="Refresh", command=self._refresh_run_list).grid(
            row=0, column=0, padx=(0, 2), sticky="ew"
        )
        ctk.CTkButton(run_controls, text="Expand all", command=self._expand_all_output_dirs).grid(
            row=0, column=1, padx=2, sticky="ew"
        )
        ctk.CTkButton(
            run_controls,
            text="Collapse all",
            command=self._collapse_all_output_dirs,
        ).grid(
            row=0, column=2, padx=(2, 0), sticky="ew"
        )

        detail_frame = ctk.CTkFrame(results)
        detail_frame.grid_rowconfigure(0, weight=1)
        detail_frame.grid_columnconfigure(0, weight=1)
        self._tabview = ctk.CTkTabview(detail_frame)
        self._tabview.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._tabview.add("Summary")
        self._tabview.add("Verifications")
        self._summary_text = ctk.CTkTextbox(self._tabview.tab("Summary"), state="disabled")
        self._summary_text.pack(fill="both", expand=True)
        self._verify_text = ctk.CTkTextbox(self._tabview.tab("Verifications"), state="disabled")
        self._verify_text.pack(fill="both", expand=True)
        self._configure_status_tags(self._summary_text)
        self._configure_status_tags(self._verify_text)

        body.add(log_frame, minsize=240, stretch="always")
        body.add(results, minsize=220, stretch="always")
        results.add(runs_frame, minsize=100, stretch="always")
        results.add(detail_frame, minsize=160, stretch="always")
        log_frame.grid_propagate(False)
        runs_frame.grid_propagate(False)
        detail_frame.grid_propagate(False)
        # Prefer a wider log pane on first layout.
        self._root.after(100, lambda: self._set_initial_sashes(body, results))

    def _pane_chrome_color(self) -> str:
        """Match tk.PanedWindow chrome to the active CTk window background."""
        try:
            return str(self._root._apply_appearance_mode(self._root.cget("fg_color")))
        except (AttributeError, tk.TclError, TypeError, ValueError):
            mode = str(self._ctk.get_appearance_mode()).lower()
            return "#2b2b2b" if mode == "dark" else "#ebebeb"

    def _make_paned(
        self,
        parent: Any,  # noqa: ANN401
        orient: Literal["horizontal", "vertical"],
    ) -> tk.PanedWindow:
        bg = self._pane_chrome_color()
        return tk.PanedWindow(
            parent,
            orient=orient,
            sashwidth=6,
            sashrelief=tk.FLAT,
            sashpad=0,
            bd=0,
            relief=tk.FLAT,
            bg=bg,
            background=bg,
            opaqueresize=True,
            showhandle=False,
        )

    def _set_initial_sashes(self, body: tk.PanedWindow, results: tk.PanedWindow) -> None:
        try:
            self._root.update_idletasks()
            width = max(body.winfo_width(), 1)
            height = max(results.winfo_height(), 1)
            body.sash_place(0, int(width * 0.65), 1)
            results.sash_place(0, 1, int(height * 0.50))
        except tk.TclError:
            pass

    def _configure_status_tags(self, textbox: Any) -> None:  # noqa: ANN401
        for status, color in _STATUS_TAG_COLORS.items():
            textbox.tag_config(f"status_{status}", foreground=color)

    @staticmethod
    def _status_button_color(status: str) -> tuple[str, str] | str:
        normalized = _normalize_status(status)
        return _STATUS_BUTTON_COLORS.get(normalized, ("gray10", "gray90"))

    def _insert_status_token(self, textbox: Any, status: str) -> None:  # noqa: ANN401
        normalized = _normalize_status(status)
        tag = f"status_{normalized}" if normalized in _STATUS_TAG_COLORS else None
        textbox.insert("end", status, tag)

    def _browse_test(self) -> None:
        path = filedialog.askopenfilename(
            title="Select test script",
            filetypes=[("Python", "*.py"), ("All files", "*.*")],
        )
        if path:
            self._test_path.set(path)

    def _browse_suite(self) -> None:
        path = filedialog.askopenfilename(
            title="Select suite TOML",
            filetypes=[("TOML", "*.toml"), ("All files", "*.*")],
        )
        if path:
            self._suite_path.set(path)

    def _browse_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Select bench config",
            filetypes=[("TOML", "*.toml"), ("All files", "*.*")],
        )
        if path:
            self._config_path.set(path)

    def _browse_metadata(self) -> None:
        path = filedialog.askopenfilename(
            title="Select metadata YAML",
            filetypes=[("YAML", "*.yaml;*.yml"), ("All files", "*.*")],
        )
        if path:
            self._metadata_path.set(path)

    def _config_value(self) -> str | None:
        value = self._config_path.get().strip()
        return value or None

    def _metadata_value(self) -> str | None:
        value = self._metadata_path.get().strip()
        return value or None

    def _run_test(self) -> None:
        path_str = self._test_path.get().strip()
        if not path_str:
            return
        path = Path(path_str).resolve()
        if not path.is_file():
            return
        self._start_run(
            RunRequest(
                RunKind.TEST,
                path,
                self._config_value(),
                self._metadata_value(),
                self._debug.get(),
            )
        )

    def _run_suite(self) -> None:
        path_str = self._suite_path.get().strip()
        if not path_str:
            return
        path = Path(path_str).resolve()
        if not path.is_file():
            return
        self._start_run(
            RunRequest(
                RunKind.SUITE,
                path,
                self._config_value(),
                self._metadata_value(),
                self._debug.get(),
            )
        )

    def _start_run(self, request: RunRequest) -> None:
        if self._worker.is_running():
            return
        self._clear_log()
        self._stop_btn.configure(state="normal")
        try:
            self._worker.start(request)
        except RuntimeError:
            self._stop_btn.configure(state="disabled")

    def _stop_run(self) -> None:
        self._worker.stop()

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _append_log(self, line: str) -> None:
        self._append_log_lines([line])

    def _append_log_lines(self, lines: list[str]) -> None:
        if not lines:
            return
        self._log_text.configure(state="normal")
        self._log_text.insert("end", "\n".join(lines) + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _poll_worker(self) -> None:
        log_lines: list[str] = []
        while True:
            try:
                event = self._worker.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "log":
                log_lines.append(event[1])
            elif kind == "started":
                self._append_log_lines(log_lines)
                log_lines = []
                self._append_log(f"--- Run started: {event[1]} ---")
            elif kind == "error":
                self._append_log_lines(log_lines)
                log_lines = []
                self._append_log(f"ERROR: {event[1]}")
                self._stop_btn.configure(state="disabled")
            elif kind == "finished":
                self._append_log_lines(log_lines)
                log_lines = []
                finished: RunFinished = event[1]
                self._append_log(f"--- Run finished (exit {finished.exit_code}) ---")
                self._stop_btn.configure(state="disabled")
                if finished.run_dir is not None:
                    self._expanded_output_dirs.add(finished.run_dir.parent)
                self._refresh_run_list()
                if finished.run_dir is not None:
                    self._select_run(finished.run_dir, load_log=False)
        self._append_log_lines(log_lines)

        while True:
            try:
                event = self._ui_events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "browser_snapshot":
                generation: int = event[1]
                browser_snapshot: RunBrowserSnapshot = event[2]
                if generation == self._browser_generation:
                    self._browser_snapshot = browser_snapshot
                    self._render_run_list()
            elif kind == "detail_snapshot":
                generation = event[1]
                detail_snapshot: DetailSnapshot = event[2]
                load_log: bool = event[3]
                if generation == self._detail_generation:
                    self._apply_detail_snapshot(detail_snapshot, load_log=load_log)

        self._root.after(200, self._poll_worker)

    def _outputs_dir_label(self, outputs_dir: Path) -> str:
        try:
            relative = outputs_dir.relative_to(self._cwd)
        except ValueError:
            return str(outputs_dir)
        return str(relative)

    def _run_list_label(self, row: RunBrowserRow, *, include_prefix: bool) -> str:
        run_dir = row.entry.path
        if include_prefix:
            prefix = self._outputs_dir_label(row.entry.outputs_dir)
            return f"{prefix} > {run_dir.name}  [{row.status}]"
        return f"{run_dir.name}  [{row.status}]"

    def _toggle_outputs_dir(self, outputs_dir: Path) -> None:
        if outputs_dir in self._expanded_output_dirs:
            self._expanded_output_dirs.remove(outputs_dir)
        else:
            self._expanded_output_dirs.add(outputs_dir)
        self._render_run_list()

    def _expand_all_output_dirs(self) -> None:
        self._expanded_output_dirs = set(self._browser_snapshot.output_dirs)
        self._render_run_list()

    def _collapse_all_output_dirs(self) -> None:
        self._expanded_output_dirs.clear()
        self._render_run_list()

    def _refresh_run_list(self) -> None:
        self._browser_generation += 1
        generation = self._browser_generation
        thread = threading.Thread(
            target=self._load_run_browser_snapshot,
            args=(generation,),
            daemon=True,
        )
        thread.start()

    def _load_run_browser_snapshot(self, generation: int) -> None:
        snapshot = load_run_browser_snapshot(self._cwd)
        self._ui_events.put(("browser_snapshot", generation, snapshot))

    def _render_run_list(self) -> None:
        for widget in self._run_widgets.values():
            widget.pack_forget()

        ctk = self._ctk
        rows = self._browser_snapshot.rows
        outputs_dirs = self._browser_snapshot.output_dirs
        grouped = len(outputs_dirs) > 1
        active_keys: set[tuple[str, Path]] = set()

        if grouped:
            rows_by_outputs: dict[Path, list[RunBrowserRow]] = {}
            for row in rows:
                rows_by_outputs.setdefault(row.entry.outputs_dir, []).append(row)
            ordered_outputs = sorted(
                rows_by_outputs,
                key=lambda outputs_dir: max(
                    row.mtime for row in rows_by_outputs[outputs_dir]
                ),
                reverse=True,
            )
            for outputs_dir in ordered_outputs:
                expanded = outputs_dir in self._expanded_output_dirs
                marker = "[-]" if expanded else "[+]"
                key = ("outputs", outputs_dir)
                active_keys.add(key)
                header = self._run_widgets.get(key)
                if header is None:
                    header = ctk.CTkButton(
                        self._run_list,
                        anchor="w",
                        fg_color="transparent",
                        text_color=("gray10", "gray90"),
                        hover_color=("gray85", "gray25"),
                        command=lambda od=outputs_dir: self._toggle_outputs_dir(od),
                    )
                    self._run_widgets[key] = header
                header.configure(text=f"{marker} {self._outputs_dir_label(outputs_dir)}")
                header.pack(fill="x", pady=(3, 1))
                if not expanded:
                    continue
                for row in rows_by_outputs[outputs_dir]:
                    active_keys.add(("run", row.entry.path))
                    self._add_run_button(row, include_prefix=False, indent=True)
        else:
            for row in rows:
                active_keys.add(("run", row.entry.path))
                self._add_run_button(row, include_prefix=False, indent=False)

        for key, widget in list(self._run_widgets.items()):
            if key not in active_keys:
                widget.destroy()
                del self._run_widgets[key]

    def _add_run_button(
        self,
        row: RunBrowserRow,
        *,
        include_prefix: bool,
        indent: bool,
    ) -> None:
        ctk = self._ctk
        run_dir = row.entry.path
        key = ("run", run_dir)
        btn = self._run_widgets.get(key)
        if btn is None:
            btn = ctk.CTkButton(
                self._run_list,
                anchor="w",
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda rd=run_dir: self._select_run(rd),
            )
            self._run_widgets[key] = btn
        btn.configure(
            text=self._run_list_label(row, include_prefix=include_prefix),
            text_color=self._status_button_color(row.status),
        )
        if indent:
            btn.pack(fill="x", padx=(18, 0), pady=1)
        else:
            btn.pack(fill="x", pady=1)

    def _select_run(self, run_dir: Path, *, load_log: bool = True) -> None:
        self._selected_run_dir = run_dir
        self._detail_generation += 1
        generation = self._detail_generation
        table = self._db_table.get().strip() or _CORE_DB_TABLES[0]
        self._show_detail_loading(run_dir, load_log=load_log)
        thread = threading.Thread(
            target=self._load_detail_snapshot,
            args=(generation, run_dir, table, load_log),
            daemon=True,
        )
        thread.start()

    def _load_detail_snapshot(
        self,
        generation: int,
        run_dir: Path,
        table: str,
        load_log: bool,
    ) -> None:
        snapshot = load_detail_snapshot(run_dir, table=table, include_log=load_log)
        self._ui_events.put(("detail_snapshot", generation, snapshot, load_log))

    def _show_detail_loading(self, run_dir: Path, *, load_log: bool) -> None:
        if load_log:
            self._replace_text(self._log_text, f"Loading debug.log for {run_dir.name}...")
        self._replace_text(
            self._db_text,
            f"Loading {self._db_table.get().strip() or _CORE_DB_TABLES[0]} from {run_dir.name}...",
        )
        self._replace_text(self._summary_text, f"Loading summary for {run_dir.name}...")
        self._replace_text(self._verify_text, f"Loading verifications for {run_dir.name}...")

    def _apply_detail_snapshot(self, snapshot: DetailSnapshot, *, load_log: bool) -> None:
        if self._selected_run_dir != snapshot.run_dir:
            return
        if load_log:
            self._show_log_snapshot(snapshot)
        self._show_database_snapshot(snapshot)
        self._show_summary_snapshot(snapshot)
        self._show_verifications_snapshot(snapshot)

    def _on_db_table_changed(self, _choice: str) -> None:
        self._reload_database()

    def _reload_database(self) -> None:
        if self._selected_run_dir is not None:
            self._select_run(self._selected_run_dir, load_log=False)

    def _replace_text(self, textbox: Any, text: str) -> None:  # noqa: ANN401
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("end", text)
        textbox.configure(state="disabled")

    @staticmethod
    def _format_db_cell(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        text = text.replace("\n", "\\n")
        if len(text) > _DB_CELL_MAX:
            return text[: _DB_CELL_MAX - 3] + "..."
        return text

    def _show_database_snapshot(self, snapshot: DetailSnapshot) -> None:
        run_dir = snapshot.run_dir
        table = snapshot.table
        self._db_text.configure(state="normal")
        self._db_text.delete("1.0", "end")
        if snapshot.table_error is not None:
            self._db_text.insert("end", snapshot.table_error)
            self._db_text.configure(state="disabled")
            return
        rows = snapshot.table_rows or []

        noun = "row" if len(rows) == 1 else "rows"
        self._db_text.insert("end", f"{run_dir.name} / {table}  ({len(rows)} {noun})\n")
        if not rows:
            self._db_text.insert("end", "(empty)\n")
            self._db_text.configure(state="disabled")
            return

        columns = list(rows[0].keys())
        self._db_text.insert("end", " | ".join(columns) + "\n")
        self._db_text.insert("end", "-+-".join("-" * max(len(c), 3) for c in columns) + "\n")
        for row in rows:
            for index, col in enumerate(columns):
                if index:
                    self._db_text.insert("end", " | ")
                cell = self._format_db_cell(row.get(col))
                if col == "status" and _normalize_status(cell) in _STATUS_TAG_COLORS:
                    self._insert_status_token(self._db_text, cell)
                else:
                    self._db_text.insert("end", cell)
            self._db_text.insert("end", "\n")
        self._db_text.see("1.0")
        self._db_text.configure(state="disabled")

    def _show_log_snapshot(self, snapshot: DetailSnapshot) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        if snapshot.log_error is not None:
            self._log_text.insert("end", snapshot.log_error)
        elif snapshot.log_text:
            self._log_text.insert("end", snapshot.log_text)
            if not snapshot.log_text.endswith("\n"):
                self._log_text.insert("end", "\n")
            self._log_text.see("1.0")
        else:
            self._log_text.insert("end", "debug.log is empty.")
        self._log_text.configure(state="disabled")

    def _show_summary_snapshot(self, snapshot: DetailSnapshot) -> None:
        summary = snapshot.summary
        self._summary_text.configure(state="normal")
        self._summary_text.delete("1.0", "end")
        if summary is None:
            self._summary_text.insert("end", "No summary.json (run incomplete or in progress).")
        else:
            overall = str(summary.get("overall_result", "?"))
            self._summary_text.insert("end", "Overall: ")
            self._insert_status_token(self._summary_text, overall)
            self._summary_text.insert("end", f" (exit {summary.get('exit_code')})\n")
            lines = [
                f"Test case: {summary.get('test_case')}",
                f"Suite: {summary.get('suite')}",
                f"Config: {summary.get('config_path')}",
                f"Output: {summary.get('output_directory')}",
                f"End time: {summary.get('end_time_utc')}",
                f"Measurements: {summary.get('measurement_count')}",
                (
                    "Verifications (required): "
                    f"{summary.get('verification_counts', {}).get('required', {})}"
                ),
                (
                    "Verifications (optional): "
                    f"{summary.get('verification_counts', {}).get('optional', {})}"
                ),
            ]
            self._summary_text.insert("end", "\n".join(lines))
            failed = summary.get("failed_required_verifications") or []
            if failed:
                self._summary_text.insert("end", "\n\nFailed required verifications:\n")
                for row in failed:
                    domain = row.get("domain")
                    command = row.get("command")
                    key = row.get("key")
                    message = row.get("message")
                    status = str(row.get("status") or "FAIL")
                    self._summary_text.insert("end", "  - ")
                    self._insert_status_token(self._summary_text, status)
                    self._summary_text.insert(
                        "end", f" {domain}.{command} key={key}: {message}\n"
                    )
        self._summary_text.configure(state="disabled")

    def _show_verifications_snapshot(self, snapshot: DetailSnapshot) -> None:
        self._verify_text.configure(state="normal")
        self._verify_text.delete("1.0", "end")
        if snapshot.verifications_error is not None:
            self._verify_text.insert("end", snapshot.verifications_error)
            self._verify_text.configure(state="disabled")
            return
        rows = snapshot.verifications or []

        if not rows:
            self._verify_text.insert("end", "No verifications recorded.")
        else:
            for row in rows:
                opt = "optional" if row.optional else "required"
                prefix = "FAIL" if row.status == "FAIL" and not row.optional else row.status
                self._verify_text.insert("end", "[")
                self._insert_status_token(self._verify_text, str(prefix))
                line = f"] {row.domain}.{row.command} key={row.key} ({opt})"
                if row.message:
                    line += f": {row.message}"
                self._verify_text.insert("end", line + "\n")
        self._verify_text.configure(state="disabled")
