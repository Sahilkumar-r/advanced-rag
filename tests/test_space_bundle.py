import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("make_space_bundle", REPO / "scripts" / "make_space_bundle.py")
msb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(msb)
HAS_DOCS = (REPO / "data" / "raw" / "manifest.json").exists()  # present after scripts/fetch_docs.py, absent in the plain unit test job


def fake_root(tmp_path: Path) -> Path:
    """A synthetic repo: every allow listed path exists, plus things that must never be copied."""
    root = tmp_path / "root"
    root.mkdir()
    (root / ".dockerignore").write_text((REPO / ".dockerignore").read_text(encoding="utf-8"), encoding="utf-8")
    for pattern in msb.allowed_paths(root):
        if pattern.endswith("/**"):
            (root / pattern[:-3]).mkdir(parents=True, exist_ok=True)
            (root / pattern[:-3] / "a.txt").write_text("x")
            (root / pattern[:-3] / "__pycache__").mkdir(exist_ok=True)
            (root / pattern[:-3] / "__pycache__" / "a.pyc").write_text("x")
        else:
            (root / pattern).parent.mkdir(parents=True, exist_ok=True)
            (root / pattern).write_text("x")
    (root / "Dockerfile").write_text("FROM scratch")
    (root / "deploy").mkdir()
    (root / "deploy" / "hf-space-README.md").write_text("---\ntitle: t\n---\n")
    (root / ".env").write_text("GROQ_API_KEY=should-never-be-copied")
    (root / "data" / "raw" / "baseline-fastapi").mkdir(parents=True, exist_ok=True)
    (root / "data" / "raw" / "baseline-fastapi" / "old.md").write_text("phase 0 copy, not part of the app")
    (root / "data" / "state").mkdir(parents=True, exist_ok=True)
    (root / "data" / "state" / "ragx.db").write_text("users")
    (root / "tests").mkdir()
    (root / "tests" / "t.py").write_text("x")
    return root


def test_a_stray_env_file_or_state_in_the_repo_never_reaches_the_bundle(tmp_path):
    root = fake_root(tmp_path)
    files = msb.bundle(tmp_path / "space", root)
    got = {str(p.relative_to(tmp_path / "space")).replace("\\", "/") for p in (tmp_path / "space").rglob("*") if p.is_file()}
    assert got == set(files)
    assert not any(f.startswith((".env", "tests/", "data/state")) or "__pycache__" in f or "baseline-fastapi" in f or f.endswith((".db", ".pyc")) for f in files)
    assert "should-never-be-copied" not in "".join(p.read_text(errors="ignore") for p in (tmp_path / "space").rglob("*") if p.is_file())
    assert (tmp_path / "space" / "README.md").read_text().startswith("---\ntitle: t")


@pytest.mark.skipif(not HAS_DOCS, reason="needs the docs from scripts/fetch_docs.py")
def test_the_real_bundle_has_the_app_the_docs_and_their_licence(tmp_path):
    files = set(msb.bundle(tmp_path / "space"))
    assert {"Dockerfile", "README.md", "NOTICE.md", "LICENSE", "pyproject.toml", "scripts/space_entry.py", "scripts/prebuild.py", "web/index.html", "src/ragx/api/app.py",
            "data/raw/manifest.json", "data/raw/fastapi/LICENSE", "data/raw/pydantic/LICENSE"} <= files
    assert not [f for f in files if f.startswith((".env", "traces/", ".git", "tests/", "ops/", "docs/")) or (f.startswith("data/") and not f.startswith("data/raw/")) or f.endswith((".pyc", ".db", ".wav"))]


def test_refuses_a_folder_that_is_not_empty(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "stale.txt").write_text("old")
    with pytest.raises(SystemExit):
        msb.bundle(tmp_path / "x", fake_root(tmp_path))


def test_the_dockerignore_is_an_allow_list_that_starts_by_excluding_everything():
    lines = (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines()
    rules = [l for l in lines if l and not l.startswith("#")]
    assert rules[0] == "*"
    assert not any(r.lstrip("!").startswith(".env") for r in rules)


def test_the_dockerfile_does_not_need_apt_or_git_and_copies_only_allow_listed_paths():
    d = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "apt-get" not in d and "git " not in d.replace("git or", "")
    allowed = msb.allowed_paths()
    for src in [l.split()[1] for l in d.splitlines() if l.startswith("COPY ") and "--from" not in l]:
        assert any(src.rstrip("/") == a.rstrip("/*") or a.startswith(src.rstrip("/") + "/") or src.rstrip("/") == a for a in allowed), f"COPY {src} is not on the allow list"
