---
type: llm
---

PASS if the final message says s2k is not ready because the SMTP login/authentication failed, explains that Gmail needs an app password rather than the normal account password, and tells the user to run `s2k init` again after creating one.
FAIL if it says s2k is ready, or does not explain the app password.
