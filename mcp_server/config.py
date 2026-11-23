"""MCP 服务配置：全部来自 ``.env``（缺省值见 ``.env.example``）。

和爬虫本体共用同一个 ``.env``：``DY_COOKIES`` 等依旧是抖音登录态，
``MCP_*`` 是这一层 HTTP 服务自己的参数。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "datas" / "mcp" / "oauth.db"

# 允许的 scope：读接口给所有工具，写接口（发评论/私信/发布…）单独一个
SCOPE_READ = "douyin.read"
SCOPE_WRITE = "douyin.write"
ALL_SCOPES = (SCOPE_READ, SCOPE_WRITE)


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return default if value is None else value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:  # 配置写错就早点报错，别带病启动
        raise SystemExit(f"{name} 需要整数，当前是 {raw!r}") from exc


def _env_flag(name: str, default: bool) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "on", "true", "yes", "y"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = _env(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class MCPConfig:
    """一份不可变的运行配置。"""

    host: str
    port: int
    public_url: str
    username: str
    password: str
    secret_key: str
    db_path: Path
    access_ttl: int
    refresh_ttl: int
    enable_write: bool
    write_rate_limit: int
    write_rate_window: int
    static_client_id: str
    static_client_secret: str
    static_client_redirect_uris: list[str]
    login_max_fails: int
    login_window: int
    login_lock_seconds: int
    im_buffer: int
    im_autostart: bool
    allowed_hosts: list[str]
    allowed_origins: list[str]
    log_level: str

    @property
    def resource_url(self) -> str:
        """MCP 端点本身，也是 OAuth 的 resource indicator（RFC 8707）。"""
        return f"{self.public_url}/mcp"

    @property
    def issuer_url(self) -> str:
        return self.public_url

    @classmethod
    def load(cls, env_path: Path | None = None) -> "MCPConfig":
        """读 ``.env`` + 进程环境变量，校验后返回配置。"""
        # 项目根目录的 .env 是唯一事实来源；override=False 让 shell 里的显式导出优先
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_path or (PROJECT_ROOT / ".env"), override=False)
        except Exception:  # pragma: no cover - dotenv 缺失时直接读环境变量
            pass

        public_url = _env("MCP_PUBLIC_URL", "http://127.0.0.1:8765").rstrip("/")
        parsed = urlparse(public_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SystemExit(f"MCP_PUBLIC_URL 必须是 http(s) 绝对地址，当前是 {public_url!r}")

        username = _env("MCP_USERNAME")
        password = _env("MCP_PASSWORD")
        if not username or not password:
            raise SystemExit("MCP_USERNAME / MCP_PASSWORD 不能为空，请在 .env 里配置")

        hostname = parsed.hostname or "127.0.0.1"
        # Host 头白名单：公网域名 + 本机回环（Cloudflare 隧道把 Host 原样带过来）
        default_hosts = [
            hostname,
            f"{hostname}:*",
            "127.0.0.1:*",
            "localhost:*",
            "testserver",  # 测试用的 Starlette TestClient
        ]
        default_origins = [
            public_url,
            "http://127.0.0.1:*",
            "http://localhost:*",
            "https://claude.ai",
            "https://chatgpt.com",
            "https://chat.openai.com",
        ]

        return cls(
            host=_env("MCP_HOST", "127.0.0.1"),
            port=_env_int("MCP_PORT", 8765),
            public_url=public_url,
            username=username,
            password=password,
            secret_key=_env("MCP_SECRET_KEY"),
            db_path=Path(_env("MCP_DB_PATH") or DEFAULT_DB_PATH),
            access_ttl=_env_int("MCP_ACCESS_TOKEN_TTL", 3600),
            refresh_ttl=_env_int("MCP_REFRESH_TOKEN_TTL", 30 * 24 * 3600),
            enable_write=_env_flag("MCP_ENABLE_WRITE", True),
            write_rate_limit=_env_int("MCP_WRITE_RATE_LIMIT", 300),
            write_rate_window=_env_int("MCP_WRITE_RATE_WINDOW", 600),
            static_client_id=_env("MCP_CLIENT_ID"),
            static_client_secret=_env("MCP_CLIENT_SECRET"),
            static_client_redirect_uris=_env_list("MCP_CLIENT_REDIRECT_URIS", []),
            login_max_fails=_env_int("MCP_LOGIN_MAX_FAILS", 5),
            login_window=_env_int("MCP_LOGIN_WINDOW", 600),
            login_lock_seconds=_env_int("MCP_LOGIN_LOCK_SECONDS", 300),
            im_buffer=_env_int("MCP_IM_BUFFER", 5000),
            im_autostart=_env_flag("MCP_IM_AUTOSTART", True),
            allowed_hosts=_env_list("MCP_ALLOWED_HOSTS", default_hosts),
            allowed_origins=_env_list("MCP_ALLOWED_ORIGINS", default_origins),
            log_level=_env("MCP_LOG_LEVEL", "INFO").upper(),
        )
