# Evidence-gated validation: verdict

Mode 1 (two independent subagents). Ledger: `claims-ledger.md`. Channel A (docs): `channel-a.md`.
Channel B (runtime probes, each with a falsifier): `channel-b.md`. Date: 2026-10-29.

| ID | Channel A | Channel B | Gate |
|---|---|---|---|
| C1 approx rel/abs | CONFIRMED | CONFIRMED | ACCEPTED |
| C2 pytest skip/xfail | CONFIRMED | CONFIRMED | ACCEPTED |
| C3 unittest places/delta, skip decorators | CONFIRMED | CONFIRMED | ACCEPTED |
| C4 numpy/torch rtol/atol | CONFIRMED | CONFIRMED | ACCEPTED |
| C5 toBeCloseTo numDigits | CONFIRMED | CONFIRMED | ACCEPTED |
| C6 jest skip/focus semantics + engine flags listed forms | CONFIRMED (gaps found: `xit.each`, `fit.each`, `*.failing` aliases, tagged-template `.each`, one marker counter for the whole diff) | CONFIRMED for the 13 listed forms | ACCEPTED for the listed forms; the gaps went to the fix round |
| C7 PreToolUse input/output fields | CONFIRMED (Write/Edit/output); MultiEdit not documented | UNVERIFIABLE (no Claude Code run); SDK types match field names | SPLIT: field names ACCEPTED (docs + SDK types); runtime ask/deny behaviour UNRESOLVED; MultiEdit UNRESOLVED (kept, harmless if never sent) |
| C8 plugin hooks load only when enabled; `${CLAUDE_PLUGIN_ROOT}` | CONFIRMED | UNVERIFIABLE | UNRESOLVED at runtime; docs-only |
| C9 GitHub workflow-command escaping | CONFIRMED | CLI half CONFIRMED, annotation half UNVERIFIABLE | CLI half ACCEPTED; annotation rendering UNRESOLVED |
| C10 composite action env, PR SHAs, fetch-depth | CONFIRMED | UNVERIFIABLE (no runner); local shallow-clone stand-in agrees | UNRESOLVED at runtime; docs-only |
| C11 git diff headers parsed | CONFIRMED | CONFIRMED | ACCEPTED |
| C12 action SHAs = tags | CONFIRMED | CONFIRMED | ACCEPTED |
| C13 Python 3.9 | CONFIRMED (read) | CONFIRMED (168 passed on CPython 3.9.25) | ACCEPTED |

What is not proven: that Claude Code really shows the "ask" prompt from this plugin's hook, and that
the Action renders annotations on a real runner. Both need a live run.
