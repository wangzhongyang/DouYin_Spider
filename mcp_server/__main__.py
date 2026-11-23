"""``python -m mcp_server``：启动远程 MCP 服务。

    python -m mcp_server                 # 按 .env 里的 MCP_HOST/MCP_PORT 启动
    python -m mcp_server --port 9000     # 临时换端口
    python -m mcp_server --check         # 只检查配置并列出工具，不起服务
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger

from . import __version__
from .app import build_app, build_config
from . import tools as tool_pkg


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m mcp_server", description="抖音 MCP 服务（OAuth 2.0 + Cloudflare 隧道）")
    parser.add_argument("--host", help="监听地址，默认取 MCP_HOST（127.0.0.1）")
    parser.add_argument("--port", type=int, help="监听端口，默认取 MCP_PORT（8765）")
    parser.add_argument("--check", action="store_true", help="只校验配置并打印工具清单")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = build_config()
    except SystemExit as exc:  # 配置错误：把原因打清楚再退出
        print(f"配置错误：{exc}", file=sys.stderr)
        return 2

    if args.check:
        tool_pkg.load_all()
        specs = [spec for spec in tool_pkg._common.TOOLS if config.enable_write or spec.read_only]
        print(f"DouYin_Spider MCP {__version__}")
        print(f"  issuer    : {config.issuer_url}")
        print(f"  resource  : {config.resource_url}")
        print(f"  listen    : {config.host}:{config.port}")
        print(f"  oauth user: {config.username}")
        print(f"  db        : {config.db_path}")
        print(f"  write     : {'on' if config.enable_write else 'off'}")
        print(f"  tools     : {len(specs)}")
        for spec in specs:
            if spec.dynamic_write:
                scope = "read/write"
            elif spec.read_only:
                scope = "read"
            else:
                scope = "write"
            print(f"    - {spec.name:<26} [{scope}] {spec.description.splitlines()[0] if spec.description else ''}")
        return 0

    host = args.host or config.host
    port = args.port or config.port
    app = build_app(config)

    if config.im_autostart:
        try:
            from .im_manager import get_manager

            status = get_manager().start()
            logger.info("私信监听已启动：running={} connected={} error={}",
                        status["running"], status["connected"], status["error"])
        except Exception as exc:  # 私信连不上不影响 MCP 主流程
            logger.warning("私信监听启动失败（可在客户端调 im_listen_start 重试）：{}", exc)

    import uvicorn

    logger.info("监听 http://{}:{}（公网入口 {}）", host, port, config.public_url)
    uvicorn.run(app, host=host, port=port, log_level=config.log_level.lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
