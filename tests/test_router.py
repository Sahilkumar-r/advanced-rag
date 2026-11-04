import pytest

from ragx.generate.providers import Completion, ProviderError
from ragx.router.router import Router

TIERS = {"answer": [("a", "m1"), ("b", "m2")], "judge": [("a", "m1")]}


class Fake:
    def __init__(self, provider, fail):
        self.provider, self.fail = provider, fail

    def complete(self, messages, **kw):
        if self.fail:
            raise ProviderError(self.provider, 500, "boom")
        return Completion("ok", self.provider, "m", 100, 50)


def router(fail=(), **kw):
    return Router(tiers=TIERS, client=lambda p, m: Fake(p, p in fail), quotas={}, spend_file=kw.pop("spend_file", None) or __import__("pathlib").Path("nul"), **kw)


def test_primary_used_when_healthy():
    r = router()
    assert r.call("answer", []).provider == "a" and r.stats["fallbacks"] == 0


def test_falls_back_and_counts_it():
    r = router(fail={"a"})
    assert r.call("answer", []).provider == "b" and r.stats["fallbacks"] == 1


def test_breaker_opens_after_threshold_then_recovers_after_cooldown():
    t = [0.0]
    r = router(fail={"a"}, breaker_threshold=2, cooldown_s=60, now=lambda: t[0])
    for _ in range(3):
        r.call("answer", [])
    assert r.stats["errors"] == 2 and r.stats["skipped_open"] == 1  # third call skipped provider a without trying it
    t[0] = 100
    r.client = lambda p, m: Fake(p, False)
    assert r.call("answer", []).provider == "a"


def test_quota_skips_provider_at_the_limit():
    r = Router(tiers=TIERS, client=lambda p, m: Fake(p, False), quotas={"a": {"rpm": 2, "rpd": 100}})
    got = [r.call("answer", []).provider for _ in range(3)]
    assert got == ["a", "a", "b"] and r.stats["skipped_quota"] == 1


def test_all_failed_raises():
    with pytest.raises(ProviderError):
        router(fail={"a", "b"}).call("answer", [])


def test_openai_off_without_prices_and_never_for_judge(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_BUDGET_USD", "1")
    for k in ("OPENAI_MODEL", "OPENAI_PRICE_IN_PER_MTOK", "OPENAI_PRICE_OUT_PER_MTOK"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr("ragx.router.router.load_env", lambda *a: None)
    assert not router(spend_file=tmp_path / "s.json")._openai_ready()
    with pytest.raises(ProviderError):
        router(fail={"a"}, spend_file=tmp_path / "s.json").call("judge", [])


def test_openai_budget_cap_stops_spending(monkeypatch, tmp_path):
    for k, v in {"OPENAI_API_KEY": "k", "OPENAI_MODEL": "x", "OPENAI_PRICE_IN_PER_MTOK": "1", "OPENAI_PRICE_OUT_PER_MTOK": "1", "OPENAI_BUDGET_USD": "0.0002"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr("ragx.router.router.load_env", lambda *a: None)
    r = router(fail={"a", "b"}, spend_file=tmp_path / "s.json")
    r.client = lambda p, m: Fake(p, p != "openai")
    assert r.call("answer", []).provider == "openai"  # 150 tokens at $1 per million = $0.00015
    assert r.spent() == pytest.approx(0.00015)
    assert r.call("answer", []).provider == "openai"  # 0.00015 < 0.0002 cap, allowed once more
    assert not r._openai_ready()  # now at 0.0003, cap reached
