"""自建登录页：OAuth 授权码流程里唯一的"人"环节。

``/authorize`` 校验完 client / redirect_uri / PKCE 之后把我们重定向到这里。
页面只做一件事：收 ``MCP_USERNAME`` / ``MCP_PASSWORD``，对上了就发码并把人送回客户端。
失败次数按 IP 记账并锁定，避免公网服务被撞库。
"""
from __future__ import annotations

import html
import hmac
import time
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from starlette.routing import Route

from mcp.server.auth.provider import construct_redirect_uri

from ..config import MCPConfig
from .provider import DouyinOAuthProvider, InvalidLoginRequest
from .store import OAuthStore

PAGE_CSS = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
  background:#0f1115;color:#e6e8ee;font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.card{width:100%;max-width:380px;padding:32px 28px;background:#171a21;border:1px solid #262b36;
  border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.45)}
h1{margin:0 0 4px;font-size:20px;font-weight:600}
.sub{margin:0 0 22px;color:#8b93a7;font-size:13px}
label{display:block;margin:14px 0 6px;font-size:13px;color:#aab2c5}
input{width:100%;padding:11px 12px;background:#0f1115;border:1px solid #2d3341;border-radius:9px;
  color:#e6e8ee;font-size:15px;outline:none}
input:focus{border-color:#4c7dff}
button{width:100%;margin-top:22px;padding:12px;background:#4c7dff;border:0;border-radius:9px;
  color:#fff;font-size:15px;font-weight:600;cursor:pointer}
button:hover{background:#3f6ef0}
.err{margin:16px 0 0;padding:10px 12px;background:#3a1b1f;border:1px solid #6b2b33;border-radius:9px;
  color:#ffb4be;font-size:13px}
.meta{margin-top:18px;padding-top:14px;border-top:1px solid #242936;color:#6f788c;font-size:12px;
  word-break:break-all}
"""


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head>
<body><div class="card">{body}</div></body></html>"""
    return HTMLResponse(document, status_code=status_code, headers={"Cache-Control": "no-store"})


def client_ip(request: Request) -> str:
    """Cloudflare 隧道会带 CF-Connecting-IP；本地/测试回落对端地址。"""
    header = request.headers
    for name in ("cf-connecting-ip", "x-real-ip"):
        value = header.get(name)
        if value:
            return value.strip()
    forwarded = header.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _locked_until(store: OAuthStore, config: MCPConfig, ip: str, now: float) -> float:
    failures = store.failures_since(ip, now - config.login_window)
    if failures < config.login_max_fails:
        return 0.0
    last = store.last_failure_at(ip)
    if last is None:
        return 0.0
    remaining = (last + config.login_lock_seconds) - now
    return max(0.0, remaining)


def _form(req: str, error: str | None, client_name: str, redirect_host: str, attempts_left: int | None = None) -> str:
    error_html = ""
    if error:
        hint = ""
        if attempts_left is not None and attempts_left > 0:
            hint = f"（还可尝试 {attempts_left} 次）"
        error_html = f'<p class="err">{html.escape(error)}{html.escape(hint)}</p>'
    return f"""
<h1>抖音 MCP 服务</h1>
<p class="sub">请输入服务账号以授权此客户端</p>
{error_html}
<form method="post" action="/login" autocomplete="on">
  <input type="hidden" name="req" value="{html.escape(req, quote=True)}">
  <label for="u">用户名</label>
  <input id="u" name="username" type="text" autocapitalize="none" autocorrect="off" required autofocus>
  <label for="p">密码</label>
  <input id="p" name="password" type="password" required>
  <button type="submit">登录并授权</button>
</form>
<div class="meta">客户端：{html.escape(client_name or "未知")}<br>回调：{html.escape(redirect_host or "-")}</div>
"""


def login_routes(provider: DouyinOAuthProvider, config: MCPConfig, store: OAuthStore) -> list[Route]:
    async def handle_login(request: Request):
        if request.method == "GET":
            req = request.query_params.get("req", "")
            try:
                payload = provider.verify_login_request(req)
            except InvalidLoginRequest as exc:
                return _page("授权失败", f'<h1>授权失败</h1><p class="err">{html.escape(str(exc))}</p>',
                             status_code=400)
            client = await provider.get_client(payload["cid"])
            if client is None:
                return _page("授权失败", '<h1>授权失败</h1><p class="err">客户端未注册或已被删除</p>',
                             status_code=400)
            return _page(
                "登录 · 抖音 MCP",
                _form(req, None, client.client_name or payload["cid"], urlparse(payload["ruri"]).netloc),
            )

        form = await request.form()
        req = str(form.get("req") or "")
        username = str(form.get("username") or "")
        password = str(form.get("password") or "")

        try:
            payload = provider.verify_login_request(req)
        except InvalidLoginRequest as exc:
            return _page("授权失败", f'<h1>授权失败</h1><p class="err">{html.escape(str(exc))}</p>',
                         status_code=400)

        ip = client_ip(request)
        now = time.time()
        locked_for = _locked_until(store, config, ip, now)
        redirect_host = urlparse(payload["ruri"]).netloc
        client = await provider.get_client(payload["cid"])
        if client is None:
            return _page("授权失败", '<h1>授权失败</h1><p class="err">客户端未注册或已被删除</p>',
                         status_code=400)

        if locked_for > 0:
            return _page(
                "登录过于频繁",
                '<h1>登录过于频繁</h1>'
                f'<p class="err">尝试次数过多，请 {int(locked_for // 60) + 1} 分钟后再试</p>',
                status_code=429,
            )

        # 两个字段都做恒定时间比较，不因为用户名先错就短路
        user_ok = hmac.compare_digest(username.encode("utf-8"), config.username.encode("utf-8"))
        pass_ok = hmac.compare_digest(password.encode("utf-8"), config.password.encode("utf-8"))
        if not (user_ok and pass_ok):
            store.record_attempt(ip, False, now)
            failures = store.failures_since(ip, now - config.login_window)
            store.prune_attempts(now - max(config.login_window, config.login_lock_seconds) * 2)
            return _page(
                "登录失败",
                _form(req, "用户名或密码不正确", client.client_name or payload["cid"], redirect_host,
                      attempts_left=max(0, config.login_max_fails - failures)),
                status_code=401,
            )

        store.record_attempt(ip, True, now)
        code = provider.issue_authorization_code(payload)
        target = construct_redirect_uri(payload["ruri"], code=code, state=payload.get("state"))
        return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store"})

    return [Route("/login", handle_login, methods=["GET", "POST"])]
