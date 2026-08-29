Quickstart
==========

Colosseum test cases are Python scripts that call ``col.<namespace>.*`` APIs from
installed plugins, then finalize with ``col.endex()``.

::

   colosseum run my_test.py --config bench.toml

See :doc:`writing_test_scripts` for a full walkthrough with matching bench TOML and
metadata YAML. Extension authors should start with :doc:`plugins`.
