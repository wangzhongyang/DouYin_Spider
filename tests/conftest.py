"""MCP 测试的公共夹具：不读真实 .env，用固定配置 + 临时 SQLite。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.app import build_app  # noqa: E402
from mcp_server.config import MCPConfig  # noqa: E402

DEFAULTS = dict(
    host="127.0.0.1",
    port=8765,
    public_url="http://127.0.0.1:8765",
    username="douyin",
    password="test-password",
    secret_key="test-secret-key-not-for-production",
    access_ttl=3600,
    refresh_ttl=86400,
    enable_write=True,
    write_rate_limit=1000,
    write_rate_window=60,
    static_client_id="",
    static_client_secret="",
    static_client_redirect_uris=[],
    login_max_fails=5,
    login_window=600,
    login_lock_seconds=300,
    im_buffer=5000,
    im_autostart=False,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "testserver"],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
    log_level="INFO",
)


@pytest.fixture
def make_config(tmp_path):
    def _make(**overrides):
        values = dict(DEFAULTS)
        values["db_path"] = tmp_path / "oauth.db"
        values.update(overrides)
        return MCPConfig(**values)

    return _make


@pytest.fixture
def mcp_app(make_config):
    def _build(**overrides):
        return build_app(make_config(**overrides))

    return _build
