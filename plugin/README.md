# s2k plugin for Claude Code

Ask Claude to put things on your Kindle — and get something pleasant to read:

- "Send me a summary of this project to my Kindle."
- "Send the plan you just wrote to my Kindle so I can review it carefully."
- "Send the spec / this file / the proposals / a progress report to my Kindle."
- "Send ./books/dune.epub to my Kindle as is."

Claude asks only what is still undecided (reading edition or as is, format, title, author, cover),
builds an EPUB reading edition when it helps, shows you a preview and sends it with the
[`s2k`](../cli/README.md) CLI.

## Install

In a Claude Code session:
```
/plugin marketplace add mjfura/send-2-kindle
/plugin install s2k@send-2-kindle
```

## Skills

| Skill | Use it for |
|---|---|
| `s2k:kindle` | Anything you want to read on your Kindle: existing files, reading editions of plans, specs and notes, or summaries and reports Claude writes for you |
| `s2k:setup` | Install `s2k-cli`, configure it (you run `s2k init` yourself) and check it with `s2k doctor` |

Claude picks them automatically; you can also call `/s2k:kindle` and `/s2k:setup`.

## Your reading profile

The first time, Claude asks which Kindle you read on, your default author, whether you want a cover
page and the language, and offers to save them in `~/.config/s2k/reading.json`. Edit or delete that
file, or ask Claude to change a default, at any time.

## Privacy

Claude never asks for, sees or stores your email password: you type it into `s2k init` in your own
terminal. Generated documents are written to a temporary folder, never into your project.

## Requirements

Python 3.13+ and `pipx` or `uv` for the CLI (`pipx install s2k-cli`), and a Gmail, iCloud Mail or
other SMTP account to send from; `s2k:setup` walks you through it. Converting `.mobi` files needs Calibre (Claude asks before installing it).

## Development

- Validate: `claude plugin validate --strict plugin && claude plugin validate --strict .`
- Tests: `python3 -m unittest discover -s plugin/tests` and `sh plugin/evals/stub/test_stub.sh`
- Evals: `plugin/evals/run.sh` — fake `s2k`, never sends email; uses model calls on your account
  (capped); run them only when the plugin changes, never in CI.
- `plugin/.claude-plugin/plugin.json` version always equals `cli/pyproject.toml` version.
