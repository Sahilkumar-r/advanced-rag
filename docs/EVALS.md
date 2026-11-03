# EVALS

What is measured, for which part of the system, how, and when. **No results yet.** Every metric below is a definition, not a number.

## 0. Map: which evals measure which part

| Part | Question it answers | Metrics | Data | Judge | When it runs |
|---|---|---|---|---|---|
| 1. Retrieval | Did we fetch the right chunks? | recall@k, precision@k, MRR, nDCG@10, context recall, context precision, ANN recall vs exact | golden set (expected pages) | none for the first five; LLM for context recall and precision | CI on every PR (no LLM subset), on demand, weekly |
| 2. Generation | Given the chunks, is the answer good? | faithfulness, answer relevancy, answer correctness, citation accuracy, refusal correctness | golden set with reference answers, retrieval held fixed (gold chunks) | LLM judge, different family, calibrated on hand labels | on demand, weekly |
| 3. RAG pipeline (end to end) | Does a question go in and a correct, grounded, cited answer come out? | end to end correct rate per question type, self-RAG vs plain RAG, with and without cache and memory, retry rate | golden set, held out split | LLM judge plus exact checks on cited pages | on demand, weekly, before any deploy |
| 4. Full system | Is it fast, cheap, reliable, and does the stack hold under load? | latency p50 and p95 per stage and total, tokens per query, cost per query, cache hit rate and wrong hit rate, fallback rate, provider error rate, throughput, memory use | replayed golden set plus a small load test | none (measured) | on demand, weekly, nightly summary from traces |
| 5. Guardrails and safety | Do the protections block bad input and unsafe output without refusing good questions? | injection block rate, false refusal rate, PII leak rate, off topic refusal rate, unsupported claim catch rate, RBAC denial correctness, memory poisoning resistance | labelled safety set (attacks, benign look-alikes, PII cases, role cases) | rules plus LLM judge for unsupported claims | CI for rule based checks, on demand, weekly |
| 6. Voice and image | Do the extra input paths work? | word error rate, error text extraction accuracy, end to end correctness on voice and image cases | recorded clips and screenshots made by Sahil | exact plus LLM judge | on demand, before release |
| 7. Online (live traffic) | How is it doing for real users right now? | see section 7 | sampled production traces and user feedback | reference free LLM judge on a sample, human review of a small slice | logged continuously, nightly job scores a sample |

Each part has its own eval_runs.kind value: retrieval, generation, pipeline, system, safety, multimodal, online.

## 1. Rules for all evals
- Fixed golden set between comparisons. Hold out 20 percent, never used for tuning. Thresholds are tuned on the dev split and confirmed on the held out split.
- Hand written cases are never replaced by generated ones. Synthetic cases are labelled synthetic and reviewed before they count.
- One change per experiment. Log config id, git sha, models and date with every result.
- The judge model is from a different family than the answer model. Calibrate it on at least 30 hand labelled cases and report the agreement. Never trust a single judge alone.
- Report negative results in the README table.
- A number without a run id and a date is a target, not a result.

## 2. Retrieval evals (part 1)
Run with no generation, so a failure here is a retrieval failure.

| Metric | Definition |
|---|---|
| recall@k | share of cases where at least one expected page is in the top k chunks (called hit@k in rag-demo); also the share of all expected pages found |
| precision@k | share of top k chunks whose page is an expected page |
| MRR | mean reciprocal rank of the first expected page |
| nDCG@10 | graded relevance ranking quality |
| context recall | share of reference answer statements supported by the retrieved context (LLM judged) |
| context precision | share of retrieved chunks that are useful for the reference answer, rank weighted (LLM judged) |
| ANN recall@k | overlap of ANN top k with exact search top k (HNSW and IVF vs flat) |
| index cost | build time, memory, query latency |

Ablations reported here: chunk size, overlap, contextual header, parent expansion, BM25 vs dense vs hybrid, HNSW vs IVF vs flat, rerank, MMR, query rewrite and HyDE.

## 3. Generation evals (part 2)
Run with the gold chunks supplied, so a failure here is a generation failure and not a retrieval one. Also run once with the real retrieved chunks to see the combined effect.

| Metric | Definition |
|---|---|
| faithfulness | share of answer claims supported by the provided context |
| answer relevancy | does the answer address the question (judge score) |
| answer correctness | agreement with the reference answer on answerable cases |
| citation accuracy | each citation points to a chunk that supports the cited sentence |
| refusal correctness | refuses unanswerable cases and answers answerable ones (precision and recall of refusal) |

## 4. RAG pipeline evals (part 3)
The whole path with everything on: guardrails, cache, memory, self-RAG, router. Reports the correct, grounded and cited answer rate overall and per question type (lookup, how to, multi hop, comparison, code, off topic, adversarial). Ablations: plain RAG vs self-RAG, cache on and off, memory on and off, changing one toggle at a time.

## 5. Full system evals (part 4)
Measured from traces, not judged.
- Latency: p50 and p95 per stage (guardrail, cache, retrieval, rerank, each LLM call, total).
- Tokens in and out per query and per tier. Cost per query (zero on free tiers; OpenAI priced from the rate card).
- Cache: hit rate, semantic wrong hit rate (checked on a labelled sample), time saved.
- Reliability: fallback rate, provider error rate, circuit breaker opens, quota exhaustion events, requests refused because of an outage.
- Throughput and memory use under a small load test (sized for the Hugging Face Space).
- Scheduler health: did the cron runs happen and finish.

## 6. Guardrail and safety evals (part 5)
A labelled set with attack cases and benign look-alikes, so both over blocking and under blocking are measured.

| Check | Metric |
|---|---|
| Prompt injection (user text, retrieved text, memory) | block rate, and false refusal rate on benign look-alikes |
| PII in input and output | detection rate, leak rate |
| Off topic | refusal rate |
| Unsupported claims | share of unsupported answers that the output check catches |
| Citation validity | share of answers whose citations resolve |
| RBAC | every cell of the permission matrix returns the expected allow or deny |
| Memory | poisoned memory entries do not change policy; a user delete removes the entry |

Rule based checks run in CI. LLM judged checks run weekly.

## 7. Online evals (part 7): live traffic
Online means measuring real requests after deploy, with no ground truth answer. Everything is logged per trace and aggregated.

| Signal | How |
|---|---|
| User feedback | thumbs up and down rate, per question type and per answer path |
| Behaviour proxies | reformulation rate (same user asks again within a minute), source click rate, copy code rate, abandoned answers |
| Reference free quality | a sampled slice (for example 5 to 10 percent, set in config) scored by the judge for faithfulness and relevancy using only the question, chunks and answer |
| Safety on live data | guardrail trigger rate, refusal rate, injection attempt rate |
| System | latency, token use, cost, cache hit rate, fallback rate, quota left per provider |
| Drift | change in question topic mix, retrieval score distribution, refusal rate and index version compared with the previous week |
| Human review | the lowest scoring and thumbs down traces go into a small review queue; reviewed bad cases are promoted into the golden set (marked source online) |

A signal outside its tolerance flags that day on the admin dashboard. Traces hold no personal data beyond what section 5 of docs/05-BACKEND-SCHEMA.md allows.

## 8. Schedule
| Run | Trigger | Data | Cost control |
|---|---|---|---|
| on demand | admin or CLI | chosen part | budget guard |
| CI | pull request | retrieval eval without LLM, rule based guardrail and RBAC tests | free |
| nightly | GitHub Actions cron | online sample from the last 24 h of traces plus 10 fixed golden cases | uses cache; skips if quota is low |
| weekly | GitHub Actions cron | full golden set for parts 1 to 6, plus the weekly online drift report | free tiers; OpenAI judge only if budget allows |
| pre deploy | manual gate | parts 1 to 5 on the held out split | counted against the OpenAI cap |

Cron times and sample sizes are set in the workflow files when built (phase 7).

## 9. Regression gate
A run is flagged when a core metric drops by more than a tolerance versus the last good run. Starting tolerances are placeholders (for example 3 points on retrieval metrics) and are tuned after enough runs show real noise. Every flag shows the diff against the last good run.

## 10. Reporting
The README table lists part, metric, value, dataset, run id, date and config id. The admin dashboard has one tab per part, reading from the eval_results table.
