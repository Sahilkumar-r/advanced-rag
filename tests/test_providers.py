import os

from ragx.config import load_env
from ragx.generate.providers import Mock, OpenAICompat, ProviderError


def test_env_loader_keeps_first_token_only(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("RAGX_TEST_KEY=abc123   # pasted note\n# RAGX_OTHER=x\nRAGX_EMPTY=\n")
    monkeypatch.delenv("RAGX_TEST_KEY", raising=False)
    load_env(f)
    assert os.environ["RAGX_TEST_KEY"] == "abc123"
    assert "RAGX_OTHER" not in os.environ


def test_mock_records_calls():
    m = Mock(lambda msgs: "hello there")
    out = m.complete([{"role": "user", "content": "hi"}])
    assert out.text == "hello there" and len(m.calls) == 1


def test_timeout_becomes_provider_error_after_three_attempts(monkeypatch):
    import httpx

    calls = []
    monkeypatch.setattr("ragx.generate.providers.load_env", lambda *a: None)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    try:
        OpenAICompat("groq", "x", cache=False).complete([{"role": "user", "content": "hi"}])
        assert False
    except ProviderError as e:
        assert e.status is None and len(calls) == 3


def test_missing_key_raises_before_any_network_call(monkeypatch):
    monkeypatch.setattr("ragx.generate.providers.load_env", lambda *a: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    p = OpenAICompat("groq", "x", cache=False)
    try:
        p.complete([{"role": "user", "content": "hi"}])
        assert False
    except ProviderError as e:
        assert e.status is None
