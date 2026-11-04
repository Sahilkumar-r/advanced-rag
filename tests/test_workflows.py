import json
import re
from pathlib import Path

import pytest
import yaml

from ragx.evals.gate import get

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_the_three_workflows_exist():
    assert {p.name for p in WORKFLOWS} == {"ci.yml", "evals-nightly.yml", "evals-weekly.yml"}


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_parses_has_least_privilege_and_pinned_actions(wf):
    d = yaml.safe_load(text(wf))
    assert d["jobs"] and d.get(True, d.get("on")), "needs jobs and a trigger (YAML reads the key 'on' as True)"
    assert d["permissions"] == {"contents": "read"}
    uses = re.findall(r"uses:\s*(\S+)", text(wf))
    assert uses and all(re.fullmatch(r"[\w./-]+@v\d+", u) for u in uses), f"actions must be pinned to a version tag: {uses}"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_secrets_come_only_from_the_secrets_context_and_openai_is_never_passed(wf):
    t = text(wf)
    assert not re.search(r"(gsk_|AIza|sk-|hf_|csk-)[A-Za-z0-9_-]{16,}", t)
    for m in re.finditer(r"^\s+([A-Z_]*(KEY|TOKEN|PASSWORD)[A-Z_]*):\s*(.*)$", t, re.M):
        assert m.group(3).startswith("${{ secrets."), f"{m.group(1)} must be read from secrets"
    assert "OPENAI" not in t, "the paid last resort must never run in CI"


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_every_script_and_result_file_a_workflow_uses_exists(wf):
    t = text(wf)
    for s in set(re.findall(r"scripts/[\w]+\.py", t)):
        assert (ROOT / s).exists(), s
    for r in set(re.findall(r"eval/results/([\w.-]+\.json)", t)) - {"02-generation-nightly.json", "02-generation-weekly.json"}:
        assert (ROOT / "eval" / "results" / r).exists() or r in ("01-retrieval.json",), r  # outputs of the run itself are excluded above


def test_scheduled_workflows_skip_visibly_without_keys_and_have_a_cron():
    for name in ("evals-nightly.yml", "evals-weekly.yml"):
        t = text(ROOT / ".github" / "workflows" / name)
        d = yaml.safe_load(t)
        assert d[True]["schedule"][0]["cron"] and "::notice::Skipped" in t and "steps.keys.outputs.run" in t


def test_every_metric_a_gate_checks_exists_in_the_committed_result_it_compares_against():
    for wf in WORKFLOWS:
        for seg in text(wf).split("regression_gate.py")[1:]:
            seg = seg.split("|")[0]
            base = re.search(r"--base\s+\S*?([\w.-]+\.json)", seg).group(1)
            base = {"safety-base.json": "04-safety.json"}.get(base, base)  # ci.yml copies the committed file to a temp name first
            data = json.loads((ROOT / "eval" / "results" / base).read_text(encoding="utf-8"))
            for path in re.findall(r"--(?:check|lower-is-better)\s+(\S+?):[\d.]+", seg):
                get(data, path)  # raises KeyError if a renamed field would silently disable the gate
