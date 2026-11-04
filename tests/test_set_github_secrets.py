import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("set_github_secrets", Path(__file__).resolve().parent.parent / "scripts" / "set_github_secrets.py")
sgs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sgs)


def test_values_go_on_stdin_never_in_argv_and_missing_names_are_skipped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "value-groq-123")
    monkeypatch.setenv("GEMINI_API_KEY", "value-gemini-456")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    calls = []

    def fake_run(argv, input=None, **kw):
        calls.append((argv, input))
        return SimpleNamespace(returncode=0, stderr="")

    done, skipped = sgs.set_secrets("o/r", sgs.DEFAULT, run=fake_run)
    assert done == ["GROQ_API_KEY", "GEMINI_API_KEY"] and skipped == ["OPENAI_API_KEY"]
    assert [c[1] for c in calls] == ["value-groq-123", "value-gemini-456"]
    assert all("value-" not in " ".join(argv) for argv, _ in calls)  # nothing secret on a command line
    assert calls[0][0] == ["gh", "secret", "set", "GROQ_API_KEY", "--repo", "o/r"]


def test_a_failing_gh_stops_without_echoing_the_value(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "value-groq-123")
    with pytest.raises(SystemExit) as e:
        sgs.set_secrets("o/r", ["GROQ_API_KEY"], run=lambda argv, input=None, **kw: SimpleNamespace(returncode=1, stderr="HTTP 403"))
    assert "value-groq-123" not in str(e.value) and "HTTP 403" in str(e.value)
