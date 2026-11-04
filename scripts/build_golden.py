"""1.4 Build eval/datasets/golden.json: 30 rag-demo questions + 40 new hand written + synthetic heading questions.

python scripts/build_golden.py
Origins: baseline (hand written by Sahil in rag-demo), claude_written (written by Claude from the docs, NOT yet
reviewed by Sahil), synthetic (templated from page headings, easy for keyword search, report separately).
Split: dev vs held_out by a stable hash of the id; choose settings on dev, report held_out once.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
F, P = "fastapi/", "pydantic/"

# (question, type, expected pages)
HAND = [
    ("How do I make a field accept a different name in the input data than the attribute name?", "howto", [P + "alias.md", P + "fields.md"]),
    ("What is the difference between a before and an after field validator?", "concept", [P + "validators.md"]),
    ("How do I validate one field using the value of another field?", "howto", [P + "validators.md"]),
    ("How do I stop pydantic from converting the string '123' into an int?", "howto", [P + "strict_mode.md", P + "conversion_table.md"]),
    ("Which input types are converted to which python types in lax mode?", "lookup", [P + "conversion_table.md"]),
    ("How do I validate a plain list of ints without defining a model?", "howto", [P + "type_adapter.md"]),
    ("How do I dump a model to a JSON string and leave some fields out?", "howto", [P + "serialization.md", P + "fields.md"]),
    ("How do I customize how a single field is written out by model_dump?", "howto", [P + "serialization.md"]),
    ("How do I generate the JSON Schema of a model?", "howto", [P + "json_schema.md"]),
    ("How can I add extra keys to the JSON Schema of one field?", "howto", [P + "json_schema.md", P + "fields.md"]),
    ("How do I pick the right model class from a union using a tag field?", "howto", [P + "unions.md"]),
    ("What is smart mode for unions and how does it choose a member?", "concept", [P + "unions.md"]),
    ("How do I refer to a class that is only defined later in the file?", "howto", [P + "forward_annotations.md"]),
    ("How do I reject extra fields passed to a model?", "howto", [P + "models.md", P + "config.md"]),
    ("How do I validate the arguments of a regular function?", "howto", [P + "validation_decorator.md"]),
    ("How can I make validation of JSON input faster?", "howto", [P + "performance.md", P + "json.md"]),
    ("Can I use standard library dataclasses with pydantic validation?", "concept", [P + "dataclasses.md"]),
    ("How do I make a model immutable after it is created?", "howto", [P + "config.md", P + "fields.md"]),
    ("How do I create a custom type with its own validation logic?", "howto", [P + "types.md"]),
    ("How do I build a model from an arbitrary object that has matching attributes?", "howto", [P + "models.md"]),
    ("How can I parse a partially complete JSON string?", "howto", [P + "json.md", P + "experimental.md"]),
    ("What order do multiple validators on one field run in?", "concept", [P + "validators.md"]),
    ("How do I show example values in the API docs for a request body?", "howto", [F + "schema-extra-example.md", F + "body-fields.md"]),
    ("How do I stream server sent events from an endpoint?", "howto", [F + "server-sent-events.md"]),
    ("How do I return a stream of JSON lines?", "howto", [F + "stream-json-lines.md"]),
    ("How do I change the title and description shown in the generated API docs?", "howto", [F + "metadata.md"]),
    ("How do I split my app into several files using routers?", "howto", [F + "bigger-applications.md"]),
    ("How do I test my endpoints without running a server?", "howto", [F + "testing.md"]),
    ("How do I serve css and images from a folder?", "howto", [F + "static-files.md"]),
    ("How do I run my own code for every request before and after the endpoint?", "howto", [F + "middleware.md"]),
    ("How do I update only some fields of a stored item?", "howto", [F + "body-updates.md"]),
    ("How do I return a different shape than the input model, for example hiding a password?", "howto", [F + "response-model.md", F + "extra-models.md"]),
    ("How do I declare a list of nested models in the request body?", "howto", [F + "body-nested-models.md"]),
    ("How do I require a path parameter to be greater than a number?", "howto", [F + "path-params-numeric-validations.md"]),
    ("How do I group several query parameters into one pydantic model?", "howto", [F + "query-param-models.md"]),
    ("How do I accept a file and form fields in the same request?", "howto", [F + "request-forms-and-files.md"]),
    ("How do I connect the app to a SQL database?", "howto", [F + "sql-databases.md"]),
    ("How do I turn a datetime into something JSON can hold?", "howto", [F + "encoder.md", F + "extra-data-types.md"]),
    ("How do I add tags, a summary and a description to one endpoint?", "howto", [F + "path-operation-configuration.md"]),
    ("How do I set a maximum value on a body field?", "howto", [F + "body-fields.md"]),
    ("How do I give a list field a default without sharing it between instances?", "howto", [P + "fields.md", P + "models.md"]),
]
GENERIC = {"recap", "check it", "technical details", "review", "recap again", "conclusion", "feedback", "warning"}


def split(qid: str) -> str:
    return "held_out" if int(hashlib.sha1(qid.encode()).hexdigest(), 16) % 10 < 3 else "dev"


def headings(path: Path) -> list[str]:
    out, in_code = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^##\s+(.*?)(\s*\{\s*#.*\})?\s*$", line)
        if m:
            h = re.sub(r"<[^>]+>|\[([^\]]+)\]\([^)]*\)|\[([^\]]+)\]\[[^\]]*\]|`", lambda x: x.group(1) or x.group(2) or "", m.group(1)).strip()
            if h.lower() not in GENERIC and len(h.split()) >= 2:
                out.append(h)
    return out


def main() -> None:
    cases = []
    base = json.loads((ROOT / "eval" / "datasets" / "baseline_questions.json").read_text(encoding="utf-8"))
    for q in base["in_domain"]:
        cases.append(dict(q=q["q"], type="howto", expected=[F + e for e in q["expected"]], origin="baseline", reviewed=True))
    for q, t, e in HAND:
        cases.append(dict(q=q, type=t, expected=e, origin="claude_written", reviewed=False))
    pages = [(s, l, p) for s, l in (("fastapi", "FastAPI"), ("pydantic", "Pydantic")) for p in sorted((RAW / s).glob("*.md"))]
    seen = [h for _, _, p in pages for h in headings(p)]
    for src, label, p in pages:
        if True:
            hs = [h for h in headings(p) if seen.count(h) == 1]  # a heading shared by two pages has no single answer
            if hs:  # one per page, the middle heading to avoid the intro and the wrap up
                cases.append(dict(q=f"Explain {hs[len(hs) // 2]} in {label}", type="synthetic_heading",
                                  expected=[f"{src}/{p.name}"], origin="synthetic", reviewed=False))
    for i, c in enumerate(cases):
        c["id"] = f"g{i:03d}"
        c["split"] = split(c["id"])
    for c in cases:
        for e in c["expected"]:
            assert (RAW / e).exists(), (c["id"], e)
    golden = dict(note="See scripts/build_golden.py for origins. Off topic questions are for the guardrail eval.",
                  cases=cases, off_topic=base["off_topic"])
    (ROOT / "eval" / "datasets" / "golden.json").write_text(json.dumps(golden, indent=1), encoding="utf-8")
    by = {}
    for c in cases:
        by[(c["origin"], c["split"])] = by.get((c["origin"], c["split"]), 0) + 1
    print(len(cases), "cases", dict(sorted(by.items())))


if __name__ == "__main__":
    main()
