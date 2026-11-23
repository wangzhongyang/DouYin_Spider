"""OAuth 2.1 授权服务器实现（自建登录页当 IdP）。

``mcp`` SDK 负责对外暴露 ``/authorize``、``/token``、``/register``、``/revoke``
和各项元数据，并做 PKCE 校验；它唯一不知道的是"人怎么证明自己是账号主人"。
这里把这个缺口补上：

1. SDK 调 ``authorize()`` → 我们签发一个短时效的 HMAC 签名串，把人引到 ``/login``；
2. 登录页校验 ``MCP_USERNAME``/``MCP_PASSWORD`` → 用同一份签名串里的
   client/redirect/PKCE 信息生成一次性授权码 → 302 回客户端；
3. SDK 的 ``/token`` 用 ``load_authorization_code`` + ``exchange_authorization_code``
   把码换成 token（PKCE 由 SDK 校验）。

令牌是 opaque 随机串，库里只存 sha256；refresh 每次轮换。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import quote

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from ..config import ALL_SCOPES, MCPConfig, SCOPE_READ
from .store import OAuthStore

LOGIN_REQUEST_TTL = 600  # 登录链接有效期：10 分钟
AUTH_CODE_TTL = 120  # 授权码有效期，RFC 6749 §4.1.2 建议短


class InvalidLoginRequest(Exception):
    """登录链接过期/被篡改/客户端已不存在。"""


class DouyinOAuthProvider(OAuthAuthorizationServerProvider):
    def __init__(self, config: MCPConfig, store: OAuthStore, clock=time.time):
        self.config = config
        self.store = store
        self._clock = clock
        self._key = config.secret_key.encode("utf-8")

    # ── 客户端 ───────────────────────────────────────────────
    def static_client(self) -> OAuthClientInformationFull | None:
        """``.env`` 里预注册的客户端，给不做 DCR 的客户端用。"""
        if not self.config.static_client_id:
            return None
        return OAuthClientInformationFull(
            client_id=self.config.static_client_id,
            client_secret=self.config.static_client_secret or None,
            client_name="pre-registered client",
            redirect_uris=[AnyUrl(uri) for uri in self.config.static_client_redirect_uris],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            token_endpoint_auth_method=(
                "client_secret_post" if self.config.static_client_secret else "none"
            ),
            scope=" ".join(ALL_SCOPES),
        )

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        static = self.static_client()
        if static is not None and static.client_id == client_id:
            return static
        return self.store.get_client(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        static = self.static_client()
        if static is not None and static.client_id == client_info.client_id:
            raise RegistrationError("invalid_client_metadata", "client_id 与预注册客户端冲突")
        self.store.save_client(client_info)

    # ── 授权（把我们自己的登录页当 IdP）─────────────────────
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        scopes = [s for s in (params.scopes or [SCOPE_READ]) if s in ALL_SCOPES] or [SCOPE_READ]
        payload = {
            "cid": client.client_id,
            "ruri": str(params.redirect_uri),
            "ruri_explicit": bool(params.redirect_uri_provided_explicitly),
            "state": params.state,
            "challenge": params.code_challenge,
            "scopes": scopes,
            "resource": params.resource,
            "exp": int(self._clock()) + LOGIN_REQUEST_TTL,
        }
        return f"{self.config.public_url}/login?req={quote(self.sign(payload), safe='')}"

    # ── 签名 / 验签 ──────────────────────────────────────────
    def sign(self, payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        sig = hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify_login_request(self, value: str) -> dict:
        try:
            body, sig = value.split(".", 1)
        except ValueError as exc:
            raise InvalidLoginRequest("授权链接格式不正确") from exc
        expected = hmac.new(self._key, body.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise InvalidLoginRequest("授权链接签名不匹配")
        padded = body + "=" * (-len(body) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        except Exception as exc:
            raise InvalidLoginRequest("授权链接内容无法解析") from exc
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) < self._clock():
            raise InvalidLoginRequest("授权链接已过期，请回到客户端重新发起授权")
        if not payload.get("cid") or not payload.get("ruri") or not payload.get("challenge"):
            raise InvalidLoginRequest("授权链接缺少必要参数")
        return payload

    def issue_authorization_code(self, payload: dict) -> str:
        """登录成功后生成一次性授权码（已由 SDK 校验过 client 与 redirect_uri）。"""
        code = secrets.token_urlsafe(32)  # 256 bit
        record = AuthorizationCode(
            code=code,
            scopes=[s for s in payload.get("scopes", [SCOPE_READ]) if s in ALL_SCOPES] or [SCOPE_READ],
            expires_at=self._clock() + AUTH_CODE_TTL,
            client_id=payload["cid"],
            code_challenge=payload["challenge"],
            redirect_uri=AnyUrl(payload["ruri"]),
            redirect_uri_provided_explicitly=bool(payload.get("ruri_explicit", True)),
            resource=payload.get("resource"),
            subject=self.config.username,
        )
        self.store.save_code(record)
        return code

    # ── 授权码兑换 ───────────────────────────────────────────
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return self.store.load_code(authorization_code, client.client_id)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        stored = self.store.load_code(authorization_code.code, client.client_id)
        if stored is None:
            raise TokenError("invalid_grant", "authorization code 不存在或已过期")
        # 先核销再发令牌：并发二次兑换也只会有一次成功
        self.store.delete_code(authorization_code.code)
        return self._issue_token(client, stored.scopes, stored.resource, stored.subject)

    # ── refresh ──────────────────────────────────────────────
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        return self.store.load_refresh(refresh_token, client.client_id)

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        stored = self.store.load_refresh(refresh_token.token, client.client_id)
        if stored is None:
            raise TokenError("invalid_grant", "refresh token 无效或已过期")
        requested = [s for s in (scopes or stored.scopes) if s in ALL_SCOPES]
        unknown = set(requested) - set(stored.scopes)
        if unknown:
            raise TokenError("invalid_scope", f"refresh 不能扩权: {sorted(unknown)}")
        self.store.delete_refresh(refresh_token.token)  # 轮换：旧的立刻作废
        return self._issue_token(
            client,
            requested or stored.scopes,
            stored.resource,
            stored.subject,
        )

    # ── access token ─────────────────────────────────────────
    async def load_access_token(self, token: str) -> AccessToken | None:
        return self.store.load_access(token)

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.store.delete_access(token.token)
        self.store.delete_refresh(token.token)

    # ── 内部 ─────────────────────────────────────────────────
    def _issue_token(
        self,
        client: OAuthClientInformationFull,
        scopes: list[str],
        resource: str | None,
        subject: str | None,
    ) -> OAuthToken:
        now = self._clock()
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(48)
        self.store.save_access(
            AccessToken(
                token=access,
                client_id=client.client_id,
                scopes=list(scopes),
                expires_at=int(now + self.config.access_ttl),
                resource=resource or self.config.resource_url,
                subject=subject,
            )
        )
        self.store.save_refresh(
            RefreshToken(
                token=refresh,
                client_id=client.client_id,
                scopes=list(scopes),
                expires_at=int(now + self.config.refresh_ttl),
                resource=resource or self.config.resource_url,
                subject=subject,
            )
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=self.config.access_ttl,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )
