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
