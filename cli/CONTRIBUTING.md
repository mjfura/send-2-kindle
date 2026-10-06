# Contributing to s2k

Python 3.13 + Poetry. The virtualenv lives in `cli/.venv`.

```bash
cd cli
poetry env use python3.13
poetry install
```

Run before every commit:
```bash
poetry run ruff check . && poetry run ruff format --check . && poetry run mypy src tests && poetry run pytest
```

- Tests never send real email (a fake SMTP replaces `smtplib`) and never read your real
  configuration (`tests/conftest.py` points `S2K_CONFIG_FILE` and `HOME` to temp paths).
- Design docs: `docs/superpowers/specs/`. Releases: `docs/releasing.md`.
- Git workflow: Conventional Commits, `<type>/<kebab-case>` branches, squash-merged PRs.

## Manual smoke test

With your real configuration (`s2k init`):
```bash
echo "s2k smoke test" > /tmp/s2k-smoke.txt
poetry run s2k send /tmp/s2k-smoke.txt
```
