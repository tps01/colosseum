# Search-and-replace checklist

Use this when forking `colosseum_template` into your own extension. Work top to
bottom.

| Find | Replace with | Where |
| --- | --- | --- |
| `colosseum_template` | `your_package` (...)` | Python pa... |
| `colosseum-template` | `your-distribution` (...)` | `pyprojec... |
| `template` | `yournamespace` (e.g. `acme`) | Entry-poi... |
| `colosseum.template` | `colosseum.yournamespace` | `get_logger(...)` |
| `template.device` | `yournamespace.device` | `ConfigSe... |
| `device_id` | `your_id` (e.g. `chamber_id`) | `ConfigSe... |
| `Colosseum Template Extension` | Your extension title | README |

## Files to edit

1. Rename directory `colosseum_template/` → `your_package/`
2. `pyproject.toml` - `name`, `description`, `dependencies`, entry points,
  `include` glob
3. `your_package/__init__.py` - `__colosseum_domain__`, namespace string,
  optional config section, logger
4. `your_package/api.py` - domain in `get_measurement(...)`, logger name,
  docstrings
5. `configs/config.template.toml` - rename file if desired; update
  `[yournamespace.device]` or `[[yournamespace.device]]` rows
6. `examples/smoke_test.py` - config path and API calls
7. This README and `RENAME.md` - update or remove template-specific paths

Each `ConfigSectionSpec` has exactly one dotted path, exactly one id field, and
any number of required/optional keys. If you drop Layer 2 (no config sections),
remove `register_config_section`, the TOML sample, and config lookups in the
API.

## Do not shadow built-in namespaces

Avoid registering: `equipment`, `shared`, `io`, `host`, `messaging`.
