"""Run the API locally: python scripts/serve.py [port]. Binds to 127.0.0.1 only; put a reverse proxy in front for anything public.

Needs JWT_SECRET in .env (32+ characters) and users from scripts/seed_users.py.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from ragx.api.factory import build_app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(build_app(), host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
