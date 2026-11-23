"""登录跳转链接的 HMAC 密钥。

``MCP_SECRET_KEY`` 缺省时自动生成并落盘（0600），保证重启后仍能验签在途链接。
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from ..config import PROJECT_ROOT

DEFAULT_SECRET_PATH = PROJECT_ROOT / "datas" / "mcp" / "secret.key"


def load_secret(env_value: str = "", path: Path | None = None) -> str:
    """优先用环境变量；没有就复用/生成落盘密钥。"""
    if env_value:
        return env_value

    secret_path = Path(path or DEFAULT_SECRET_PATH)
    try:
        existing = secret_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except FileNotFoundError:
        pass

    secret_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    value = secrets.token_hex(32)
    # O_EXCL：并发启动时只有一个进程能写成功，另一个复用它的值
    try:
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")
    finally:
        try:
            os.chmod(secret_path, 0o600)
        except OSError:  # pragma: no cover - 非 POSIX 场景
            pass
    return value
