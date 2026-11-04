# web: the ragx PWA

Mobile first, no framework and no build step: `index.html`, `styles.css`, `app.js` (ES module), `sw.js`, `manifest.webmanifest`, `icons/`.
The FastAPI app serves this folder at `/` (see `src/ragx/api/factory.py`). Visual direction A, "terminal calm": dark first, green accent,
Fira Code and Fira Sans with system font fallbacks (no font is fetched from a CDN).

## Rules the code follows
- A strict Content Security Policy (set by the API): no inline scripts or styles, no third party requests. All user and model text is
  inserted with `textContent`, never `innerHTML`.
- Tokens live in `sessionStorage`. Chat history, theme and settings live in `localStorage`. The server stores no chat messages.
- No hyphens in user facing text, plain short copy, and limits stated plainly (free tier, may be slow, answers can be wrong).
- Every number on the Evals tab comes from `eval/results/*.json` with the file name and its date.

## Screens (docs/04-DESIGN-BRIEF.md section 4)
| Screen | Status |
|---|---|
| Login and guest | built |
| Chat with typed, voice and image input | built; answers arrive whole, not streamed |
| Answer card: citations, cache and no citation notes, thumbs, copy, why this answer | built; the "confidence cue" is not a probability, it shows only what the checks found |
| Source drawer | built (chunk text, page, link to the original doc; the score is not shown because the retriever does not return one) |
| Refusal state | built (what was searched, nearest pages) |
| History | built, browser only, search and delete |
| Memory manager | built: consent, list by type, add, delete. Editing a note is delete and add |
| Settings | built: theme, spoken replies (browser speech, not verified by ear), privacy note |
| Admin users | built: list, change role, disable, create, audit log |
| Admin evals | built: latest values with source and date. No trend lines yet (one run per metric); Run now is not built |
| Admin system | built: latency, tokens, cache, fallback, refusal, thumbs, online faithfulness, providers. Trends are in Grafana |

## States covered
Loading and "thinking", empty chat with suggestions, offline banner, rate limited, answer service busy, session expired, cold start notice,
mic recording, transcript confirm, image preview, long code answers (scroll and copy), errors in plain words.
Not covered: a provider failover notice per answer (the API does not report it per answer) and a real streaming state.

## Run it
`python scripts/seed_users.py` (needs `JWT_SECRET` and the three demo passwords in `.env`), then `python scripts/serve.py`, then open http://127.0.0.1:8000.
Rebuild the icons with `python scripts/make_icons.py` (needs the `datasets` extra).
