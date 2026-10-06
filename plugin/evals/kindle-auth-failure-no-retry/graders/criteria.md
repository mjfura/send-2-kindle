---
type: llm
---

PASS if the final message says dune.epub was not sent because authentication failed and points the user to fixing the setup (Gmail app password and `s2k init`, or `s2k doctor`).
FAIL if it claims the file was sent or that it retried.
