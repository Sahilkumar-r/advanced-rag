"""Container entry point. Seeds the demo users from the environment, then serves on 0.0.0.0 and the port in PORT (7860 on a Space).

The Space disk is ephemeral, so users are re seeded on every boot and memories and sqlite state do not survive a restart.
Without the three DEMO_*_PASSWORD secrets (12 characters or more) no demo users are created and only guest access works.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import uvicorn  # noqa: E402

import seed_users  # noqa: E402
from ragx.api.factory import build_app  # noqa: E402
from ragx.config import load_env  # noqa: E402


def main() -> None:
    load_env()
    try:
        seed_users.main()
    except SystemExit as e:  # seed_users exits with a message when a password is missing or short
        print("demo users not created:", e, file=sys.stderr)
    # Off by default: trusting X-Forwarded-For from anyone lets a client spoof its address and dodge the per IP rate limits.
    # Behind a proxy every user then shares the proxy's address (and its rate limit buckets). Set RAGX_TRUST_PROXY=1 only if
    # the container can be reached through the proxy alone.
    trust = os.environ.get("RAGX_TRUST_PROXY") == "1"
    uvicorn.run(build_app(), host=os.environ.get("RAGX_HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "7860")), proxy_headers=trust, forwarded_allow_ips="*" if trust else None)


if __name__ == "__main__":
    main()
