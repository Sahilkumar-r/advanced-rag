"""Assemble the folder that becomes the Hugging Face Space repo: python scripts/make_space_bundle.py <empty folder>

Copies exactly the paths on the allow list in .dockerignore (so the Space can never get more than the Docker build gets), the Dockerfile,
and deploy/hf-space-README.md as README.md (it carries the Space front matter). Refuses a folder that is not empty.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def allowed_paths(root: Path = ROOT) -> list[str]:
    return [l[1:].strip() for l in (root / ".dockerignore").read_text(encoding="utf-8").splitlines() if l.startswith("!")]


def bundle(dest: Path, root: Path = ROOT) -> list[str]:
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} is not empty; give an empty folder so nothing stale ends up in the Space")
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for pattern in allowed_paths(root):
        base = pattern[:-3] if pattern.endswith("/**") else pattern
        src = root / base
        files = [p for p in src.rglob("*") if p.is_file() and "__pycache__" not in p.parts] if pattern.endswith("/**") else [src]
        for f in files:
            if not f.is_file():
                raise SystemExit(f"allow listed path is missing: {f.relative_to(root)}")
            out = dest / f.relative_to(root)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            copied.append(str(f.relative_to(root)).replace("\\", "/"))
    shutil.copy2(root / "Dockerfile", dest / "Dockerfile")
    shutil.copy2(root / "deploy" / "hf-space-README.md", dest / "README.md")
    return copied + ["Dockerfile", "README.md"]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python scripts/make_space_bundle.py <empty folder>")
    files = bundle(Path(sys.argv[1]))
    print(f"{len(files)} files copied to {sys.argv[1]}")


if __name__ == "__main__":
    main()
