# colosseum_template

Copy-ready stub for a **third-party Colosseum extension**. Fork this directory, follow [RENAME.md](RENAME.md), and implement your API under your own namespace (default demo: `template` → `col.template.*`).

Official guide (layered MVP → extras): [`docs/sphinx/source/guides/plugins.rst`](../../../docs/sphinx/source/guides/plugins.rst).

A plugin needs **three** things to work. Everything else is optional.

| Layer | What | Required? |
|-------|------|-----------|
| 0 | Entry point + `register_namespace` + API module | **Yes** |
| 1 | `@command` / `@measurement` / `@verification` | When you need evidence |
| 2 | `ConfigSectionSpec` + bench TOML | When you own config rows |
| 3 | Validators, shutdown, connection helpers | When you need them |

This template is a Layer 1–2 demo (evidence + one config section). For Layer 0 only, see first-party `colosseum-shared`.

---

## Part A — Extension author

### 1. Copy and rename

Copy `examples/plugins/colosseum_template/` elsewhere. Work through [RENAME.md](RENAME.md).

### 2. Layer 0 — wire discovery

**`pyproject.toml`:**

```toml
[project.entry-points."colosseum.plugins"]
template = "colosseum_template:register"
```

The entry-point **key** is metadata; the runtime namespace is the string passed to `register_namespace`.

**`colosseum_template/__init__.py`:**

```python
def register(registry):
    from colosseum_template import api
    registry.register_namespace("template", api)  # → col.template.*
```

`register_namespace` also sets the evidence domain to `"template"` unless the package already defines `__colosseum_domain__`.

Keep heavy imports inside `register()` so importing the package stays lightweight.

### 3. Layer 1 — implement the API (this template)

Edit `colosseum_template/api.py`:

- `@command` / `@measurement` / `@verification` from `colosseum.decorators`.
- Look up prior measurements with `get_context().db.get_measurement(...)` (domain matches namespace after rename).
- Log with `get_logger("colosseum.template")` so lines appear in `debug.log`.
- Scripts: one keyword-arg `col.*` call per line.

### 4. Layer 2 — bench config (this template)

This demo registers **one** `ConfigSectionSpec` and reads it from `arm_device`. Each spec is one table type:

| Field | This demo | Rule |
|-------|-----------|------|
| `dotted_path` | `template.device` | Exactly one per spec (the `[[table]]` header) |
| `id_field` | `device_id` | Exactly one per spec (integer, unique in that section) |
| `required_keys` | `serial` | Any number, including none |
| `optional_keys` | `label` | Any number, including none |

Call `register_config_section` again to own a second dotted path. Drop it entirely if your plugin has no TOML.

```python
registry.register_config_section(
    ConfigSectionSpec(
        dotted_path="template.device",
        id_field="device_id",
        required_keys=("serial",),
        optional_keys=("label",),
    )
)
```

```toml
[[template.device]]
device_id = 1
serial = "TEMPLATE-001"
# label = "optional field"
```

### 5. Layer 3 — optional extras

Add only when needed:

- `registry.register_config_validator(...)` — warning strings for a section.
- `registry.register_shutdown(...)` — release resources on `col.endex()`.
- Connection / cache helpers as ordinary module functions (see messaging/equipment).

### Logging

```python
from colosseum.logging import get_logger

_logger = get_logger("colosseum.template")
```

Rename to `colosseum.<yournamespace>` when forking. Names like `template` or `colosseum_template` never reach `debug.log`.

### 6. Install locally (editable)

```powershell
pip install -e .
```

Entry points require install metadata. You also need `colosseum-core` in the same environment.

### 7. Verify

```powershell
python examples/smoke_test.py
```

Or:

```powershell
colosseum run examples/smoke_test.py --config configs/bench.template.toml
```

### 8. Optional tests

This stub does not ship tests. Patterns: Colosseum `tests/unit/` (`unit_runtime_context`) and `tests/integration/test_plugin_registry_load.py`.

### 9. Publishing

Build with `python -m build`. Do not register a reserved or already-owned namespace (`equipment`, `shared`, `io`, `host`, `messaging`).

---

## Part B — End user: install and use on a bench

### 1. Prerequisites

- Python >= 3.9
- Core installed (`pip install colosseum-core`)
- Any optional dependencies declared by your extension

### 2. Install the extension

```powershell
pip install acme-bench==1.0.0
# or lab development:
pip install -e C:\path\to\acme_bench
```

Same Python environment as Colosseum and your test scripts.

### 3. Bench TOML

Add the extension's section(s) if it registers any. One `[[dotted.path]]` (or
`[dotted.path]`) per table type; each row needs that section's integer id field:

```toml
[[template.device]]
device_id = 1
serial = "LAB-DUT-001"
```

### 4. Use in test scripts

```python
import colosseum as col

col.config.load_config("bench.toml")
col.template.arm_device(device_id=1)
col.template.measure_widget_count(device_id=1, key="widgets")
col.template.verify_widget_count(key="widgets", expected_val=10.0, tolerance=0.0)
col.endex()
```

- **`col.endex()`** — flush logs/DB, write summaries, exit `0`/`1`.
- **Utility scripts** — `load_config(..., no_artifacts=True)` or CLI `--no-artifacts`.

### 5. Use via CLI

```powershell
colosseum run my_test.py --config bench.toml
```

### 6. Evidence

Normal runs create `debug.log`, `execution.sqlite`, `summary.txt`, and `summary.json` under `outputs/`. Use `--no-artifacts` when you do not need persisted evidence.

### 7. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `Namespace '…' is not registered` | Extension not installed in this env |
| `Failed to load plugin entry point` | Exception inside `register()` — see traceback |
| `Configuration is not loaded` | Call `col.config.load_config(path)` first |
| Missing required keys | Bench TOML row incomplete for your `ConfigSectionSpec` |
| `Config section … is already registered` | Two plugins claim the same section |
| `AttributeError` on `col.yournamespace` | Typo in namespace or registration |

---

## Layout

```
colosseum_template/
  pyproject.toml
  README.md
  RENAME.md
  configs/bench.template.toml
  examples/smoke_test.py
  colosseum_template/
    __init__.py       # register(registry)
    api.py            # col.template.*
```
