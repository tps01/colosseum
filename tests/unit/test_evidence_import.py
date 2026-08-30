"""Unit tests for importing prior-run evidence."""

from __future__ import annotations

from colosseum.context import init_context
from colosseum.database import CommandRow, MeasurementRow
from colosseum.database.evidence_import import import_evidence_from_previous


def test_import_evidence_from_previous(tmp_path, isolated_cwd) -> None:
    source_dir = tmp_path / "prior-pass"
    source_dir.mkdir()
    source_ctx = init_context(test_case_name="prior", no_artifacts=False)
    source_ctx.output_dir = source_dir
    source_ctx.runtime_ready = True
    source_ctx.db.initialize(source_dir / "execution.sqlite")
    source_ctx.db.insert_measurement(
        MeasurementRow(domain="core", command="measure_value", key="stored", value=4.2),
    )
    source_ctx.db.insert_command(
        CommandRow(domain="stub", command="ping", key="k1", result={"ok": True}),
    )
    source_ctx.db.close()

    target_ctx = init_context(test_case_name="rerun", no_artifacts=False)
    target_ctx.output_dir = isolated_cwd / "outputs" / "2026-01-01_120000_rerun"
    target_ctx.output_dir.mkdir(parents=True)
    target_ctx.db.initialize(target_ctx.output_dir / "execution.sqlite")
    target_ctx.runtime_ready = True

    import_evidence_from_previous(target_ctx, source_dir)

    row = target_ctx.db.get_measurement("core", "measure_value", "stored")
    assert row is not None
    assert row.value == 4.2
    commands = target_ctx.db.fetch_table_rows("commands")
    assert len(commands) == 1
    metadata = {item.key: item.value for item in target_ctx.db.fetch_run_metadata()}
    assert metadata["imported_from"] == str(source_dir)
