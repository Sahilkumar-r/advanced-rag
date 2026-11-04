import json
import re
from pathlib import Path

import yaml

from ragx.observability.metrics import Observer

MON = Path(__file__).resolve().parent.parent / "ops" / "monitoring"


def known_metrics() -> set[str]:
    """Every series name the app can export, including the _bucket, _sum, _count and _total forms Prometheus derives."""
    names: set[str] = set()
    for name, kind in re.findall(r"^# TYPE (\S+) (\w+)", Observer().exposition().decode(), re.M):
        names.add(name)
        if kind == "histogram":
            names |= {name + s for s in ("_bucket", "_sum", "_count")}
        if kind == "counter":
            names.add(name.removesuffix("_total") + "_total")
    return names


def used(expr: str) -> set[str]:
    return set(re.findall(r"\bragx_[a-z_]+", expr))


def test_every_metric_in_the_rules_and_dashboard_exists_in_the_app():
    known = known_metrics()
    rules = yaml.safe_load((MON / "rules.yml").read_text(encoding="utf-8"))
    exprs = [r["expr"] for g in rules["groups"] for r in g["rules"]]
    dash = json.loads((MON / "grafana" / "dashboards" / "ragx.json").read_text(encoding="utf-8"))
    exprs += [t["expr"] for p in dash["panels"] for t in p["targets"]]
    unknown = sorted({m for e in exprs for m in used(e)} - known)
    assert unknown == [], f"queries use metrics the app does not export: {unknown}"


def test_dashboard_is_well_formed_and_matches_the_provisioned_datasource():
    dash = json.loads((MON / "grafana" / "dashboards" / "ragx.json").read_text(encoding="utf-8"))
    ds = yaml.safe_load((MON / "grafana" / "provisioning" / "datasources" / "prometheus.yml").read_text(encoding="utf-8"))["datasources"][0]
    ids = [p["id"] for p in dash["panels"]]
    assert len(ids) == len(set(ids)) >= 10
    assert all(t["datasource"]["uid"] == ds["uid"] and t["expr"].strip() for p in dash["panels"] for t in p["targets"])


def test_compose_is_pinned_local_only_and_keeps_secrets_out_of_the_file():
    c = yaml.safe_load((MON / "docker-compose.yml").read_text(encoding="utf-8"))
    for name, svc in c["services"].items():
        assert re.search(r":v?\d+\.\d+", svc["image"]) and ":latest" not in svc["image"], f"{name} image is not pinned"
        assert all(p.startswith("127.0.0.1:") for p in svc["ports"]), f"{name} must bind to localhost only"
    pw = c["services"]["grafana"]["environment"]["GF_SECURITY_ADMIN_PASSWORD"]
    assert pw.startswith("${GRAFANA_ADMIN_PASSWORD:?"), "the Grafana password must come from the environment and have no default"
    p = yaml.safe_load((MON / "prometheus.yml").read_text(encoding="utf-8"))
    auth = p["scrape_configs"][0]["authorization"]
    assert "credentials_file" in auth and "credentials" not in auth


def test_every_alert_threshold_is_labelled_a_placeholder():
    text = (MON / "rules.yml").read_text(encoding="utf-8")
    rules = yaml.safe_load(text)["groups"][0]["rules"]
    thresholded = [r for r in rules if r["alert"] != "RagxDown"]
    assert thresholded and all("placeholder" in r["annotations"]["summary"] for r in thresholded)
