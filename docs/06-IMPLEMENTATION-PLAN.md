# 06. Implementation Plan

Each phase ends with a **gate**: measured numbers written to the README (good or bad) and a review (code-review, plus security-review for phases that touch auth or secrets). Nothing public (GitHub repo, push, deploy) happens without asking Sahil first.

Effort is an estimate, not a promise: roughly 2 to 3 weeks of focused work, inside week 5 of the roadmap and spilling over if needed.

## Phase 0. Baseline and repo bootstrap
- [x] 0.1 Create venv (Python 3.12), pin dependencies, pytest runs.
- [x] 0.2 Copy baseline code and the 30 question set from rag-demo; reproduce its numbers (hit@5, MRR) in this repo.
- [~] 0.3 Convert metrics to the new definitions (recall@k, precision@k, MRR, nDCG, context recall and precision). (done: recall, precision, MRR, nDCG; not done: context recall and precision, which need the LLM judge)
Gate: baseline table matches rag-demo or the difference is explained.

## Phase 1. Ingestion, indexes, retrieval evals
- [x] 1.1 Fetch FastAPI and Pydantic docs with licenses; document records.
- [x] 1.2 Parent child chunking; chunk size and overlap study (128, 256, 512 tokens; 0 and 15 percent overlap; header on and off).
- [~] 1.3 Dense + BM25 + RRF; Qdrant HNSW; FAISS flat and IVF; MMR; rerank; query rewrite and HyDE. (done: dense, BM25, RRF, FAISS flat, HNSW, IVF, MMR, rerank; not done: Qdrant, query rewrite, HyDE)
- [~] 1.4 Golden set: 40 hand written questions plus synthetic up to 100+, labelled by type and reviewed; imports the 30 from rag-demo. (done: 128 cases; the 41 Claude written questions still need Sahil review)
- [x] 1.5 Retrieval eval runner and ablation table (also latency, memory, build time). Larger synthetic corpus for the ANN study, labelled synthetic.
Gate: ablation table in README with winners, losers and the chosen defaults.

## Phase 2. Generation and self-RAG
- [x] 2.1 Provider adapters for Groq and Gemini first; mock provider for tests.
- [x] 2.2 Cited answer prompt, refusal rules, context assembly (parent expansion).
- [x] 2.3 Self-RAG controller (need retrieval, relevance, support, usefulness, retry cap 2).
- [~] 2.4 Generation eval: faithfulness, answer relevancy, citation accuracy, refusal correctness; judge from a different model family; hand label 30 cases to calibrate the judge. (done; the 30 judge cases are Claude labelled, unreviewed)
Gate: plain RAG vs self-RAG table (quality, latency, tokens).

## Phase 3. Router, cache, pipeline and system evals
- [x] 3.1 Router with tiers, fallback chain, circuit breaker, quota counters, OpenAI budget cap.
- [x] 3.2 Exact and semantic cache; threshold tuned on the eval set; wrong hit rate measured.
- [x] 3.3 Tracing (JSONL, optional Langfuse), token and cost accounting.
- [x] 3.4 Pipeline eval (end to end) and system eval (latency percentiles, tokens, cost, cache hit rate, fallback rate).
Gate: system table with real numbers; free route cost verified.

## Phase 4. Auth, RBAC, guardrails, memory
- [x] 4.1 Users, roles, permissions, JWT, argon2, rate limits, audit log; seed script.
- [x] 4.2 Guardrails (input, retrieval, output) with a labelled safety eval set (injection, PII, off topic, unsupported claims).
- [~] 4.3 Six memory types with consent, view and delete endpoints; memory ablation on multi turn cases. (done; long term memory effect on answers not measured)
Gate: security review; RBAC test matrix passes; safety eval table.

## Phase 5. Voice and image
- [~] 5.1 Whisper STT endpoint; transcript confirm; word error check on a small recorded set made by Sahil. (done on a synthetic set; real recordings and screenshots still needed)
- [~] 5.2 Image endpoint with a vision model; test set of error screenshots and diagrams. (done on a synthetic set; real recordings and screenshots still needed)
- [~] 5.3 Browser TTS option. (moved to phase 6: it is a browser feature) (built in Settings as spoken replies; not verified by ear)
Gate: voice and image eval numbers, with failures listed.

## Phase 6. UI and UX
- [x] 6.1 Pick the visual direction with ui-ux-pro-max (2 or 3 mockups, Sahil chooses).
- [x] 6.2 PWA: login, chat, mic, attach, answer card, source drawer, history, memory, settings.
- [x] 6.3 Admin: users, eval dashboard, system metrics.
- [~] 6.4 Accessibility pass, Lighthouse mobile, real phone test. (Lighthouse and performance trace recorded; real phone, keyboard walk through and screen reader pass not done)
Gate: Lighthouse and axe results recorded; screens checklist from the design brief.

## Phase 7. Scheduled evals and CI
- [~] 7.1 GitHub Actions: ci.yml (tests, lint, secret scan), evals-nightly.yml (sample of traces), evals-weekly.yml (full golden set), manual dispatch. (written and checked locally; never run on GitHub)
- [~] 7.2 Regression gate with tolerances from docs/EVALS.md; results stored and shown in the dashboard. (gate built and tested; no scheduled run has completed)
Gate: at least two scheduled runs completed and visible.

## Phase 8. Deploy and publish (each step needs Sahil approval)
- [ ] 8.1 Dockerfile for the Space; secrets set in Space settings (Sahil enters them).
- [ ] 8.2 Create the GitHub repo (public or private as Sahil decides) and push; git identity checked.
- [ ] 8.3 Deploy the Space; test on phone and laptop; record cold start time.
- [ ] 8.4 README with the measured table, limitations, and a demo credentials policy (no passwords in the README).
- [ ] 8.5 Update the roadmap tracker (data/projects.json entry 07, run generate.mjs, redeploy tracker) and write portfolio text.
Gate: public URL works; every metric in SPEC.md has a measured number.

## Dependencies on Sahil
Create free accounts and keys (Groq, Google AI Studio, OpenRouter, optional Cerebras, NVIDIA, Mistral, Hugging Face) and put them only in a local .env. Decide public or private repo. Record a few voice clips and screenshots for phase 5. Rotate any key ever pasted into a chat.

## Risks to watch each phase
Free quota burn during evals (use cache, small samples, off peak). Judge bias. Overfitting thresholds to the golden set (keep a held out split). Scope creep: P2 features move last.
