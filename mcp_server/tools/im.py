"""私信（IM）工具：建会话 + 发各种消息。

会话解析（user_url → uid → 建会话）和文本 content 构造都在 API 层
（``DouyinAPI.open_conversation_with_user`` / ``build_text_content``），
本层只做工具声明、参数映射和返回值整理。
"""
from __future__ import annotations

from typing import Any

from dy_apis.douyin_api import DouyinAPI

from ._common import douyin_auth, read_tool, write_tool


def _card_kwargs(**values: Any) -> dict:
    """卡片可选字段：只传真正有值的，别用空串覆盖接口的自动推导。"""
    return {key: value for key, value in values.items() if value not in (None, "", [], {})}


def _user_card_content(auth: Any, user: str | dict) -> dict:
    """用户名片既要能传已抓好的 user 对象，也要能传主页链接（现场抓一次）。"""
    if isinstance(user, dict):
        return user
    text = str(user).strip()
    if text.startswith(("http://", "https://")):
        info = DouyinAPI.get_user_info(auth, text) or {}
        card = info.get("user") or {}
        if not card.get("uid"):
            raise RuntimeError(f"无法从 {user!r} 解析出用户信息")
        return card
    if text.isdigit():
        return {"uid": text}
    raise ValueError("user 需要是用户主页链接、纯数字 uid，或已抓好的 user 对象")


@read_tool
def im_conversation_info(target: str) -> dict:
    """查询与某个用户的私信会话信息。

    Args:
        target: 对方主页链接，或对方的纯数字 uid。
    """
    auth = douyin_auth()
    uid, conversation_id, short_id, _ticket = DouyinAPI.open_conversation_with_user(auth, target)
    info = DouyinAPI.get_conversation_list(auth, uid, short_id)
    return {"to_user_id": uid, "conversation_id": conversation_id, "conversation_short_id": short_id,
            "conversation": info}


@read_tool
def im_conversations(conversation_type: int = 1, cursor: str = "0", limit: int = 20) -> dict:
    """获取会话列表（单聊 / 群聊分开查，互不包含）。

    返回里带 ``conversation_id`` / ``conversation_short_id`` / ``conversation_type`` /
    ``ticket`` / ``name`` / ``icon`` / ``participants_count``；ticket 是短时会话凭据，
    供 im_send_text_to_conversation 使用（不传 ticket 时工具会自己取）。

    Args:
        conversation_type: 1 单聊（默认），2 群聊。
        cursor: 分页游标，首页传 "0"；下一页用返回的 next_cursor。
        limit: 每页数量，默认 20。
    """
    return DouyinAPI.get_user_conversation_list(
        douyin_auth(), con_type=int(conversation_type), cursor=int(cursor or 0), limit=int(limit)
    )


@read_tool
def im_conversation_ticket(conversation_short_id: str, conversation_type: int = 1,
                           conversation_id: str = "") -> dict:
    """取某个会话的 ticket（会话列表里没有或发送报 InvalidTicket 时用）。

    Args:
        conversation_short_id: 会话 short_id（im_conversations 返回）。
        conversation_type: 1 单聊，2 群聊。
        conversation_id: 可选，会话 id；需要区分同 short_id 的会话时传。
    """
    ticket = DouyinAPI.resolve_conversation_ticket(
        douyin_auth(), int(conversation_short_id),
        conversation_type=int(conversation_type), conversation_id=conversation_id,
    )
    return {"conversation_short_id": int(conversation_short_id),
            "conversation_type": int(conversation_type), "ticket": ticket}


@read_tool
def im_conversation_members(conversation_id: str, conversation_short_id: str,
                            conversation_type: int = 2, cursor: str = "0",
                            limit: int = 100) -> dict:
    """获取会话成员列表（群聊 @人 前先查 uid）。

    Args:
        conversation_id: 会话 id（im_conversations 返回）。
        conversation_short_id: 会话 short_id。
        conversation_type: 1 单聊，2 群聊（默认）。
        cursor: 分页游标，首页传 "0"。
        limit: 每页数量，默认 100。
    """
    return DouyinAPI.get_conversation_participants(
        douyin_auth(), str(conversation_id), int(conversation_short_id),
        conversation_type=int(conversation_type), cursor=int(cursor or 0), limit=int(limit),
    )


@read_tool
def sticker_favorites(cursor: str = "0", page_size: str = "50") -> dict:
    """列出已收藏的表情包（收藏页，含贴纸 / GIF）。

    返回 ``id_str`` / ``name`` / ``sticker_type`` / ``source`` / ``url``（动图优先），
    发送时可直接用 ``im_send_sticker`` 的元数据，或作为收藏管理的前置查询。

    Args:
        cursor: 分页游标，首页传 "0"。
        page_size: 每页数量，默认 50。
    """
    result = DouyinAPI.get_collected_stickers(douyin_auth(), cursor, str(page_size))
    stickers = []
    for item in result.get("stickers", []):
        urls = ((item.get("animate_url") or {}).get("url_list")
                or (item.get("static_url") or {}).get("url_list") or [])
        stickers.append({
            "id_str": str(item.get("id_str") or item.get("id") or ""),
            "name": item.get("display_name") or "",
            "sticker_type": item.get("sticker_type"),
            "source": item.get("sticker_info_source") or "",
            "uri": (item.get("animate_url") or {}).get("uri")
                   or (item.get("static_url") or {}).get("uri") or "",
            "url": urls[0] if urls else "",
        })
    return {
        "count": len(stickers),
        "stickers": stickers,
        "next_cursor": result.get("next_cursor"),
        "is_completed": result.get("is_completed"),
    }


@write_tool
def sticker_collect(
    image_id: str,
    action: str = "collect",
    sticker_type: int = 0,
    sticker_uri: str = "",
    sticker_url: str = "",
    resource_id: str = "0",
) -> dict:
    """收藏 / 取消收藏一个表情包（贴纸、GIF、互动表情）。

    消息里的表情包：``image_id`` / ``sticker_uri`` / ``sticker_url`` /
    ``resource_id`` 直接取 ``im_listen_events`` 的 type=5 事件
    （``image_id``、``uri``、``url``、``package_id``），``sticker_type=1``。
    GIF 面板项：``image_id`` 用 ``single_hey_can_id``，``sticker_type=0``，其余留空。
    小表情（``[微笑]`` 这类系统脸）没有收藏入口，只能作为文本 token 发送。

    Args:
        image_id: 表情 id（消息事件里的 image_id / GIF 的 single_hey_can_id）。
        action: collect 收藏（默认），remove 取消收藏。
        sticker_type: 1 系统/消息表情包，0 GIF/互动表情，2 用户上传。
        sticker_uri: 表情 CDN uri（消息表情包必填）。
        sticker_url: 表情 CDN url（消息表情包必填）。
        resource_id: 消息表情包取 content.package_id；GIF 用 "0"。
    """
    mode = str(action or "collect").strip().lower()
    if mode in {"collect", "add", "1"}:
        code = 1
    elif mode in {"remove", "cancel", "0"}:
        code = 0
    else:
        raise ValueError("action 只能是 collect / remove")
    result = DouyinAPI.collect_sticker(
        douyin_auth(), [str(image_id)], action=code, sticker_type=int(sticker_type),
        sticker_uri=sticker_uri, sticker_url=sticker_url, resource_id=resource_id,
    )
    status = result.get("status_code")
    return {
        "ok": status in (0, 200),
        "status_code": status,
        "status_msg": result.get("status_msg") or "",
        "items": result.get("success_items"),
    }


@read_tool
def emoji_list(with_urls: bool = False, show_hidden: bool = False) -> dict:
    """列出 PC 端小表情（文本里用 ``name``，例如 ``[微笑]``）。

    Args:
        with_urls: 是否连图片地址一起返回，默认只给名字（列表较长）。
        show_hidden: 是否包含客户端隐藏的表情，默认过滤。
    """
    items = DouyinAPI.get_emoji_list(douyin_auth())
    if not show_hidden:
        items = [item for item in items if not item.get("hide")]
    if not with_urls:
        items = [{"name": item["name"]} for item in items]
    return {"count": len(items), "emojis": items}


@write_tool
def im_send_text_to_conversation(
    conversation_id: str,
    conversation_short_id: str,
    text: str = "",
    conversation_type: int = 1,
    ticket: str = "",
    mentions: list[dict] | None = None,
    emojis: list[str] | None = None,
    reply: dict | None = None,
) -> dict:
    """向已存在的会话发文本消息（群聊用这个；conversation_type=2）。

    支持 @人、表情、引用回复，三者可组合：
    - mentions: [{"uid": "123", "name": "昵称"}]，uid 从 im_conversation_members 取；
      文本前会自动补 ``@昵称 ``，并写好 richTextInfos / mentioned_users。
    - emojis: 表情 token 列表（emoji_list 的 name，如 ``["[微笑]"]``），直接拼在正文前。
    - reply: 引用回复，取自 im_listen_events 的事件：
      ``{"server_message_id": "...", "uid": 发送者uid, "nickname": "昵称",
         "hint": "引用摘要", "content": "原消息内容", "type": 7}``；
      ``self`` 不传会按当前账号自动判断。

    会话标识直接取 im_conversations 或 im_listen_events 的返回；
    ticket 留空会自动按「会话列表 → get_ticket」解析。

    Args:
        conversation_id: 会话 id（群聊形如 "7710946258684363323"）。
        conversation_short_id: 会话 short_id。
        text: 消息正文。
        conversation_type: 1 单聊，2 群聊。
        ticket: 可选的已取到的会话 ticket；留空自动获取。
        mentions: @ 的成员列表。
        emojis: 表情 token 列表。
        reply: 引用回复信息。
    """
    auth = douyin_auth()
    short_id = int(conversation_short_id)
    ctype = int(conversation_type)
    content, mentioned, ref_info = DouyinAPI.build_text_content(
        text, conversation_id=str(conversation_id),
        mentions=mentions, emojis=emojis, reply=reply, auth=auth,
    )
    ticket = DouyinAPI.resolve_conversation_ticket(
        auth, short_id, conversation_type=ctype,
        conversation_id=str(conversation_id), ticket=ticket,
    )
    if not ticket:
        raise RuntimeError("取会话 ticket 失败，无法发送")
    kwargs: dict = {"conversation_type": ctype}
    if mentioned:
        kwargs["mentioned_users"] = mentioned
    if ref_info:
        kwargs["ref_msg_info"] = ref_info
    ok = DouyinAPI.send_msg(
        auth, str(conversation_id), short_id, ticket, content, **kwargs
    )
    return {"ok": bool(ok), "conversation_id": str(conversation_id),
            "conversation_short_id": short_id, "conversation_type": ctype,
            "mentioned": mentioned, "emojis": emojis or [],
            "reply_to": (ref_info or {}).get("referenced_message_id")}


@write_tool
def im_send_text(target: str, text: str = "", mentions: list[dict] | None = None,
                 emojis: list[str] | None = None, reply: dict | None = None) -> dict:
    """发送文本私信（单聊；支持 @、表情、引用回复）。

    Args:
        target: 对方主页链接或纯数字 uid。
        text: 消息正文。
        mentions: @ 的成员列表 [{"uid","name"}]。
        emojis: 表情 token 列表（emoji_list 的 name）。
        reply: 引用回复信息，字段同 im_send_text_to_conversation。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    content, mentioned, ref_info = DouyinAPI.build_text_content(
        text, conversation_id=str(conversation_id),
        mentions=mentions, emojis=emojis, reply=reply, auth=auth,
    )
    kwargs: dict = {}
    if mentioned:
        kwargs["mentioned_users"] = mentioned
    if ref_info:
        kwargs["ref_msg_info"] = ref_info
    ok = DouyinAPI.send_msg(auth, conversation_id, short_id, ticket, content, **kwargs)
    return {"ok": bool(ok), "to": target, "mentioned": mentioned,
            "emojis": emojis or [], "reply_to": (ref_info or {}).get("referenced_message_id")}


@write_tool
def im_send_sticker_to_conversation(
    conversation_id: str,
    conversation_short_id: str,
    image_id: str,
    uri: str,
    url_list: list[str] | None = None,
    width: int = 0,
    height: int = 0,
    image_type: str = "gif",
    display_name: str = "",
    package_id: int = 0,
    conversation_type: int = 1,
    ticket: str = "",
    awe_type: int = 0,
) -> dict:
    """向已存在的会话发表情包（群聊用这个；conversation_type=2）。

    表情元数据来自 ``sticker_favorites`` / ``im_listen_events``（type=5）：
    ``image_id``、``uri``、``url``、``width``、``height``、``image_type``、``package_id``。

    Args:
        conversation_id: 会话 id。
        conversation_short_id: 会话 short_id。
        image_id: 表情 id（消息里的 image_id / GIF 的 single_hey_can_id）。
        uri: 表情 CDN uri。
        url_list: 表情 CDN url 列表（建议传，否则只有 uri）。
        width: 宽。
        height: 高。
        image_type: gif / webp。
        display_name: 显示名。
        package_id: 表情包 id。
        conversation_type: 1 单聊，2 群聊。
        ticket: 可选会话 ticket；留空自动解析。
        awe_type: 510 消息贴纸（默认），501 GIF 面板表情；GIF 必须传 501，
            否则 PC 端显示“暂不支持该消息类型展示”。
    """
    auth = douyin_auth()
    short_id = int(conversation_short_id)
    ctype = int(conversation_type)
    ticket = DouyinAPI.resolve_conversation_ticket(
        auth, short_id, conversation_type=ctype,
        conversation_id=str(conversation_id), ticket=ticket,
    )
    if not ticket:
        raise RuntimeError("取会话 ticket 失败，无法发送")
    kwargs = {"conversation_type": ctype}
    if awe_type:
        kwargs["awe_type"] = int(awe_type)
    ok = DouyinAPI.send_sticker(
        auth, str(conversation_id), short_id, ticket,
        image_id=str(image_id), uri=uri, display_name=display_name,
        image_type=image_type, width=int(width), height=int(height),
        package_id=int(package_id), url_list=url_list, **kwargs,
    )
    return {"ok": bool(ok), "conversation_id": str(conversation_id),
            "conversation_short_id": short_id, "conversation_type": ctype,
            "image_id": str(image_id)}


@write_tool
def im_send_image(target: str, image: str) -> dict:
    """发送图片私信（会自动上传）。

    Args:
        target: 对方主页链接或纯数字 uid。
        image: 本地图片绝对路径，或 http(s) 图片地址。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_image(auth, conversation_id, short_id, ticket, image)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_video(target: str, video: str, thumb: str | None = None) -> dict:
    """发送视频私信（会自动上传）。

    Args:
        target: 对方主页链接或纯数字 uid。
        video: 本地视频路径或 http(s) 地址。
        thumb: 可选，封面图路径/地址。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_video(auth, conversation_id, short_id, ticket, video, thumb=thumb)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_file(target: str, file: str) -> dict:
    """发送文件私信（自动上传；抖音 PC IM 限制单文件 10MB 以内）。

    Args:
        target: 对方主页链接或纯数字 uid。
        file: 本地文件路径或 http(s) 地址。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_file(auth, conversation_id, short_id, ticket, file)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_audio(target: str, content: dict) -> dict:
    """发送语音消息（需要传入兼容客户端抓到的 voice content dict）。

    PC IM 网页端没有公开的语音上传协议，所以这里不做本地录音上传，
    只接受已经成形的 voice payload。

    Args:
        target: 对方主页链接或纯数字 uid。
        content: 语音消息 payload（dict）。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_audio(auth, conversation_id, short_id, ticket, None, content=content)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_sticker(
    target: str,
    image_id: str,
    uri: str,
    display_name: str = "",
    image_type: str = "gif",
    width: int = 0,
    height: int = 0,
    package_id: int = 0,
    url_list: list[str] | None = None,
) -> dict:
    """发送表情包（BIG_EMOJI，需要平台表情的 CDN 元数据）。

    Args:
        target: 对方主页链接或纯数字 uid。
        image_id: 表情的 image_id。
        uri: 表情 CDN 的 uri。
        display_name: 显示名。
        image_type: 图片类型，默认 gif。
        width: 宽。
        height: 高。
        package_id: 表情包 id。
        url_list: 表情 CDN 的候选地址列表（可选，取不到时接口会用 uri 拼）。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_sticker(
        auth, conversation_id, short_id, ticket,
        image_id=image_id, uri=uri, display_name=display_name, image_type=image_type,
        width=width, height=height, package_id=package_id, url_list=url_list,
    )
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_share_aweme(
    target: str,
    aweme: str,
    title: str = "",
    uid: str = "",
    sec_uid: str = "",
    name: str = "",
    item_id: str = "",
    share_id: str = "",
    timestamp: int | None = None,
) -> dict:
    """把某个作品以卡片形式分享给私信对象。

    Args:
        target: 对方主页链接或纯数字 uid。
        aweme: 作品链接或作品 id（链接会自动取详情）。
        title: 可选卡片标题。
        uid: 作品作者的 uid，留空自动取。
        sec_uid: 作品作者的 sec_uid，留空自动取。
        name: 作者昵称，留空自动取。
        item_id: 作品 id，留空自动取。
        share_id: 分享 id，留空自动拼 ``uid_时间戳_item_id``。
        timestamp: 拼 share_id 用的毫秒时间戳，留空取当前时间。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    url = aweme if aweme.startswith("http") else f"https://www.douyin.com/video/{aweme}"
    kwargs = _card_kwargs(
        title=title, uid=uid, sec_uid=sec_uid, name=name,
        item_id=item_id, share_id=share_id, timestamp=timestamp,
    )
    ok = DouyinAPI.send_share_aweme(auth, conversation_id, short_id, ticket, url, **kwargs)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_share_photos(
    target: str,
    aweme: str,
    title: str = "",
    image_count: int | None = None,
    image_index: int = 0,
) -> dict:
    """把图集作品以卡片形式分享给私信对象。

    Args:
        target: 对方主页链接或纯数字 uid。
        aweme: 图集作品链接或作品 id（链接会自动取详情）。
        title: 可选卡片标题。
        image_count: 图集张数，留空按作品详情自动取。
        image_index: 卡片展示第几张图，默认 0。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    url = aweme if aweme.startswith("http") else f"https://www.douyin.com/note/{aweme}"
    kwargs = _card_kwargs(title=title, image_count=image_count, image_index=image_index)
    ok = DouyinAPI.send_share_photos(auth, conversation_id, short_id, ticket, url, **kwargs)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_share_web(
    target: str,
    link_url: str,
    title: str = "",
    desc: str = "",
    cover_url: str = "",
) -> dict:
    """把网页链接以卡片形式分享给私信对象。

    Args:
        target: 对方主页链接或纯数字 uid。
        link_url: 要分享的网页地址。
        title: 卡片标题。
        desc: 卡片描述。
        cover_url: 卡片封面图地址。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    kwargs = _card_kwargs(title=title, desc=desc, cover_url=cover_url)
    ok = DouyinAPI.send_share_web(auth, conversation_id, short_id, ticket, link_url, **kwargs)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_user_card(target: str, user: str, name: str = "") -> dict:
    """发送用户名片。

    Args:
        target: 对方主页链接或纯数字 uid。
        user: 要分享的用户主页链接、纯数字 uid，或已抓好的 user 对象。
        name: 卡片显示名，留空沿用用户资料。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    content = _user_card_content(auth, user)
    kwargs = _card_kwargs(name=name)
    ok = DouyinAPI.send_user_card(auth, conversation_id, short_id, ticket, content, **kwargs)
    return {"ok": bool(ok), "to": target}


@write_tool
def im_send_card(target: str, message_type: int, content: dict) -> dict:
    """发送任意类型的卡片消息（底层透传，类型和 payload 由调用方负责）。

    常见类型：8 分享视频 / 25 用户名片 / 26 网页 / 77 图集。
    除非有专用工具覆盖不到的场景，优先用 im_send_share_* / im_send_user_card。

    Args:
        target: 对方主页链接或纯数字 uid。
        message_type: 消息类型编号。
        content: 卡片 payload（dict）。
    """
    auth = douyin_auth()
    _uid, conversation_id, short_id, ticket = DouyinAPI.open_conversation_with_user(auth, target)
    ok = DouyinAPI.send_card(auth, conversation_id, short_id, ticket, int(message_type), content)
    return {"ok": bool(ok), "to": target}
