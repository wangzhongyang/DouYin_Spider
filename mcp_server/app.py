"""组装 MCP 服务：FastMCP（工具 + OAuth 装配） + 我们自己的 /login、/healthz。

SDK 的 ``streamable_http_app()`` 已经把所有 OAuth 端点、``/mcp`` 的 Bearer 校验、
RFC 9728 元数据都挂好了；我们只在它的路由表**前面**插入登录页和探活接口，
这样它的 lifespan（StreamableHTTP 会话管理器）保持原样，不用自己接管。
"""
from __future__ import annotations

import atexit
from dataclasses import replace

from loguru import logger
from mcp.server.auth.routes import create_protected_resource_routes
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from . import __version__, tools
from .config import ALL_SCOPES, MCPConfig, SCOPE_READ
from .oauth.login import login_routes
from .oauth.provider import DouyinOAuthProvider
from .oauth.secret import load_secret
from .oauth.store import OAuthStore

INSTRUCTIONS = """抖音数据与互动工具集（DouYin_Spider）。

能力分组：
- 账号：auth_status 检查服务端抖音登录态；my_security_token / device_id 排障
- 用户/作品/评论/搜索：user_*、work_*、comment_*、search_*（含 *_page 游标分页）
- 直播（只读）：live_info、live_contribution_rank、live_pk_*、live_products 等
- 私信：im_send_text / image / video / file / sticker，以及 im_send_share_* / im_send_user_card / im_send_card
- 会话：im_conversations（单聊/群聊列表）、im_conversation_members、im_conversation_ticket、
  im_send_text_to_conversation（群聊回复，支持 @人 / 表情 / 引用回复）、
  im_send_sticker_to_conversation（群发表情包，awe_type 501=GIF / 510=贴纸）
- 表情：emoji_list 查表情 token；sticker_favorites / sticker_collect 管理收藏表情包
- 创作者：creator_publish_images / creator_publish_video，cover_gen_ref / media_url / video_enable / video_transend
- 本地任务：download_work / download_works、export_excel、crawl_user、crawl_search
- 高级兜底：douyin_api_call（白名单方法透传，写方法同样受开关/scope/限流约束）

写操作需要在 OAuth 令牌里带 douyin.write scope，并且受服务端频率限制。
全部接口都跑在服务端持有的那一份抖音登录态上（.env 的 DY_COOKIES）。
"""


def build_config(env_path=None) -> MCPConfig:
    config = MCPConfig.load(env_path)
    if not config.secret_key:
        config = replace(config, secret_key=load_secret(config.secret_key))
    return config


def build_app(config: MCPConfig | None = None) -> Starlette:
    config = config or build_config()
    store = OAuthStore(config.db_path)
    provider = DouyinOAuthProvider(config, store)

    server = FastMCP(
        name="DouYin_Spider",
        instructions=INSTRUCTIONS,
        auth_server_provider=provider,
        auth=AuthSettings(
            issuer_url=config.issuer_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=list(ALL_SCOPES),
                default_scopes=list(ALL_SCOPES),
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[SCOPE_READ],
            resource_server_url=config.resource_url,
            # 只接受签发给本服务 /mcp 的 token（RFC 8707 resource）
            validate_token_resource=True,
        ),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=config.allowed_hosts,
            allowed_origins=config.allowed_origins,
        ),
    )

    # FastMCP 把 name/version 交给底层 Server；version 默认是 SDK 版本号，改成项目版本
    try:
        server._mcp_server.version = __version__
    except Exception:  # pragma: no cover - SDK 内部字段变动时不影响主流程
        pass

    tools.load_all()
    registered = tools._common.register_tools(server, config)

    # 私信监听缓冲大小来自配置；真正的连接由 --autostart 或 im_listen_start 触发
    from .im_manager import get_manager

    get_manager().configure(config.im_buffer)

    app = server.streamable_http_app()

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "name": "DouYin_Spider MCP",
                "version": __version__,
                "tools": len(registered),
                "write_enabled": config.enable_write,
                "issuer": config.issuer_url,
                "resource": config.resource_url,
            }
        )

    async def index(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "name": "DouYin_Spider MCP",
                "version": __version__,
                "mcp": config.resource_url,
                "authorization_server": f"{config.issuer_url}/.well-known/oauth-authorization-server",
                "protected_resource": f"{config.issuer_url}/.well-known/oauth-protected-resource",
                "login": f"{config.issuer_url}/login",
                "health": f"{config.issuer_url}/healthz",
                "tools": len(registered),
            }
        )

    extra = login_routes(provider, config, store) + [
        Route("/healthz", healthz, methods=["GET"]),
        Route("/", index, methods=["GET"]),
    ]
    # 覆盖 SDK 的 protected-resource 元数据：它只广告 required_scopes（read），
    # 但客户端应该知道还能申请 write。同时补一个不带路径的别名，方便探活/排障。
    extra = create_protected_resource_routes(
        resource_url=config.resource_url,
        authorization_servers=[config.issuer_url],
        scopes_supported=list(ALL_SCOPES),
        resource_name="DouYin_Spider MCP",
    ) + extra
    # 放在 SDK 路由之前：/login、/healthz、元数据都不需要 Bearer
    app.router.routes[0:0] = extra

    atexit.register(store.close)
    logger.info(
        "MCP 服务就绪：issuer={} resource={} tools={} write={}",
        config.issuer_url, config.resource_url, len(registered), "on" if config.enable_write else "off",
    )
    app.state.mcp_config = config
    app.state.mcp_server = server
    app.state.mcp_tools = registered
    return app
