"""MCP 工具层测试：注册表、schema、序列化、scope 门禁、错误包装、写限流。"""
from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal

import jsonschema
import pytest
from mcp_auth_helpers import full_login, initialize, rpc
from mcp_server import tools as tool_pkg
from mcp_server.tools import _common
from mcp_server.tools.advanced import douyin_api_call
from starlette.testclient import TestClient


@pytest.fixture(scope="module", autouse=True)
def loaded_tools():
    tool_pkg.load_all()


def test_registry_names_are_unique_and_complete():
    names = [spec.name for spec in _common.TOOLS]
    assert len(names) == len(set(names)), "工具名重复"
    assert len(names) >= 45
    for expected in ("auth_status", "work_info", "search_works", "live_info", "im_send_text",
                     "creator_publish_video", "download_work", "douyin_api_call"):
        assert expected in names


def test_write_tools_are_classified():
    write_names = {spec.name for spec in _common.TOOLS if not spec.read_only}
    assert {"publish_comment", "im_send_text", "creator_publish_images", "live_send_danmaku",
            "download_work", "crawl_user"} <= write_names
    assert "auth_status" not in write_names
    for spec in _common.TOOLS:
        if spec.read_only:
            assert "douyin.read" in spec.scopes
        else:
            assert "douyin.write" in spec.scopes


def test_every_tool_exposes_a_valid_schema(mcp_app):
    app = mcp_app()
    server = app.state.mcp_server
    assert app.state.mcp_tools

    listed = asyncio.run(server.list_tools())
    assert len(listed) == len(app.state.mcp_tools)
    for tool in listed:
        schema = tool.inputSchema
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["type"] == "object"
        assert "args" not in schema.get("properties", {})
        assert "kwargs" not in schema.get("properties", {})


def test_json_safe_handles_common_types():
    payload = {
        "when": datetime(2026, 11, 24, 10, 30, 0),
        "raw": b"\xff\xfe",
        "text": "弹幕".encode(),
        "price": Decimal("1.25"),
        "nested": [{"a": (1, 2)}],
    }
    safe = _common.json_safe(payload)
    assert safe["when"] == "2026-11-24T10:30:00"
    assert safe["raw"] == "//4="
    assert safe["text"] == "弹幕"
    assert safe["price"] == 1.25
    assert safe["nested"] == [{"a": [1, 2]}]


def test_api_call_rejects_unknown_method():
    with pytest.raises(ValueError):
        douyin_api_call("rm_rf")


def test_api_call_rejects_reserved_params():
    with pytest.raises(ValueError) as exc:
        douyin_api_call("get_device_id", {"auth": {}})
    assert "auth" in str(exc.value)


def test_write_rate_limiter_blocks_burst():
    limiter = _common.WriteRateLimiter(limit=2, window=60)
    limiter.check()
    limiter.check()
    with pytest.raises(Exception):
        limiter.check()


def test_write_tools_not_registered_when_disabled(make_config):
    config = make_config(enable_write=False)
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("test")
    registered = _common.register_tools(server, config)
    assert "auth_status" in registered
    assert "im_send_text" not in registered
    assert len(registered) < len(_common.TOOLS)


def test_read_only_token_cannot_call_write_tool(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        _client_id, token = full_login(client, scope="douyin.read")
        assert token["scope"] == "douyin.read"
        session, _info = initialize(client, token["access_token"])
        status, body, _session = rpc(client, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "im_send_text", "arguments": {"target": "123", "text": "hi"}},
        }, token["access_token"], session)
        assert status == 200
        assert body["result"]["isError"] is True
        assert "scope" in str(body["result"]["content"])


def test_tool_exception_is_wrapped_without_secrets(mcp_app, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("cookie=SECRET_VALUE 出错")

    monkeypatch.setattr("mcp_server.tools.account.douyin_auth", boom)
    with TestClient(mcp_app(), follow_redirects=False) as client:
        _client_id, token = full_login(client)
        session, _info = initialize(client, token["access_token"])
        status, body, _session = rpc(client, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "auth_status", "arguments": {}},
        }, token["access_token"], session)
        assert status == 200
        assert body["result"]["isError"] is True
        text = str(body["result"]["content"])
        assert "RuntimeError" in text
