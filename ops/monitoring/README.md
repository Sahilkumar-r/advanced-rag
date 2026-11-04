# Online evals in Prometheus and Grafana

The app records the online signals from `docs/EVALS.md` section 7 as Prometheus metrics. Prometheus scrapes `/metrics`; Grafana draws them.
Nothing here sends data to a third party: both run on your machine and bind to 127.0.0.1.

## What is recorded (all in `src/ragx/observability/metrics.py`)
| Signal | Metric |
|---|---|
| answered, refused, blocked by a guardrail, cache kind, text or image | `ragx_ask_total` |
| answer latency | `ragx_ask_seconds` (histogram) |
| tokens, provider calls and errors, fallbacks, paid spend | `ragx_tokens_total`, `ragx_llm_calls_total`, `ragx_llm_seconds`, `ragx_llm_fallbacks_total`, `ragx_cost_usd_total` |
| guardrail triggers by kind | `ragx_guardrail_total` |
| thumbs up and down | `ragx_feedback_total` |
| reference free quality | `ragx_online_faithfulness` and `ragx_online_judged_total`: a sampled slice of live answers (default 5 percent, `RAGX_ONLINE_JUDGE_RATE`) is scored by the judge after the response is sent |
| HTTP traffic | `ragx_http_requests_total`, `ragx_http_request_seconds` |

Question text is never a label or a log field.

Not recorded yet: reformulation rate, source click and copy rates, abandoned answers, drift against the previous week, and the human review queue
from EVALS.md. Those need client events and a store that do not exist.

## Start it
1. Start the app with `METRICS_TOKEN` set in `.env` (any long random string). Without it `/metrics` answers 404.
2. Put the same value in the file `ops/monitoring/secrets/metrics_token` (gitignored).
3. Set `GRAFANA_ADMIN_PASSWORD` in your shell (compose refuses to start without it).
4. Start Docker Desktop, then `docker compose -f ops/monitoring/docker-compose.yml up -d`.
5. Prometheus: http://127.0.0.1:9090 (Status, Targets should show `ragx` as UP). Grafana: http://127.0.0.1:3000, dashboard "ragx online evals".

The app listens on 127.0.0.1:8000; the Prometheus container reaches it as `host.docker.internal:8000`.

## Status
The configs are validated by `tests/test_ops_configs.py` (YAML parses, images pinned, ports local only, no secret in any file, every metric a query
uses exists in the app). The `/metrics` endpoint was checked live against the running app. **The Docker stack itself has not been started yet**
(Docker Desktop was not running when this was built), so scraping by Prometheus and the Grafana panels are untested.

## Alerts
`rules.yml` defines flags for fallback rate, provider errors, refusal rate, injection spikes, low online faithfulness and high thumbs down.
Every threshold is a placeholder; tune them after a few weeks of real traffic.

## Why not LangGraph
LangGraph orchestrates agent workflows; it does not store or chart eval results. Langfuse is the tool `docs/02-TRD.md` mentions for traces
(optional). It can be added later next to this; the JSONL traces in `traces/` already carry a trace id for it.
