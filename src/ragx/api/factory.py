"""Production wiring: builds the real retriever, router, cache, pipeline, memory, speech and vision functions into the API app.

RAGX_MODE picks plain_rag (default: cheaper, and no worse on faithfulness in the phase 2 and 3 evals) or self_rag.
JWT_SECRET (at least 32 characters) must be set. Demo users come from scripts/seed_users.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
from fastapi import FastAPI

from ragx.api.app import create_app
from ragx.auth.store import Store
from ragx.cache.cache import Cache
from ragx.config import ROOT, load_env
from ragx.evals import generation as G
from ragx.evals.summary import latest_results
from ragx.ingest.parent_child import chunk_pages
from ragx.memory.memory import Memory, propose
from ragx.observability.metrics import Observer
from ragx.observability.trace import Tracer
from ragx.pipeline import Pipeline
from ragx.retrieve.hybrid import EMBED_MODEL, Retriever
from ragx.router.router import Router
from ragx.vision import image as vimg
from ragx.voice import stt

RAW, CACHE_DIR = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
# What ask_fn hands to the API layer. "_sources" (objects, for the judge) and "tokens" stay inside: the API builds the client response itself.
PUBLIC_KEYS = ("text", "refused", "citations", "sources", "source_details", "cache", "trace_id", "steps", "tokens", "_sources")


def build_app(db_path: Path | None = None) -> FastAPI:
    from fastembed import TextEmbedding

    load_env()
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    if not pages:
        raise RuntimeError("no docs found: run scripts/fetch_docs.py first")
    parents, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE_DIR)
    emb = TextEmbedding(EMBED_MODEL)
    embed = lambda q: (lambda v: v / np.linalg.norm(v))(np.array(next(iter(emb.query_embed(q))), dtype=np.float32))
    cfg = ROOT / "eval" / "results" / "03-cache.json"
    threshold = json.loads(cfg.read_text(encoding="utf-8"))["chosen"]["threshold"] if cfg.exists() else 0.94
    obs = Observer()
    router = Router(on_call=lambda **k: obs.llm_call(**k))
    cache = Cache(embed, threshold=threshold, namespace="v1")
    manifest_file = RAW / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    pipe = Pipeline(lambda q: retr.search(q, "hybrid", k=8), parents, router, cache, Tracer(), mode=os.environ.get("RAGX_MODE", "plain_rag"),
                    url_for=lambda doc: (manifest.get(doc) or {}).get("url"))
    store = Store(db_path or ROOT / "data" / "state" / "ragx.db")
    memory = Memory(store, embed)
    return create_app(
        store,
        ask_fn=lambda q, mem, hist: {k: v for k, v in pipe.ask(q, memory=mem, history=hist).items() if k in PUBLIC_KEYS},
        memory=memory,
        metrics_fn=lambda: {"router": {k: (dict(v) if isinstance(v, dict) else v) for k, v in router.stats.items()}},
        propose_fn=lambda q, a: propose(router.call, q, a),
        transcribe_fn=lambda data, kind: stt.transcribe(data, kind, prompt=stt.GLOSSARY),
        vision_fn=lambda data, mime, q: vimg.extract(data, mime, q, router.call),
        observer=obs,
        # online reference free quality: a sampled slice of live answers scored by the judge after the response is sent
        judge_fn=lambda q, sources, text: G.faithfulness(G.judge(q, sources, text, router.call)),
        judge_rate=float(os.environ.get("RAGX_ONLINE_JUDGE_RATE", "0.05")),
        web_dir=ROOT / "web",
        metrics_token=os.environ.get("METRICS_TOKEN") or None,
        evals_fn=lambda: latest_results(ROOT / "eval" / "results"),
    )
