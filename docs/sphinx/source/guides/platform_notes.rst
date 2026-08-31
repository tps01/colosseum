Platform notes
==============

Core uses platform-neutral Python APIs. Output is written beneath ``outputs/`` in the
process working directory unless ``--no-artifacts`` is used.

Windows
-------

Create and activate a virtual environment with::

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

python.org CPython installers include ``tkinter``, so ``colosseum --gui`` works after a
normal ``colosseum-core`` (or offline wheelhouse) install.

Linux
-----

Create and activate a virtual environment with::

   python3 -m venv .venv
   . .venv/bin/activate

For GUI use, the Python build must provide ``tkinter`` (Debian/Ubuntu: ``python3-tk``).
That is an OS/image prerequisite, not a pip package. Air-gapped hosts should bake it into
the golden image together with Python. See ``offline/README.md`` in the integration
checkout.

SSH X11 forwarding (``ssh -X``) still requires Tk on the Linux side and a working
``DISPLAY``.

Documentation
-------------

The Sphinx **PDF** is the primary manual and needs ``latexmk`` plus a TeX
distribution. HTML is a backup of the same sources
(``python scripts/docgen/build_all.py --skip-pdf``).

Hardware permissions, native libraries, and driver runtimes are plugin concerns and
should be documented by the plugin that needs them.
