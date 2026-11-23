"""直播相关工具：房间信息、榜单、PK、连麦、小黄车，以及直播间点赞/发弹幕。

注意：**实时监听（WebSocket 弹幕流）没有做成工具**——它需要长连接和后台线程，
和 MCP 的请求-响应模型不搭；需要弹幕流请继续用 ``python -m dy_live.server <id>``。
这里的都是普通 REST 调用，复用 ``DouyinAPI`` 现成方法。

大部分接口要 room_id / anchor_id / sec_uid 三件套，这里统一由直播间号现场解析，
免得调用方自己拼。
"""
from __future__ import annotations

from typing import Any

from dy_apis.douyin_api import DouyinAPI

from ._common import douyin_auth, read_tool, write_tool


def _room(auth: Any, live_id: str) -> dict:
    info, _ = DouyinAPI.get_live_info(auth, live_id)
    if not info:
        raise RuntimeError(f"解析直播间失败：{live_id}（可能未开播、链接不对，或登录态已失效）")
    return info


def _room_ids(auth: Any, live_id: str) -> tuple[str, str, str]:
    info = _room(auth, live_id)
    return str(info.get("room_id") or ""), str(info.get("anchor_id") or ""), str(info.get("sec_uid") or "")


@read_tool
def live_info(live_id: str) -> dict:
    """获取直播间基本信息（是否在播、标题、主播、房间 ID）。

    Args:
        live_id: 直播间号，https://live.douyin.com/123456789 里的那串数字。
    """
    info, data = DouyinAPI.get_live_info(douyin_auth(), str(live_id))
    return {"room": info, "detail": data}


@read_tool
def live_room_enter(web_rid: str) -> dict:
    """进入直播间（上报一次进场，顺带拿到房间上下文）。

    Args:
        web_rid: 直播间号。
    """
    return DouyinAPI.get_live_room_enter(douyin_auth(), str(web_rid))


@read_tool
def webcast_detail(live_id: str) -> dict:
    """获取直播间 webcast 详情（房间 ID、游标、internal_ext 等底层信息）。

    Args:
        live_id: 直播间号。
    """
    auth = douyin_auth()
    info = _room(auth, str(live_id))
    return DouyinAPI.get_webcast_detail(
        auth,
        str(info.get("user_id") or ""),
        str(info.get("room_id") or ""),
        f"https://live.douyin.com/{live_id}",
    )


@read_tool
def live_contribution_rank(live_id: str, rank_type: str = "30") -> dict:
    """直播间贡献榜（打赏排行）。

    Args:
        live_id: 直播间号。
        rank_type: 榜单类型，默认 "30"。
    """
    auth = douyin_auth()
    room_id, anchor_id, sec_uid = _room_ids(auth, str(live_id))
    return DouyinAPI.get_live_contribution_rank(
        auth, room_id, anchor_id, sec_uid, web_rid=str(live_id), rank_type=rank_type
    )


@read_tool
def live_thousand_ticket_rank(live_id: str, seats_type: str = "2") -> dict:
    """直播间千元榜（付费礼物榜）。

    Args:
        live_id: 直播间号。
        seats_type: 席位类型，默认 "2"。
    """
    auth = douyin_auth()
    room_id, _, _ = _room_ids(auth, str(live_id))
    return DouyinAPI.get_live_thousand_ticket_rank(auth, room_id, web_rid=str(live_id), seats_type=seats_type)


@read_tool
def live_pk_context(live_id: str, channel_id: str | None = None) -> dict:
    """查询当前 PK 上下文（是否在 PK、双方主播、当前比分）。

    Args:
        live_id: 直播间号。
        channel_id: PK 频道 ID；留空自动从房间信息里发现。
    """
    return DouyinAPI.get_live_pk_context(douyin_auth(), str(live_id), channel_id)


@read_tool
def live_pk_rank(live_id: str, side: str = "current") -> dict:
    """查询 PK 排行榜。

    Args:
        live_id: 直播间号。
        side: "current" 当前侧 或 "other" 对侧。
    """
    return DouyinAPI.get_live_pk_rank(douyin_auth(), str(live_id), side)


@read_tool
def live_linkmic_list(live_id: str, channel_id: str) -> dict:
    """连麦列表面板。

    Args:
        live_id: 直播间号。
        channel_id: 连麦频道 ID。
    """
    auth = douyin_auth()
    room_id, anchor_id, _ = _room_ids(auth, str(live_id))
    return DouyinAPI.get_live_linkmic_list(auth, room_id, channel_id, anchor_id, web_rid=str(live_id))


@read_tool
def live_products(live_id: str) -> dict:
    """直播间小黄车商品列表。

    Args:
        live_id: 直播间号。
    """
    return DouyinAPI.get_all_live_production(douyin_auth(), f"https://live.douyin.com/{live_id}")


@read_tool
def live_product_detail(live_id: str, promotion_id: str, origin_type: str = "638303") -> dict:
    """直播间某个商品的详情。

    Args:
        live_id: 直播间号。
        promotion_id: 商品 promotion_id（从 live_products 里拿）。
        origin_type: 来源类型，默认 "638303"。
    """
    return DouyinAPI.get_live_production_detail(
        douyin_auth(), f"https://live.douyin.com/{live_id}", promotion_id, origin_type
    )


@read_tool
def live_product_comments(
    product_id: str,
    shop_id: str,
    cursor: str = "0",
    count: str = "10",
    sort_type: str = "0",
    tag_id: str = "",
    stat_id: str = "",
) -> dict:
    """直播间商品的评价列表。

    Args:
        product_id: 商品 ID。
        shop_id: 店铺 ID。
        cursor: 分页游标。
        count: 每页数量。
        sort_type: 排序方式。
        tag_id: 评价标签 ID。
        stat_id: 统计 ID。
    """
    return DouyinAPI.get_product_comments(
        douyin_auth(), product_id, shop_id, cursor, count, sort_type, tag_id, stat_id
    )


@write_tool
def live_digg(live_id: str, count: str = "1") -> dict:
    """给直播间点赞。

    Args:
        live_id: 直播间号。
        count: 连点次数，默认 "1"。
    """
    auth = douyin_auth()
    room_id, _, _ = _room_ids(auth, str(live_id))
    return DouyinAPI.diggLiveRoom(auth, room_id, count)


@write_tool
def live_send_danmaku(live_id: str, content: str) -> dict:
    """在直播间发送弹幕。

    Args:
        live_id: 直播间号。
        content: 弹幕内容。
    """
    auth = douyin_auth()
    room_id, _, _ = _room_ids(auth, str(live_id))
    return DouyinAPI.sendMsgInRoom(auth, room_id, content)
