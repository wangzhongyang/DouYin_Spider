"""把直播间事件写进 Redis Stream，供 ai-games 那边的电子宠物消费。

设计要点：
- **旁路**：文本日志照旧写，这里只是额外发一份结构化事件；
- **不阻塞**：所有写入走后台线程 + 有界队列，Redis 挂了也不能卡住 websocket；
- **可关闭**：`.env` 里 LIVE_EVENT=off 时完全不初始化，行为与改动前一致。

事件结构与 ai-games 的 src/pet/types.ts 保持一致：
    {"id", "source": "live", "type", "ts", "detail", "gameTimeSec": null, "payload": {...}}
Redis 里每个条目只有一个字段 data，值是上面这段 JSON。
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import threading
import time
from datetime import datetime
from typing import Any

from loguru import logger

try:  # 允许在没装 redis 的环境里继续跑（只是不发事件）
    import redis
except ImportError:  # pragma: no cover
    redis = None

# 抖音昵称里会混入零宽字符，不清理会让下游的 TTS 莫名其妙停顿
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)

QUEUE_LIMIT = 2000
WARN_INTERVAL_SEC = 30.0


def clean_text(value: Any) -> str:
    """去掉零宽字符与控制符，并压掉多余空白。"""
    if value is None:
        return ""
    text = str(value).translate(_INVISIBLE)
    text = "".join(ch for ch in text if ch == "\n" or ch.isprintable())
    return " ".join(text.split())


def to_millis(ts: Any) -> int:
    """抖音消息时间戳统一成毫秒。服务端给的是秒（可能是 float）。"""
    if ts is None:
        return int(time.time() * 1000)
    if isinstance(ts, datetime):
        return int(ts.timestamp() * 1000)
    value = float(ts)
    if value < 1e11:  # 秒
        return int(value * 1000)
    return int(value)


def parse_log_time(line: str) -> int | None:
    """解析日志里的 'YYYY-MM-DD HH:MM:SS.mmm'，回放时要用。"""
    text = line.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(text, fmt).timestamp() * 1000)
        except ValueError:
            continue
    return None


class RedisEventSink:
    """后台线程 + 有界队列的 Redis Stream 写入器。"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        stream: str = "ai-games:stream:live",
        maxlen: int = 5000,
    ) -> None:
        self._host = host
        self._port = port
        self._password = password or None
        self._db = db
        self._stream = stream
        self._maxlen = maxlen

        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=QUEUE_LIMIT)
        self._client = None
        self._stopping = threading.Event()
        self._last_warn = 0.0
        self._dropped = 0
        self._sent = 0

        self._thread = threading.Thread(target=self._run, name="live-event-sink", daemon=True)
        self._thread.start()
        atexit.register(self.close)

    # ---------- 对外 ----------

    @classmethod
    def from_env(cls) -> "RedisEventSink | None":
        """按 .env 配置决定是否启用。"""
        enabled = (os.getenv("LIVE_EVENT") or "on").strip().lower()
        if enabled in ("off", "0", "false", "no"):
            logger.info("直播间事件：未启用（LIVE_EVENT=off），只写文本日志")
            return None
        if redis is None:
            logger.warning(
                "直播间事件：未安装 redis 包，跳过事件上报。"
                "如需启用请在当前环境执行 pip install redis"
            )
            return None

        sink = cls(
            host=(os.getenv("LIVE_REDIS_HOST") or "127.0.0.1").strip(),
            port=int((os.getenv("LIVE_REDIS_PORT") or "6379").strip()),
            password=(os.getenv("LIVE_REDIS_PASSWORD") or "").strip() or None,
            db=int((os.getenv("LIVE_REDIS_DB") or "0").strip()),
            stream=(os.getenv("LIVE_EVENT_STREAM") or "ai-games:stream:live").strip(),
            maxlen=int((os.getenv("LIVE_EVENT_MAXLEN") or "5000").strip()),
        )
        logger.info(
            f"直播间事件：写入 {sink._host}:{sink._port} 的 {sink._stream}"
        )
        return sink

    def emit(
        self,
        kind: str,
        ts: Any,
        detail: str,
        payload: dict[str, Any] | None = None,
        event_id: Any = None,
    ) -> None:
        """投递一条事件；队列满了直接丢，绝不阻塞调用方。"""
        event = {
            "id": clean_text(event_id) or f"live-{int(time.time() * 1000)}",
            "source": "live",
            "type": kind,
            "ts": to_millis(ts),
            "detail": clean_text(detail),
            "gameTimeSec": None,
            "payload": payload or {},
        }
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._dropped += 1
            self._warn(f"事件队列已满，丢弃 {self._dropped} 条（Redis 可能不可用）")

    def stats(self) -> dict[str, int]:
        return {"sent": self._sent, "dropped": self._dropped, "pending": self._queue.qsize()}

    def close(self) -> None:
        if self._stopping.is_set():
            return
        self._stopping.set()
        # 给后台线程一点时间把队列冲刷完
        self._thread.join(timeout=2.0)
        if self._client is not None:
            try:
                self._client.close()
            except Exception:  # pragma: no cover
                pass
            self._client = None
        if self._sent or self._dropped:
            logger.info(f"直播间事件：已发送 {self._sent} 条，丢弃 {self._dropped} 条")

    # ---------- 内部 ----------

    def _warn(self, message: str) -> None:
        now = time.time()
        if now - self._last_warn < WARN_INTERVAL_SEC:
            return
        self._last_warn = now
        logger.warning(message)

    def _connect(self):
        self._client = redis.Redis(
            host=self._host,
            port=self._port,
            password=self._password,
            db=self._db,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
            health_check_interval=30,
            decode_responses=True,
        )
        self._client.ping()

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                event = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self._client is None:
                try:
                    self._connect()
                except Exception as exc:
                    # 发不出去就丢掉这条，但别把队列堵死
                    self._warn(f"连接 Redis 失败（{exc}），事件暂不发送")
                    continue

            try:
                self._client.xadd(
                    self._stream,
                    {"data": json.dumps(event, ensure_ascii=False)},
                    maxlen=self._maxlen,
                    approximate=True,
                )
                self._sent += 1
            except Exception as exc:
                self._warn(f"写入 Redis 失败（{exc}），稍后重连")
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
