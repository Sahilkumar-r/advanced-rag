"""4.1 FastAPI app: auth, RBAC on every route, rate limits, audit log, guardrails around the pipeline, memory endpoints.

create_app takes its dependencies, so tests run with a fake pipeline and no network.
ask_fn(question, memory_text, history) -> dict with text, refused, citations, sources (list[str]).
"""
from __future__ import annotations

import hmac
import time
import uuid
from typing import Callable

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ragx.generate.providers import ProviderError

from ragx.auth import security as sec
from ragx.auth.store import Store
from ragx.guardrails.checks import check_input, check_output
from ragx.memory.memory import KINDS, Memory, format_memory

REFUSE_TEXT = "I can't help with that request."


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
               limiter: sec.RateLimiter | None = None) -> FastAPI:
    key = key or sec.secret()
    limiter = limiter or sec.RateLimiter()
    store.salt = store.salt or hmac.new(key.encode(), b"ip-hash-salt", "sha256").hexdigest()  # a salted hash, never the bare address
    app = FastAPI(title="ragx", docs_url=None, redoc_url=None)

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
    @app.post("/api/ask")
    def ask(b: Ask, request: Request, p: dict = Depends(need("ask"))):
        throttle(p, request)
        v = check_input(b.question, p["role"])
        if v.blocked:
            store.audit(p["sub"], "guardrail_block", v.reason, False, ip(request))
            return {"text": REFUSE_TEXT, "refused": True, "reason": v.reason, "citations": [], "sources": [], "flags": v.flags}
        user_id = uid(p)
        consent = bool(user_id and store.user(user_id)["memory_consent"])
        sess = f"{p['sub']}:{b.session_id}" if b.session_id else None
        mem_text = format_memory(memory.recall(user_id, v.text)) if consent else ""
        out = ask_fn(v.text, mem_text, memory.history(sess) if sess else [])
        ov = check_output(out["text"], len(out["sources"]), out["refused"])
        if sess:
            memory.add_turn(sess, v.text, ov.text)
        if consent and propose_fn:
            for kind, content in propose_fn(v.text, ov.text):
                memory.add(user_id, kind, content, consent=True)  # rules in add() still apply
        return {"text": ov.text, "refused": out["refused"], "citations": out["citations"], "sources": out["sources"], "flags": v.flags + ov.flags, "cache": out.get("cache")}

    @app.post("/api/ask-image")
    def ask_image(p: dict = Depends(need("ask_image"))):
        raise HTTPException(501, "image questions arrive in phase 5")

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
    @app.get("/api/admin/metrics")
    def metrics(p: dict = Depends(need("view_metrics"))):
        return metrics_fn() if metrics_fn else {}

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

    return app
