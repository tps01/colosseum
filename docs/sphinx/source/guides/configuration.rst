Configuration
=============

Core reads one TOML config file. Installed plugins declare the sections they own.
Core itself does not define instrument or device keys.

The :doc:`writing_test_scripts` walkthrough uses a ``[template.device]`` table from the
``colosseum_template`` plugin. The rules below apply to any plugin section.

Configuration sections
----------------------

Each registered section is one ``ConfigSectionSpec``:

* exactly one dotted path (the TOML table, for example ``template.device``)
* exactly one integer ID field (the row identity, for example ``device_id``)
* any number of required keys (including none)
* any number of optional keys (including none)

A plugin that owns several table types registers several specs, one
``register_config_section`` call per dotted path. The same file can mix sections
from many plugins.

TOML shape
----------

Write either a single table (one row) or an array of tables (several rows).
Do not mix both for the same dotted path. Both forms become the same ID-indexed
map at runtime.

Single row::

   [template.device]
   device_id = 1
   serial = "TEMPLATE-001"

Several rows::

   [[template.device]]
   device_id = 1
   serial = "TEMPLATE-001"

   [[template.device]]
   device_id = 2
   serial = "TEMPLATE-002"

The dotted path is the table header. The ID field must be an integer and unique
within that section. Missing IDs, non-integer IDs, and duplicate IDs fail the
load. Missing required keys fail when a plugin loads that row. Unknown keys
produce warnings and are ignored at runtime.

Load configuration before calling plugin APIs::

   import colosseum as col

   col.config.load_config("config.toml")

or ``colosseum run my_test.py -g config.toml`` (``-g`` is the legacy short form of
``--config``). That discovers plugins, normalizes registered sections, then attaches a
config store to the run.

Reading rows
------------

* ``col.config.get("template.device")``: raw nested table or list (or ``None``).
* ``store.list_items("template.device")``: normalized rows, sorted by ID.
* ``store.get_item("template.device", 1)`` / ``store.require_item(...)``: one row
  by ID. ``require_item`` also checks required keys.

Unregistered tables stay in the raw store (``col.config.get("runtime.label")``)
but are not ID-indexed.

Plain string tokens may omit quotes when they contain only supported path/token
characters. Standard TOML quoting remains recommended for portable configuration.

Suite TOML (``colosseum run-suite``) lists scripts. It is not a plugin section
file; pass config separately with ``--config``.

Run metadata (``[colosseum.metadata]``)
---------------------------------------

Core owns a flat singleton table for test-report identity fields. It is **not**
a plugin ``ConfigSectionSpec`` (no integer ID field). Unknown keys produce
warnings.

::

   [colosseum.metadata]
   location = "TBD_PHYSICAL_LOCATION"
   process_code = "1234"
   revision = "1.2.3"
   serial_number = "123"
   test_intent = "Acceptance"
   user_name = "USERNAME"
   uut = "PARTNUMBER"
   # wats_folder = "D:/wats/inbox"   # optional copy destination

The same keys may appear in a metadata YAML file (``test_metadata:`` block).
Load YAML with ``col.config.load_metadata("metadata.yaml")`` or
``colosseum run my_test.py -m metadata.yaml`` (``-m`` is the short form of
``--metadata``).

Metadata precedence
~~~~~~~~~~~~~~~~~~~

1. Values from ``[colosseum.metadata]`` in config TOML (if present).
2. YAML ``test_metadata`` overrides TOML when both are loaded.
3. Runtime defaults (hostname, OS user, empty identity fields) fill any remaining gaps.

Finalize writes ``wats_<datetime>_<script>.json`` beside ``summary.json`` (see
:doc:`output_artifacts`). That file uses the WATS WSJF JSON format. Without
metadata, Colosseum still writes the report using runtime defaults.

Optional keys (never required) may enrich the report when set in YAML:
``process_name``, ``report_text``, ``seq_version``, ``batch_serial``,
``fixture_id``, ``comment``, ``misc_infos``, and ``sub_units``. Existing
metadata files without these keys continue to work unchanged.

Plugin-owned config sections are documented by each plugin (README or project docs).
