"""私信接收测试：缓冲/游标/长轮询/溢出，以及 WS 帧 → 事件的解析。"""
from __future__ import annotations

import json
import threading
import time

import pytest
from mcp_server.im_manager import IMMessageManager


class FakeReceiver:
    def __init__(self, on_event):
        self.on_event = on_event
        self._opened = False
        self.received = 0
        self.ready = threading.Event()
        self._stop = threading.Event()

    def start(self):
        self._opened = True
        self.ready.set()
        self._stop.wait(10)

    def stop(self):
        self._stop.set()


def make_manager(**kwargs):
    holder: dict = {}

    def factory(on_event):
        receiver = FakeReceiver(on_event)
        holder["receiver"] = receiver
        return receiver

    manager = IMMessageManager(receiver_factory=factory, **kwargs)
    return manager, holder


def test_start_push_and_incremental_cursor():
    manager, holder = make_manager()
    manager.start()
    assert holder["receiver"].ready.wait(2)
    assert manager.status()["connected"] is True

    manager.push({"type": 7, "text": "第一条", "uid": 111})
    manager.push({"type": 7, "text": "第二条", "uid": 111})

    first = manager.events(after_seq=0)
    assert first["count"] == 2
    assert [e["seq"] for e in first["events"]] == [1, 2]
    assert first["events"][0]["text"] == "第一条"
    assert first["next_seq"] == 2

    assert manager.events(after_seq=2)["count"] == 0

    manager.push({"type": 27, "url": "http://cdn/x.jpg", "uid": 222})
    third = manager.events(after_seq=2)
    assert third["count"] == 1
    assert third["events"][0]["url"] == "http://cdn/x.jpg"
    assert third["next_seq"] == 3
    manager.stop()


def test_long_poll_wakes_up_on_new_event():
    manager, _holder = make_manager()
    manager.start()

    def later():
        time.sleep(0.3)
        manager.push({"type": 7, "text": "迟到的消息"})

    threading.Thread(target=later, daemon=True).start()
    started = time.time()
    result = manager.events(after_seq=0, limit=10, wait_seconds=5)
    elapsed = time.time() - started
    assert result["count"] == 1
    assert elapsed < 3, "长轮询应该被新消息唤醒，而不是等满 5 秒"
    manager.stop()


def test_long_poll_returns_empty_after_timeout():
    manager, _holder = make_manager()
    manager.start()
    started = time.time()
    result = manager.events(after_seq=0, wait_seconds=1)
    elapsed = time.time() - started
    assert result["count"] == 0
    assert 0.8 <= elapsed < 3
    manager.stop()


def test_buffer_overflow_counts_dropped():
    manager, _holder = make_manager(buffer_size=100)
    manager.start()
    for i in range(150):
        manager.push({"type": 7, "text": f"m{i}"})
    status = manager.status()
    assert status["buffer_size"] == 100
    assert status["buffered"] == 100
    assert status["dropped"] == 50
    events = manager.events(after_seq=0, limit=500)["events"]
    assert events[0]["text"] == "m50", "溢出后保留的是最后 100 条"
    manager.stop()


def test_stop_reports_not_running():
    manager, _holder = make_manager()
    manager.start()
    time.sleep(0.05)
    status = manager.stop()
    assert status["running"] is False
    assert manager.events()["running"] is False


def test_ws_frame_is_parsed_into_event():
    from dy_apis.douyin_recv_msg import DouyinRecvMsg
    from static import Live_pb2, Response_pb2

    response = Response_pb2.Response()
    notify = response.body.new_message_notify
    notify.message.conversation_id = "conversation-1"
    notify.message.conversation_short_id = 4294967297
    notify.message.message_type = 7
    notify.message.sender = 2511699079608468
    notify.message.index_in_conversation = 5
    notify.message.conversation_type = 2
    notify.message.content = json.dumps({"text": "在吗"}, ensure_ascii=False)

    frame = Live_pb2.PushFrame(payloadType="pb", payload=response.SerializeToString())

    captured: list[dict] = []
    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.on_event = captured.append
    receiver.received = 0
    receiver.on_message(None, frame.SerializeToString())

    assert len(captured) == 1
    event = captured[0]
    assert event["text"] == "在吗"
    assert event["type"] == 7
    assert event["uid"] == 2511699079608468
    assert event["conversation_id"] == "conversation-1"
    assert event["conversation_short_id"] == 4294967297
    assert event["index"] == 5
    assert event["conversation_type"] == 2
    assert event["chat_type"] == "group"
    assert event["server_message_id"] == ""
    assert isinstance(event["ts"], int)


def test_ws_frame_without_hook_does_not_raise(capsys):
    from dy_apis.douyin_recv_msg import DouyinRecvMsg
    from static import Live_pb2, Response_pb2

    response = Response_pb2.Response()
    response.body.new_message_notify.message.message_type = 7
    response.body.new_message_notify.message.content = json.dumps({"text": "no hook"})
    frame = Live_pb2.PushFrame(payloadType="pb", payload=response.SerializeToString())

    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.on_event = None
    receiver.received = 0
    receiver.on_message(None, frame.SerializeToString())  # 不抛异常即可
    assert receiver.received == 1


@pytest.mark.parametrize("wait_seconds", [0, 1])
def test_events_clamps_wait_seconds(wait_seconds):
    manager, holder = make_manager()
    manager.start()
    assert holder["receiver"].ready.wait(2)
    started = time.time()
    manager.events(after_seq=0, wait_seconds=wait_seconds)
    assert time.time() - started < 30
    manager.stop()


def test_single_conversation_type_is_marked_single():
    from dy_apis.douyin_recv_msg import DouyinRecvMsg
    from static import Live_pb2, Response_pb2

    response = Response_pb2.Response()
    notify = response.body.new_message_notify
    notify.message.conversation_type = 1
    notify.message.message_type = 7
    notify.message.sender = 42
    notify.message.content = json.dumps({"text": "私聊"}, ensure_ascii=False)
    frame = Live_pb2.PushFrame(payloadType="pb", payload=response.SerializeToString())

    captured = []
    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.on_event = captured.append
    receiver.received = 0
    receiver.on_message(None, frame.SerializeToString())

    assert captured[0]["chat_type"] == "single"
    assert captured[0]["conversation_type"] == 1


def test_unknown_conversation_type_falls_back():
    from dy_apis.douyin_recv_msg import DouyinRecvMsg
    from static import Live_pb2, Response_pb2

    response = Response_pb2.Response()
    notify = response.body.new_message_notify
    notify.message.conversation_type = 7
    notify.message.message_type = 50001
    notify.message.content = json.dumps({"read_index": 3})
    frame = Live_pb2.PushFrame(payloadType="pb", payload=response.SerializeToString())

    captured = []
    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.on_event = captured.append
    receiver.received = 0
    receiver.on_message(None, frame.SerializeToString())

    assert captured[0]["chat_type"] == "type_7"
    assert captured[0]["read_index"] == 3


def test_ws_sticker_event_keeps_raw_content():
    from dy_apis.douyin_recv_msg import DouyinRecvMsg
    from static import Live_pb2, Response_pb2

    sticker = {
        "aweType": 501,
        "display_name": "",
        "height": 300,
        "width": 300,
        "image_id": "7363590957897403657",
        "image_type": "webp",
        "package_id": 0,
        "url": {
            "uri": "tos-cn-i-x/abc",
            "url_list": ["https://cdn/x.webp"],
            "height": 0,
            "width": 0,
        },
    }
    response = Response_pb2.Response()
    notify = response.body.new_message_notify
    notify.message.conversation_id = "7710946258684363323"
    notify.message.conversation_short_id = 7710946258684363323
    notify.message.message_type = 5
    notify.message.sender = 53127236531
    notify.message.index_in_conversation = 9
    notify.message.conversation_type = 2
    notify.message.content = json.dumps(sticker, ensure_ascii=False)

    frame = Live_pb2.PushFrame(payloadType="pb", payload=response.SerializeToString())
    captured: list[dict] = []
    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.on_event = captured.append
    receiver.received = 0
    receiver.on_message(None, frame.SerializeToString())

    event = captured[0]
    assert event["type"] == 5
    assert event["image_id"] == "7363590957897403657"
    assert event["uri"] == "tos-cn-i-x/abc"
    assert event["url"] == "https://cdn/x.webp"
    assert event["package_id"] == 0
    assert event["raw_content"] == sticker


def _bare_receiver():
    """不跑 __init__（会发 get_device_id 请求），手工拼一个接收器。"""
    from dy_apis.douyin_recv_msg import DouyinRecvMsg

    receiver = DouyinRecvMsg.__new__(DouyinRecvMsg)
    receiver.auto_reconnect = True
    receiver.on_event = None
    receiver.received = 0
    receiver.auth = None
    receiver.ws = None
    receiver._stopped = False
    receiver._opened = False
    receiver._ever_opened = False
    receiver.RECONNECT_BACKOFF_START = 0
    receiver.RECONNECT_BACKOFF_MAX = 0
    return receiver


def test_clean_close_marks_disconnected():
    receiver = _bare_receiver()
    receiver.on_open(None)
    assert receiver._opened is True
    receiver.on_close(None, 1000, "bye")
    assert receiver._opened is False, "关闭后 connected 必须变 False，否则 im_listen_status 会撒谎"


def test_reconnects_after_clean_close(monkeypatch):
    """服务端正常 close（on_error 不触发）也必须重连，不能静默退出。"""
    receiver = _bare_receiver()
    calls: list[int] = []

    class FakeWS:
        def run_forever(self, **_kwargs):
            calls.append(1)
            receiver.on_open(self)
            receiver.on_close(self, 1000, "server closed")  # 无 error 回调
            if len(calls) >= 3:
                receiver.stop()

        def close(self):
            pass

    monkeypatch.setattr(receiver, "_new_ws", lambda: FakeWS())
    receiver.start()
    assert len(calls) == 3, "正常关闭后要循环重连，而不是只连一次"
    assert receiver._stopped is True


def test_stop_prevents_further_reconnect(monkeypatch):
    receiver = _bare_receiver()
    calls: list[int] = []

    class FakeWS:
        def run_forever(self, **_kwargs):
            calls.append(1)
            receiver.on_open(self)
            receiver.stop()  # 第一次就连上后主动停

        def close(self):
            pass

    monkeypatch.setattr(receiver, "_new_ws", lambda: FakeWS())
    receiver.start()
    assert len(calls) == 1
