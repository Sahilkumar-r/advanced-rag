# Portfolio text (draft, for the owner to edit)

Every number below is in the project README with its dataset, date and caveats. Labels and test sets were written by Claude and are not human
reviewed; voice and image results are on synthetic data. Edit freely, but do not add a number that is not in the README.

## One line
A docs assistant for FastAPI and Pydantic that measures every layer of itself, and reports the experiments that did not work.

## Short version
ragx answers questions about the FastAPI and Pydantic docs with citations, refuses when the docs do not cover the question, and takes typed, spoken or
screenshot questions. It runs on free tier model providers, so answering costs nothing. The point of the project is the measurement: retrieval, generation,
the full pipeline, system behaviour, safety, voice and image each have an eval, a fixed test set and a recorded result, including the results that got worse.

## What is in it
- Hybrid retrieval (BM25 plus dense, fused with RRF) over about 900 chunks, chosen over rerank and MMR because the others scored lower on the same questions.
- Self-RAG and plain RAG compared on the same 43 questions, with an LLM judge from a different model family than the answerer.
- A model router with fallback, a circuit breaker and a capped paid last resort that is off by default, a semantic cache tuned for wrong hits,
  argon2 and JWT auth with an RBAC matrix test, rule based guardrails, six memory types with consent and delete.
- A mobile first PWA (Lighthouse mobile: accessibility 100, best practices 100, SEO 100), online evals in Prometheus and Grafana, and CI on GitHub Actions
  with a regression gate.

## Results worth quoting (small sets, so differences under about 5 points are noise)
- Retrieval: hybrid nDCG@10 0.88 on the development split and 0.84 on the held out split; reranking made it worse.
- Generation: faithfulness 0.91 to 0.93 and citations on 96 to 100 percent of answers; self-RAG did not beat plain RAG on faithfulness and cost about twice
  the tokens, though it answered more of the answerable questions.
- Safety: 22 of 24 attack prompts blocked and none of 17 look alike questions blocked, on a set the same author tuned against.
- A bug the tests missed and a browser found: citations written with fullwidth brackets were not counted, which made citation coverage look like 33 to 74
  percent when it was 83 to 100 percent. Found, fixed with a test, and the results re measured and corrected in the README.

## Honest limits
Free tier models are slow at busy times (median 2.6 s for plain RAG in one run, 46 s for self-RAG when providers throttled). The demo disk is ephemeral.
Test sets are small and written by the author. Context recall and context precision are not measured. Not tried on real phone recordings or real photos.
