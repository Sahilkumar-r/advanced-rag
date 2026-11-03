# CLAUDE.md: rules for this repo

## Non-negotiable
- **Never fabricate** metrics, costs, limits or users. A number enters the README only after it is measured or sourced with a URL and date. Targets are labelled targets.
- **Secrets:** no keys, tokens or passwords in files, commits, logs or chat. `.env` is gitignored. Demo passwords come from env. Remind the user to rotate anything they paste.
- **Ask before** creating the GitHub repo, pushing, deploying, posting, spending money, or installing plugins. No force push.
- **Git identity:** name `Sahilkumar-r`, email `sahilrathi.k@gmail.com`. Check `git config user.email` before the first commit.
- Free tiers first. OpenAI key is last resort and judge only, capped by `OPENAI_BUDGET_USD`.
- Free tier prompts may be used for training: send only public docs text and demo questions.
- Site copy: plain, honest, no hyphens.

## Eval discipline
Change one thing at a time. Keep the golden set fixed between runs. Record every experiment in `eval/results/` and the README table, including ones that got worse. Use a judge model from a different family than the answer model. Hand label a sample to calibrate any LLM judge.

## Repo map
`docs/` six core docs + FREE-APIS, EVALS, PLUGINS. `src/ragx/` packages (ingest, index, retrieve, rerank, selfrag, generate, router, cache, memory, guardrails, auth, voice, vision, evals, api, observability). `eval/datasets/` golden set. `.claude/` agents, commands, skills. `web/` PWA.

## Commands (filled as phases land)
See `Makefile` and `docs/06-IMPLEMENTATION-PLAN.md`. Slash commands: `/run-evals`, `/ablate`, `/check-secrets`, `/release-check`.

## Plugins to use
code-review and security-review before each phase gate; tdd-workflow for new modules; ui-ux-pro-max for UI; rag-pipeline-reviewer and fastapi-reviewer agents (ecc). See `docs/PLUGINS.md`.
