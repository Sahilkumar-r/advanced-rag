from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BP = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
SVC = BP["services"][0]


def test_it_is_a_free_docker_web_service_built_from_this_repo_with_a_health_check():
    assert SVC["type"] == "web" and SVC["runtime"] == "docker" and SVC["plan"] == "free"
    assert (REPO / SVC["dockerfilePath"]).exists() and SVC["healthCheckPath"] == "/api/health" and SVC["autoDeploy"] is False


def test_no_secret_value_is_stored_and_the_paid_key_is_never_requested():
    for e in SVC["envVars"]:
        assert "value" not in e, f"{e['key']} must not carry a value in the repo"
        assert e.get("sync") is False or e.get("generateValue") is True, f"{e['key']} must be entered in the dashboard or generated"
    names = {e["key"] for e in SVC["envVars"]}
    assert {"JWT_SECRET", "GROQ_API_KEY", "GEMINI_API_KEY"} <= names and not any("OPENAI" in n for n in names)


def test_the_app_can_start_from_a_plain_checkout_because_the_pinned_docs_are_in_git():
    assert (REPO / "data" / "raw" / "manifest.json").exists() and (REPO / "data" / "raw" / "fastapi" / "LICENSE").exists()
