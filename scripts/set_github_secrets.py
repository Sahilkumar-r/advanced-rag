"""Set GitHub repository secrets from .env: python scripts/set_github_secrets.py [--repo OWNER/NAME] [NAME ...]

Loads .env with ragx.config.load_env (the load_dotenv equivalent for this repo: it keeps only the first token of a value, so a note written after a key
cannot corrupt it). Default names: GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY. Each value is piped to `gh secret set` on stdin, so it is never on a
command line or in a process listing, and the script prints names only. Secrets are write only on GitHub: nobody can read them back.
Note: no workflow reads OPENAI_API_KEY (tests/test_workflows.py enforces that); setting it only makes it available to a future, reviewed workflow.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.config import load_env  # noqa: E402

DEFAULT = ["GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"]


def set_secrets(repo: str, names: list[str], run=subprocess.run) -> tuple[list[str], list[str]]:
    done, skipped = [], []
    for n in names:
        value = os.environ.get(n, "")
        if not value:
            skipped.append(n)
            continue
        r = run(["gh", "secret", "set", n, "--repo", repo], input=value, text=True, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f"gh failed for {n}: {r.stderr.strip()[:200]}")
        done.append(n)
    return done, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="")
    ap.add_argument("names", nargs="*", default=DEFAULT)
    a = ap.parse_args()
    load_env()
    repo = a.repo or subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
    done, skipped = set_secrets(repo, a.names)
    print(f"{repo}: set {', '.join(done) or 'nothing'}" + (f"; not in .env, skipped: {', '.join(skipped)}" if skipped else ""))


if __name__ == "__main__":
    main()
