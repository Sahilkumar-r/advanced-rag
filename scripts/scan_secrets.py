"""Scan git tracked files for key shaped strings: python scripts/scan_secrets.py
Prints file, line and the kind of match, never the matched text. Exit code 1 if anything matches. Run in CI and before every commit.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "groq key": r"gsk_[A-Za-z0-9]{20,}", "google key": r"AIza[0-9A-Za-z_-]{30,}", "openai style key": r"sk-[A-Za-z0-9]{20,}",
    "huggingface token": r"hf_[A-Za-z0-9]{20,}", "cerebras key": r"csk-[A-Za-z0-9]{20,}", "github token": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "aws access key": r"AKIA[0-9A-Z]{16}", "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}
SKIP_SUFFIX = (".png", ".jpg", ".wav", ".ico", ".npy", ".pyc")


def scan(files: list[Path], root: Path = ROOT) -> list[tuple[str, int, str]]:
    hits = []
    for f in files:
        if f.suffix in SKIP_SUFFIX or not f.is_file():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for kind, rx in PATTERNS.items():
                if re.search(rx, line):
                    hits.append((str(f.relative_to(root)) if f.is_relative_to(root) else str(f), n, kind))
    return hits


def tracked() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    return [ROOT / p for p in out]


def main() -> None:
    hits = scan(tracked())
    for f, n, kind in hits:
        print(f"{f}:{n}: looks like a {kind}")
    print(f"{len(hits)} suspicious line(s) in tracked files" if hits else "no key shaped strings in tracked files")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
