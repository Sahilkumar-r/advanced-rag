import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import run_pii_eval as P  # noqa: E402

CASES = [(P.expand(c["text"]), c["kinds"]) for c in P.DS["pii"]]


def ask(text):
    with tempfile.TemporaryDirectory() as d:
        c, h, router, store, memory, pipe, trace = P.build(Path(d))
        r = c.post("/api/ask", json={"question": text, "session_id": "s"}, headers=h)
        return r.status_code, P.leaked(P.pii_values(text), P.surfaces(router, store, memory, pipe, trace, r.text))


def test_no_pii_the_user_types_reaches_the_model_the_response_or_any_store():
    for text, kinds in CASES:
        if kinds:
            status, where = ask(text)
            assert status == 200 and where == [], (text, where)


def test_the_harness_can_fail_so_a_clean_result_means_something():
    found = P.control(CASES)
    assert found["cases_leaking_with_guards_off"] == found["of"] > 0
