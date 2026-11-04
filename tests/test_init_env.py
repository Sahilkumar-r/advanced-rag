import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("init_env", Path(__file__).resolve().parent.parent / "scripts" / "init_env.py")
init_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init_env)


def test_adds_only_missing_names_and_never_touches_existing_lines(tmp_path):
    f = tmp_path / ".env"
    f.write_text("GROQ_API_KEY=abc   # my note\nJWT_SECRET=keepme-keepme-keepme-keepme-keepme-12\n# METRICS_TOKEN=commented out\n")
    added = init_env.init(f)
    text = f.read_text()
    assert "JWT_SECRET" not in added and "METRICS_TOKEN" in added  # a commented line does not count as set
    assert text.startswith("GROQ_API_KEY=abc   # my note\nJWT_SECRET=keepme-keepme-keepme-keepme-keepme-12\n")
    assert init_env.init(f) == [] and f.read_text() == text  # second run changes nothing


def test_creates_the_file_adds_a_newline_when_needed_and_generates_strong_values(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=1")  # no trailing newline
    init_env.init(f)
    lines = f.read_text().splitlines()
    assert lines[0] == "A=1" and len(lines) == 1 + len(init_env.GENERATED)
    values = dict(l.split("=", 1) for l in lines[1:])
    assert len(values["JWT_SECRET"]) >= 32 and all(len(v) >= 24 for k, v in values.items() if k != "METRICS_TOKEN")
    assert len(set(values.values())) == len(values)  # no value is reused
    g = tmp_path / "new" / ".env"
    g.parent.mkdir()
    assert len(init_env.init(g)) == len(init_env.GENERATED)
