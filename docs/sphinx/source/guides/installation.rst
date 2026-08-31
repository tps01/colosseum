Installation
============

Online (PyPI or editable)
-------------------------

Install the standalone runtime::

   pip install colosseum-core

The Python import is ``import colosseum as col``. Install each plugin distribution in the
same environment; core discovers plugins through ``colosseum.plugins`` entry points.

The examples in this manual use the ``colosseum-template`` plugin (namespace ``template``,
API ``col.template.*``). Install it when following the walkthroughs::

   pip install colosseum-template

Or install the template wheel from a local build alongside core (versions must match)::

   pip install colosseum_core-0.16.2-py3-none-any.whl colosseum_template-0.1.0-py3-none-any.whl

The desktop runner (``colosseum --gui``) is included with the core install.

One install covers runtime, tests, static analysis, and docs tooling::

   pip install -e .

Python 3.9 and newer are supported.

Offline
-------

Offline installs are a first-class workflow. Build a wheelhouse on a networked twin
(same OS, architecture, and Python version as the target), then install with
``--no-index``.

The integration scripts and host prerequisites (including Linux ``tkinter`` / Tk) are
documented in the parent checkout::

   offline/README.md

Quick path from that parent directory::

   python offline/build_wheelhouse.py
   python offline/install_offline.py --wheelhouse colosseum-wheelhouse
   python offline/verify_env.py

``customtkinter`` ships in the wheelhouse; system Tcl/Tk does not. On Linux, bake
``python3-tk`` (or a Tk-enabled Python) into the offline host image.
