"""只读工具：用户、作品、评论、收藏、通知、推荐流。

全部直接调 ``dy_apis.douyin_api.DouyinAPI`` 里现成的 static 方法，本层只做参数归一
（把 user_url 解析成 uid/sec_uid）和数量裁剪。
"""
from __future__ import annotations

from typing import Any

from dy_apis.douyin_api import DouyinAPI, parse_aweme_id

from ._common import douyin_auth, read_tool

MAX_LIMIT = 200


def _comment_ref(url: str, comment_id: str) -> dict:
    """评论回复接口只认 ``{"aweme_id", "cid"}`` 两个字段，这里由链接 + 评论 id 组装。"""
    aweme_id, _ = parse_aweme_id(url)
    return {"aweme_id": aweme_id, "cid": str(comment_id)}


def _user_ids(auth: Any, user_url: str) -> tuple[str, str]:
    info = DouyinAPI.get_user_info(auth, user_url)
    user = (info or {}).get("user") or {}
    return str(user.get("uid") or ""), str(user.get("sec_uid") or "")


def _trim(items: list, limit: int) -> dict:
    limit = max(1, min(int(limit), MAX_LIMIT))
    return {"total": len(items), "returned": min(len(items), limit), "items": items[:limit]}


@read_tool
def user_info(user_url: str) -> dict:
    """获取用户主页信息。

    Args:
        user_url: 用户主页链接，如 https://www.douyin.com/user/MS4wLjABAAAA...
    """
    return DouyinAPI.get_user_info(douyin_auth(), user_url)


@read_tool
def user_works(user_url: str, limit: int = 50) -> dict:
    """获取某个用户的全部作品（翻完所有分页后返回，可用 limit 截断）。

    Args:
        user_url: 用户主页链接。
        limit: 最多返回多少条作品，默认 50，上限 200。
    """
    auth = douyin_auth()
    works = DouyinAPI.get_user_all_work_info(auth, user_url)
    return _trim(works or [], limit)


@read_tool
def user_work_page(user_url: str, max_cursor: str = "0") -> dict:
    """按游标翻一页用户作品（需要自己处理分页时用）。

    Args:
        user_url: 用户主页链接。
        max_cursor: 上一页返回的 max_cursor，首页传 "0"。
    """
    return DouyinAPI.get_user_work_info(douyin_auth(), user_url, max_cursor)


@read_tool
def user_followers(user_url: str, limit: int = 20) -> dict:
    """获取用户的粉丝列表。

    Args:
        user_url: 用户主页链接。
        limit: 最多返回多少条，默认 20，上限 200。
    """
    auth = douyin_auth()
    uid, sec_uid = _user_ids(auth, user_url)
    items = DouyinAPI.get_some_user_follower_list(auth, uid, sec_uid, max(1, min(limit, MAX_LIMIT)))
    return {"uid": uid, "sec_uid": sec_uid, **_trim(items or [], limit)}


@read_tool
def user_following(user_url: str, limit: int = 20) -> dict:
    """获取用户的关注列表。

    Args:
        user_url: 用户主页链接。
        limit: 最多返回多少条，默认 20，上限 200。
    """
    auth = douyin_auth()
    uid, sec_uid = _user_ids(auth, user_url)
    items = DouyinAPI.get_some_user_following_list(auth, uid, sec_uid, max(1, min(limit, MAX_LIMIT)))
    return {"uid": uid, "sec_uid": sec_uid, **_trim(items or [], limit)}


@read_tool
def user_follower_page(user_url: str, max_time: str = "0", count: str = "20") -> dict:
    """按游标翻一页粉丝列表（需要自己控制分页时用）。

    Args:
        user_url: 用户主页链接。
        max_time: 上一页返回的 min_time；首页传 "0"（服务端会换成当前时间戳）。
        count: 每页数量，默认 "20"。
    """
    auth = douyin_auth()
    uid, sec_uid = _user_ids(auth, user_url)
    return DouyinAPI.get_user_follower_list(auth, uid, sec_uid, max_time, str(count))


@read_tool
def user_following_page(user_url: str, max_time: str = "0", count: str = "20") -> dict:
    """按游标翻一页关注列表（需要自己控制分页时用）。

    Args:
        user_url: 用户主页链接。
        max_time: 上一页返回的 min_time；首页传 "0"。
        count: 每页数量，默认 "20"。
    """
    auth = douyin_auth()
    uid, sec_uid = _user_ids(auth, user_url)
    return DouyinAPI.get_user_following_list(auth, uid, sec_uid, max_time, str(count))


@read_tool
def user_favorite(sec_user_id: str, limit: int = 18, max_cursor: str = "0") -> dict:
    """获取某个用户收藏的作品。

    Args:
        sec_user_id: 目标用户的 sec_uid（主页链接里 user/ 后面那串）。
        limit: 最多返回多少条，默认 18。
        max_cursor: 分页游标，首页传 "0"。
    """
    items = DouyinAPI.get_user_favorite(douyin_auth(), sec_user_id, max_cursor, str(limit))
    return _trim(items or [], limit) if isinstance(items, list) else items


@read_tool
def work_info(url: str) -> dict:
    """获取单个作品详情（视频或图集）。

    Args:
        url: 作品链接，https://www.douyin.com/video/<id> 或 /note/<id>。
    """
    return DouyinAPI.get_work_info(douyin_auth(), url)


@read_tool
def work_comments(url: str, limit: int = 50, with_replies: bool = True) -> dict:
    """获取作品的评论区（可选是否带上每条评论下的多级回复）。

    Args:
        url: 作品链接。
        limit: 最多返回多少条一级评论，默认 50，上限 200。
        with_replies: True 时把每条评论的子回复也抓下来（更慢、请求更多）。
    """
    auth = douyin_auth()
    limit = max(1, min(limit, MAX_LIMIT))
    if with_replies:
        items = DouyinAPI.get_work_all_comment(auth, url)
    else:
        items = DouyinAPI.get_work_all_out_comment(auth, url, count=str(limit))
    return _trim(items or [], limit)


@read_tool
def work_comment_page(url: str, cursor: str = "0") -> dict:
    """按游标翻一页作品的一级评论（需要自己控制分页时用）。

    接口固定每页 5 条，页大小不可调；要一次拿全量用 work_comments。

    Args:
        url: 作品链接。
        cursor: 上一页返回的 cursor，首页传 "0"。
    """
    return DouyinAPI.get_work_out_comment(douyin_auth(), url, cursor)


@read_tool
def comment_replies(url: str, comment_id: str, limit: int = 50) -> dict:
    """获取某条一级评论下的**全部**二级回复（自动翻完所有分页后截断）。

    Args:
        url: 作品链接。
        comment_id: 一级评论的 cid（从 work_comments / work_comment_page 的返回里取）。
        limit: 最多返回多少条回复，默认 50，上限 200。
    """
    auth = douyin_auth()
    limit = max(1, min(int(limit), MAX_LIMIT))
    items = DouyinAPI.get_work_all_inner_comment(auth, _comment_ref(url, comment_id))
    return _trim(items or [], limit)


@read_tool
def comment_reply_page(url: str, comment_id: str, cursor: str = "0", count: str = "5") -> dict:
    """按游标翻一页某条一级评论的二级回复（需要自己控制分页时用）。

    Args:
        url: 作品链接。
        comment_id: 一级评论的 cid。
        cursor: 上一页返回的 cursor，首页传 "0"。
        count: 每页数量，默认 "5"。
    """
    return DouyinAPI.get_work_inner_comment(
        douyin_auth(), _comment_ref(url, comment_id), cursor, str(count)
    )


@read_tool
def list_comment_stickers(cursor: str = "0", page_size: str = "500", source: str = "comment") -> dict:
    """列出可用于评论的图片表情包资源。

    Args:
        cursor: 分页游标，首页 "0"。
        page_size: 每页数量，默认 500。
        source: 资源来源，默认 "comment"（评论表情）。
    """
    return DouyinAPI.get_custom_stickers(douyin_auth(), cursor, page_size, source)


@read_tool
def collect_list() -> dict:
    """获取我自己的收藏夹列表。"""
    return DouyinAPI.get_collect_list(douyin_auth())


@read_tool
def notices(limit: int = 20, group: str = "960") -> dict:
    """获取消息通知（点赞/评论/关注等）。

    Args:
        limit: 最多返回多少条，默认 20。
        group: 通知分组，默认 "960"。
    """
    items = DouyinAPI.get_some_notice_list(douyin_auth(), max(1, min(limit, MAX_LIMIT)), group)
    return _trim(items or [], limit)


@read_tool
def notices_page(
    min_time: str = "0",
    max_time: str = "0",
    count: str = "10",
    group: str = "960",
) -> dict:
    """按时间窗取一页通知（原始分页接口，返回 has_more / min_time 等游标字段）。

    Args:
        min_time: 最小时间戳，默认 "0" 不限。
        max_time: 最大时间戳，默认 "0" 不限。
        count: 每页数量，默认 "10"。
        group: 通知分组，默认 "960"；700 全部 / 401 粉丝 / 601 @我的 / 2 评论 / 3 点赞 / 520 弹幕。
    """
    return DouyinAPI.get_notice_list(
        douyin_auth(), min_time=min_time, max_time=max_time, count=str(count), notice_group=group
    )


@read_tool
def feed(count: str = "20", refresh_index: str = "2") -> dict:
    """获取推荐流。

    Args:
        count: 拉取数量，默认 20。
        refresh_index: 刷新序号，默认 "2"。
    """
    return DouyinAPI.get_feed(douyin_auth(), count, refresh_index)
