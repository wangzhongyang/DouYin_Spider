"""覆盖面回归：接口端有的能力必须能被 MCP 调到，且写入口的开关/限流不能被绕开。

这些测试只做参数透传与注册表断言，不发真实网络请求。
"""
from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path

import pytest
from mcp_auth_helpers import full_login, initialize, rpc
from mcp_server.tools import _common
from mcp_server.tools import account as account_tools
from mcp_server.tools import creator as creator_tools
from mcp_server.tools import im as im_tools
from mcp_server.tools import search as search_tools
from mcp_server.tools import tasks as task_tools
from mcp_server.tools import user as user_tools
from mcp_server.tools.advanced import READ_METHODS, WRITE_METHODS
from starlette.testclient import TestClient

from dy_apis.douyin_api import DouyinAPI

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "mcp_server" / "tools"

# 直播实时能力由 dy_live 独立承担，不在 MCP 工具范围内
LIVE_METHODS = {
    "get_live_info",
    "get_live_production",
    "get_all_live_production",
    "get_live_production_detail",
    "get_product_comments",
    "get_product_comment_counter",
    "search_live",
    "search_some_live",
    "get_live_room_enter",
    "get_live_linkmic_list",
    "get_live_pk_contribution_rank",
    "get_live_pk_context",
    "get_live_pk_rank",
    "get_live_contribution_rank",
    "get_live_thousand_ticket_rank",
    "get_rank_list",
    "get_webcast_detail",
    "diggLiveRoom",
    "sendMsgInRoom",
}


def _api_methods() -> set[str]:
    """公开方法名；纯别名（send_text = send_msg 这类）只保留一份语义，直接跳过。"""
    members = {
        name: value
        for name, value in inspect.getmembers(DouyinAPI, inspect.isfunction)
        if not name.startswith("_")
    }
    owners: dict[int, list[str]] = {}
    for name, fn in members.items():
        owners.setdefault(id(fn), []).append(name)
    aliases = {name for names in owners.values() if len(names) > 1 for name in names}
    return set(members) - aliases


def test_every_non_live_api_method_is_reachable():
    """DouyinAPI 的每个非直播公开方法，都要有专用工具或进 douyin_api_call 白名单。"""
    source = "\n".join(path.read_text() for path in TOOLS_DIR.glob("*.py"))
    referenced = set(re.findall(r"DouyinAPI\.([A-Za-z_]+)", source))
    whitelisted = set(READ_METHODS) | set(WRITE_METHODS)
    missing = sorted(_api_methods() - LIVE_METHODS - referenced - whitelisted)
    assert missing == [], f"接口端有、MCP 调不到：{missing}"


def test_douyin_api_call_is_dynamic_write():
    spec = next(item for item in _common.TOOLS if item.name == "douyin_api_call")
    assert spec.read_only is True, "要在 MCP_ENABLE_WRITE=off 时保留读透传"
    assert spec.dynamic_write is True


def test_douyin_api_call_annotation_is_not_read_only(mcp_app):
    app = mcp_app()
    listed = asyncio.run(app.state.mcp_server.list_tools())
    tool = next(item for item in listed if item.name == "douyin_api_call")
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is False


def _tool_call(client, token, session, name, arguments):
    return rpc(client, {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }, token, session)


def test_api_call_write_counts_against_write_limiter(mcp_app, monkeypatch):
    calls: list[dict] = []

    def fake_send_card(auth, **kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(DouyinAPI, "send_card", fake_send_card)
    monkeypatch.setattr("mcp_server.tools.advanced.douyin_auth", lambda **_: object())
    with TestClient(mcp_app(write_rate_limit=1), follow_redirects=False) as client:
        _client_id, token = full_login(client)
        session, _info = initialize(client, token["access_token"])
        args = {"method": "send_card", "params": {"message_type": 26, "content": {"a": 1}}}
        status, body, _ = _tool_call(client, token["access_token"], session, "douyin_api_call", args)
        assert status == 200 and body["result"].get("isError") is not True, body
        assert len(calls) == 1
        status, body, _ = _tool_call(client, token["access_token"], session, "douyin_api_call", args)
        assert status == 200
        assert body["result"]["isError"] is True
        assert "频繁" in str(body["result"]["content"])


def test_api_call_write_rejected_when_write_disabled(mcp_app, monkeypatch):
    def boom(*_args, **_kwargs):  # 开关应该拦在调用抖音接口之前
        raise AssertionError("不应发请求")

    monkeypatch.setattr(DouyinAPI, "send_card", boom)
    with TestClient(mcp_app(enable_write=False), follow_redirects=False) as client:
        _client_id, token = full_login(client)
        session, _info = initialize(client, token["access_token"])
        status, body, _ = _tool_call(
            client, token["access_token"], session, "douyin_api_call",
            {"method": "send_card", "params": {"message_type": 26, "content": {}}},
        )
        assert status == 200
        assert body["result"]["isError"] is True
        assert "关闭" in str(body["result"]["content"])


def test_api_call_read_still_available_when_write_disabled(mcp_app, monkeypatch):
    monkeypatch.setattr(DouyinAPI, "get_device_id", lambda auth: "dev-1")
    monkeypatch.setattr("mcp_server.tools.advanced.douyin_auth", lambda **_: object())
    with TestClient(mcp_app(enable_write=False), follow_redirects=False) as client:
        _client_id, token = full_login(client)
        session, _info = initialize(client, token["access_token"])
        status, body, _ = _tool_call(
            client, token["access_token"], session, "douyin_api_call",
            {"method": "get_device_id", "params": {}},
        )
        assert status == 200 and body["result"].get("isError") is not True, body


def test_search_users_forwards_filters(monkeypatch):
    captured: dict = {}

    def fake(auth, query, num, **kwargs):
        captured.update(query=query, num=num, kwargs=kwargs)
        return []

    monkeypatch.setattr(DouyinAPI, "search_some_user", fake)
    search_tools.search_users("榴莲", num=3, fans="1k_1w", user_type="personal_user")
    assert captured == {
        "query": "榴莲",
        "num": 3,
        "kwargs": {"douyin_user_fans": "1k_1w", "douyin_user_type": "personal_user"},
    }


def test_search_pages_forward_cursor(monkeypatch):
    captured: dict = {}

    def fake_general(auth, query, sort_type, publish_time, offset, *args, **kwargs):
        captured["general"] = (offset, kwargs.get("search_id"))
        return {"data": []}

    def fake_video(auth, query, offset, count, sort_type, publish_time, *args):
        captured["video"] = (offset, count, args[-1])
        return "next-id", ["guide"], {"data": []}

    def fake_user(auth, query, offset, num, **kwargs):
        captured["user"] = (offset, num, kwargs)
        return {"user_list": []}

    monkeypatch.setattr(DouyinAPI, "search_general_work", fake_general)
    monkeypatch.setattr(DouyinAPI, "search_video_work", fake_video)
    monkeypatch.setattr(DouyinAPI, "search_user", fake_user)
    search_tools.search_works_page("q", offset="15", search_id="sid")
    assert search_tools.search_videos_page("q", offset="16", count="10", search_id="sid")["next_search_id"] == "next-id"
    search_tools.search_users_page("q", offset="25", num="10", fans="1w_10w")
    assert captured["general"] == ("15", "sid")
    assert captured["video"] == ("16", "10", "sid")
    assert captured["user"] == ("25", "10", {"douyin_user_fans": "1w_10w", "douyin_user_type": ""})


def test_comment_replies_builds_comment_ref(monkeypatch):
    captured: dict = {}

    def fake(auth, comment):
        captured.update(comment)
        return [{"cid": "r1"}, {"cid": "r2"}]

    monkeypatch.setattr(DouyinAPI, "get_work_all_inner_comment", fake)
    result = user_tools.comment_replies("https://www.douyin.com/note/7351", "900", limit=1)
    assert captured == {"aweme_id": "7351", "cid": "900"}
    assert result["returned"] == 1 and result["total"] == 2


def test_comment_replies_rejects_bad_url():
    with pytest.raises(ValueError):
        user_tools.comment_replies("https://www.douyin.com/", "900")


def test_creator_publish_images_forwards_new_params(monkeypatch):
    captured: dict = {}

    def fake_post(auth, images, **kwargs):
        captured.update(images=images, kwargs=kwargs)
        return True, "ok", {"status_code": 0}

    monkeypatch.setattr(creator_tools, "douyin_auth", lambda **_: object())
    monkeypatch.setattr(creator_tools.DouyinCreatorAPI, "post_images", staticmethod(fake_post))
    creator_tools.creator_publish_images(
        ["a.jpg"],
        cover_uri="tos-cover",
        poi={"poi_id": "p1", "poi_name": "上海"},
        activity=[{"activity_id": "1"}],
        mix_id="mix-1",
        hot_spot={"word": "热点"},
        creation_id="cid-img",
    )
    kwargs = captured["kwargs"]
    assert kwargs["cover_uri"] == "tos-cover"
    assert kwargs["poi"] == {"poi_id": "p1", "poi_name": "上海"}
    assert kwargs["activity"] == [{"activity_id": "1"}]
    assert kwargs["mix_id"] == "mix-1"
    assert kwargs["hot_spot"] == {"word": "热点"}
    assert kwargs["creation_id"] == "cid-img"


def test_creator_publish_video_forwards_new_params(monkeypatch):
    captured: dict = {}

    def fake_post(auth, video, **kwargs):
        captured.update(video=video, kwargs=kwargs)
        return True, "ok", {"status_code": 0}

    monkeypatch.setattr(creator_tools, "douyin_auth", lambda **_: object())
    monkeypatch.setattr(creator_tools.DouyinCreatorAPI, "post_video", staticmethod(fake_post))
    creator_tools.creator_publish_video(
        "a.mp4",
        cover_delay=2,
        poi={"poi_id": "p1", "poi_name": "上海"},
        activity=[{"activity_id": "1"}],
        mix_id="mix-1",
        hot_spot={"word": "热点"},
        chapter={"chapter_abstract": "第一章"},
        creation_id="cid-1",
    )
    kwargs = captured["kwargs"]
    assert kwargs["cover_delay"] == 2
    assert kwargs["chapter"] == {"chapter_abstract": "第一章"}
    assert kwargs["creation_id"] == "cid-1"
    assert kwargs["mix_id"] == "mix-1"


def test_creator_poi_must_be_object():
    with pytest.raises(ValueError) as exc:
        creator_tools.creator_publish_images(["a.jpg"], poi="上海")
    assert "poi_id" in str(exc.value)

    with pytest.raises(ValueError):
        creator_tools.creator_publish_images(["a.jpg"], poi={"poi_name": "上海"})


def test_creator_visibility_documented_like_api():
    for fn in (creator_tools.creator_publish_images, creator_tools.creator_publish_video):
        doc = fn.__doc__ or ""
        assert "0 公开" in doc and "1 仅自己可见" in doc
        assert "1 公开" not in doc


def test_creator_media_url_returns_url(monkeypatch):
    monkeypatch.setattr(creator_tools, "douyin_auth", lambda **_: object())
    monkeypatch.setattr(
        creator_tools.DouyinCreatorAPI, "get_creator_media_url",
        staticmethod(lambda auth, uri: f"https://cdn/{uri}"),
    )
    assert creator_tools.creator_media_url("a.jpg") == {"url": "https://cdn/a.jpg"}


def test_im_card_tools_forward_payload(monkeypatch):
    captured: list[tuple] = []

    def fake_send_web(auth, conversation_id, short_id, ticket, content, **kwargs):
        captured.append(("web", content, kwargs))
        return True

    def fake_send_photos(auth, conversation_id, short_id, ticket, content, **kwargs):
        captured.append(("photos", content, kwargs))
        return True

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(DouyinAPI, "open_conversation_with_user", staticmethod(lambda auth, target: (9, 1, 2, "tk")))
    monkeypatch.setattr(DouyinAPI, "send_share_web", staticmethod(fake_send_web))
    monkeypatch.setattr(DouyinAPI, "send_share_photos", staticmethod(fake_send_photos))

    im_tools.im_send_share_web("123", "https://example.com/a", title="标题")
    im_tools.im_send_share_photos("123", "7351", title="图集", image_count=3, image_index=1)
    assert captured[0][0] == "web"
    assert captured[0][1] == "https://example.com/a"
    assert captured[0][2] == {"title": "标题"}
    assert captured[1][1] == "https://www.douyin.com/note/7351"
    assert captured[1][2] == {"title": "图集", "image_count": 3, "image_index": 1}


def test_im_user_card_resolves_profile_url(monkeypatch):
    captured: dict = {}

    def fake_user_info(auth, url):
        return {"user": {"uid": "42", "sec_uid": "MS4", "nickname": "张三"}}

    def fake_send_user_card(auth, conversation_id, short_id, ticket, content, **kwargs):
        captured.update(content=content, kwargs=kwargs)
        return True

    monkeypatch.setattr(DouyinAPI, "get_user_info", staticmethod(fake_user_info))
    monkeypatch.setattr(DouyinAPI, "send_user_card", staticmethod(fake_send_user_card))
    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(DouyinAPI, "open_conversation_with_user", staticmethod(lambda auth, target: (9, 1, 2, "tk")))
    im_tools.im_send_user_card("123", "https://www.douyin.com/user/MS4")
    assert captured["content"]["uid"] == "42"
    assert captured["kwargs"] == {}


def test_download_works_combines_media_and_excel(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(task_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(task_tools, "_collect", lambda auth, urls: [{"work_id": "1"}])
    monkeypatch.setattr(task_tools, "_download", lambda infos, choice: called.append(f"download:{choice}") or {})
    monkeypatch.setattr(task_tools, "_excel", lambda infos, name: called.append(f"excel:{name}") or "/tmp/x.xlsx")

    result = task_tools.download_works(["https://www.douyin.com/video/1"], save_choice="all", excel_name="out")
    assert called == ["download:all", "excel:out"]
    assert result["count"] == 1 and result["excel"] == "/tmp/x.xlsx"

    called.clear()
    task_tools.download_works(["https://www.douyin.com/video/1"], save_choice="excel", excel_name="out")
    assert called == ["excel:out"]


def test_download_works_requires_excel_name(monkeypatch):
    monkeypatch.setattr(task_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(task_tools, "_collect", lambda auth, urls: [])
    with pytest.raises(ValueError):
        task_tools.download_works(["https://www.douyin.com/video/1"], save_choice="excel")
    with pytest.raises(ValueError):
        task_tools.download_works(["https://www.douyin.com/video/1"], save_choice="nope")


def test_account_debug_tools(monkeypatch):
    monkeypatch.setattr(account_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(DouyinAPI, "get_identity_security_token", staticmethod(lambda auth, force=False: ("t", "d")))
    monkeypatch.setattr(DouyinAPI, "get_device_id", staticmethod(lambda auth: "dev"))
    assert account_tools.my_security_token() == {"identity_security_token": "t", "device_id": "d"}
    assert account_tools.device_id() == {"device_id": "dev"}


# ── 群会话：会话列表 / ticket / 按会话发送 ─────────────────────
def _group_list_payload():
    from builder.proto import ProtoBuilder as PB

    core = PB.proto_field_bytes(5, "鱼缸".encode()) + PB.proto_field_bytes(7, b"https://icon")
    conv = (
        PB.proto_field_bytes(1, b"7710946258684363323")
        + PB.proto_field_varint(2, 7710946258684363323)
        + PB.proto_field_varint(3, 2)
        + PB.proto_field_bytes(4, b"ticket-abc")
        + PB.proto_field_varint(7, 2)
        + PB.proto_field_bytes(50, core)
    )
    listing = (
        PB.proto_field_bytes(1, conv)
        + PB.proto_field_varint(2, 0)
        + PB.proto_field_varint(3, 1)
    )
    return PB.proto_field_bytes(6, PB.proto_field_bytes(2006, listing)) + PB.proto_field_bytes(4, b"OK")


def test_conversation_list_parses_group_fields(monkeypatch):
    monkeypatch.setattr(
        DouyinAPI, "_im_post",
        staticmethod(lambda auth, path, request: _group_list_payload()),
    )
    result = DouyinAPI.get_user_conversation_list(object(), con_type=2)
    assert result["message"] == "OK"
    assert result["has_more"] is False and result["next_cursor"] == 1
    conv = result["conversations"][0]
    assert conv == {
        "conversation_id": "7710946258684363323",
        "conversation_short_id": 7710946258684363323,
        "conversation_type": 2,
        "ticket": "ticket-abc",
        "name": "鱼缸",
        "icon": "https://icon",
        "participants_count": 2,
    }


def test_send_message_body_carries_conversation_type(monkeypatch):
    from builder.proto import ProtoBuilder as PB

    request = PB.build_send_message_request(
        object(), "g-1", 42, "tk", content={"text": "hi"}, message_type=7, conversation_type=2,
    )
    body = request.body.send_message_body
    assert body.conversation_type == 2
    assert body.conversation_id == "g-1"
    assert body.ticket == "tk"


def test_im_send_text_to_conversation_autofills_ticket(monkeypatch):
    captured: dict = {}

    def fake_send(auth, conversation_id, short_id, ticket, content, **kwargs):
        captured.update(
            conversation_id=conversation_id, short_id=short_id,
            ticket=ticket, content=content, kwargs=kwargs,
        )
        return True

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "resolve_conversation_ticket",
        staticmethod(lambda auth, short_id, conversation_type=1, conversation_id="", ticket="": "tk2"),
    )
    monkeypatch.setattr(DouyinAPI, "send_msg", staticmethod(fake_send))
    result = im_tools.im_send_text_to_conversation("g-1", "42", "回复", conversation_type=2)
    assert result["ok"] is True and result["conversation_type"] == 2
    assert captured == {
        "conversation_id": "g-1",
        "short_id": 42,
        "ticket": "tk2",
        "content": {"aweType": 700, "type": 0, "richTextInfos": [], "text": "回复"},
        "kwargs": {"conversation_type": 2},
    }


def test_im_send_text_to_conversation_requires_ticket(monkeypatch):
    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "resolve_conversation_ticket",
        staticmethod(lambda *args, **kwargs: ""),
    )
    with pytest.raises(RuntimeError):
        im_tools.im_send_text_to_conversation("g-1", "42", "回复", conversation_type=2)


def test_im_conversations_forwards_filters(monkeypatch):
    captured: dict = {}

    def fake(auth, con_type=1, cursor=0, limit=20, **kwargs):
        captured.update(con_type=con_type, cursor=cursor, limit=limit)
        return {"conversations": []}

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(DouyinAPI, "get_user_conversation_list", staticmethod(fake))
    im_tools.im_conversations(conversation_type=2, cursor="5", limit=10)
    assert captured == {"con_type": 2, "cursor": 5, "limit": 10}


def test_proto_wire_builders_use_expected_field_numbers():
    from builder.proto import ProtoBuilder as PB

    ticket_body = PB.parse_proto_fields(PB.build_get_ticket_body(
        conversation_short_id=42, conversation_type=2,
    ))
    assert set(ticket_body) == {2005}
    inner = PB.parse_proto_fields(ticket_body[2005][0])
    assert inner[1] == [1] and inner[2] == [2] and inner[5] == [42]

    list_body = PB.parse_proto_fields(PB.build_get_conversation_list_body(
        cursor=3, limit=20, con_type=2, sort_type=1,
    ))
    assert set(list_body) == {2006}
    inner = PB.parse_proto_fields(list_body[2006][0])
    assert inner[1] == [1] and inner[2] == [3] and inner[3] == [2] and inner[4] == [20]


# ── @人 / 表情 / 引用回复 ────────────────────────────────────
def test_build_text_content_with_mentions_and_emojis():
    content, mentioned, ref = DouyinAPI.build_text_content(
        "你好", conversation_id="g1",
        mentions=[{"uid": "42", "name": "张三"}], emojis=["[微笑]"],
    )
    assert content["aweType"] == 700
    assert content["text"] == "@张三 [微笑]你好"
    assert mentioned == [42] and ref is None
    first = content["richTextInfos"][0]
    assert first["info"] == {"uid": "42", "con_id": "g1"}
    assert first["infoType"] == 1 and first["location"] == 0
    assert first["length"] == len("@张三 ")
    # 第二条是编辑器同款的加粗样式
    assert content["richTextInfos"][1] == {
        "info": {"font_weight": 2}, "infoType": 2, "length": len("@张三 "), "location": 0,
    }


def test_build_text_content_reply_marks_ref_msg():
    import json

    reply = {
        "server_message_id": "999", "uid": 7, "nickname": "李四",
        "hint": "原消息", "content": '{"text":"原消息"}', "type": 7, "self": False,
    }
    content, mentioned, ref = DouyinAPI.build_text_content(
        "回复", conversation_id="g1", reply=reply,
    )
    assert content["aweType"] == 703
    assert mentioned == []
    assert ref["referenced_message_id"] == 999
    hint = json.loads(ref["hint"])
    assert hint["refmsg_uid"] == 7
    assert hint["nickname"] == "李四"
    assert hint["refmsg_type"] == 7
    assert hint["scene_type"] == 1  # 回复别人；回复自己应为 2
    assert hint["content"] == "原消息"


def test_build_text_content_reply_requires_server_id():
    with pytest.raises(ValueError):
        DouyinAPI.build_text_content("x", reply={"uid": 1})


def test_build_text_content_rejects_bad_mention():
    with pytest.raises(ValueError):
        DouyinAPI.build_text_content("x", mentions=[{"name": "没有 uid"}])


def test_send_request_encodes_ref_msg_info():
    from builder.proto import ProtoBuilder as PB

    request = PB.build_send_message_request(
        object(), "g-1", 42, "tk", content={"text": "x"},
        message_type=7, conversation_type=2,
        ref_msg_info={"referenced_message_id": 999, "hint": "h"},
    )
    fields = PB.parse_proto_fields(request.body.send_message_body.SerializeToString())
    assert 11 in fields
    inner = PB.parse_proto_fields(fields[11][0])
    assert inner[1] == [999] and inner[2] == [b"h"]


def test_conversation_participants_parses_members(monkeypatch):
    from builder.proto import ProtoBuilder as PB

    participant = (
        PB.proto_field_varint(1, 42)
        + PB.proto_field_varint(3, 1)
        + PB.proto_field_bytes(4, "群昵称".encode())
        + PB.proto_field_bytes(5, b"MS4wLjABAAAA")
        + PB.proto_field_bytes(40, b"https://avatar")
    )
    page = (
        PB.proto_field_bytes(1, participant)
        + PB.proto_field_varint(2, 0)
        + PB.proto_field_varint(3, 7)
    )
    payload = PB.proto_field_bytes(6, PB.proto_field_bytes(605, PB.proto_field_bytes(1, page)))
    monkeypatch.setattr(DouyinAPI, "_im_post", staticmethod(lambda auth, path, request: payload))
    result = DouyinAPI.get_conversation_participants(object(), "g-1", 42, conversation_type=2)
    assert result["has_more"] is False and result["cursor"] == 7
    assert result["participants"] == [{
        "uid": "42",
        "sec_uid": "MS4wLjABAAAA",
        "alias": "群昵称",
        "role": 1,
        "avatar": "https://avatar",
    }]


def test_im_send_text_to_conversation_forwards_mentions_and_reply(monkeypatch):
    captured: dict = {}

    def fake_send(auth, conversation_id, short_id, ticket, content, **kwargs):
        captured.update(
            conversation_id=conversation_id, short_id=short_id, ticket=ticket,
            content=content, kwargs=kwargs,
        )
        return True

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "resolve_conversation_ticket",
        staticmethod(lambda *args, **kwargs: "tk"),
    )
    monkeypatch.setattr(DouyinAPI, "send_msg", staticmethod(fake_send))
    result = im_tools.im_send_text_to_conversation(
        "g-1", "42", "你好", conversation_type=2,
        mentions=[{"uid": "7", "name": "李四"}],
        emojis=["[微笑]"],
        reply={"server_message_id": "999", "uid": 7, "nickname": "李四",
               "hint": "原消息", "content": "原消息", "type": 7, "self": False},
    )
    assert result["mentioned"] == [7] and result["reply_to"] == 999
    assert captured["content"]["aweType"] == 703
    assert captured["content"]["text"] == "@李四 [微笑]你好"
    assert captured["kwargs"]["mentioned_users"] == [7]
    assert captured["kwargs"]["ref_msg_info"]["referenced_message_id"] == 999
    assert captured["kwargs"]["conversation_type"] == 2


def test_emoji_list_filters_hidden_and_urls(monkeypatch):
    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "get_emoji_list",
        staticmethod(lambda auth: [
            {"name": "[微笑]", "url": "https://e1", "hide": 0},
            {"name": "[隐藏]", "url": "https://e2", "hide": 1},
        ]),
    )
    plain = im_tools.emoji_list()
    assert plain == {"count": 1, "emojis": [{"name": "[微笑]"}]}
    full = im_tools.emoji_list(with_urls=True, show_hidden=True)
    assert full["count"] == 2 and full["emojis"][0]["url"] == "https://e1"


def test_sticker_favorites_maps_fields(monkeypatch):
    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "get_collected_stickers",
        staticmethod(lambda auth, cursor="0", page_size="50": {
            "stickers": [{
                "id_str": "1", "display_name": "猫猫", "sticker_type": "2",
                "sticker_info_source": "comment_sticker",
                "animate_url": {"uri": "tos-x", "url_list": ["https://a"]},
            }],
            "next_cursor": 0, "is_completed": True,
        }),
    )
    result = im_tools.sticker_favorites()
    assert result["count"] == 1 and result["is_completed"] is True
    assert result["stickers"][0] == {
        "id_str": "1", "name": "猫猫", "sticker_type": "2",
        "source": "comment_sticker", "uri": "tos-x", "url": "https://a",
    }


# ── 收藏表情 ───────────────────────────────────────────────
def test_collect_sticker_request_uses_aid_1128(monkeypatch):
    from types import SimpleNamespace

    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = "{}"
        headers: dict = {}

        def json(self):
            return {"status_code": 0, "success_items": [{"id_str": "123"}]}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("dy_apis.douyin_api.requests.post", fake_post)
    auth = SimpleNamespace(
        cookie={"UIFID": "u", "s_v_web_id": "fp"},
        webid="w", msToken="ms",
    )
    result = DouyinAPI.collect_sticker(
        auth, ["123"], action=1, sticker_type=1,
        sticker_uri="uri-x", sticker_url="https://cdn", resource_id="-9",
    )
    assert result["status_code"] == 0
    assert captured["url"].endswith("/aweme/v1/web/im/resource/sticker/collect/")
    params = captured["params"]
    # with_platform() 会写 aid=6383，这里必须被 1128 覆盖
    assert params["aid"] == "1128" and params["app_id"] == "1128"
    assert params["device_platform"] == "webapp" and params["channel"] == "channel_pc_web"
    assert params["sticker_ids"] == "[123]"
    assert params["sticker_type"] == "1" and params["resource_id"] == "-9"
    assert params["sticker_uri"] == "uri-x" and params["sticker_url"] == "https://cdn"
    assert params["action"] == "1"
    headers = captured["headers"]
    assert headers["x-secsdk-csrf-token"] == "DOWNGRADE"
    assert "application/json" in headers["content-type"]
    assert captured["data"] == "{}"


def test_sticker_collect_maps_action(monkeypatch):
    captured: dict = {}

    def fake_collect(auth, ids, **kwargs):
        captured.update(ids=ids, kwargs=kwargs)
        return {"status_code": 0, "success_items": [{"id_str": ids[0]}]}

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(DouyinAPI, "collect_sticker", staticmethod(fake_collect))
    result = im_tools.sticker_collect("123", action="collect", sticker_type=1,
                                      sticker_uri="u", sticker_url="https://x", resource_id="-9")
    assert result["ok"] is True and captured["kwargs"]["action"] == 1
    assert captured["ids"] == ["123"]

    im_tools.sticker_collect("123", action="remove")
    assert captured["kwargs"]["action"] == 0
    with pytest.raises(ValueError):
        im_tools.sticker_collect("123", action="nope")


def test_im_send_sticker_to_conversation_forwards_metadata(monkeypatch):
    captured: dict = {}

    def fake_send_sticker(auth, conversation_id, short_id, ticket, **kwargs):
        captured.update(
            conversation_id=conversation_id, short_id=short_id,
            ticket=ticket, kwargs=kwargs,
        )
        return True

    monkeypatch.setattr(im_tools, "douyin_auth", lambda: object())
    monkeypatch.setattr(
        DouyinAPI, "resolve_conversation_ticket",
        staticmethod(lambda *args, **kwargs: "tk"),
    )
    monkeypatch.setattr(DouyinAPI, "send_sticker", staticmethod(fake_send_sticker))
    result = im_tools.im_send_sticker_to_conversation(
        "g-1", "42", image_id="107972593", uri="tos-x",
        url_list=["https://a", "https://b"], width=300, height=240,
        image_type="webp", package_id=0, conversation_type=2, awe_type=501,
    )
    assert result["ok"] is True and result["conversation_type"] == 2
    kwargs = captured["kwargs"]
    assert kwargs["image_id"] == "107972593"
    assert kwargs["url_list"] == ["https://a", "https://b"]
    assert kwargs["conversation_type"] == 2
    assert kwargs["awe_type"] == 501
    assert captured["ticket"] == "tk"


def test_resolve_user_uid_and_open_conversation(monkeypatch):
    def fake_user_info(auth, url):
        return {"user": {"uid": 42}}

    monkeypatch.setattr(DouyinAPI, "get_user_info", staticmethod(fake_user_info))
    monkeypatch.setattr(
        DouyinAPI, "create_conversation",
        staticmethod(lambda auth, uid: (f"c-{uid}", 7, "tk")),
    )
    assert DouyinAPI.resolve_user_uid(object(), "123") == 123
    assert DouyinAPI.resolve_user_uid(object(), "https://www.douyin.com/user/MS4") == 42
    assert DouyinAPI.open_conversation_with_user(object(), "MS4") == (42, "c-42", 7, "tk")


def test_build_text_content_detects_self_reply(monkeypatch):
    import json
    from types import SimpleNamespace

    auth = SimpleNamespace(get_uid=lambda: 42)
    reply = {"server_message_id": "9", "uid": 42, "hint": "hi"}
    _content, _mentioned, ref = DouyinAPI.build_text_content("x", reply=reply, auth=auth)
    assert json.loads(ref["hint"])["scene_type"] == 2  # 回复自己

    reply["uid"] = 7
    _content, _mentioned, ref = DouyinAPI.build_text_content("x", reply=reply, auth=auth)
    assert json.loads(ref["hint"])["scene_type"] == 1  # 回复别人


def test_feed_uses_current_tab_feed_endpoint(monkeypatch):
    from types import SimpleNamespace

    captured: dict = {}

    class FakeResponse:
        status_code = 200
        text = '{"status_code":0,"aweme_list":[]}'
        headers: dict = {}

        def json(self):
            return {"status_code": 0, "aweme_list": []}

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return FakeResponse()

    monkeypatch.setattr("dy_apis.douyin_api.requests.get", fake_get)
    auth = SimpleNamespace(
        cookie={"UIFID": "u", "s_v_web_id": "fp"},
        webid="w", msToken="ms",
    )
    DouyinAPI.get_feed(auth, count="10", refresh_index="2")
    assert captured["url"].endswith("/aweme/v1/web/tab/feed/")
    params = captured["params"]
    assert params["aid"] == "6383" and params["channel"] == "channel_pc_web"
    assert params["tag_id"] == "" and params["count"] == "10"
    assert params["refresh_index"] == "2" and params["video_type_select"] == "1"
