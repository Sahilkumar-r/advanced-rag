"""4.1 Password hashing, JWT, RBAC matrix and rate limiting. A demo of RBAC, not production identity.

JWT_SECRET must come from the environment (at least 32 chars). There is no default, so a missing secret fails loudly.
"""
from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict, deque

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ROLES = ("admin", "developer", "viewer", "guest")
PERMISSIONS = ("ask", "ask_image", "view_history", "manage_memory", "run_evals", "view_metrics", "manage_users")
MATRIX = {  # docs/05-BACKEND-SCHEMA.md section 4
    "admin": set(PERMISSIONS),
    "developer": {"ask", "ask_image", "view_history", "manage_memory", "view_metrics"},
    "viewer": {"ask", "view_history", "manage_memory"},
    "guest": {"ask"},
}
# Requests per minute. Initial placeholders, to be measured and tuned (docs/05 section 4); not a claim about capacity.
RATE_LIMITS = {"admin": 60, "developer": 30, "viewer": 20, "guest": 5}
ACCESS_TTL_S, REFRESH_TTL_S = 15 * 60, 7 * 24 * 3600

_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash("not-a-real-password")  # verified against when the email is unknown, so timing does not reveal accounts


def can(role: str, permission: str) -> bool:
    return permission in MATRIX.get(role, set())


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(hashed: str | None, password: str) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, password) and hashed is not None
    except (VerificationError, InvalidHashError):
        return False


def secret() -> str:
    s = os.environ.get("JWT_SECRET", "")
    if len(s) < 32:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters")
    return s


def make_token(sub: str, role: str, kind: str, key: str, ttl_s: int | None = None, now: float | None = None) -> str:
    t = int(now if now is not None else time.time())
    ttl = ttl_s if ttl_s is not None else (ACCESS_TTL_S if kind == "access" else REFRESH_TTL_S)
    return jwt.encode({"sub": sub, "role": role, "typ": kind, "iat": t, "exp": t + ttl, "jti": uuid.uuid4().hex}, key, algorithm="HS256")


def decode_token(token: str, key: str, kind: str) -> dict:
    """Raises jwt.PyJWTError for a bad signature, expiry, wrong algorithm, or the wrong token type."""
    d = jwt.decode(token, key, algorithms=["HS256"], options={"require": ["exp", "sub", "typ"]})
    if d["typ"] != kind or d.get("role") not in ROLES:
        raise jwt.InvalidTokenError("wrong token type or role")
    return d


class RateLimiter:
    def __init__(self, now=time.time):
        self.hits: dict[str, deque] = defaultdict(deque)
        self.now = now

    def allow(self, key: str, limit: int, per_s: float = 60.0) -> bool:
        t, q = self.now(), self.hits[key]
        while q and q[0] <= t - per_s:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(t)
        if len(self.hits) > 10000:  # evict idle keys so random addresses cannot grow memory without bound
            for k in [k for k, v in self.hits.items() if not v or v[-1] <= t - per_s]:
                del self.hits[k]
        return True
