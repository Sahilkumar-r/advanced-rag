# Free and low cost model APIs

Researched 2026-11-04 by web search. **All figures come from third party pages and conflict in places. None is a quote. Re-check the vendor page before relying on a number, and again before each eval run.** Router defaults in config are copied from here and must carry the check date.

## Candidate providers
| Provider | Use in this project | Free tier (as found) | Data terms | Sources |
|---|---|---|---|---|
| Groq | answer + fast tiers, Whisper STT | gpt-oss-120b, gpt-oss-20b, qwen3.8-27b about 30 RPM, 1,000 RPD, 8K TPM, 200K TPD; Whisper large v3 about 20 RPM, 2,000 RPD; smaller 8B models reported up to 14,400 RPD (conflicting) | not used for training per one summary; verify | console.groq.com/docs/rate-limits; flatkey.ai/blog/free-llm-apis-2026; github.com/nejib1/Free-LLM |
| Google AI Studio (Gemini Flash, Flash-Lite) | vision + long context + alternate answer | free of charge on listed Flash and Flash-Lite models; per model limits visible only in AI Studio | **free tier content may be used to improve Google products**; only public docs and demo questions go here | ai.google.dev/gemini-api/docs/pricing; ai.google.dev/gemini-api/docs/rate-limits |
| OpenRouter | breadth of open models behind one key | models ending in :free: 20 RPM, 50 requests per day (1,000 after a $10 credit purchase, not done without Sahil agreeing); failed calls count | depends on upstream provider | openrouter.ai/pricing; openrouter.ai/docs/api/reference/limits |
| Cerebras | fast batch for evals | sources disagree: about 1M tokens per day free vs trial credit ($5, 30 days) | not used for training per one summary | inference-docs.cerebras.ai/support/rate-limits; requesty.ai/blog/free-llm-apis |
| NVIDIA NIM (build.nvidia.com) | alternate open models (Nemotron, DeepSeek) | about 40 RPM, phone verification, meant for prototyping | check terms | build.nvidia.com; github.com/nejib1/Free-LLM |
| Mistral La Plateforme | alternate | free Experiment tier, about 1 request per second | **opt in to training on free tier** | github.com/nejib1/Free-LLM; openrouter.ai/blog/tutorials/free-llm-apis-compared |
| Cloudflare Workers AI | optional small models | 10,000 neurons per day | check terms | developers.cloudflare.com/workers-ai/platform/pricing |
| Hugging Face | model and dataset downloads, Space hosting; Inference Providers have no free credit for free accounts | n/a for inference | n/a | huggingface.co/docs/inference-providers/pricing |
| OpenAI (Sahil has about $5 credit) | last resort fallback and optional judge, capped | paid | API data not used for training by default per OpenAI policy; verify | platform.openai.com/docs |
| OmniRoute (diegosouzapw/OmniRoute) | optional self hosted gateway that routes many free providers with fallback | software is free (MIT); you bring provider keys | inherits provider terms | github.com/diegosouzapw/OmniRoute; omniroute.online |

## Excluded or skipped
- **GitHub Models**: reported retired on 2026-07-30 (flatkey.ai, citing GitHub docs). Older lists still show it. Excluded.
- **xAI Grok**: no permanent free API tier found. Skipped unless Sahil supplies a key. (Sahil confirmed "Grok" meant Groq.)
- Cohere trial: 1,000 calls per month, non commercial, evaluation only. Not used.
- Pollinations, LLM7, Routeway, Api.Airforce and similar aggregators: unclear terms and reliability. Not used in the demo.

## Proposed tier assignment (to validate by eval, not final)
| Tier | Primary | Fallbacks |
|---|---|---|
| fast (rewrite, grade) | Groq small model | OpenRouter :free small model, Cerebras |
| answer | Groq gpt-oss-120b | Gemini Flash-Lite, OpenRouter :free, NVIDIA |
| vision | Gemini Flash-Lite | OpenRouter :free vision model if available |
| stt | Groq Whisper | none free; show text input |
| judge | a different family than answer (Gemini when answer is Groq) | OpenAI within budget |
| embeddings | local ONNX (no API) | none needed |

## Practical rules
1. Never rely on one free provider; keep at least two per tier.
2. Free model IDs expire. Keep model names in config, not code, with a last verified date.
3. Quota math: 30 RPM and about 1,000 RPD means a 100 question eval with self-RAG (3 to 5 calls each) uses a large share of a day. Eval runs use the cache, small samples and off peak hours.
4. Do not send private data to free tiers. This project only sends public docs text and demo questions.
5. OpenAI spend is capped by OPENAI_BUDGET_USD and logged per call.
