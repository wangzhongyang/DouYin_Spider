"""私信（IM）**接收**工具：启动监听、增量取消息、看状态、停止。

抖音没有私信历史接口，能拿到的只有 WebSocket 推送。所以这里是一套
「常驻连接 + 环形缓冲 + 按 seq 增量取」的模型：

1. 服务启动时自动连上（``MCP_IM_AUTOSTART=on``），也可以显式调 ``im_listen_start``；
2. 客户端用 ``im_listen_events(after_seq, wait_seconds)`` 轮询/长轮询取新消息；
3. 每条消息带自增 ``seq``，``next_seq`` 回填下一次的 ``after_seq``，不会重复也不会漏
   （除非超过缓冲上限，看 ``dropped``）。

消息里能拿到：消息类型（文本/表情/语音/图片/分享视频/已读回执）、发送者 uid、
`conversation_type`（1 单聊 / 2 群聊，同时给了 `chat_type` 便于判断）、
conversation_id / conversation_short_id、消息序号、文本或媒体 URL。
表情消息（type=5）额外给 `image_id` / `uri` / `package_id` / `display_name`，
并把原始 content 放在 `raw_content`（含 width/height/image_type/aweType 等，
转发或精确收藏时用）。
**没有历史**：服务没连着的时段收到的消息取不回来。
"""
from __future__ import annotations

from ..im_manager import get_manager
from ._common import read_tool


@read_tool
def im_listen_start() -> dict:
    """启动私信实时监听（已启动则直接返回当前状态）。

    长连接建在服务端，断线会自动按退避重连；收到的消息进内存缓冲，用
    im_listen_events 取。重复调用安全。
    """
    manager = get_manager()
    status = manager.start() if not manager.status()["running"] else manager.status()
    return {"status": status, "hint": "之后用 im_listen_events(after_seq, wait_seconds) 取新消息"}


@read_tool
def im_listen_status() -> dict:
    """查看私信监听状态：是否在连、连上了没、缓冲里有多少、丢过多少。"""
    return get_manager().status()


@read_tool
def im_listen_events(after_seq: int = 0, limit: int = 50, wait_seconds: int = 0) -> dict:
    """增量读取已收到的私信（按自增 seq 游标，可长轮询等待新消息）。

    Args:
        after_seq: 上次返回的 next_seq；从 0 开始就是拿缓冲里全部。
        limit: 本次最多返回多少条，默认 50，上限 500。
        wait_seconds: 没有新消息时最多等几秒（长轮询，0 表示立刻返回，上限 25）。
    """
    return get_manager().events(after_seq=after_seq, limit=limit, wait_seconds=wait_seconds)


@read_tool
def im_listen_stop() -> dict:
    """停止私信监听（释放长连接）。停止期间收到的消息不会补发。"""
    return get_manager().stop()
