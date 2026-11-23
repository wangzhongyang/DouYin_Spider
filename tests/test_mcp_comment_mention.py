"""评论 @ 提及（text_extra）透传测试。

抓包依据（2026-11-24 @豆包 评论）：
    text="@豆包 这首是什么歌"
    text_extra=[{"user_id":"1994962122842643","sec_uid":"MS4wLjABAAAA...",
                 "type":0,"start":0,"end":3}]
"""
from __future__ import annotations

import pytest
from mcp_server.tools import interactions

CAPTURED = [{
    "user_id": "1994962122842643",
    "sec_uid": "MS4wLjABAAAALSNkLwg8rxzewZcDBVAvv8QzYitAE793UlGNb6JSu859IV8EoEnicVdc1Zy7ofVN",
    "type": 0,
    "start": 0,
    "end": 3,
}]


@pytest.fixture
def captured_call(monkeypatch):
    calls: list[dict] = []

    def fake_publish(auth, aweme_id, content="", reply_id="", sticker=None, **kwargs):
        calls.append({"auth": auth, "aweme_id": aweme_id, "content": content,
                      "reply_id": reply_id, "sticker": sticker, "kwargs": kwargs})
        return {"status_code": 0}

    monkeypatch.setattr(interactions, "douyin_auth", lambda: "AUTH")
    monkeypatch.setattr(interactions.DouyinAPI, "publish_comment", fake_publish)
    return calls


def test_text_extra_is_forwarded(captured_call):
    interactions.publish_comment(
        aweme_id="7648930504200228096",
        content="@豆包 这首是什么歌",
        text_extra=CAPTURED,
    )
    assert len(captured_call) == 1
    call = captured_call[0]
    assert call["kwargs"]["text_extra"] == CAPTURED
    assert call["content"] == "@豆包 这首是什么歌"


def test_without_text_extra_keeps_old_call_shape(captured_call):
    interactions.publish_comment(aweme_id="123", content="普通评论")
    call = captured_call[0]
    assert call["kwargs"] == {}, "没传 mentions 时不应凭空塞 text_extra"


def test_empty_list_is_treated_as_absent(captured_call):
    interactions.publish_comment(aweme_id="123", content="随便说点", text_extra=[])
    assert captured_call[0]["kwargs"] == {}


def test_text_extra_coexists_with_sticker(captured_call):
    sticker = {"id_str": "7694150285622509605", "animate_url": {"uri": "tos-cn-o-0812/abc"}}
    interactions.publish_comment(
        aweme_id="123", content="@豆包", sticker=sticker, text_extra=CAPTURED,
    )
    call = captured_call[0]
    assert call["sticker"] == sticker
    assert call["kwargs"]["text_extra"] == CAPTURED


def test_tool_declares_text_extra_in_schema(mcp_app):
    """客户端能看到的 inputSchema 里必须有 text_extra（否则等于没透传）。"""
    import asyncio

    app = mcp_app()
    listed = asyncio.run(app.state.mcp_server.list_tools())
    tool = next(item for item in listed if item.name == "publish_comment")
    properties = tool.inputSchema["properties"]
    assert "text_extra" in properties
    schema = properties["text_extra"]
    types = {schema.get("type")} if "type" in schema else set()
    types |= {sub.get("type") for sub in schema.get("anyOf", [])}
    assert "array" in types, schema
