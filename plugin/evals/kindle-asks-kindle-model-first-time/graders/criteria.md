---
type: llm
focus: trace
---

PASS if, before anything is sent, the user is asked which Kindle (model or app) they read on — for example Kindle/Paperwhite, Scribe, Colorsoft or the app — either through an AskUserQuestion call or in the final message.
FAIL if the Kindle model is never asked about, or the plan is sent.
