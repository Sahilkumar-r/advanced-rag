"""Run the built image locally the way a Space runs it.

python scripts/run_space_local.py up|down|logs     (build first: docker build -t ragx-space .)
Secrets are passed to the container by NAME (-e NAME), so values never appear on a command line or in a process listing.
OPENAI_API_KEY is never passed. The app is published on 127.0.0.1:7860 only.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.config import load_env  # noqa: E402

NAME = "ragx-space"
PASS = ["JWT_SECRET", "DEMO_ADMIN_PASSWORD", "DEMO_DEVELOPER_PASSWORD", "DEMO_VIEWER_PASSWORD", "GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "METRICS_TOKEN"]


def main() -> None:
    load_env()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "up"
    if cmd == "up":
        if not os.environ.get("JWT_SECRET"):
            sys.exit("JWT_SECRET is not set in .env. Run: python scripts/init_env.py")
        subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
        names = [n for n in PASS if os.environ.get(n)]
        args = ["docker", "run", "-d", "--name", NAME, "-p", "127.0.0.1:7860:7860", *[x for n in names for x in ("-e", n)], "ragx-space"]
        subprocess.run(args, check=True, env=os.environ.copy())
        print("started; passing", len(names), "settings by name:", ", ".join(names))
    elif cmd == "down":
        subprocess.run(["docker", "rm", "-f", NAME], check=True)
    elif cmd == "logs":
        subprocess.run(["docker", "logs", "--tail", "40", NAME], check=True)
    else:
        sys.exit("usage: run_space_local.py up|down|logs")


if __name__ == "__main__":
    main()
