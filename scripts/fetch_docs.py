"""1.1 Fetch the FastAPI tutorial and Pydantic concepts docs (both MIT) into data/raw with a manifest.

python scripts/fetch_docs.py
Each page records its url, source repo, upstream commit and license, so a number in the README can be traced to a doc version.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LOCK = ROOT / "eval" / "datasets" / "docs.lock.json"
SOURCES = {
    "fastapi": dict(repo="https://github.com/fastapi/fastapi.git", sub="docs/en/docs/tutorial",
                    url="https://fastapi.tiangolo.com/tutorial/{stem}/", license="MIT"),
    "pydantic": dict(repo="https://github.com/pydantic/pydantic.git", sub="docs/concepts",
                     url="https://docs.pydantic.dev/latest/concepts/{stem}/", license="MIT"),
}


def git(*args: str, cwd: Path) -> str:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout.strip()


def main() -> None:
    """Uses the commits in eval/datasets/docs.lock.json when it exists, so every run (and CI) sees the docs the baselines were measured on.
    --latest fetches the newest upstream docs instead and rewrites the lock; the numbers must then be re measured."""
    latest = "--latest" in sys.argv
    lock = {} if latest or not LOCK.exists() else json.loads(LOCK.read_text(encoding="utf-8"))
    manifest, shas = {}, {}
    for name, s in SOURCES.items():
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / name
            git("clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", s["repo"], str(repo), cwd=Path(tmp))
            git("sparse-checkout", "set", "--no-cone", "/" + s["sub"], "/LICENSE", cwd=repo)
            if name in lock:
                git("fetch", "-q", "--depth", "1", "origin", lock[name], cwd=repo)
                git("checkout", "-q", lock[name], cwd=repo)
            else:
                git("checkout", "-q", cwd=repo)
            sha = shas[name] = git("rev-parse", "HEAD", cwd=repo)
            out = RAW / name
            if out.exists():
                shutil.rmtree(out)
            out.mkdir(parents=True)
            for p in sorted((repo / s["sub"]).glob("*.md")):  # top level pages only, no subfolders
                shutil.copy(p, out / p.name)
                manifest[f"{name}/{p.name}"] = {"url": s["url"].format(stem=p.stem), "repo": s["repo"],
                                                "commit": sha, "license": s["license"]}
            shutil.copy(repo / "LICENSE", out / "LICENSE")
    (RAW / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not lock:
        LOCK.write_text(json.dumps(shas, indent=1) + "\n", encoding="utf-8")
    print({n: sum(k.startswith(n + "/") for k in manifest) for n in SOURCES}, "pages")


if __name__ == "__main__":
    main()
