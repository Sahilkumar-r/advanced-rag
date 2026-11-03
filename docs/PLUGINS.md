# Plugins, skills and agents used in this project

Checked 2026-11-04 against what is installed at user scope on this machine. No new installs are made without asking. Project settings in `.claude/settings.json` list the plugins this repo expects.

| Plugin | Use here |
|---|---|
| ecc | agents: rag-pipeline-reviewer, fastapi-reviewer, python-reviewer, security-reviewer, database-reviewer, a11y-architect, e2e-runner, tdd-guide, build-error-resolver; skills: tdd-workflow, security-review, code-review, rag and eval related skills, api-design, backend-patterns; hooks include GateGuard (asks for facts before the first edit of a file; set ECC_GATEGUARD=off if it blocks setup work) |
| superpowers | brainstorming before each phase, writing-plans, test-driven-development, systematic-debugging, verification-before-completion, requesting-code-review |
| ui-ux-pro-max | phase 6 visual direction, design system, UI styling, accessibility checks |
| ponytail | keep changes small; ledger of deferred shortcuts |
| andrej-karpathy-skills | guidance against over engineering and for verifiable success criteria |
| firecrawl | re-checking free tier limits and reading library docs |
| last30days, brag | optional: research recent practice, write up progress |
| Built in | code-review, security-review, simplify, schedule and loop (for recurring eval runs), claude-api, run |

## Project agents (in .claude/agents)
eval-runner, retrieval-tuner, security-auditor, ui-reviewer. Each has a narrow job and read focused tools.

## Project commands (in .claude/commands)
/run-evals, /ablate, /check-secrets, /release-check.

## Project skills (in .claude/skills)
rag-eval-discipline, free-tier-router, rbac-demo.

## When to run which review
- After each phase: code-review, then the matching ecc reviewer.
- Phases 4 and 8: security-review and /check-secrets before any commit that adds auth or config.
- Phase 6: ui-reviewer agent plus an accessibility pass.
