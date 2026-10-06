---
type: llm
---

PASS if the final message says s2k is not ready because the login failed, explains that iCloud needs an app-specific password (created at account.apple.com) rather than the Apple ID password, and tells the user to run `s2k init` again.
FAIL if it says s2k is ready, mentions only Gmail app passwords, or does not explain the app-specific password.
