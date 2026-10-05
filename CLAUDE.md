<!-- git-workflow:start -->
## Git workflow

This project follows the **git-workflow** skill (`~/.claude/skills/git-workflow`). Load it before any
branch, commit, push, PR, merge, tag or release operation. Key rules:

- Everything written to git is in English.
- Only one long-lived branch: `main`, always releasable. Never commit work directly on it.
- Work branches: `<type>/<kebab-case>` from `main`; types: feat, fix, docs, refactor, test, chore, ci, perf.
- Conventional Commits; PR title is a Conventional Commit (it becomes the squash commit).
- Squash merge into `main`; rebase to update branches.
- Releases are annotated SemVer tags on `main` (`vX.Y.Z`, candidates `vX.Y.Z-rc.N`).
- No AI attribution in commits or PRs (no Co-Authored-By, no session links).
<!-- git-workflow:end -->
