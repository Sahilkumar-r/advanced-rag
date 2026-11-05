"""4.2 End to end PII leak eval (no LLM, no network). Runs in CI.

python scripts/run_pii_eval.py
Sends every PII case from eval/datasets/safety.json through the real API app (auth, guardrails, real Pipeline, real cache, tracer, memory, audit log)
with a stub model that behaves as badly as possible: it echoes everything it is given into the answer and proposes the user's own text as a memory.
Then it searches every place data can land for the PII strings the user typed:
  llm_input (everything a provider would receive), response, trace file, audit log, stored memories, session history, cache.
A leak is a surface that contains a PII value the user typed. The image path is tested too (PII "read" from a screenshot).
Labels come from safety.json, written by Claude and not reviewed by a human. The stub is a worst case, not a measurement of a real model.
Writes eval/results/04-pii-leak.json.
"""
import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.api.app import create_app  # noqa: E402
from ragx.auth import security as sec  # noqa: E402
from ragx.auth.store import Store  # noqa: E402
from ragx.cache.cache import Cache  # noqa: E402
from ragx.generate.providers import Completion  # noqa: E402
from ragx.guardrails.checks import PII, _real  # noqa: E402
from ragx.ingest.parent_child import Child, Parent  # noqa: E402
from ragx.memory.memory import Memory, propose  # noqa: E402
from ragx.observability.trace import Tracer  # noqa: E402
from ragx.pipeline import Pipeline  # noqa: E402
from ragx.vision import image as vimg  # noqa: E402

DS = json.loads((ROOT / "eval" / "datasets" / "safety.json").read_text(encoding="utf-8"))
FAKE = {"{KEY}": "sk-" + "FAKE" * 6, "{GSK}": "gsk_" + "FAKE" * 6}
PW = "correct-horse-battery"
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
IMG_EMAIL, IMG_KEY = "alice.smith@example.com", FAKE["{KEY}"]
EXTRACTION = json.dumps({"kind": "error", "error_text": f"Authorization failed for {IMG_EMAIL} using {IMG_KEY}", "library": "fastapi",
                         "summary": f"login error for {IMG_EMAIL}", "search_query": "fastapi authorization failed"})


def expand(s: str) -> str:
    for k, v in FAKE.items():
        s = s.replace(k, v)
    return s


def pii_values(text: str) -> list[str]:
    """The exact strings in text that the PII patterns count as real PII."""
    return [m.group(0).strip() for kind, rx in PII.items() for m in rx.finditer(text) if _real(kind, m.group(0))]


class Router:
    """Stands in for the model router. Records every text message that would leave the server."""
    def __init__(self):
        self.sent: list[str] = []
        self.stats = {"fallbacks": 0, "calls": 0, "cost_usd": 0.0}

    def call(self, tier, messages, max_tokens=800):
        self.stats["calls"] += 1
        if tier == "vision":  # the screenshot "contains" PII; the text reply is what flows downstream
            return Completion(EXTRACTION, "stub", "stub")
        self.sent += [m["content"] for m in messages]
        user = messages[-1]["content"]
        if "Extract at most 2 durable facts" in messages[0]["content"]:  # propose(): worst case, remember the user's own words
            return Completion(json.dumps({"memories": [{"kind": "long_term", "content": user.splitlines()[0].removeprefix("User: ")}]}), "stub", "stub")
        return Completion(f"You said: {user} [1]", "stub", "stub")  # worst case: echoes the whole prompt


def build(tmp: Path):
    router = Router()
    store = Store(tmp / "t.db", ip_salt="s")
    store.create_user("dev@x.test", sec.hash_password(PW), "developer")
    memory = Memory(store)
    parents = [Parent(0, "fastapi/a.md", "Path", "Use Path() to declare a path parameter.")]
    children = [Child(0, "fastapi/a.md", "Path", "Use Path() to declare a path parameter.", 0)]
    trace = tmp / "traces.jsonl"
    pipe = Pipeline(lambda q: children, parents, router, Cache(None, namespace="pii"), Tracer(trace), mode="plain_rag")
    keep = ("text", "refused", "citations", "sources", "cache", "trace_id", "steps", "tokens", "_sources")
    app = create_app(store, lambda q, mem, hist: {k: v for k, v in pipe.ask(q, memory=mem, history=hist).items() if k in keep}, memory, key="k" * 40,
                     propose_fn=lambda q, a: propose(router.call, q, a), vision_fn=lambda data, mime, q: vimg.extract(data, mime, q, router.call))
    c = TestClient(app)
    h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={"email": "dev@x.test", "password": PW}).json()["access"]}
    c.post("/api/memories/consent", json={"consent": True}, headers=h)
    return c, h, router, store, memory, pipe, trace


def surfaces(router, store, memory, pipe, trace, response: str) -> dict[str, str]:
    return {"llm_input": "\n".join(router.sent), "response": response, "trace": trace.read_text(encoding="utf-8") if trace.exists() else "",
            "audit": json.dumps(store.audit_rows(1000)), "memory": json.dumps(memory.list(1)),
            "history": json.dumps({k: list(v) for k, v in memory.turns.items()}),
            "cache": json.dumps([e.question + json.dumps(e.value, default=str) for e in pipe.cache.exact.values()])}


def leaked(values: list[str], s: dict[str, str]) -> list[str]:
    return sorted(k for k, text in s.items() if any(v in text for v in values))


def control(cases) -> dict:
    """Positive control: with input redaction and output checks switched off the same harness must see leaks, otherwise a 0 means nothing."""
    from ragx.api import app as api
    from ragx.guardrails.checks import OutputVerdict, Verdict
    saved = api.check_input, api.check_output
    api.check_input = lambda t, role="viewer", classifier=None: Verdict(False, None, [], t)
    api.check_output = lambda text, n, refused, src="": OutputVerdict([], text)
    try:
        found, seen = 0, set()
        for text, kinds in (c for c in cases if c[1]):
            with tempfile.TemporaryDirectory() as d:
                c, h, router, store, memory, pipe, trace = build(Path(d))
                r = c.post("/api/ask", json={"question": text, "session_id": "s"}, headers=h)
                w = leaked(pii_values(text), surfaces(router, store, memory, pipe, trace, r.text))
                found, seen = found + bool(w), seen | set(w)
        return {"cases_leaking_with_guards_off": found, "of": sum(1 for c in cases if c[1]), "surfaces_seen": sorted(seen)}
    finally:
        api.check_input, api.check_output = saved


def main() -> None:
    cases = [(expand(c["text"]), c["kinds"]) for c in DS["pii"]]
    per_case = []
    for i, (text, kinds) in enumerate(cases):
        with tempfile.TemporaryDirectory() as d:
            c, h, router, store, memory, pipe, trace = build(Path(d))
            r = c.post("/api/ask", json={"question": text, "session_id": f"s{i}"}, headers=h)
            per_case.append({"case": i, "status": r.status_code, "kinds": kinds, "leaked_into": leaked(pii_values(text), surfaces(router, store, memory, pipe, trace, r.text)),
                             "redacted_before_model": any("[REDACTED" in m for m in router.sent)})
    pii_cases = [x for x in per_case if x["kinds"]]
    leaks = [x for x in pii_cases if x["leaked_into"]]
    wrongly = [x["case"] for x in per_case if not x["kinds"] and x["redacted_before_model"]]
    with tempfile.TemporaryDirectory() as d:
        c, h, router, store, memory, pipe, trace = build(Path(d))
        r = c.post("/api/ask-image", files={"image": ("e.png", PNG, "image/png")}, data={"question": ""}, headers=h)
        img = leaked([IMG_EMAIL, IMG_KEY], surfaces(router, store, memory, pipe, trace, r.text))
    direct = Memory(Store(Path(tempfile.mkdtemp()) / "m.db", ip_salt="s"))
    rejected = [direct.add(1, "long_term", f"my contact is {pii_values(t)[0]}", True)[1] == "pii" for t, k in cases if k and pii_values(t)]
    res = {
        "labeller": "claude, unreviewed; the stub model is a worst case (echoes everything), not a real model",
        "text_cases_with_pii": len(pii_cases), "text_cases_total": len(per_case),
        "text_leak_rate": round(len(leaks) / len(pii_cases), 4), "text_leaks": leaks,
        "no_pii_cases_wrongly_redacted": wrongly,
        "image_status": r.status_code, "image_leaked_into": img, "image_leak_rate": 1.0 if img else 0.0,
        "memory_add_rejects_pii_rate": round(sum(rejected) / len(rejected), 4) if rejected else None, "memory_add_n": len(rejected),
        "positive_control": control(cases),
        "surfaces_checked": ["llm_input", "response", "trace", "audit", "memory", "history", "cache"],
        "per_case": per_case,
    }
    (ROOT / "eval" / "results" / "04-pii-leak.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "per_case"}, indent=2))


if __name__ == "__main__":
    main()
