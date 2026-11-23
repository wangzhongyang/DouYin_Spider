"""工具层公共设施：注册表、线程卸载、scope 校验、写限流、序列化、抖音登录态。

设计要点
- 现有 ``DouyinAPI`` 全是同步函数（curl_cffi 阻塞），必须 ``anyio.to_thread`` 挪出事件循环；
  ``mcp`` v1 的 FastMCP 不会自动做这件事。
- 工具声明与注册分开：``@read_tool`` / ``@write_tool`` 只往 ``TOOLS`` 里加一条，
  真正注册到 server 在 ``register_tools()``，这样 ``--check`` 不启动服务也能列出工具。
- 写工具统一走 scope 检查 + 进程内限流；错误统一转 ``ToolError``，消息里不带凭据。
"""
from __future__ import annotations

import base64
import functools
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import anyio
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from ..config import MCPConfig, SCOPE_READ, SCOPE_WRITE

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = PROJECT_ROOT / "datas" / "media_datas"
EXCEL_DIR = PROJECT_ROOT / "datas" / "excel_datas"


@dataclass(frozen=True)
class ToolSpec:
    fn: Callable[..., Any]
    name: str
    description: str
    scopes: tuple[str, ...]
    read_only: bool
    destructive: bool
    # 读写由运行时参数决定（douyin_api_call）：注册时按只读对待以便 MCP_ENABLE_WRITE=off
    # 时仍保留读透传，但 annotation 不能谎报 readOnlyHint，写分支自己查限流/开关。
    dynamic_write: bool = False


TOOLS: list[ToolSpec] = []


def tool(
    *,
    name: str | None = None,
    scopes: tuple[str, ...] = (SCOPE_READ,),
    read_only: bool = True,
    destructive: bool = False,
    dynamic_write: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        TOOLS.append(
            ToolSpec(
                fn=fn,
                name=name or fn.__name__,
                description=(fn.__doc__ or "").strip(),
                scopes=scopes,
                read_only=read_only,
                destructive=destructive,
                dynamic_write=dynamic_write,
            )
        )
        return fn

    return decorator


def read_tool(_fn: Callable[..., Any] | None = None, **kwargs: Any):
    """``@read_tool`` 与 ``@read_tool(...)`` 两种写法都支持。"""
    kwargs.setdefault("scopes", (SCOPE_READ,))
    kwargs.setdefault("read_only", True)
    decorator = tool(**kwargs)
    return decorator if _fn is None else decorator(_fn)


def write_tool(_fn: Callable[..., Any] | None = None, **kwargs: Any):
    kwargs.setdefault("scopes", (SCOPE_WRITE,))
    kwargs.setdefault("read_only", False)
    kwargs.setdefault("destructive", False)
    decorator = tool(**kwargs)
    return decorator if _fn is None else decorator(_fn)


# ── 序列化 ───────────────────────────────────────────────────
def json_safe(value: Any, _depth: int = 0) -> Any:
    """把抖音接口的返回值转成 MCP 能传的结构（bytes/datetime/protobuf 都见过）。"""
    if _depth > 12:
        return str(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(value).decode("ascii")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(v, _depth + 1) for v in value]
    # protobuf Message：项目里 comment/sticker 等接口会带
    if hasattr(value, "SerializeToString") and hasattr(value, "DESCRIPTOR"):
        try:
            from google.protobuf.json_format import MessageToDict

            return json_safe(MessageToDict(value, preserving_proto_field_name=True), _depth + 1)
        except Exception:
            return str(value)
    if hasattr(value, "to_dict"):
        try:
            return json_safe(value.to_dict(), _depth + 1)
        except Exception:
            pass
    return str(value)


def _sanitize_error(exc: BaseException) -> str:
    message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    message = " ".join(message.split())
    return message[:600]


# ── 抖音登录态 ───────────────────────────────────────────────
_auth_lock = threading.Lock()
_auth: Any = None
_auth_bootstrapped = False


def douyin_auth(*, bootstrap_creator: bool = False) -> Any:
    """懒加载 ``.env`` 里的抖音登录态；进程内复用同一个 ``DouyinAuth``。

    与 CLI 完全一致（``utils.common_util.load_env``），cookie 的 Set-Cookie 回流
    也才有意义。``bootstrap_creator=True`` 会补创作者中心的会话，只在发布工具里用。
    """
    global _auth, _auth_bootstrapped
    with _auth_lock:
        if _auth is None or (bootstrap_creator and not _auth_bootstrapped):
            from utils import common_util

            _auth = common_util.load_env(bootstrap_creator=bootstrap_creator)
            _auth_bootstrapped = _auth_bootstrapped or bootstrap_creator
        return _auth


def reset_auth() -> None:
    """测试用：丢掉缓存的登录态。"""
    global _auth, _auth_bootstrapped
    with _auth_lock:
        _auth = None
        _auth_bootstrapped = False


def ensure_dirs() -> None:
    for path in (MEDIA_DIR, EXCEL_DIR):
        path.mkdir(parents=True, exist_ok=True)


# ── 写操作限流 ───────────────────────────────────────────────
class WriteRateLimiter:
    """简单的滑动窗口；写接口是最容易被抖音风控/封号的部分，留一道闸。"""

    def __init__(self, limit: int, window: int):
        self.limit = max(1, limit)
        self.window = max(1, window)
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def check(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            while self._hits and now - self._hits[0] > self.window:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                wait = int(self.window - (now - self._hits[0])) + 1
                raise ToolError(
                    f"写操作过于频繁（{self.window} 秒内最多 {self.limit} 次），请 {wait} 秒后再试"
                )
            self._hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# ── 运行时上下文（给「读写由参数决定」的工具用） ──────────────
_runtime: tuple[MCPConfig, WriteRateLimiter] | None = None
_runtime_lock = threading.Lock()


def active_runtime() -> tuple[MCPConfig, WriteRateLimiter] | None:
    """返回本次注册生效的 (config, limiter)；未注册时返回 None。

    进程内只跑一份服务，后一次 ``register_tools`` 覆盖前一次（测试里会多次建 app）。
    """
    with _runtime_lock:
        return _runtime


def _set_runtime(config: MCPConfig, limiter: WriteRateLimiter) -> None:
    global _runtime
    with _runtime_lock:
        _runtime = (config, limiter)


# ── 注册 ─────────────────────────────────────────────────────
def _check_scope(spec: ToolSpec) -> None:
    token = get_access_token()
    if token is None:
        raise ToolError("未认证：请先完成 OAuth 登录")
    granted = set(token.scopes or [])
    missing = [scope for scope in spec.scopes if scope not in granted]
    if missing:
        raise ToolError(f"当前令牌缺少 scope：{', '.join(missing)}（该操作属于写入类工具）")


def require_scope(scope: str) -> None:
    """给「运行时才知道要不要写权限」的工具（如 douyin_api_call）用。"""
    token = get_access_token()
    if token is None:
        raise ToolError("未认证：请先完成 OAuth 登录")
    if scope not in set(token.scopes or []):
        raise ToolError(f"当前令牌缺少 scope：{scope}")


def make_callable(spec: ToolSpec, config: MCPConfig, limiter: WriteRateLimiter) -> Callable[..., Any]:
    """把同步工具包成 async：鉴权/限流在事件循环里做，抖音调用丢线程池。"""

    @functools.wraps(spec.fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        _check_scope(spec)
        if not spec.read_only:
            limiter.check()
        try:
            result = await anyio.to_thread.run_sync(lambda: spec.fn(*args, **kwargs))
        except ToolError:
            raise
        except Exception as exc:  # 统一成 MCP 的 isError，而不是 500 堆栈
            raise ToolError(_sanitize_error(exc)) from exc
        return json_safe(result)

    return wrapper


def register_tools(server: Any, config: MCPConfig) -> list[str]:
    limiter = WriteRateLimiter(config.write_rate_limit, config.write_rate_window)
    _set_runtime(config, limiter)
    registered: list[str] = []
    for spec in TOOLS:
        if not config.enable_write and not spec.read_only:
            continue
        server.add_tool(
            make_callable(spec, config, limiter),
            name=spec.name,
            description=spec.description,
            annotations=ToolAnnotations(
                title=spec.name,
                # dynamic_write 的工具可能写，不能标成只读，否则客户端会自动放行
                readOnlyHint=spec.read_only and not spec.dynamic_write,
                destructiveHint=spec.destructive,
                idempotentHint=spec.read_only and not spec.dynamic_write,
                openWorldHint=True,
            ),
        )
        registered.append(spec.name)
    return registered
