# EVALS

Metric definitions and rules. No results yet.

## Principles
- Fixed golden set between comparisons; hold out 20 percent, never used for tuning.
- Hand written cases are never replaced by generated ones; synthetic cases need review.
- One change per experiment. Log config, git sha, models and dates.
- The judge model is from a different family than the answer model; calibrate against hand labels and report the agreement.
- Report negative results.

## 1. Retrieval
| Metric | Definition |
|---|---|
| recall@k | share of cases where at least one expected page is in the top k chunks (called hit@k in rag-demo); also the share of expected pages found |
| precision@k | share of top k chunks whose page is an expected page |
| MRR | mean reciprocal rank of the first expected page |
| nDCG@10 | graded relevance ranking quality |
| context recall | share of reference answer statements supported by the retrieved context (LLM judged, calibrated) |
| context precision | share of retrieved chunks actually useful for the reference answer (LLM judged, calibrated) |
| ANN recall@k | overlap of ANN top k with exact search top k |
| index cost | build time, memory, query latency |

## 2. Generation
| Metric | Definition |
|---|---|
| faithfulness | share of answer claims supported by the provided context |
| answer relevancy | does the answer address the question (judge score) |
| answer correctness | agreement with the reference answer on answerable cases |
| citation accuracy | citations point to chunks that support the cited sentence |
| refusal correctness | refuses unanswerable cases and answers answerable ones (precision and recall of refusal) |

## 3. Pipeline (end to end)
Correct, grounded, cited answer rate per question type; self-RAG vs plain RAG; with and without cache and memory.

## 4. System
Latency p50 and p95 per stage and total; tokens per query; cost per query; cache hit rate and wrong hit rate; fallback rate; provider error rate; refusal rate; throughput under a small load test.

## 5. Safety
Prompt injection block rate, PII leak rate, off topic refusal rate, unsupported claim rate, RBAC denial correctness.

## 6. Voice and image
Word error rate on a recorded set; correct error text extraction from screenshots; end to end answer correctness on image cases.

## Schedule
| Run | Trigger | Data | Cost control |
|---|---|---|---|
| on demand | admin or CLI | chosen layer | budget guard |
| nightly | GitHub Actions cron | random sample of the last 24 h of traces plus 10 fixed golden cases | uses cache; skips if quota is low |
| weekly | GitHub Actions cron | full golden set, all layers | free tiers; OpenAI judge only if budget allows |
| CI | pull request | retrieval eval only (no LLM) | free |

Cron times and sample sizes are set in the workflow files when built.

## Regression gate
A run is flagged when a core metric drops by more than a tolerance versus the last good run. Starting tolerances are placeholders (for example 3 points on retrieval metrics) and are tuned after enough runs show real noise. Every flag shows the diff.

## Reporting
The README table lists metric, value, dataset, date and config id. Dashboard charts read from the eval_results table.
