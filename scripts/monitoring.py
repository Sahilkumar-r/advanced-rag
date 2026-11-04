"""Start, stop and check the local Prometheus and Grafana stack (the steps in ops/monitoring/README.md).

python scripts/monitoring.py up       write the scrape token file, then docker compose up -d
python scripts/monitoring.py status   is Prometheus scraping the app, is the dashboard loaded, does Grafana see the data source
python scripts/monitoring.py down
Needs METRICS_TOKEN and GRAFANA_ADMIN_PASSWORD in .env (python scripts/init_env.py adds them). Secrets are never printed.
"""
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.config import load_env  # noqa: E402

MON = ROOT / "ops" / "monitoring"
COMPOSE = ["docker", "compose", "-f", str(MON / "docker-compose.yml")]


def need(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        sys.exit(f"{name} is not set in .env. Run: python scripts/init_env.py")
    return v


def up() -> None:
    token = need("METRICS_TOKEN")
    need("GRAFANA_ADMIN_PASSWORD")
    (MON / "secrets").mkdir(exist_ok=True)
    (MON / "secrets" / "metrics_token").write_text(token, encoding="utf-8")  # gitignored; Prometheus reads it as a file
    subprocess.run([*COMPOSE, "up", "-d"], check=True, env=os.environ.copy())


def status() -> int:
    bad = 0
    try:
        t = httpx.get("http://127.0.0.1:9090/api/v1/targets", timeout=10).json()["data"]["activeTargets"]
        for x in t:
            ok = x["health"] == "up"
            bad += not ok
            print(f"prometheus target {x['labels'].get('job')} {x['scrapeUrl']}: {x['health']}" + ("" if ok else f" ({x.get('lastError', '')[:120]})"))
        r = httpx.get("http://127.0.0.1:9090/api/v1/rules", timeout=10).json()["data"]["groups"]
        print("prometheus alert rules loaded:", sum(len(g["rules"]) for g in r))
    except Exception as e:
        bad += 1
        print("prometheus not reachable:", type(e).__name__)
    try:
        auth = ("admin", need("GRAFANA_ADMIN_PASSWORD"))
        print("grafana health:", httpx.get("http://127.0.0.1:3000/api/health", timeout=10).json().get("database"))
        found = httpx.get("http://127.0.0.1:3000/api/search", params={"query": "ragx"}, auth=auth, timeout=10).json()
        print("grafana dashboards:", [d["title"] for d in found] or "none")
        bad += not found
        ds = httpx.get("http://127.0.0.1:3000/api/datasources/uid/ragx-prom/health", auth=auth, timeout=15)
        print("grafana data source ragx-prom:", ds.json().get("status", ds.status_code))
        bad += ds.status_code != 200
    except SystemExit:
        raise
    except Exception as e:
        bad += 1
        print("grafana not reachable:", type(e).__name__)
    return 1 if bad else 0


def main() -> None:
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "up":
        up()
    elif cmd == "down":
        subprocess.run([*COMPOSE, "down"], check=True, env=os.environ.copy())
    elif cmd == "status":
        sys.exit(status())
    else:
        sys.exit("usage: monitoring.py up|down|status")


if __name__ == "__main__":
    main()
