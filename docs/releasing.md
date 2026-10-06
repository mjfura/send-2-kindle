# Releasing send-2-kindle

One version for the whole repository. A `vX.Y.Z` tag on `main` publishes the CLI to PyPI
(`send-2-kindle`) and creates a GitHub Release (`.github/workflows/release.yml`).

## One-time setup (owner)

1. Create a PyPI account at <https://pypi.org/account/register/> and enable 2FA.
2. *Your account → Publishing → Add a new pending publisher* (GitHub tab):
   - PyPI project name: `send-2-kindle`
   - Owner: `mjfura` · Repository: `send-2-kindle`
   - Workflow name: `release.yml` · Environment name: `pypi`
3. The GitHub environment `pypi` already exists in the repository settings (*Settings →
   Environments*). Optionally add yourself as a required reviewer to approve each publication.

No tokens or passwords are stored anywhere: PyPI trusts this workflow through OIDC.

## Each release

1. Pick the version: `~/.claude/skills/git-workflow/scripts/next-version.sh --verbose`.
2. If it differs from `cli/pyproject.toml`, open a PR `chore(release): vX.Y.Z` that changes only
   `version` (canonical PEP 440 form, e.g. `0.2.0rc1` for `v0.2.0-rc.1`) and merge it.
3. Tag and push:
   ```bash
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. Watch it: `gh run watch $(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')`.
5. Smoke test from a clean environment: `pipx install send-2-kindle==X.Y.Z && s2k --version`.

If any job before `publish` fails, nothing is published: fix on `main` and tag again with the next
version (PyPI never accepts the same version twice; tags are protected from being moved).
Pre-release tags (`-rc.N`) publish PyPI pre-releases that `pipx install` ignores unless asked.
