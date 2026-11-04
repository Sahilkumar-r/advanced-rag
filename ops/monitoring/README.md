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
The short way, with Docker Desktop running:
```
python scripts/init_env.py          # adds any missing secrets to .env (JWT_SECRET, METRICS_TOKEN, GRAFANA_ADMIN_PASSWORD, demo passwords); prints names only
python scripts/seed_users.py        # demo users
python scripts/serve.py             # the app on 127.0.0.1:8000, with /metrics protected by METRICS_TOKEN
python scripts/monitoring.py up     # writes the gitignored token file and runs docker compose up -d
python scripts/monitoring.py status # checks the Prometheus target, rules, Grafana, the dashboard and the data source
```
The same steps by hand: set `METRICS_TOKEN` in `.env` (without it `/metrics` answers 404), put the same value in `ops/monitoring/secrets/metrics_token`
(gitignored), set `GRAFANA_ADMIN_PASSWORD` (compose refuses to start without it; the generated one is in your `.env`), and run
`docker compose -f ops/monitoring/docker-compose.yml up -d`.
Prometheus: http://127.0.0.1:9090 (Status, Targets shows `ragx` as UP). Grafana: http://127.0.0.1:3000, user `admin`, dashboard "ragx online evals".

The app listens on 127.0.0.1:8000; the Prometheus container reaches it as `host.docker.internal:8000`. Stop the stack with `python scripts/monitoring.py down`.

## Status
Run and checked on 2026-11-05 on Windows with Docker Desktop (Prometheus v2.53.0, Grafana 11.1.0): the Prometheus target for the app is UP and scrapes
with the bearer token, all 7 alert rules load, Grafana is healthy with the dashboard provisioned and the data source testing OK, and **all 13 dashboard
panels returned data** when each panel's query was run through Grafana's own API after live traffic (answers, a cache hit, a refusal, a blocked injection,
thumbs, and sampled judge scores). The configs are also validated by `tests/test_ops_configs.py`.
Two things to know: counters only show change that happens while Prometheus is scraping, so a panel is empty or flat until there is traffic after the
stack starts; and the online faithfulness panel was checked with the judge sampling every answer (4 samples), which is not the default 5 percent.
Not checked: alert firing (no threshold was crossed), long running retention, and the stack on a deployed server.

## Alerts
`rules.yml` defines flags for fallback rate, provider errors, refusal rate, injection spikes, low online faithfulness and high thumbs down.
Every threshold is a placeholder; tune them after a few weeks of real traffic.

## Why not LangGraph
LangGraph orchestrates agent workflows; it does not store or chart eval results. Langfuse is the tool `docs/02-TRD.md` mentions for traces
(optional). It can be added later next to this; the JSONL traces in `traces/` already carry a trace id for it.
