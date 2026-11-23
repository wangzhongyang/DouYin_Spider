"""私信实时接收管理器。

抖音私信是 **WebSocket 推送**，没有可翻页的历史接口，所以策略是：
服务端常驻一条连接（``MCP_IM_AUTOSTART=on`` 默认开机即连），收到的消息进内存环形缓冲，
MCP 工具按自增 ``seq`` 增量取。缓冲有上限（``MCP_IM_BUFFER``），服务停机期间的消息
取不回来——这一点和直播间监听一样，是推送模型的固有限制。

连接与解析完全复用 ``dy_apis/douyin_recv_msg.py``（只加了 ``on_event`` 回调），
断线重连、重连退避都是那份实现自己的逻辑。
"""
from __future__ import annotations

import atexit
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable

MAX_WAIT_SECONDS = 25  # 单次长轮询上限，避免撞客户端超时


class IMMessageManager:
    def __init__(self, buffer_size: int = 5000, receiver_factory: Callable[..., Any] | None = None):
        self._buffer_size = max(100, int(buffer_size))
        self._receiver_factory = receiver_factory
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._events: deque[dict] = deque(maxlen=self._buffer_size)
        self._seq = 0
        self._thread: threading.Thread | None = None
        self._receiver: Any = None
        self._running = False
        self._started_at: float | None = None
        self._last_event_at: float | None = None
        self._error: str | None = None
        self._dropped = 0

    # ── 生命周期 ─────────────────────────────────────────────
    def configure(self, buffer_size: int) -> None:
        """未启动前才允许改缓冲大小（启动后改会丢已有语义）。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            size = max(100, int(buffer_size))
            if size != self._buffer_size:
                self._buffer_size = size
                self._events = deque(self._events, maxlen=size)

    def start(self, auth: Any = None) -> dict:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return self.status()
            self._error = None

        # 建连接（含 get_device_id 请求）放在锁外，别卡住 status/events
        try:
            receiver = self._build_receiver(auth)
        except Exception as exc:
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"[:300]
            return self.status()

        with self._lock:
            self._receiver = receiver
            self._running = True
            self._started_at = time.time()
            self._thread = threading.Thread(target=self._run, name="douyin-im-recv", daemon=True)
            self._thread.start()
        return self.status()

    def _build_receiver(self, auth: Any):
        if self._receiver_factory is not None:
            return self._receiver_factory(on_event=self.push)
        from dy_apis.douyin_recv_msg import DouyinRecvMsg

        if auth is None:
            from .tools._common import douyin_auth

            auth = douyin_auth()
        return DouyinRecvMsg(auth, auto_reconnect=True, on_event=self.push)

    def _run(self) -> None:
        receiver = self._receiver
        try:
            receiver.start()  # 阻塞；内部自带断线重连
        except Exception as exc:  # pragma: no cover - 依赖网络
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"[:300]
        finally:
            with self._lock:
                self._running = False

    def stop(self, timeout: float = 5.0) -> dict:
        with self._lock:
            receiver, thread = self._receiver, self._thread
        if receiver is not None:
            try:
                receiver.stop()
            except Exception:  # pragma: no cover
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        with self._lock:
            self._running = bool(thread and thread.is_alive())
            if not self._running:
                self._receiver = None
                self._thread = None
        return self.status()

    # ── 事件缓冲 ─────────────────────────────────────────────
    def push(self, event: dict) -> None:
        now_ms = int(time.time() * 1000)
        with self._cond:
            self._seq += 1
            if len(self._events) == self._events.maxlen:
                self._dropped += 1
            item = dict(event)
            item["seq"] = self._seq
            item["received_at"] = now_ms
            self._events.append(item)
            self._last_event_at = now_ms / 1000
            self._cond.notify_all()

    def events(self, after_seq: int = 0, limit: int = 50, wait_seconds: int = 0) -> dict:
        limit = max(1, min(int(limit), 500))
        wait = max(0, min(int(wait_seconds), MAX_WAIT_SECONDS))
        deadline = time.time() + wait

        with self._cond:
            while True:
                items = [event for event in self._events if event["seq"] > after_seq][:limit]
                remaining = deadline - time.time()
                if items or remaining <= 0:
                    break
                self._cond.wait(remaining)
            next_seq = items[-1]["seq"] if items else after_seq
            return {
                "events": items,
                "next_seq": next_seq,
                "count": len(items),
                "running": self._running,
                "dropped": self._dropped,
                "buffered": len(self._events),
            }

    # ── 状态 ─────────────────────────────────────────────────
    def status(self) -> dict:
        with self._lock:
            thread = self._thread
            alive = bool(thread and thread.is_alive())
            receiver = self._receiver
            return {
                "running": alive,
                "connected": bool(getattr(receiver, "_opened", False)) if receiver else False,
                "started_at": _iso(self._started_at),
                "last_event_at": _iso(self._last_event_at),
                "buffered": len(self._events),
                "buffer_size": self._buffer_size,
                "dropped": self._dropped,
                "received": getattr(receiver, "received", 0) if receiver else 0,
                "error": self._error,
            }


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts else None


_manager: IMMessageManager | None = None


def get_manager() -> IMMessageManager:
    global _manager
    if _manager is None:
        _manager = IMMessageManager()
        atexit.register(_manager.stop)
    return _manager
