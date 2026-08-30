from __future__ import annotations

import queue
import time

from colosseum.gui.run_worker import RunFinished, RunKind, RunRequest, RunWorker


def test_run_worker_streams_stdout_before_process_finishes(
    isolated_cwd,
    monkeypatch,
    repo_root,
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(repo_root))
    script = isolated_cwd / "live_stdout.py"
    script.write_text(
        "\n".join(
            [
                "import time",
                "",
                "def main():",
                "    print('live stdout marker', flush=True)",
                "    time.sleep(1.0)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    worker = RunWorker(cwd=isolated_cwd)
    worker.start(RunRequest(RunKind.TEST, script, config_path=None, metadata_path=None, debug=False))

    saw_live_line_while_running = False
    finished: RunFinished | None = None
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        try:
            event = worker.events.get(timeout=0.2)
        except queue.Empty:
            continue
        if event[0] == "log" and "live stdout marker" in event[1] and worker.is_running():
            saw_live_line_while_running = True
        if event[0] == "finished":
            finished = event[1]
            break

    assert saw_live_line_while_running
    assert finished is not None
    assert finished.exit_code == 0
    assert finished.run_dir is not None
    assert finished.run_dir.name.endswith("-pass")
