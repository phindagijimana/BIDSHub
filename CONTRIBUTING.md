# Contributing to BIDSHub

## Development setup

```bash
./hub install
pip install -r requirements-dev.txt
```

`./hub install` only installs the locked application stack (`requirements.txt`). Tests and `pip-tools` for refreshing locks live in `requirements-dev.txt`.

## Tests

- Run the full suite: `python -m pytest tests/ -q` (or `./hub test` after dev deps are installed).
- Pytest disables the optional `dandi` plugin (`-p no:dandi`) to avoid environment-specific plugin conflicts. Options are in `pytest.ini`.
- `BIDSHUB_NONINTERACTIVE=1` makes `scripts/init_db.py` skip the interactive recreate prompt when a database file already exists (used by CI and `./hub install`).

## Refreshing `requirements.txt`

The committed `requirements.txt` is a full **pinned** environment. `requirements.in` lists direct dependencies; regenerating a lock in one shot may hit `resolution-too-deep` on some pip versions, so the documented fallback is:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install "numpy==1.26.0" "protobuf>=4.21,<5" "urllib3>=2.0.0,<3,!=2.2.0"
pip install --use-deprecated=legacy-resolver -r requirements.in
pip freeze > requirements.txt
```

Re-add the header comment at the top of `requirements.txt` after freeze.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on pushes and pull requests to `main` and `develop`, using Python 3.10 and 3.12 on Ubuntu and macOS.

## Releasing (version bump)

1. Set **`src/bidshub_version.py`** `__version__` and the **`version`** in **`pyproject.toml`** to the same value (e.g. `3.1.2`).
2. Add a section to **`CHANGELOG.md`** for the release.
3. Tag: `git tag v3.1.2` (or match your scheme) and push tags if you use remote hosting.
4. (Optional) add compare URLs at the bottom of `CHANGELOG.md` to your public repo.
