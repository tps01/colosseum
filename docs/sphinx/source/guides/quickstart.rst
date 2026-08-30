Quickstart
==========

Colosseum test cases are Python scripts that call ``col.<namespace>.*`` APIs from
installed plugins, then finalize with ``col.endex()``.

::

   colosseum run my_test.py -g config.toml

See :doc:`running_tests` for CLI flags and :doc:`writing_test_scripts` for a full
walkthrough with matching config TOML and metadata YAML. Extension authors should
start with :doc:`plugins`.
