"""写操作：点赞、评论（含图片表情）、收藏夹增删改。

全部是 ``DouyinAPI`` 现成方法的包装；写接口在服务端受 scope + 频率限制约束。
"""
from __future__ import annotations

from dy_apis.douyin_api import DouyinAPI

from ._common import douyin_auth, write_tool


@write_tool
def digg_work(aweme_id: str, digg_type: str = "1") -> dict:
    """给作品点赞 / 取消点赞。

    Args:
        aweme_id: 作品 ID 或作品链接。
        digg_type: "1" 点赞（默认）, "0" 取消点赞。
    """
    return {"ok": bool(DouyinAPI.digg(douyin_auth(), aweme_id, digg_type))}


@write_tool
def publish_comment(
    aweme_id: str,
    content: str = "",
    reply_id: str = "",
    sticker: dict | None = None,
    text_extra: list[dict] | None = None,
) -> dict:
    """发布评论或回复（支持图片表情评论、支持 @ 提及）。

    Args:
        aweme_id: 作品 ID 或作品链接。
        content: 评论文本；发纯表情评论时传空字符串。
        reply_id: 回复某条评论时填它的 comment id；发一级评论留空。
        sticker: 表情对象（可直接用 list_comment_stickers 返回的某一项，
            需要 id_str 与 animate_url.uri）。
        text_extra: @ 提及列表，字段与 PC Web 一致：
            [{"user_id": "1994962122842643",
              "sec_uid": "MS4wLjABAAAA...",
              "type": 0, "start": 0, "end": 3}]
            start/end 是 content 里 "@昵称" 的字符区间（左闭右开，与 Python 切片一致）；
            content 必须同时包含这段 "@昵称" 文本，否则服务端会丢弃该提及。
    """
    # 只在真的传了 mentions 时才带这个字段，保持原有调用形态不变
    kwargs = {"text_extra": text_extra} if text_extra else {}
    return DouyinAPI.publish_comment(douyin_auth(), aweme_id, content, reply_id, sticker, **kwargs)


@write_tool
def collect_work(aweme_id: str, action: str = "1") -> dict:
    """收藏 / 取消收藏作品。

    Args:
        aweme_id: 作品 ID 或作品链接。
        action: "1" 收藏（默认）, "0" 取消收藏。
    """
    return DouyinAPI.collect_aweme(douyin_auth(), aweme_id, action)


@write_tool
def move_collect(aweme_id: str, collect_name: str, collect_id: str) -> dict:
    """把作品移动到另一个收藏夹。

    Args:
        aweme_id: 作品 ID 或作品链接。
        collect_name: 目标收藏夹名称。
        collect_id: 目标收藏夹 ID。
    """
    return DouyinAPI.move_collect_aweme(douyin_auth(), aweme_id, collect_name, collect_id)


@write_tool
def remove_collect(aweme_id: str, collect_name: str, collect_id: str) -> dict:
    """从指定收藏夹移除作品。

    Args:
        aweme_id: 作品 ID 或作品链接。
        collect_name: 收藏夹名称。
        collect_id: 收藏夹 ID。
    """
    return DouyinAPI.remove_collect_aweme(douyin_auth(), aweme_id, collect_name, collect_id)
