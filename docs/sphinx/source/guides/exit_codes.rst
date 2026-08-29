Exit codes
==========

Colosseum uses a single-bit policy in v1:

.. list-table::
   :header-rows: 1

   * - Code
     - Meaning
   * - ``0``
     - All required verifications and commands passed. For suites, all **test** slots
       passed (setup, ``between_tests``, and teardown outcomes are ignored unless
       ``rip_cord = true``).
   * - ``1``
     - Otherwise (including a required command ERROR)

Optional verifications and optional commands (``optional=True``) are recorded and
appear in ``summary.txt`` but do not change the exit code.

Call ``col.endex()`` at the end of direct-Python tests to flush artifacts and exit with the correct code.
