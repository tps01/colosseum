# Colosseum Core

Core of the Colosseum test automation framework. It provides:

- command, measurement, and verification decorators
- TOML configuration and plugin registration
- test and test suite runners
- SQLite databse, logs, summaries, and artifacts
- GUI

## Install

```sh
pip install colosseum-core
```

## Develop

```sh
python -m venv .venv
python -m pip install -e .
python scripts/run_tests.py
python scripts/run_static.py
python tests/regression/run_docgen_check.py --skip-pdf
```

See [docs/DEVELOPING.md](docs/DEVELOPING.md) for details.
