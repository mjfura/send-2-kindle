---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion]
append_system_prompt: "Eval environment: the s2k CLI, Python and the kindle skill's EPUB script are installed at ./bin/s2k, ./bin/python3 and ./bin/make_epub.py (relative to the working directory). Run `./bin/s2k` instead of `s2k`, `./bin/python3` instead of `python3`, and `./bin/python3 ./bin/make_epub.py` instead of `python3 <skill directory>/scripts/make_epub.py`."
env:
  EVAL_S2K_SCENARIO: ready
---

Send me ./docs/plan.md on my Kindle, I want to review it carefully.
