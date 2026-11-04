# Deploying to a Hugging Face Space (Phase 8)

Nothing here pushes, creates or publishes anything by itself. Each outward step below needs the owner's decision first (CLAUDE.md).

## What is ready
- `Dockerfile` and `.dockerignore`: a two stage image. Stage 1 fetches the docs at the commits pinned in `eval/datasets/docs.lock.json`; the final image
  installs the dependencies, pre computes the embeddings (`scripts/prebuild.py`), runs as user 1000 and listens on port 7860 (`scripts/space_entry.py`).
  The `.dockerignore` is an allow list, so `.env`, `.git`, `data/` and `traces/` cannot enter an image.
- `scripts/run_space_local.py up|down|logs`: runs the built image the way a Space does, with secrets passed by name.
- `scripts/make_space_bundle.py <empty folder>`: assembles the Space repo tree from the same allow list, plus `deploy/hf-space-README.md` as the Space
  README (it holds the `sdk: docker` and `app_port: 7860` front matter).

## Secrets (you enter these in the Space settings, never in a file)
Required: `JWT_SECRET` (32+ characters), `GROQ_API_KEY`, `GEMINI_API_KEY`. Recommended: `CEREBRAS_API_KEY`, `OPENROUTER_API_KEY`.
Demo logins: `DEMO_ADMIN_PASSWORD`, `DEMO_DEVELOPER_PASSWORD`, `DEMO_VIEWER_PASSWORD` (12+ characters each); without them only guest access works.
Optional: `METRICS_TOKEN` (enables `/metrics`), `RAGX_ONLINE_JUDGE_RATE` (default 0.05). Do not set `OPENAI_API_KEY`: the app does not need it and CI never gets it.
Generate values locally with `python scripts/init_env.py` (it prints names only; open `.env` yourself to copy a value).

## Steps, in order
1. **Decided (2026-11-05):** a public GitHub repository, `Sahilkumar-r/advanced-rag`.
2. **8.2 GitHub** (done 2026-11-05): the repository was created and `main` pushed. `python scripts/set_github_secrets.py` set the repository secrets
   `GROQ_API_KEY`, `GEMINI_API_KEY` and `OPENAI_API_KEY` from `.env` (values go to `gh` on stdin; no workflow reads the OpenAI one). Without the first two
   the nightly and weekly eval workflows skip with a notice. To add more, for example `CEREBRAS_API_KEY`, run the script with those names.
3. **8.3 Space.** `python scripts/deploy_space.py` does all of this (create the Space, upload the bundle, set the secrets, watch the build) using `HF_TOKEN`
   from `.env`. **Blocked on 2026-11-05:** the API answered `402 Payment Required`, because Docker Spaces on free cpu-basic now need a Hugging Face PRO
   subscription. The manual route below needs the same plan. Create a Space with the Docker SDK, then
   `python scripts/make_space_bundle.py <empty folder>`, commit that folder to the Space's git repo and push it. Enter the secrets above in the
   Space settings, wait for the build, and open the Space URL.
4. **Test and record:** on a laptop and on a real phone (sign in, ask, voice, image, memory, admin), and note the cold start time.
5. **8.4 and 8.5:** put the measured numbers and the limits in the README (done as far as measured), and update the roadmap tracker (`deploy/portfolio.md` has a draft).

## Limits to keep in the open
- The free Space disk is ephemeral: users are re seeded on every start, and memories and the audit log are lost on restart. A Space can also sleep when
  idle, so the first request can be slow (check the current Hugging Face rules; no figure here is measured).
- Behind the Space proxy every visitor shares one address unless `RAGX_TRUST_PROXY=1` is set, which is only safe if the container can be reached
  through the proxy alone; with it off, the per address guest limit is shared by everyone.
- Free tier providers can rate limit or remove models; the router falls back and `docs/FREE-APIS.md` carries the check date.
