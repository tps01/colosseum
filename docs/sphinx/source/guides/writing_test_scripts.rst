Writing test scripts
====================

Colosseum test cases are ordinary Python scripts. Installed plugins expose APIs
as ``col.<namespace>.*``. This chapter walks through a complete script with matching
config TOML and metadata YAML. Install ``colosseum-core`` and ``colosseum-template`` first
(see :doc:`installation`).

Recommended project layout
--------------------------

Organize files so suite paths stay relative to the suite file::

   my_project/
     config/
       config.toml
       metadata.yaml
     scripts/
       my_test.py
     suites/
       smoke.toml

Suite script paths are relative to the suite TOML file (for example
``../scripts/my_test.py``). Config and metadata paths are passed on the CLI or
loaded from your script.

Script anatomy
--------------

Every test script follows the same shape:

1. ``import colosseum as col``
2. Load config (and optional metadata) before calling plugin APIs when running
   with ``python my_test.py``. The CLI loads ``--config`` and ``--metadata`` for you.
3. Call plugin APIs in ``main()`` (one ``col.*`` call per line, keyword arguments inline).
   Decorated APIs use keyword arguments so scripts stay readable to people less
   familiar with Python: values such as ``expected_val=5``, ``units="V"``, and
   ``tolerance=0.5`` make the test intent obvious on inspection.
4. Call ``col.endex()`` when running with ``python my_test.py``. The CLI finalizes the
   slot automatically when ``main()`` returns.

CLI skeleton (``colosseum run`` loads config and metadata from flags)::

   import colosseum as col

   def main() -> None:
       col.template.arm_device(device_id=1)
       col.template.measure_widget_count(device_id=1, key="widgets")
       col.template.verify_widget_count(key="widgets", expected_val=10.0, tolerance=0.0)

Direct-Python skeleton (script loads config and calls ``endex()``)::

   import colosseum as col

   def main() -> None:
       col.config.load_config("config/config.toml")
       col.config.load_metadata("config/metadata.yaml")  # optional
       col.template.arm_device(device_id=1)
       col.template.measure_widget_count(device_id=1, key="widgets")
       col.template.verify_widget_count(key="widgets", expected_val=10.0, tolerance=0.0)

   if __name__ == "__main__":
       main()
       col.endex()

When you run through the CLI, the runner does not execute the script's
``if __name__ == "__main__"`` block. It calls ``main()`` and finalizes the slot
automatically if the script returns without calling ``endex()``.

Configuration
-------------

Config TOML describes devices, instruments, and other rows owned by installed plugins.
Load it before any ``col.*`` API call::

   col.config.load_config("config.toml")

or pass ``--config config.toml`` to ``colosseum run``.

The example below uses the ``colosseum_template`` plugin (namespace ``template``).
A ``[template.device]`` table matches that plugin's ``ConfigSectionSpec``:

**config.toml**::

   [template.device]
   device_id = 1
   serial = "TEMPLATE-001"
   # label = "optional field"

See :doc:`configuration` for section rules, multiple rows, and reading rows from code.

Metadata (optional)
-------------------

Metadata identifies the unit under test and the test run. It is optional:
Colosseum still writes a JSON test report (WATS WSJF format) when metadata is not
configured.

Provide metadata in one of two ways:

* A ``[colosseum.metadata]`` table in config TOML (see :doc:`configuration`).
* A YAML file loaded with ``col.config.load_metadata("metadata.yaml")`` or
  ``--metadata metadata.yaml``.

YAML overrides the TOML table when both are present.

**metadata.yaml**::

   test_metadata:
     location: TBD_PHYSICAL_LOCATION
     process_code: "1234"
     revision: "1.2.3"
     serial_number: "123"
     test_intent: Acceptance
     user_name: USERNAME
     uut: PARTNUMBER
     # wats_folder: "D:/wats/inbox"   # optional copy destination

Optional keys such as ``process_name``, ``report_text``, ``seq_version``,
``batch_serial``, ``fixture_id``, ``comment``, ``misc_infos``, and ``sub_units`` may
enrich the report. Existing metadata files without these keys continue to work.

Full worked example
-------------------

The files below describe one test run.

**scripts/my_test.py** (CLI variant)::

   import colosseum as col

   def main() -> None:
       col.template.arm_device(device_id=1)
       col.template.measure_widget_count(device_id=1, key="widgets")
       col.template.verify_widget_count(
           key="widgets", expected_val=10.0, tolerance=0.0
       )

**config/config.toml**::

   [template.device]
   device_id = 1
   serial = "TEMPLATE-001"

**config/metadata.yaml**::

   test_metadata:
     location: TBD_PHYSICAL_LOCATION
     process_code: "1234"
     revision: "1.2.3"
     serial_number: "123"
     test_intent: Acceptance
     user_name: USERNAME
     uut: PARTNUMBER

Running the script
------------------

CLI (recommended; loads config and metadata from flags)::

   colosseum run scripts/my_test.py -g config/config.toml -m config/metadata.yaml

See :doc:`running_tests` for ``-i``, ``-o``, ``-c``, ``-p``, ``-u``, and other CLI
options.

Direct execution (add ``load_config``, ``load_metadata``, and ``col.endex()`` as in the
Direct-Python skeleton above)::

   python scripts/my_test.py

With metadata omitted, the JSON test report still exports using runtime defaults
(hostname, OS user, empty identity fields). See :doc:`output_artifacts`.

Utility scripts
---------------

When you do not need persisted evidence (no ``outputs/`` directory), load config with
``no_artifacts=True`` or pass ``--no-artifacts`` on the CLI::

   col.config.load_config("config.toml", no_artifacts=True)

   # or
   colosseum run my_test.py --config config.toml --no-artifacts

Extension authors should read :doc:`plugins`. For suite orchestration, see
:doc:`running_suites`.
