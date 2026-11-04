"""4.1 FastAPI app: auth, RBAC on every route, rate limits, audit log, guardrails around the pipeline, memory endpoints.

create_app takes its dependencies, so tests run with a fake pipeline and no network.
ask_fn(question, memory_text, history) -> dict with text, refused, citations, sources (list[str]).
"""
from __future__ import annotations

import hmac
import random
import time
import uuid
from pathlib import Path
from typing import Callable

import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ragx.generate.providers import ProviderError
from ragx.observability.metrics import Observer
from ragx.vision import image as vimg
from ragx.voice import stt

from ragx.auth import security as sec
from ragx.auth.store import Store
from ragx.guardrails.checks import check_input, check_output
from ragx.memory.memory import KINDS, Memory, format_memory

REFUSE_TEXT = "I can't help with that request."
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; "
                               "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Permissions-Policy": "microphone=(self), camera=(), geolocation=()",
}


class Feedback(BaseModel):
    trace_id: str | None = Field(default=None, max_length=32)
    value: int


class UserPatch(BaseModel):
    role: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)  # bounded so a huge password cannot burn CPU in argon2


class Refresh(BaseModel):
    refresh: str = Field(max_length=2000)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    session_id: str | None = Field(default=None, max_length=64)


class NewUser(BaseModel):
    email: str
    password: str = Field(min_length=12)
    role: str


class NewMemory(BaseModel):
    kind: str = Field(max_length=20)
    content: str = Field(max_length=1000)


class Consent(BaseModel):
    consent: bool


def create_app(store: Store, ask_fn: Callable[[str, str, list], dict], memory: Memory, key: str | None = None,
               metrics_fn: Callable[[], dict] | None = None, propose_fn: Callable[[str, str], list] | None = None,
               limiter: sec.RateLimiter | None = None, transcribe_fn: Callable[[bytes, str], str] | None = None,
               vision_fn: Callable[[bytes, str, str], dict] | None = None, observer: Observer | None = None,
               judge_fn: Callable[[str, list, str], float | None] | None = None, judge_rate: float = 0.0, web_dir: Path | None = None,
               metrics_token: str | None = None, evals_fn: Callable[[], list] | None = None) -> FastAPI:
    obs = observer or Observer()
    key = key or sec.secret()
    limiter = limiter or sec.RateLimiter()
    store.salt = store.salt or hmac.new(key.encode(), b"ip-hash-salt", "sha256").hexdigest()  # a salted hash, never the bare address
    app = FastAPI(title="ragx", docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def instrument(request: Request, call_next):
        t = time.perf_counter()
        resp = await call_next(request)
        route = getattr(request.scope.get("route"), "path", None)  # the route template, so ids in paths do not explode the labels
        obs.request(route if route and route != "/" else "other", request.method, resp.status_code, time.perf_counter() - t)
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        return resp

    @app.exception_handler(ProviderError)
    def provider_down(request: Request, exc: ProviderError):
        return JSONResponse({"detail": "the answer service is busy, try again shortly"}, status_code=503)  # no provider text goes to the client

    def ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def principal(request: Request, authorization: str | None = Header(default=None)) -> dict:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing token")
        try:
            d = sec.decode_token(authorization[7:], key, "access")
        except jwt.PyJWTError:
            raise HTTPException(401, "invalid or expired token")
        if not d["sub"].startswith("guest:"):  # re-check the account on every call so a disabled user loses access at once
            u = store.user(int(d["sub"]))
            if not u or not u["is_active"]:
                raise HTTPException(401, "account disabled")
            d["role"] = u["role"]  # the database is the source of truth, not the token
        return d

    def need(permission: str):
        def dep(request: Request, p: dict = Depends(principal)) -> dict:
            ok = sec.can(p["role"], permission)
            if not ok or p["role"] == "admin":  # log every denial and every admin action
                store.audit(p["sub"], f"{request.method} {request.url.path}", permission, ok, ip(request))
            if not ok:
                raise HTTPException(403, "forbidden")
            return p
        return dep

    def uid(p: dict) -> int | None:
        return None if p["sub"].startswith("guest:") else int(p["sub"])

    def throttle(p: dict, request: Request) -> None:
        who = f"ip:{ip(request)}" if p["role"] == "guest" else p["sub"]  # guests can mint tokens, so key them by address
        if not limiter.allow(f"ask:{who}", sec.RATE_LIMITS[p["role"]]):
            raise HTTPException(429, "rate limit exceeded")

    def tokens(user_id: int, role: str) -> dict:
        refresh = sec.make_token(str(user_id), role, "refresh", key)
        store.save_refresh(refresh, user_id, time.time() + sec.REFRESH_TTL_S)
        return {"access": sec.make_token(str(user_id), role, "access", key), "refresh": refresh, "role": role}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # --- auth -----------------------------------------------------------
    @app.post("/api/auth/login")
    def login(b: Login, request: Request):
        if not limiter.allow(f"login:{ip(request)}", 10) or not limiter.allow(f"login-email:{b.email.lower()}", 10):  # per address and per account
            raise HTTPException(429, "too many attempts")
        u = store.user_by_email(b.email)
        ok = sec.verify_password(u["password_hash"] if u else None, b.password) and bool(u and u["is_active"])
        store.audit(u["id"] if u else None, "login", None, ok, ip(request))
        if not ok:
            raise HTTPException(401, "invalid credentials")  # same message for unknown email and wrong password
        store.touch_login(u["id"])
        return tokens(u["id"], u["role"])

    @app.post("/api/auth/refresh")
    def refresh(b: Refresh, request: Request):
        if not limiter.allow(f"refresh:{ip(request)}", 30):
            raise HTTPException(429, "too many attempts")
        try:
            d = sec.decode_token(b.refresh, key, "refresh")
        except jwt.PyJWTError:
            raise HTTPException(401, "invalid refresh token")
        owner = store.refresh_user(b.refresh)  # also revokes every token of the user if a rotated one is replayed
        u = store.user(owner) if owner is not None and d["sub"] == str(owner) else None
        if not u or not u["is_active"]:
            raise HTTPException(401, "invalid refresh token")
        store.revoke_refresh(b.refresh)  # rotation: a refresh token works once
        return tokens(u["id"], u["role"])

    @app.post("/api/auth/logout")
    def logout(b: Refresh):
        store.revoke_refresh(b.refresh)
        return {"ok": True}

    @app.post("/api/auth/guest")
    def guest(request: Request):
        if not limiter.allow(f"guest:{ip(request)}", 5):
            raise HTTPException(429, "too many guest sessions")
        return {"access": sec.make_token(f"guest:{uuid.uuid4().hex}", "guest", "access", key, ttl_s=3600), "role": "guest"}

    # --- ask ------------------------------------------------------------
    def blocked(reason: str, flags: list[str], modality: str) -> dict:
        obs.guardrail(reason)
        obs.ask("blocked", None, 0.0, 0, modality)
        return {"text": REFUSE_TEXT, "refused": True, "reason": reason, "citations": [], "sources": [], "source_details": [], "flags": flags}

    def score_online(question: str, sources: list, text: str) -> None:
        try:
            obs.online_faithfulness(judge_fn(question, sources, text))
        except Exception:  # a judge outage must never touch the user's request; it is counted
            obs.judged.labels("error").inc()

    def respond(out: dict, flags: list[str], modality: str, t0: float, question: str, background: BackgroundTasks) -> tuple[object, dict]:
        ov = check_output(out["text"], len(out["sources"]), out["refused"])
        for f in flags + ov.flags:
            obs.guardrail(f.split(":")[0])
        obs.ask("refused" if out["refused"] else "answered", out.get("cache"), (time.perf_counter() - t0) * 1000, out.get("tokens", 0), modality)
        if judge_fn and judge_rate and not out["refused"] and out.get("_sources") and random.random() < judge_rate:
            background.add_task(score_online, question, out["_sources"], ov.text)  # runs after the response is sent
        return ov, {"text": ov.text, "refused": out["refused"], "citations": out["citations"], "sources": out["sources"], "source_details": out.get("source_details", []),
                    "flags": flags + ov.flags, "cache": out.get("cache"), "trace_id": out.get("trace_id"), "steps": out.get("steps", [])}

    @app.post("/api/ask")
    def ask(b: Ask, request: Request, background: BackgroundTasks, p: dict = Depends(need("ask"))):
        throttle(p, request)
        t0 = time.perf_counter()
        v = check_input(b.question, p["role"])
        if v.blocked:
            store.audit(p["sub"], "guardrail_block", v.reason, False, ip(request))
            return blocked(v.reason, v.flags, "text")
        user_id = uid(p)
        consent = bool(user_id and store.user(user_id)["memory_consent"])
        sess = f"{p['sub']}:{b.session_id}" if b.session_id else None
        mem_text = format_memory(memory.recall(user_id, v.text)) if consent else ""
        out = ask_fn(v.text, mem_text, memory.history(sess) if sess else [])
        ov, body = respond(out, v.flags, "text", t0, v.text, background)
        if sess:
            memory.add_turn(sess, v.text, ov.text)
        if consent and propose_fn:
            for kind, content in propose_fn(v.text, ov.text):
                memory.add(user_id, kind, content, consent=True)  # rules in add() still apply
        return body

    @app.post("/api/ask-voice")
    async def ask_voice(request: Request, audio: UploadFile = File(...), p: dict = Depends(need("ask"))):
        """Returns the transcript only. The client shows it, the user confirms, and then it goes to /api/ask like typed text."""
        if transcribe_fn is None:
            raise HTTPException(503, "voice input is not configured")
        throttle(p, request)
        data = await audio.read(stt.MAX_BYTES + 1)
        if len(data) > stt.MAX_BYTES:
            raise HTTPException(413, "audio too large")
        kind = stt.sniff_audio(data)
        if kind is None:
            raise HTTPException(415, "unsupported audio type")
        return {"transcript": transcribe_fn(data, kind), "confirm": True}  # bytes are dropped here, never stored

    @app.post("/api/ask-image")
    async def ask_image(request: Request, background: BackgroundTasks, image: UploadFile = File(...), question: str = Form(default="", max_length=500), p: dict = Depends(need("ask_image"))):
        if vision_fn is None:
            raise HTTPException(503, "image input is not configured")
        throttle(p, request)
        t0 = time.perf_counter()
        data = await image.read(vimg.MAX_BYTES + 1)
        if len(data) > vimg.MAX_BYTES:
            raise HTTPException(413, "image too large")
        mime = vimg.sniff_image(data)
        if mime is None:
            raise HTTPException(415, "unsupported image type")
        qv = check_input(question, p["role"]) if question else None
        if qv and qv.blocked:
            store.audit(p["sub"], "guardrail_block", qv.reason, False, ip(request))
            return blocked(qv.reason, qv.flags, "image")
        d = vision_fn(data, mime, qv.text if qv else "")
        if d.get("blocked"):  # instructions hidden inside the picture
            store.audit(p["sub"], "guardrail_block", f"image:{d['blocked']}", False, ip(request))
            return blocked("image_" + d["blocked"], ["image_injection"], "image")
        query = vimg.make_query(qv.text if qv else "", d)
        if not query:
            obs.ask("refused", None, (time.perf_counter() - t0) * 1000, 0, "image")
            return {"text": "I could not read anything useful in that image.", "refused": True, "reason": "unreadable", "citations": [], "sources": [], "source_details": [], "flags": []}
        out = ask_fn(query, "", [])
        _, body = respond(out, [], "image", t0, query, background)
        return {**body, "read_from_image": {"kind": d.get("kind"), "summary": d.get("summary"), "error_text": d.get("error_text")}}

    @app.get("/api/history")
    def history(session_id: str, p: dict = Depends(need("view_history"))):
        return {"turns": memory.history(f"{p['sub']}:{session_id}")}  # scoped to the caller, never to a bare session id

    # --- memory ---------------------------------------------------------
    @app.get("/api/memories")
    def memories(p: dict = Depends(need("manage_memory"))):
        return {"memories": memory.list(uid(p)), "consent": bool(store.user(uid(p))["memory_consent"]), "kinds": list(KINDS)}

    @app.post("/api/memories/consent")
    def consent(b: Consent, p: dict = Depends(need("manage_memory"))):
        store.set_consent(uid(p), b.consent)
        if not b.consent:
            memory.delete_all(uid(p))  # withdrawing consent erases what was stored
        return {"consent": b.consent}

    @app.post("/api/memories")
    def add_memory(b: NewMemory, p: dict = Depends(need("manage_memory"))):
        ok, reason = memory.add(uid(p), b.kind, b.content, consent=bool(store.user(uid(p))["memory_consent"]))
        if not ok:
            raise HTTPException(422, reason)
        return {"stored": True}

    @app.delete("/api/memories/{memory_id}")
    def delete_memory(memory_id: int, p: dict = Depends(need("manage_memory"))):
        if not memory.delete(uid(p), memory_id):
            raise HTTPException(404, "not found")  # also the answer for someone else's memory
        return {"deleted": True}

    # --- admin ----------------------------------------------------------
    @app.get("/api/me")
    def me(p: dict = Depends(principal)):
        u = None if p["sub"].startswith("guest:") else store.user(int(p["sub"]))
        return {"role": p["role"], "email": u["email"] if u else None, "guest": u is None, "memory_consent": bool(u and u["memory_consent"]), "permissions": sorted(sec.MATRIX[p["role"]])}

    @app.post("/api/feedback")
    def feedback(b: Feedback, p: dict = Depends(need("ask"))):
        if b.value not in (-1, 1):
            raise HTTPException(422, "value must be -1 or 1")
        if not limiter.allow(f"fb:{p['sub']}", 60):
            raise HTTPException(429, "too many requests")
        obs.thumbs(b.value)
        return {"ok": True}

    @app.get("/metrics")
    def prometheus(authorization: str | None = Header(default=None)):
        """Prometheus scrape target. Off unless METRICS_TOKEN is set; scrapers send it as a bearer token."""
        if not metrics_token:
            raise HTTPException(404, "not found")
        given = (authorization or "").removeprefix("Bearer ").strip()
        if not hmac.compare_digest(given.encode(), metrics_token.encode()):
            raise HTTPException(401, "unauthorized")
        return Response(obs.exposition(), media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/api/admin/metrics")
    def metrics(p: dict = Depends(need("view_metrics"))):
        return {**obs.snapshot(), **(metrics_fn() if metrics_fn else {})}

    @app.get("/api/admin/evals")
    def evals(p: dict = Depends(need("view_metrics"))):
        return {"results": evals_fn() if evals_fn else []}

    @app.patch("/api/admin/users/{user_id}")
    def patch_user(user_id: int, b: UserPatch, p: dict = Depends(need("manage_users"))):
        if str(user_id) == p["sub"]:
            raise HTTPException(400, "you cannot change your own role or status")  # avoids locking the last admin out
        if b.role is not None and b.role not in sec.ROLES:
            raise HTTPException(422, "unknown role")
        if not store.update_user(user_id, b.role, b.is_active):
            raise HTTPException(404, "not found")
        return {"ok": True}

    @app.post("/api/admin/evals/run")
    def run_evals(p: dict = Depends(need("run_evals"))):
        raise HTTPException(501, "eval runs from the UI arrive in phase 7")

    @app.get("/api/admin/users")
    def users(p: dict = Depends(need("manage_users"))):
        return {"users": store.users()}

    @app.post("/api/admin/users", status_code=201)
    def create_user(b: NewUser, p: dict = Depends(need("manage_users"))):
        if b.role not in sec.ROLES:
            raise HTTPException(422, "unknown role")
        if store.user_by_email(b.email):
            raise HTTPException(409, "email exists")
        return {"id": store.create_user(b.email, sec.hash_password(b.password), b.role)}

    @app.get("/api/admin/audit")
    def audit(p: dict = Depends(need("manage_users"))):
        return {"rows": store.audit_rows()}

    if web_dir:  # last, so every API route above wins over the static files
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app
