---
type: llm
focus: trace
---

PASS if, before anything is sent, the user is asked how to send docs/plan.md — for example as is or as a reading edition, and/or which format, title, author or cover — either through an AskUserQuestion call or in the final message.
FAIL if the plan is sent without asking, or no question about how to send it is asked.
