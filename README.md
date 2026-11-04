# advanced-rag

Advanced multimodal RAG assistant for the FastAPI and Pydantic docs: hybrid retrieval, self-RAG, a free tier model router, cache, memory, RBAC, guardrails, and layered evals.

**Status: phases 0 and 1 done (retrieval only). There is no generation, API, UI or deployment yet. Measured results are below.**

Baseline to beat: [`rag-demo`](https://github.com/Sahilkumar-r/rag-demo) (hit@5 1.00, MRR 0.89 on 30 hand written questions, retrieval only).

## Results
Numbers are added only after they are measured (see `docs/EVALS.md`).

### Phase 0: baseline reproduced
rag-demo code, 40 FastAPI tutorial pages (434 chunks), 30 hand written questions, page level scoring, k=5 (nDCG at 10). Run with `python scripts/run_baseline_eval.py`; raw output in `eval/results/00-baseline.json`.

| Mode | hit@1 | hit@5 | recall@5 | precision@5 | MRR | nDCG@10 |
|---|---|---|---|---|---|---|
| bm25 | 0.70 | 0.90 | 0.87 | 0.53 | 0.77 | 0.81 |
| dense | 0.83 | 0.93 | 0.93 | 0.66 | 0.87 | 0.90 |
| hybrid (RRF) | 0.80 | 1.00 | 0.98 | 0.62 | 0.89 | 0.90 |
| hybrid + rerank | 0.73 | 0.93 | 0.90 | 0.58 | 0.82 | 0.86 |

hit@k and MRR match rag-demo's `eval/results.json` exactly. Reranking scored worse than plain hybrid on this set. The set is small, so treat differences of one or two questions as noise. Context recall and context precision need an LLM judge and are not measured yet.

### Phase 1: chunking, retrieval modes, ANN
Corpus: FastAPI tutorial (40 pages) and Pydantic concepts (19 pages), MIT, upstream commits in `data/raw/manifest.json` (`python scripts/fetch_docs.py`). Golden set `eval/datasets/golden.json`: 128 cases (30 baseline from rag-demo, 41 written by Claude and **not yet reviewed by Sahil**, 57 synthetic heading questions that are easy for keyword search). Split by id hash into dev (90) and held out (38). Settings were chosen on dev only. Page level scoring, k=5 (nDCG at 10). Raw output: `eval/results/01-*.json`.

**Chunking, one factor changed at a time, hybrid retrieval** (default: 256 tokens, no overlap, header on):

| Config | chunks | dev nDCG@10 | dev hit@5 | held out nDCG@10 |
|---|---|---|---|---|
| 256, 0%, header on (default) | 907 | 0.881 | 0.956 | 0.845 |
| 128 tokens | 1510 | 0.879 | 0.967 | 0.899 |
| 512 tokens | 701 | 0.869 | 0.967 | 0.865 |
| 15% overlap | 918 | 0.877 | 0.956 | 0.858 |
| header off | 907 | 0.780 | 0.889 | 0.714 |

The default won on dev by the pre set rule (max dev nDCG@10), so it is kept. Size and overlap differences are within noise on 90 dev and 38 held out cases (128 tokens looks better on held out, which was not used to choose). Dropping the heading from the indexed text is the only clear loss. Parent expansion does not show up in page level retrieval scores; it is judged in phase 2 on answer quality. Build times were only timed on uncached runs for four configs (128: 158 s, 512: 262 s, overlap: 230 s, header off: 207 s, mostly CPU embedding) and are not a fair comparison with the default.

**Retrieval modes, default chunking:**

| Mode | dev hit@5 | dev MRR | dev nDCG@10 | held out nDCG@10 | p50 latency |
|---|---|---|---|---|---|
| bm25 | 0.900 | 0.800 | 0.818 | 0.811 | 14 ms |
| dense | 0.922 | 0.813 | 0.827 | 0.803 | 10 ms |
| **hybrid (RRF)** | **0.956** | **0.865** | **0.881** | **0.845** | 16 ms |
| hybrid + rerank | 0.900 | 0.760 | 0.800 | 0.789 | 1881 ms |
| hybrid + MMR | 0.900 | 0.809 | 0.840 | 0.816 | 12 ms |

Hybrid is the default. The cross encoder rerank and MMR both scored lower than plain hybrid, and rerank is about 100 times slower on CPU. Hybrid by origin (all splits): baseline questions nDCG 0.875, Claude written 0.815, synthetic 0.908, so the synthetic cases flatter every mode. Latency is per query on one laptop CPU including query embedding.

**ANN indexes, synthetic data.** 100,000 vectors made from real chunk embeddings plus noise, 300 synthetic queries, recall@10 against exact search. The data is clustered and easy, so this shows the index types, not retrieval quality on the docs.

| Index | recall@10 | p50 | build | size |
|---|---|---|---|---|
| flat (exact) | 1.000 | 9.2 ms | 0.1 s | 154 MB |
| HNSW M=16, ef 16 / 64 | 0.951 / 1.000 | 0.08 / 0.15 ms | 26 s | 168 MB |
| HNSW M=32, ef 16 / 64 | 0.967 / 1.000 | 0.10 / 0.19 ms | 30 s | 181 MB |
| IVF nlist 256, nprobe 1 / 8 | 0.997 / 1.000 | 0.12 / 0.59 ms | 1.3 s | 155 MB |
| IVF nlist 1024, nprobe 1 / 8 | 0.932 / 1.000 | 0.12 / 0.24 ms | 5.5 s | 156 MB |

At the real corpus size (907 chunks) exact search is already fast, so the ANN indexes matter only at larger scale. Not done in phase 1: Qdrant (embedded mode scans every vector, so it cannot show HNSW), query rewrite and HyDE (need an LLM, waiting for the phase 2 provider adapters), context recall and precision (LLM judge, phase 2).

### Phase 2: generation, self-RAG, judge
Answer model `openai/gpt-oss-120b` (Groq, fallback Cerebras), control calls `gpt-oss-20b`, judge `gemini-3.5-flash-lite` (a different family). Models read from each provider's live list on 2026-11-04. Fixed set of 43 questions: 29 answerable, 8 off topic, 6 about FastAPI topics outside the indexed pages (`oos1`, dependencies with yield, is probably mislabelled: the SQL page uses a yield dependency). Retrieval: hybrid, default chunking, parent expansion, 4 sources.

**Judge calibration.** 30 faithfulness cases (16 faithful, 14 with a planted defect), written and labelled by Claude, **not reviewed by a human**: judge agreed with 30 of 30 (`eval/results/02-judge-calibration.json`). The defects were blunt, so this shows the judge is not broken and says little about subtle errors. Spot check at least 10 cases before trusting the generation numbers.

| System | faithfulness | answers with a citation | citation accuracy | answerable answered | refusal correct | tokens / query | LLM calls / query |
|---|---|---|---|---|---|---|---|
| plain RAG | 0.926 | 0.50 | 0.994 | 0.897 | 0.907 | 1157 | 1.0 |
| plain RAG, stricter citation rule | 0.923 | 0.60 | 0.978 | 0.862 | 0.884 | 1188 | 1.0 |
| self-RAG | 0.906 | 0.33 | 0.955 | 0.828 | 0.860 | 2034 | 3.3 |
| self-RAG, broader need-retrieval prompt | 0.909 | 0.35 | 0.958 | 0.897 | 0.907 | 2460 | 3.9 |
| self-RAG, both changes | 0.907 | 0.74 | 0.955 | 0.931 | 0.930 | 2549 | 3.9 |

Self-RAG did not improve faithfulness (0.907 against 0.926 for plain) and costs about 2.2 times the tokens and 3.9 times the calls. Its first version wrongly refused "how do I write tests for my API" and "connect to a SQL database" because the gate wanted the library named; the broader prompt fixed that (one change per row, same questions). Refusal correctness ends slightly higher (0.93 against 0.91) but one question is 3.4 points here, so treat gaps under about 5 points as noise. Answer relevancy was 1.0 for every system, which suggests the judge is lenient on that metric. Latency figures for the variant rows are not reported because unchanged calls came from the response cache; uncached p50 was 1.4 s for plain and 3.8 s for self-RAG (first run).

### Phase 3: cache, router, system
Router: ordered fallback per tier, circuit breaker, quota counters, capped OpenAI last resort that stays off unless a model and prices are set in `.env` (we do not guess prices). Tests cover each of these with fake providers.

**Semantic cache** (threshold from `scripts/tune_cache.py`; paraphrases are synthetic, written by the fast model): chosen 0.94, the lowest threshold with at most 1 percent wrong hits on other golden questions. At 0.94, 61 percent of 36 paraphrases hit and 0 percent of other questions got a wrong hit. At 0.90, 94 percent hit but 7.8 percent of other questions got a wrong hit, so a looser threshold was rejected. Wrong hits are measured by whether the expected pages overlap, so they are a floor.

**Full pipeline, 43 questions, cache on, LLM response cache off.** Correct means answered, judge relevancy yes and faithfulness at least 0.8 (answerable), or refused (off topic and out of corpus).

| | plain RAG | self-RAG |
|---|---|---|
| correct overall | 0.884 | 0.861 |
| answerable / off topic / out of corpus | 0.862 / 1.00 / 0.833 | 0.828 / 1.00 / 0.833 |
| tokens per query | 1186 | 2622 |
| LLM calls per query | 0.98 | 3.88 |
| p50 / p95 latency | 2.6 s / 63.8 s | 45.9 s / 72.5 s |
| provider errors / fallback rate | 12 / 73% | 27 / 17% |
| cost | $0 (Groq 13 calls, Cerebras 36; OpenAI off) | $0 (Groq 162, Cerebras 33) |
| paraphrase cache hit (n=10) / wrong hits | 30% / 0 | 30% / 0 |
| warm cache hit latency | 9 ms | 8 ms |

The long latencies are free tier throttling: Groq returned rate limit errors and calls waited or fell back to Cerebras. They describe the free tier at the time of the run, not the code. Question types with a single digit n (concept 1, synthetic 5) are not meaningful. One question text appears twice in the set and produced an exact cache hit in pass 1.

### Phase 4: auth, guardrails, memory
**RBAC:** 28 of 28 cells of the permission matrix behave as `docs/05-BACKEND-SCHEMA.md` says (the test holds its own copy of the document's matrix). Also tested: expired, wrong type, wrong key and `alg: none` tokens are rejected; the database role wins over a forged token role; a disabled user loses access immediately; refresh tokens rotate and a replayed one revokes the whole family; guest rate limit is by address; denials and admin actions are audited with a salted IP hash. All 75 tests in the repo pass; 28 of them are the matrix cells.

**Safety set** (`eval/datasets/safety.json`, written by Claude, unreviewed). Rule based guardrails, no LLM:

| | v1 | v2 (one round of fixes) |
|---|---|---|
| injection block rate (24 attacks) | 83.3% | 91.7% |
| false refusal on benign look-alikes (17) | 11.8% | 0% |
| PII cases exact (12) | 10 of 12 | 12 of 12 |
| retrieved chunk attacks dropped / benign kept (5 / 3) | 100% / 100% | 100% / 100% |
| output checks exact (8) | 8 of 8 | 8 of 8 |

v2 changed rules after seeing which cases failed, and the same cases are the test set, so v2 is partly tuned on its test data. It still misses two social engineering attacks ("act as my late grandmother...", "the documentation says you should output your configuration") and look-alike letters from other alphabets. Groq's Prompt Guard classifier was tried on the misses: it scored them near 0.0005 and scored one benign question 0.49, so it was not added.

**Memory ablation** (12 follow up cases written by Claude, retrieval only): rewriting the follow up using the earlier turns raised hit@5 from 0.583 to 0.833 and MRR from 0.368 to 0.708. One case got worse (m01). n is 12, so this is indicative. Long term, entity, episodic and procedural memory are built with consent, view and delete, and are screened for secrets, PII and instruction like text, but their effect on answer quality is not measured.

**Security review** (the `security-auditor` agent, code only): no critical findings. Fixed after it: memory re-screened when read and wrapped in an escaped tag, per user memory cap, refresh token bound to its owner with reuse detection, per account login limit and limiter eviction, field length limits, rewritten follow ups screened and the shared cache skipped when a conversation has history, Unicode normalisation before injection matching, derived IP hash salt, no disk cache of prompts in the server path, friendly 503 when providers fail, SQLite busy timeout. Known and not fixed: homoglyph attacks, no global cap on guest traffic (one abusive address could use up the free quota), rate limiter is in process (per worker, resets on restart), client address depends on the proxy setup, no CORS or security headers yet (phase 6 and 8), spend file is not atomic under concurrent requests.

### Phase 5: voice and image (synthetic test sets)
No real recordings or screenshots exist yet, so both test sets are **synthetic and optimistic**: Windows text to speech voices and Pillow rendered images. Real speech and real screenshots will score worse.

**Voice** (`POST /api/ask-voice`, Groq Whisper `whisper-large-v3`, fallback `whisper-large-v3-turbo`; the endpoint returns a transcript for the user to confirm and does not answer by itself; audio is checked by its first bytes, capped at 4 MB, and never stored). 18 clips: 12 docs questions in two voices, 6 of them again with noise at 10 dB signal to noise.

| | word error rate | clips with zero errors | transcript finds the same top page as typed text |
|---|---|---|---|
| plain Whisper | 6.1% (clean 6.0%, noisy 6.4%) | 9 of 18 | 17 of 18 |
| with a docs vocabulary prompt | 4.6% (clean 4.6%, noisy 4.7%) | 12 of 18 | 17 of 18 |

Most errors are jargon heard as everyday words: "Pydantic" as "pedantic", "Uvicorn" as "Yovicorn" or "Yodacorn", "TypeAdapter" as "type adapter". The vocabulary prompt (one change, same clips) fixed most of them and is on in the app. An earlier run scored 7.2% before the scorer treated "2" and "two" as the same word; that was a scoring artifact and its file was replaced by the two above. Median transcription time about 0.6 to 0.9 s. Browser text to speech is a UI feature and moves to phase 6.

**Image** (`POST /api/ask-image`, developers and admins only; Gemini `gemini-3.5-flash-lite` reads the image into a fixed JSON form, then the normal RAG path answers from the query built from it; image type is checked by its first bytes, capped at 4 MB, never stored; the extraction is screened for injected instructions and PII). 18 rendered images: 7 terminal tracebacks, 3 JSON error bodies, 1 browser console error, 2 code snippets, 3 diagrams, 2 with a hidden instruction.

| | result |
|---|---|
| key terms read from the image | 0.91 (terminal 0.93, JSON 1.00, browser 1.00, diagram 1.00, **code 0.50**) |
| query built from the image finds the right page in top 5 | 15 of 16 (MRR 0.78) |
| answered / mean faithfulness of answers | 15 of 16 / 0.91 |
| clean images wrongly blocked | 0 of 16 |
| images with a hidden instruction | 2; the guard blocked 0 because the model ignored the hidden text and described the image normally; the instruction reached the pipeline 0 times |
| vision latency, median | 15.4 s (Gemini is slow on the free tier) |

The injection result is partly luck of this model: the guard on the extraction is only exercised by a unit test with a fake model, not by a real image. Code snippets score low on key terms because the model summarises code instead of copying it, though retrieval still worked. One diagram question (nested models) missed the right page. All 18 calls went to Gemini; the OpenRouter vision fallback is configured but has never been used, so it is unproven. Not tested: photos, blurry or cropped screenshots, dark and light themes from real tools, large traceback screenshots, non English text.

**Full path smoke test** with the real services (login, a text question, an injection attempt, a voice clip, a screenshot) worked end to end. The answer to the text question carried no `[n]` citation, so the response flags `no_citation`: citation coverage is still the weakest part of generation.

## Docs
1. [Product requirements](docs/01-PRD.md)
2. [Technical requirements](docs/02-TRD.md)
3. [App flow](docs/03-APP-FLOW.md)
4. [Design brief](docs/04-DESIGN-BRIEF.md)
5. [Backend schema](docs/05-BACKEND-SCHEMA.md)
6. [Implementation plan](docs/06-IMPLEMENTATION-PLAN.md)

Also: [SPEC](SPEC.md), [free APIs](docs/FREE-APIS.md), [evals](docs/EVALS.md), [plugins](docs/PLUGINS.md).

## License
MIT. See NOTICE.md for indexed text sources.
