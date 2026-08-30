# Cutting a release

1. Validate `develop` with tests, static analysis, docs, and `python
  scripts/ci/build_dist.py`.
2. Update the version in `pyproject.toml`.
3. Merge `develop` into release-only `main`.
4. Tag `main` with `v<version>` and push the tag.

The tag must match `project.version`. Release orchestration (GitHub Actions
today,
Bamboo later) should stay thin and call the same scripts under `scripts/ci/`.

## CI-agnostic scripts

| Script | Purpose |
| --- | --- |
| `scripts/ci/build_dist.py` | sdist + wheel into `dist/` |
| `scripts/ci/build_offline_wheelhouse.py` | wheels; optional `--zip` |
| `scripts/ci/verify_release_tag.py` | ensure tag matches `pyproject.toml` |

Examples:

```bash
python scripts/ci/build_dist.py
python scripts/ci/build_offline_wheelhouse.py --zip
python scripts/ci/verify_release_tag.py --tag v0.15.2
```

Plugins add core into the offline house:

```bash
python scripts/ci/build_offline_wheelhouse.py --also-build ../colosseum-core --zip
```

Build on the same OS / arch / Python minor as the install target. Archive names
look like
`colosseum-core-offline-{windows,linux}-py{3.9,3.12}.zip`.

## What a release publishes

- `colosseum_core-<version>-py3-none-any.whl`
- `colosseum_core-<version>.tar.gz`
- core PDF and HTML documentation
- offline wheelhouses for **Windows and Linux × Python 3.9 and 3.12**

`workflow_dispatch` (or the Bamboo equivalent) can build artifacts without
publishing.

Plugins ship the same script set. Equipment uses Python **3.10** and **3.12**.

## Bamboo

Mirror the GitHub Actions stages with Specs that only:

1. Select agent OS and Python version
2. Checkout (plugins also checkout `colosseum-core`)
3. Run the scripts above
4. Publish `dist/*` and `*-offline-*.zip` as Bamboo artifacts

Do not put packaging logic in a `bamboo.bat`; keep agents as thin callers.

For a combined four-package house from a local parent checkout, use the
integration
`offline/` scripts instead of per-package CI.
