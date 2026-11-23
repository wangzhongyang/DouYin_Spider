"""OAuth 状态的 SQLite 存储。

表很小：客户端注册信息、授权码、access/refresh token、登录失败记录。
令牌只存 sha256，明文只在签发那一刻出现在响应里，落盘不落明文。

用标准库 sqlite3（不引额外依赖），进程内单连接 + 互斥锁；WAL 让读写不互相阻塞。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from mcp.server.auth.provider import AccessToken, AuthorizationCode, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id  TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS codes (
    code_hash  TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS access_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    expires_at REAL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    expires_at REAL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    ip  TEXT NOT NULL,
    ts  REAL NOT NULL,
    ok  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_ip_ts ON login_attempts (ip, ts);
"""


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class OAuthStore:
    """轻量持久层；所有方法都是同步的，调用方在事件循环里用 to_thread 或直接调（很快）。"""

    def __init__(self, path: str | Path = ":memory:"):
        self._is_memory = str(path) == ":memory:"
        if not self._is_memory:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        if not self._is_memory:
            # 库里只有 token 的 sha256，但仍是凭据衍生数据，权限收紧到 600
            try:
                os.chmod(path, 0o600)
            except FileNotFoundError:
                pass
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        if not self._is_memory:
            try:
                os.chmod(path, 0o600)
            except OSError:  # pragma: no cover - 非 POSIX 场景
                pass
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            if not self._is_memory:
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.commit()

    # ── 客户端 ───────────────────────────────────────────────
    def save_client(self, client: OAuthClientInformationFull) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO clients (client_id, data, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(client_id) DO UPDATE SET data = excluded.data",
                (client.client_id, client.model_dump_json(), time.time()),
            )
            self._conn.commit()

    def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        if row is None:
            return None
        return OAuthClientInformationFull.model_validate_json(row["data"])

    def delete_client(self, client_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM clients WHERE client_id = ?", (client_id,))
            self._conn.commit()

    # ── 授权码 ───────────────────────────────────────────────
    def save_code(self, code: AuthorizationCode) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO codes (code_hash, client_id, data, expires_at) VALUES (?, ?, ?, ?)",
                (token_hash(code.code), code.client_id, code.model_dump_json(), code.expires_at),
            )
            self._conn.commit()

    def load_code(self, code: str, client_id: str) -> AuthorizationCode | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data, expires_at FROM codes WHERE code_hash = ? AND client_id = ?",
                (token_hash(code), client_id),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] < time.time():
            self.delete_code(code)
            return None
        return AuthorizationCode.model_validate_json(row["data"])

    def delete_code(self, code: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM codes WHERE code_hash = ?", (token_hash(code),))
            self._conn.commit()

    # ── 令牌 ─────────────────────────────────────────────────
    def save_access(self, token: AccessToken) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO access_tokens (token_hash, client_id, data, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash(token.token), token.client_id, token.model_dump_json(), token.expires_at),
            )
            self._conn.commit()

    def load_access(self, token: str) -> AccessToken | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data, expires_at FROM access_tokens WHERE token_hash = ?", (token_hash(token),)
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] is not None and row["expires_at"] < time.time():
            self.delete_access(token)
            return None
        return AccessToken.model_validate_json(row["data"])

    def delete_access(self, token: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM access_tokens WHERE token_hash = ?", (token_hash(token),))
            self._conn.commit()

    def save_refresh(self, token: RefreshToken) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO refresh_tokens (token_hash, client_id, data, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (token_hash(token.token), token.client_id, token.model_dump_json(), token.expires_at),
            )
            self._conn.commit()

    def load_refresh(self, token: str, client_id: str) -> RefreshToken | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data, expires_at FROM refresh_tokens WHERE token_hash = ? AND client_id = ?",
                (token_hash(token), client_id),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] is not None and row["expires_at"] < time.time():
            self.delete_refresh(token)
            return None
        return RefreshToken.model_validate_json(row["data"])

    def delete_refresh(self, token: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash(token),))
            self._conn.commit()

    def purge_expired(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        removed = 0
        with self._lock:
            for table in ("codes", "access_tokens", "refresh_tokens"):
                cur = self._conn.execute(f"DELETE FROM {table} WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
                removed += cur.rowcount or 0
            self._conn.commit()
        return removed

    # ── 登录尝试（限流）─────────────────────────────────────
    def record_attempt(self, ip: str, ok: bool, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        with self._lock:
            self._conn.execute(
                "INSERT INTO login_attempts (ip, ts, ok) VALUES (?, ?, ?)", (ip, ts, int(ok))
            )
            self._conn.commit()

    def failures_since(self, ip: str, since: float) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM login_attempts WHERE ip = ? AND ts >= ? AND ok = 0",
                (ip, since),
            ).fetchone()
        return int(row["n"] if row else 0)

    def last_failure_at(self, ip: str) -> float | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT MAX(ts) AS ts FROM login_attempts WHERE ip = ? AND ok = 0", (ip,)
            ).fetchone()
        return None if row is None or row["ts"] is None else float(row["ts"])

    def prune_attempts(self, before: float) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM login_attempts WHERE ts < ?", (before,))
            self._conn.commit()

    # ── 生命周期 ─────────────────────────────────────────────
    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover
                pass

    def stats(self) -> dict[str, int]:
        with self._lock:
            out = {}
            for table in ("clients", "codes", "access_tokens", "refresh_tokens"):
                out[table] = int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return out

    def dump_json(self) -> str:  # pragma: no cover - 排障用
        return json.dumps(self.stats(), ensure_ascii=False)
