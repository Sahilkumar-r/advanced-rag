"""Add the secrets the app and the monitoring stack need to .env, generating only the ones that are missing.

python scripts/init_env.py
Never prints, logs or overwrites a value: existing lines are untouched and the output is the list of names added.
"""
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = {  # name: bytes of randomness
    "JWT_SECRET": 48, "METRICS_TOKEN": 24, "GRAFANA_ADMIN_PASSWORD": 18,
    "DEMO_ADMIN_PASSWORD": 18, "DEMO_DEVELOPER_PASSWORD": 18, "DEMO_VIEWER_PASSWORD": 18,
}


def missing_names(text: str) -> list[str]:
    present = {l.split("=", 1)[0].strip() for l in text.splitlines() if "=" in l and not l.lstrip().startswith("#")}
    return [n for n in GENERATED if n not in present]


def init(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    add = missing_names(text)
    if add:
        lines = "".join(f"{n}={secrets.token_urlsafe(GENERATED[n])}\n" for n in add)
        path.write_text(text + ("" if not text or text.endswith("\n") else "\n") + lines, encoding="utf-8")
    return add


def main() -> None:
    added = init(ROOT / ".env")
    print("added to .env:", ", ".join(added) if added else "nothing, all present")
    sys.exit(0)


if __name__ == "__main__":
    main()
