"""Create or update the Hugging Face Space, set its secrets and wait for the build: python scripts/deploy_space.py [--name ragx] [--private] [--no-wait]

Needs HF_TOKEN (write access) in .env. Steps: whoami, create the Space (Docker SDK, public unless --private), upload the bundle from
scripts/make_space_bundle.py, set the secrets, watch the build. Secrets are set with add_space_secret (write only); only names are printed.
A fresh JWT_SECRET is generated when the Space is first created. Demo passwords and provider keys are copied from .env. OPENAI_API_KEY is never sent.
"""
import argparse
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # the TRD notes xet transfers can fail on some networks; plain HTTP is slower but works

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import make_space_bundle  # noqa: E402
from ragx.config import load_env  # noqa: E402

COPY_FROM_ENV = ["GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "DEMO_ADMIN_PASSWORD", "DEMO_DEVELOPER_PASSWORD", "DEMO_VIEWER_PASSWORD"]
NEVER = {"OPENAI_API_KEY", "HF_TOKEN"}
DONE_STAGES = {"RUNNING", "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "PAUSED", "NO_APP_FILE"}


def space_secrets(env: dict, new_space: bool, rotate_jwt: bool = False) -> dict[str, str]:
    out = {k: env[k] for k in COPY_FROM_ENV if env.get(k)}
    if new_space or rotate_jwt:
        out["JWT_SECRET"] = secrets.token_urlsafe(48)  # separate from the local one on purpose; not stored anywhere
    assert not (set(out) & NEVER)
    return out


def deploy(api, name: str, private: bool, env: dict, wait: bool = True, bundle_fn=make_space_bundle.bundle, rotate_jwt: bool = False, poll_s: int = 15, max_wait_s: int = 1800) -> dict:
    owner = api.whoami()["name"]
    repo = f"{owner}/{name}"
    new_space = not api.repo_exists(repo, repo_type="space")
    api.create_repo(repo, repo_type="space", space_sdk="docker", private=private, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        files = bundle_fn(Path(tmp) / "space")
        api.upload_folder(folder_path=str(Path(tmp) / "space"), repo_id=repo, repo_type="space", commit_message="Deploy ragx")
    names = []
    for k, v in space_secrets(env, new_space, rotate_jwt).items():
        api.add_space_secret(repo, k, v)
        names.append(k)
    result = {"repo": repo, "new": new_space, "files": len(files), "secrets": names, "private": private, "stage": None, "seconds": None}
    if wait:
        t0 = time.time()
        while time.time() - t0 < max_wait_s:
            stage = api.get_space_runtime(repo).stage
            if stage != result["stage"]:
                print(f"  {int(time.time() - t0):>4}s  stage: {stage}", flush=True)
            result["stage"], result["seconds"] = stage, int(time.time() - t0)
            if stage in DONE_STAGES:
                break
            time.sleep(poll_s)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="ragx")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-wait", action="store_true")
    ap.add_argument("--rotate-jwt", action="store_true")
    a = ap.parse_args()
    load_env()
    if not os.environ.get("HF_TOKEN"):
        sys.exit("HF_TOKEN is not set in .env")
    from huggingface_hub import HfApi

    r = deploy(HfApi(token=os.environ["HF_TOKEN"]), a.name, a.private, dict(os.environ), wait=not a.no_wait, rotate_jwt=a.rotate_jwt)
    host = r["repo"].replace("/", "-").replace("_", "-").lower() + ".hf.space"
    print(f"space {r['repo']} ({'created' if r['new'] else 'updated'}, {'private' if r['private'] else 'public'}): {r['files']} files, secrets set: {', '.join(r['secrets'])}")
    print(f"stage {r['stage']} after {r['seconds']} s; page https://huggingface.co/spaces/{r['repo']}; app https://{host}")


if __name__ == "__main__":
    main()
