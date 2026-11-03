# SPEC: Advanced multimodal RAG (project 07)

Extends `Sahilkumar-r/rag-demo` (FastAPI docs assistant). Status: **scaffold only, no application code yet.**
All numbers below are **targets to measure, not results.**

## Problem
Teams ship RAG without measuring retrieval, generation or cost, so quality, regressions and spend are unknown. Docs assistants are the most common RAG product, so this project builds one properly and measures every layer.

## Scope
1. Ingest two public doc sets (FastAPI, Pydantic) with parent child chunking and a chunk size study.
2. Retrieval: dense, BM25, hybrid RRF, HNSW vs IVF cluster index vs flat, rerank, query rewrite. Compare, keep what wins, report what did not.
3. Self-RAG: retrieve decision, relevance grading, grounding check, bounded retry.
4. Generation with citations and refusals. Router across free LLM tiers with fallback and a capped paid last resort.
5. Voice (speech in via Whisper, speech out via browser) and image (error screenshot or diagram) input.
6. Semantic and exact cache. Six memory types. Demo auth with RBAC.
7. Guardrails on input, retrieval and output.
8. Evals for seven parts (retrieval, generation, RAG pipeline, full system, guardrails, voice and image, online) run on demand, in CI, nightly on a sample, and weekly in full. See docs/EVALS.md.
9. Mobile first UI. Deployed on a Hugging Face Space. Code on GitHub.

## Non-goals
Fine tuning models, a vector DB at millions of vectors, real user accounts or payments, production SLAs, selling it as a product (a buyer is a hypothesis to validate later).

## Success metrics (targets, measured in the README when done)
| Layer | Metric | Target |
|---|---|---|
| Retrieval | recall@5, precision@5, MRR, nDCG@10, context recall, context precision | at least match rag-demo baseline (hit@5 1.00, MRR 0.89 on 30 questions) on the larger set; report any drop |
| Generation | faithfulness, answer relevancy, citation accuracy, refusal correctness | report values; no fixed pass mark until the judge is calibrated against hand labels |
| Pipeline | end to end correct answer rate on golden set | report overall and per question type |
| System | p50 and p95 latency, tokens and cost per query, cache hit rate, fallback rate | cost per query $0 on the free route; report the rest |
| Safety | prompt injection block rate, off-topic refusal rate, PII leak rate | report; failures listed |
Experiments that did not help are reported in the same table.

## Risks
Free tier rate limits and sudden model removals (router fallback, pinned alternatives). LLM judge bias (calibrate on hand labeled cases, use a different model family as judge). Small hand made eval set (grow to 100+, mark synthetic cases). Free tier providers may train on prompts (only public docs and demo questions are sent; no private data). HF Space disk is ephemeral (documented, state in a small dataset or rebuilt on boot).

## Done means
Every metric in the table has a measured number in the README, including bad ones. Public URL works on phone and laptop. Scheduled evals ran at least twice and their output is visible. No secrets in the repo.

## Related
`docs/01-PRD.md` .. `docs/06-IMPLEMENTATION-PLAN.md`, `docs/FREE-APIS.md`, `docs/EVALS.md`, `docs/PLUGINS.md`.
