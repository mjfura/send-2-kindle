# Releasing s2k-cli

One version for the whole repository. A `vX.Y.Z` tag on `main` publishes the CLI to PyPI
(`s2k-cli`) and creates a GitHub Release (`.github/workflows/release.yml`).

The same tag versions the Claude Code plugin in `plugin/`; users receive a new plugin copy when its
`plugin.json` version changes.

## One-time setup (owner)

1. Create a PyPI account at <https://pypi.org/account/register/> and enable 2FA.
2. *Your account → Publishing → Add a new pending publisher* (GitHub tab):
   - PyPI project name: `s2k-cli`
   - Owner: `mjfura` · Repository: `send-2-kindle`
   - Workflow name: `release.yml` · Environment name: `pypi`
3. The GitHub environment `pypi` already exists in the repository settings (*Settings →
   Environments*). Optionally add yourself as a required reviewer to approve each publication.

No tokens or passwords are stored anywhere: PyPI trusts this workflow through OIDC.

The package is `s2k-cli`, not `send-2-kindle`: PyPI rejects names that match an existing project
once `-`, `_` and `.` are removed, and `send2kindle` already exists.

## Each release

1. Pick the version: `~/.claude/skills/git-workflow/scripts/next-version.sh --verbose`.
2. If it differs from `cli/pyproject.toml`, open a PR `chore(release): vX.Y.Z` that changes only
   the version in `cli/pyproject.toml` **and** `plugin/.claude-plugin/plugin.json` (canonical PEP 440
   form, e.g. `0.2.0rc1` for `v0.2.0-rc.1`) and merge it. If `plugin/` changed since the last tag,
   the owner may run the evals first (`plugin/evals/run.sh --runs 1 --ablation none`) and paste the
   summary in the PR.
3. Tag and push:
   ```bash
   git switch main && git pull --ff-only
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```
4. Watch it: `gh run watch $(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')`.
5. Smoke test from a clean environment: `pipx install s2k-cli==X.Y.Z && s2k --version`.

If any job before `publish` fails, nothing is published: fix on `main` and tag again with the next
version (PyPI never accepts the same version twice; tags are protected from being moved).
Pre-release tags (`-rc.N`) publish PyPI pre-releases that `pipx install` ignores unless asked.
