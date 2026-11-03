---
name: free-tier-router
description: How to add or change a model provider in the router safely. Use when editing src/ragx/router or docs/FREE-APIS.md.
---
# Free tier router rules
- Providers and model names live in config, each with a last verified date and a source URL from docs/FREE-APIS.md.
- Every tier has at least two providers. The last resort is OpenAI, capped by OPENAI_BUDGET_USD and logged per call.
- Handle 429, 5xx and timeouts with a circuit breaker and fallback; never surface raw provider errors.
- Track per provider RPM and RPD from the provider_usage table; skip a provider that is near its limit.
- Keep the judge model family different from the answer model family.
- Free tiers may train on prompts: only public docs text and demo questions are sent.
- Never log keys or full prompts. Tests use a mock provider; live tests are gated by env.
