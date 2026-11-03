---
description: Run evals for one layer and compare with the last good run
argument-hint: retrieval | generation | pipeline | system | safety | full
---
Use the eval-runner agent to run the "$ARGUMENTS" evals defined in docs/EVALS.md. If no layer is given, ask which one. Report the table, the diff against the last good run, regressions first, and what was not checked. Do not edit eval cases.
