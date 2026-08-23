# Search-and-replace checklist

Use this when forking `colosseum_template` into your own extension. Work top to bottom.

| Find | Replace with | Where |
|------|--------------|-------|
| `colosseum_template` | `your_package` (e.g. `acme_bench`) | Python package directory, imports |
| `colosseum-template` | `your-distribution` (e.g. `acme-bench`) | `pyproject.toml` `[project].name` |
| `template` | `yournamespace` (e.g. `acme`) | Entry-point keys, `register_namespace`, `__colosseum_domain__`, config section prefix, `get_measurement` domain |
| `colosseum.template` | `colosseum.yournamespace` | `get_logger(...)` in `api.py`, `__init__.py` |
| `template.device` | `yournamespace.device` | `ConfigSectionSpec`, bench TOML |
| `Colosseum Template Extension` | Your extension title | README |

## Files to edit

1. Rename directory `colosseum_template/` → `your_package/`
2. `pyproject.toml` — `name`, `description`, `dependencies`, entry points, `include` glob
3. `your_package/__init__.py` — `__colosseum_domain__`, namespace string, optional config section, logger
4. `your_package/api.py` — domain in `get_measurement(...)`, logger name, docstrings
5. `configs/bench.template.toml` — rename file if desired; update `[[yournamespace.device]]`
6. `examples/smoke_test.py` — config path and API calls
7. This README and `RENAME.md` — update or remove template-specific paths

If you drop Layer 2 (no bench config), remove `register_config_section`, the TOML sample, and config lookups in the API.

## Do not shadow built-in namespaces

Avoid registering: `equipment`, `shared`, `io`, `host`, `messaging`.
