"""MCP 工具集：每个模块用 ``@read_tool`` / ``@write_tool`` 往注册表里加工具。

导入顺序无关，真正的注册发生在 ``mcp_server.app.build_app()`` 里。
"""
from __future__ import annotations

import importlib

MODULES = (
    "account",
    "user",
    "search",
    "interactions",
    "live",
    "im",
    "im_recv",
    "creator",
    "tasks",
    "advanced",
)


def load_all() -> None:
    """导入所有工具模块（幂等）。"""
    for name in MODULES:
        importlib.import_module(f"{__name__}.{name}")
