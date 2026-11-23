"""MCP 的 OAuth 2.1 全流程测试（离线，全部走 Starlette TestClient）。"""
from __future__ import annotations

import urllib.parse

import pytest
from mcp_auth_helpers import (
    REDIRECT,
    authorize,
    code_from,
    exchange,
    full_login,
    login,
    pkce,
    register,
)
from starlette.testclient import TestClient


def test_metadata_and_unauthorized_challenge(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        prm = client.get("/.well-known/oauth-protected-resource/mcp")
        assert prm.status_code == 200
        assert prm.json()["resource"] == "http://127.0.0.1:8765/mcp"
        assert prm.json()["scopes_supported"] == ["douyin.read", "douyin.write"]

        as_meta = client.get("/.well-known/oauth-authorization-server")
        assert as_meta.status_code == 200
        body = as_meta.json()
        assert body["code_challenge_methods_supported"] == ["S256"]
        assert body["registration_endpoint"].endswith("/register")

        challenge = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={"Accept": "application/json, text/event-stream"},
        )
        assert challenge.status_code == 401
        header = challenge.headers["www-authenticate"]
        assert "resource_metadata=" in header
        assert "/.well-known/oauth-protected-resource/mcp" in header


def test_healthz_is_public(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        body = client.get("/healthz").json()
        assert body["ok"] is True
        assert body["tools"] > 40
        assert body["issuer"] == "http://127.0.0.1:8765"


def test_full_authorization_code_flow(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        client_id, token = full_login(client)
        assert token["token_type"] == "Bearer"
        assert token["scope"] == "douyin.read douyin.write"
        assert token["expires_in"] == 3600
        assert client_id

        headers = {"Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {token['access_token']}"}
        init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"}}}, headers=headers)
        assert init.status_code == 200
        assert "DouYin_Spider" in init.text

        headers["mcp-session-id"] = init.headers["mcp-session-id"]
        listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
        assert listed.status_code == 200
        assert "auth_status" in listed.text
        assert "im_send_text" in listed.text


def test_wrong_password_then_lockout(mcp_app):
    with TestClient(mcp_app(login_max_fails=2), follow_redirects=False) as client:
        _verifier, challenge = pkce()
        client_id = register(client)
        req = authorize(client, client_id, challenge)

        bad = login(client, req, password="wrong")
        assert bad.status_code == 401
        assert "用户名或密码不正确" in bad.text

        assert login(client, req, password="wrong2").status_code == 401

        # 超过阈值后，即使密码正确也要等锁过期
        blocked = login(client, req)
        assert blocked.status_code == 429
        assert "尝试次数过多" in blocked.text


def test_pkce_mismatch_rejected(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        verifier, challenge = pkce()
        client_id = register(client)
        req = authorize(client, client_id, challenge)
        code = code_from(login(client, req))

        wrong = exchange(client, client_id, code, "definitely-the-wrong-verifier")
        assert wrong.status_code == 400
        assert wrong.json()["error"] == "invalid_grant"


def test_authorization_code_is_single_use(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        verifier, challenge = pkce()
        client_id = register(client)
        req = authorize(client, client_id, challenge)
        code = code_from(login(client, req))

        assert exchange(client, client_id, code, verifier).status_code == 200
        replay = exchange(client, client_id, code, verifier)
        assert replay.status_code == 400
        assert replay.json()["error"] == "invalid_grant"


def test_refresh_rotates_and_old_token_dies(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        client_id, token = full_login(client)
        first = client.post("/token", data={
            "grant_type": "refresh_token", "refresh_token": token["refresh_token"], "client_id": client_id})
        assert first.status_code == 200
        assert first.json()["access_token"] != token["access_token"]

        reuse = client.post("/token", data={
            "grant_type": "refresh_token", "refresh_token": token["refresh_token"], "client_id": client_id})
        assert reuse.status_code == 400
        assert reuse.json()["error"] == "invalid_grant"


def test_revocation_kills_access_token(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        client_id, token = full_login(client)
        revoked = client.post("/revoke", data={
            "token": token["access_token"], "client_id": client_id, "client_secret": ""})
        assert revoked.status_code == 200, revoked.text

        headers = {"Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {token['access_token']}"}
        after = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"}}}, headers=headers)
        assert after.status_code == 401


def test_redirect_uri_must_match_registration(mcp_app):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        _verifier, challenge = pkce()
        client_id = register(client, redirect=REDIRECT)
        response = client.get("/authorize", params={
            "client_id": client_id,
            "redirect_uri": "http://127.0.0.1:9998/evil",
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        assert response.status_code == 400

        unknown = client.get("/authorize", params={
            "client_id": "not-a-client",
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        assert unknown.status_code == 400


@pytest.mark.parametrize("tampered", ["", "abc.def", "eyJleHAiOjB9.bad"])
def test_tampered_login_request_rejected(mcp_app, tampered):
    with TestClient(mcp_app(), follow_redirects=False) as client:
        assert client.get("/login", params={"req": tampered}).status_code == 400
