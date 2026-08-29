from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

from ..output.runs import find_run_directory
from ..runner.suite import load_suite_toml


class RunKind(Enum):
    TEST = auto()
    SUITE = auto()


@dataclass
class RunRequest:
    kind: RunKind
    path: Path
    config_path: str | None
    metadata_path: str | None
    debug: bool


@dataclass
class RunFinished:
    run_dir: Path | None
    exit_code: int


class RunWorker:
    """Background subprocess runner with debug.log tailing."""

    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = cwd or Path.cwd()
        self._queue: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._stop_requested = False

    @property
    def events(self) -> queue.Queue[Any]:
        return self._queue

    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def stop(self) -> None:
        self._stop_requested = True
        proc = self._process
        if proc is None or proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def start(self, request: RunRequest) -> None:
        if self.is_running():
            raise RuntimeError("A run is already in progress")
        self._stop_requested = False
        self._thread = threading.Thread(target=self._run, args=(request,), daemon=True)
        self._thread.start()

    def _logical_name(self, request: RunRequest) -> str:
        if request.kind == RunKind.TEST:
            return request.path.stem
        suite = load_suite_toml(request.path)
        return suite.name

    def _build_argv(self, request: RunRequest) -> list[str]:
        argv = [sys.executable, "-u", "-m", "colosseum.runner.cli"]
        if request.kind == RunKind.TEST:
            argv.extend(["run", str(request.path)])
        else:
            argv.extend(["run-suite", str(request.path)])
        if request.config_path:
            argv.extend(["--config", request.config_path])
        if request.metadata_path:
            argv.extend(["--metadata", request.metadata_path])
        if request.debug:
            argv.append("--debug")
        return argv

    def _stream_stdout(self, pipe: Any) -> None:  # noqa: ANN401
        try:
            for line in iter(pipe.readline, ""):
                self._queue.put(("log", line.rstrip("\r\n")))
        finally:
            pipe.close()

    def _run(self, request: RunRequest) -> None:
        logical_name = self._logical_name(request)
        start_time = time.time()
        argv = self._build_argv(request)
        self._queue.put(("started", logical_name))

        try:
            self._process = subprocess.Popen(
                argv,
                cwd=str(self._cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as exc:
            self._queue.put(("error", str(exc)))
            self._process = None
            return

        run_dir: Path | None = None
        proc = self._process
        stdout_thread: threading.Thread | None = None
        if proc.stdout is not None:
            stdout_thread = threading.Thread(
                target=self._stream_stdout,
                args=(proc.stdout,),
                daemon=True,
            )
            stdout_thread.start()

        while proc.poll() is None or (run_dir is None and not self._stop_requested):
            if run_dir is None:
                run_dir = find_run_directory(self._cwd, logical_name, since=start_time - 1.0)
                if run_dir is None:
                    run_dir = find_run_directory(self._cwd, logical_name, since=None)

            if proc.poll() is not None:
                break
            time.sleep(0.3)

        exit_code = proc.wait()
        if stdout_thread is not None:
            stdout_thread.join(timeout=2.0)

        final_run_dir = find_run_directory(self._cwd, logical_name, since=start_time - 1.0)
        if final_run_dir is None:
            final_run_dir = find_run_directory(self._cwd, logical_name, since=None)

        self._queue.put(("finished", RunFinished(run_dir=final_run_dir, exit_code=exit_code)))
        self._process = None
