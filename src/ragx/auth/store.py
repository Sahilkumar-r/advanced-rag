"""4.1 SQLite store for users, refresh tokens (hash only) and the audit log. One connection per call keeps it thread safe for a demo."""
from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1, memory_consent INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, last_login_at REAL);
CREATE TABLE IF NOT EXISTS refresh_tokens(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at REAL NOT NULL, revoked_at REAL);
CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, user_id TEXT, action TEXT NOT NULL, target TEXT, allowed INTEGER NOT NULL, ip_hash TEXT, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, embedding BLOB,
  consent INTEGER NOT NULL, created_at REAL NOT NULL, expires_at REAL);
CREATE INDEX IF NOT EXISTS memories_user ON memories(user_id, kind);
"""


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class _Conn:
    """Context manager: commit on success, roll back on error, always close."""

    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, timeout=10)  # wait for a write lock instead of failing with "database is locked"
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, *_):
        (self.conn.rollback if exc_type else self.conn.commit)()
        self.conn.close()


class Store:
    def __init__(self, path: Path | str, ip_salt: str = ""):
        self.path, self.salt = str(path), ip_salt
        with self._c() as c:
            c.executescript(SCHEMA)

    def _c(self) -> _Conn:
        return _Conn(self.path)

    def create_user(self, email: str, password_hash: str, role: str) -> int:
        with self._c() as c:
            return c.execute("INSERT INTO users(email,password_hash,role,created_at) VALUES(?,?,?,?)", (email.lower(), password_hash, role, time.time())).lastrowid

    def user_by_email(self, email: str):
        with self._c() as c:
            return c.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()

    def user(self, user_id: int):
        with self._c() as c:
            return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    def users(self) -> list[dict]:
        with self._c() as c:
            return [dict(r) | {"password_hash": None} for r in c.execute("SELECT * FROM users ORDER BY id")]

    def touch_login(self, user_id: int) -> None:
        with self._c() as c:
            c.execute("UPDATE users SET last_login_at=? WHERE id=?", (time.time(), user_id))

    def set_consent(self, user_id: int, consent: bool) -> None:
        with self._c() as c:
            c.execute("UPDATE users SET memory_consent=? WHERE id=?", (int(consent), user_id))

    def save_refresh(self, token: str, user_id: int, expires_at: float) -> None:
        with self._c() as c:
            c.execute("INSERT INTO refresh_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)", (sha(token), user_id, expires_at))

    def refresh_user(self, token: str) -> int | None:
        """The user a live refresh token was issued to, else None. A revoked token being replayed revokes all of that user's tokens."""
        with self._c() as c:
            r = c.execute("SELECT user_id, expires_at, revoked_at FROM refresh_tokens WHERE token_hash=?", (sha(token),)).fetchone()
            if r and r["revoked_at"] is not None:  # reuse after rotation or logout: assume theft
                c.execute("UPDATE refresh_tokens SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL", (time.time(), r["user_id"]))
                return None
        return r["user_id"] if r and r["expires_at"] > time.time() else None

    def revoke_refresh(self, token: str) -> None:
        with self._c() as c:
            c.execute("UPDATE refresh_tokens SET revoked_at=? WHERE token_hash=?", (time.time(), sha(token)))

    def audit(self, user_id, action: str, target: str | None, allowed: bool, ip: str | None = None) -> None:
        with self._c() as c:
            c.execute("INSERT INTO audit_log(user_id,action,target,allowed,ip_hash,ts) VALUES(?,?,?,?,?,?)",
                      (str(user_id) if user_id is not None else None, action, target, int(allowed), sha(self.salt + ip)[:16] if ip else None, time.time()))

    def audit_rows(self, limit: int = 100) -> list[dict]:
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]
