"""测试用的 OAuth 客户端小工具（模拟真实 MCP 客户端的授权码 + PKCE 流程）。"""
from __future__ import annotations

import base64
import hashlib
import secrets
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REDIRECT = "http://127.0.0.1:9999/callback"


def pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def register(client, scope="douyin.read douyin.write", redirect=REDIRECT) -> str:
    response = client.post(
        "/register",
        json={
            "client_name": "pytest",
            "redirect_uris": [redirect],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": scope,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["client_id"]


def authorize(client, client_id, challenge, scope="douyin.read douyin.write", state="st-1") -> str:
    response = client.get(
        "/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "scope": scope,
        },
    )
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    assert "/login?req=" in location
    return urllib.parse.parse_qs(urllib.parse.urlparse(location).query)["req"][0]


def login(client, req, password="test-password", username="douyin"):
    return client.post("/login", data={"req": req, "username": username, "password": password})


def exchange(client, client_id, code, verifier):
    return client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )


def code_from(response) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlparse(response.headers["location"]).query)["code"][0]


def full_login(client, scope="douyin.read douyin.write"):
    verifier, challenge = pkce()
    client_id = register(client, scope=scope)
    req = authorize(client, client_id, challenge, scope=scope)
    response = login(client, req)
    assert response.status_code == 302, response.text
    token = exchange(client, client_id, code_from(response), verifier)
    assert token.status_code == 200, token.text
    return client_id, token.json()


def rpc(client, payload, token, session=None):
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session:
        headers["mcp-session-id"] = session
    response = client.post("/mcp", json=payload, headers=headers)
    data = [line[6:] for line in response.text.splitlines() if line.startswith("data: ")]
    import json

    body = json.loads(data[-1]) if data else response.text
    return response.status_code, body, response.headers.get("mcp-session-id")


def initialize(client, token):
    """跑一次 initialize，返回 (session_id, serverInfo)。"""
    status, body, session = rpc(client, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "pytest", "version": "1"}},
    }, token)
    assert status == 200, body
    return session, body["result"]["serverInfo"]
