"""Generate the Grafana dashboard for the online evals: python scripts/make_dashboard.py
Writes ops/monitoring/grafana/dashboards/ragx.json. Every query uses a metric defined in src/ragx/observability/metrics.py
(tests/test_dashboard.py checks that). Colours are left to Grafana's accessible defaults; no panel relies on colour alone.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ops" / "monitoring" / "grafana" / "dashboards" / "ragx.json"
DS = {"type": "prometheus", "uid": "ragx-prom"}
PANELS = []


def panel(title, exprs, kind="timeseries", unit="short", desc="", w=8, legends=None):
    i = len(PANELS)
    PANELS.append({
        "id": i + 1, "type": kind, "title": title, "description": desc, "datasource": DS,
        "gridPos": {"h": 8, "w": w, "x": (i * 8) % 24 if w == 8 else 0, "y": (i // 3) * 8},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "bottom"}} if kind == "timeseries" else {"reduceOptions": {"calcs": ["lastNotNull"]}},
        "targets": [{"refId": chr(65 + k), "datasource": DS, "expr": e, "legendFormat": (legends or [""] * len(exprs))[k]} for k, e in enumerate(exprs)],
    })


R = "$__rate_interval"
panel("Questions per minute by outcome", [f"sum by (outcome) (rate(ragx_ask_total[{R}])) * 60"], desc="answered, refused or blocked by a guardrail", legends=["{{outcome}}"])
panel("Refusal rate", [f"sum(rate(ragx_ask_total{{outcome=\"refused\"}}[{R}])) / clamp_min(sum(rate(ragx_ask_total[{R}])), 1e-9)"], unit="percentunit", desc="share of questions the assistant declined to answer")
panel("Cache hit rate", [f"sum(rate(ragx_ask_total{{cache!=\"none\"}}[{R}])) / clamp_min(sum(rate(ragx_ask_total[{R}])), 1e-9)"], unit="percentunit")
panel("Answer latency p50 and p95", [f"histogram_quantile(0.5, sum by (le) (rate(ragx_ask_seconds_bucket[{R}])))", f"histogram_quantile(0.95, sum by (le) (rate(ragx_ask_seconds_bucket[{R}])))"], unit="s", desc="includes cache hits; free tier throttling dominates the tail", legends=["p50", "p95"])
panel("Tokens per minute", [f"sum by (kind) (rate(ragx_tokens_total[{R}])) * 60"], legends=["{{kind}}"])
panel("Provider calls per minute", [f"sum by (provider, status) (rate(ragx_llm_calls_total[{R}])) * 60"], legends=["{{provider}} {{status}}"])
panel("Fallback rate", [f"sum(rate(ragx_llm_fallbacks_total[{R}])) / clamp_min(sum(rate(ragx_llm_calls_total{{status=\"ok\"}}[{R}])), 1e-9)"], unit="percentunit", desc="share of successful calls served by a provider other than the first choice")
panel("Guardrail triggers per hour", [f"sum by (kind) (rate(ragx_guardrail_total[{R}])) * 3600"], legends=["{{kind}}"], desc="input, image and output checks, by kind")
panel("Thumbs per hour", [f"sum by (value) (rate(ragx_feedback_total[{R}])) * 3600"], legends=["{{value}}"])
panel("Online faithfulness (sampled, judge)", ["sum(rate(ragx_online_faithfulness_sum[1h])) / clamp_min(sum(rate(ragx_online_faithfulness_count[1h])), 1e-9)"], unit="percentunit", desc="reference free score on a sampled slice of live answers; read it together with the sample count below")
panel("Judged samples", ["sum by (result) (increase(ragx_online_judged_total[1h]))"], legends=["{{result}}"], desc="how many sampled answers were scored, failed to parse, or errored")
panel("Paid spend (USD)", ["sum(ragx_cost_usd_total)"], kind="stat", unit="currencyUSD", desc="0 while only free tier providers answer")
panel("HTTP requests by status", [f"sum by (status) (rate(ragx_http_requests_total[{R}])) * 60"], legends=["{{status}}"])

dash = {"uid": "ragx-online", "title": "ragx online evals", "tags": ["ragx"], "schemaVersion": 39, "version": 1, "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
        "timezone": "browser", "panels": PANELS,
        "description": "Online signals from live traffic (docs/EVALS.md section 7). Thresholds for flags live in ops/monitoring/rules.yml and are placeholders."}

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dash, indent=1), encoding="utf-8")
    print(len(PANELS), "panels ->", OUT)
