# 01. Product Requirements Document

Status: draft. Every number is a **target**, not a result.

## 1. Summary
A docs assistant for FastAPI and Pydantic that answers by text, voice or screenshot, cites sources, refuses when the docs do not cover the question, and exposes its own quality numbers.

## 2. Problem
RAG demos usually show one good answer. Teams do not know their retrieval recall, how often answers are unsupported, what a query costs, or when quality regresses. This product makes those visible.

## 3. Users (personas, assumed, not validated)
| Persona | Need | Role in app |
|---|---|---|
| Learner Lena | Quick, correct answers with links while following the tutorial, often on a phone | viewer |
| Backend dev Dev | Paste an error screenshot or ask by voice while coding, trust the citation | developer |
| Maintainer Max | See quality, cost and failures, run evals, manage users | admin |
| Visitor | Try the demo without an account | guest (rate limited) |

Validation plan: run the same pipeline on a second doc set (Pydantic) to test generalisation. A real buyer is a hypothesis; nothing here claims customers.

## 4. Jobs to be done
1. Ask a question in text or voice and get a cited answer in seconds.
2. Send a screenshot of an error and get docs grounded help.
3. Trust the answer: see sources, a refusal when unsupported, and a confidence cue.
4. As admin: see retrieval, generation and system metrics over time and catch regressions.

## 5. Features
- **P0 (must):** ingestion of two corpora; hybrid retrieval; cited generation with refusal; golden set with retrieval and generation evals; auth with roles; guardrails; cost and token tracking.
- **P1:** self-RAG loop; model router with fallback; semantic cache; voice in and out; memory (short, session, long term); scheduled evals; admin dashboard.
- **P2:** image questions; entity, episodic and procedural memory; HNSW vs IVF study write up; Langfuse tracing.

## 6. Functional requirements
- FR1 Answer text questions with numbered citations linking to the doc page.
- FR2 Refuse and say so when best evidence is below threshold or the self-check fails.
- FR3 Accept voice (record, transcribe, answer, optional spoken reply).
- FR4 Accept an image (screenshot or diagram), describe it, then answer from docs.
- FR5 Keep per user short term context; remember stated preferences with consent; allow view and delete of memories.
- FR6 Log every request with trace id, models used, tokens, latency, cache status, cost.
- FR7 Role based access: guests ask only; viewers ask and keep history; developers also use image and API tokens; admins manage users, run evals, see dashboards.
- FR8 Run evals on demand, nightly on a sample of logged traffic, weekly on the full golden set; store and chart results.
- FR9 Provider failure never shows a raw error: fallback chain, then a clear message.

## 7. Non-functional targets
| Area | Target (to measure) |
|---|---|
| Latency | text answer p50 under 4 s, p95 under 10 s on free tier (cache hit under 300 ms) |
| Cost | $0 per query on the free route; paid fallback capped by `OPENAI_BUDGET_USD` |
| Availability | best effort; free host sleeps; wake time shown in UI |
| Accessibility | WCAG 2.2 AA on core flows |
| Security | OWASP basics, hashed passwords, JWT expiry, rate limits, no secrets in repo |
| Privacy | only public docs and demo questions sent to free providers |

## 8. Success metrics
See `SPEC.md`. Reported honestly, including worse than baseline.

## 9. Non-goals
Fine tuning, real payments, enterprise SSO, millions of documents, native mobile apps (PWA only).

## 10. Risks and open questions
Free tier limits change or vanish (router plus dated `docs/FREE-APIS.md`). LLM judge bias. Small hand labelled set. HF Space ephemeral disk. Voice and image quality on free models is unmeasured until phase 5.
