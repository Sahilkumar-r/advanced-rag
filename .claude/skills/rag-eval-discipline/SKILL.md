---
name: rag-eval-discipline
description: Rules for running and reporting RAG evals honestly in this repo. Use whenever you change retrieval, prompts, chunking, router or cache, or report any metric.
---
# RAG eval discipline
1. One change per experiment, golden set fixed, held out split untouched until the end.
2. Log config id, git sha, models and date with every result.
3. Report all layers affected (retrieval, generation, pipeline, system), not just the one that improved.
4. Negative results go in the README table.
5. LLM judges: a different model family than the answer model; calibrate on hand labelled cases; report agreement; never trust one judge alone.
6. Synthetic data is labelled synthetic wherever it is used.
7. A number without a run id and a date is a target, not a result.
8. Thresholds (guardrail, semantic cache) are tuned on the dev split and checked on the held out split.
Definitions live in docs/EVALS.md.
