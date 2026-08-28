Configuration
=============

Core reads one bench TOML file. Installed plugins declare the sections they own.
Core itself does not define instrument or device keys.

Section contract
----------------

Each registered section is one ``ConfigSectionSpec``:

* exactly one dotted path (the TOML table, for example ``acme.device``)
* exactly one integer ID field (the row identity, for example ``device_id``)
* any number of required keys (including none)
* any number of optional keys (including none)

A plugin that owns several table types registers several specs — one
``register_config_section`` call per dotted path. The same file can mix sections
from many plugins.

TOML shape
----------

Write either a single table (one row) or an array of tables (several rows).
Do not mix both for the same dotted path. Both forms become the same ID-indexed
map at runtime.

Single row::

   [acme.device]
   device_id = 1
   serial = "DUT-001"

Several rows::

   [[acme.device]]
   device_id = 1
   serial = "DUT-001"

   [[acme.device]]
   device_id = 2
   serial = "DUT-002"

The dotted path is the table header. The ID field must be an integer and unique
within that section. Missing IDs, non-integer IDs, and duplicate IDs fail the
load. Missing required keys fail when a plugin loads that row. Unknown keys
produce warnings and are ignored at runtime.

Load configuration before calling plugin APIs::

   import colosseum as col

   col.config.load_config("bench.toml")

or ``colosseum run my_test.py --config bench.toml``. That discovers plugins,
normalizes registered sections, then attaches a config store to the run.

Reading rows
------------

* ``col.config.get("acme.device")`` — raw nested table or list (or ``None``).
* ``store.list_items("acme.device")`` — normalized rows, sorted by ID.
* ``store.get_item("acme.device", 1)`` / ``store.require_item(...)`` — one row
  by ID. ``require_item`` also checks required keys.

Unregistered tables stay in the raw store (``col.config.get("runtime.label")``)
but are not ID-indexed.

Plain string tokens may omit quotes when they contain only supported path/token
characters. Standard TOML quoting remains recommended for portable configuration.

Suite TOML (``colosseum run-suite``) lists scripts. It is not a plugin section
file; pass bench config separately with ``--config``.

Core WATS metadata (``[colosseum.metadata]``)
----------------------------------------------

Core owns a flat singleton table for WATS report identity fields. It is **not**
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
``colosseum run my_test.py --metadata metadata.yaml``. YAML overrides the TOML
table. Finalize writes ``wats_<datetime>_<script>.json`` beside
``summary.json`` (see :doc:`output_artifacts`). Without metadata, the WATS report
is still written using runtime defaults (hostname, OS user, empty identity fields).

Optional keys (never required) may enrich the report when set in YAML:
``process_name``, ``report_text``, ``seq_version``, ``batch_serial``,
``fixture_id``, ``comment``, ``misc_infos``, and ``sub_units``. Existing
metadata files without these keys continue to work unchanged.

The generated :doc:`bench_config_reference` lists sections provided by the plugins
installed in the documentation build environment. A core-only build therefore contains
no plugin sections.
