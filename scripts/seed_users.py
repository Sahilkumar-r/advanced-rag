"""4.1 Create the demo users. Passwords come from the environment (or .env) and are never printed.

DEMO_ADMIN_PASSWORD, DEMO_DEVELOPER_PASSWORD, DEMO_VIEWER_PASSWORD, each at least 12 characters.
python scripts/seed_users.py [path to sqlite db]
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.auth.security import hash_password  # noqa: E402
from ragx.auth.store import Store  # noqa: E402
from ragx.config import load_env  # noqa: E402

USERS = {"admin": ("admin@demo.local", "DEMO_ADMIN_PASSWORD"), "developer": ("developer@demo.local", "DEMO_DEVELOPER_PASSWORD"),
         "viewer": ("viewer@demo.local", "DEMO_VIEWER_PASSWORD")}


def main() -> None:
    load_env()
    bad = [var for _, var in USERS.values() if len(os.environ.get(var, "")) < 12]
    if bad:
        sys.exit("refusing to seed: set these to at least 12 characters in .env: " + ", ".join(bad))
    store = Store(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "state" / "ragx.db")
    Path(store.path).parent.mkdir(parents=True, exist_ok=True)
    for role, (email, var) in USERS.items():
        if store.user_by_email(email):
            print("exists:", email)
        else:
            store.create_user(email, hash_password(os.environ[var]), role)
            print("created:", email, role)


if __name__ == "__main__":
    main()
