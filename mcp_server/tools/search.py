"""只读工具：搜索（视频 / 用户 / 直播）。"""
from __future__ import annotations

from dy_apis.douyin_api import DouyinAPI

from ._common import douyin_auth, read_tool


@read_tool
def search_works(
    query: str,
    num: int = 20,
    sort_type: str = "0",
    publish_time: str = "0",
    filter_duration: str = "",
    search_range: str = "",
    content_type: str = "",
) -> dict:
    """搜索视频作品（综合搜索，支持排序/时间/时长/内容形式筛选）。

    Args:
        query: 搜索关键词。
        num: 需要多少条结果，默认 20。
        sort_type: 排序 0 综合, 1 最多点赞, 2 最新发布。
        publish_time: 发布时间 0 不限, 1 一天内, 7 一周内, 180 半年内。
        filter_duration: 时长 "" 不限, "0-1" 一分钟内, "1-5" 1-5 分钟, "5-10000" 5 分钟以上。
        search_range: 范围 0 不限, 1 最近看过, 2 还未看过, 3 关注的人。
        content_type: 内容形式 0 不限, 1 视频, 2 图文。
    """
    return DouyinAPI.search_some_general_work(
        douyin_auth(), query, num, sort_type, publish_time, filter_duration, search_range, content_type
    )


@read_tool
def search_videos(
    query: str,
    num: int = 20,
    sort_type: str = "0",
    publish_time: str = "0",
    filter_duration: str = "",
    search_range: str = "",
) -> dict:
    """搜索视频（视频专用搜索接口，比综合搜索少了图文混排）。

    Args:
        query: 搜索关键词。
        num: 需要多少条结果，默认 20。
        sort_type: 排序 0 综合, 1 最多点赞, 2 最新发布。
        publish_time: 发布时间 0 不限, 1 一天内, 7 一周内, 180 半年内。
        filter_duration: 时长筛选，同 search_works。
        search_range: 搜索范围，同 search_works。
    """
    return DouyinAPI.search_some_video_work(
        douyin_auth(), query, num, sort_type, publish_time, filter_duration, search_range
    )


@read_tool
def search_users(query: str, num: int = 20, fans: str = "", user_type: str = "") -> dict:
    """搜索用户（支持按粉丝数区间和认证类型筛选）。

    Args:
        query: 搜索关键词。
        num: 需要多少条结果，默认 20。
        fans: 粉丝数区间 "" 不限, "0_1k" 1000 以下, "1k_1w" 1000-1 万,
            "1w_10w" 1-10 万, "10w_100w" 10-100 万, "100w_" 100 万以上。
        user_type: 用户类型 "" 不限, "common_user" 普通用户,
            "enterprise_user" 企业用户, "personal_user" 个人认证用户。
    """
    return DouyinAPI.search_some_user(
        douyin_auth(), query, num, douyin_user_fans=fans, douyin_user_type=user_type
    )


@read_tool
def search_works_page(
    query: str,
    offset: str = "0",
    sort_type: str = "0",
    publish_time: str = "0",
    filter_duration: str = "",
    search_range: str = "",
    content_type: str = "",
    search_id: str = "",
) -> dict:
    """按 offset 翻一页综合搜索（需要自己控制分页时用）。

    Args:
        query: 搜索关键词。
        offset: 偏移量，首页传 "0"；下一页按返回条数递增。
        sort_type: 排序 0 综合, 1 最多点赞, 2 最新发布。
        publish_time: 发布时间 0 不限, 1 一天内, 7 一周内, 180 半年内。
        filter_duration: 时长 "" 不限, "0-1" 一分钟内, "1-5" 1-5 分钟, "5-10000" 5 分钟以上。
        search_range: 范围 0 不限, 1 最近看过, 2 还未看过, 3 关注的人。
        content_type: 内容形式 0 不限, 1 视频, 2 图文。
        search_id: 上一页返回的 search_id，用于翻页时保持同一搜索会话。
    """
    return DouyinAPI.search_general_work(
        douyin_auth(), query, sort_type, publish_time, offset,
        filter_duration, search_range, content_type, search_id=search_id,
    )


@read_tool
def search_videos_page(
    query: str,
    offset: str = "0",
    count: str = "16",
    sort_type: str = "0",
    publish_time: str = "0",
    filter_duration: str = "",
    search_range: str = "0",
    search_id: str = "",
) -> dict:
    """按 offset 翻一页视频搜索（需要自己控制分页时用）。

    Args:
        query: 搜索关键词。
        offset: 偏移量，首页传 "0"。
        count: 每页数量，默认 "16"。
        sort_type: 排序 0 综合, 1 最多点赞, 2 最新发布。
        publish_time: 发布时间 0 不限, 1 一天内, 7 一周内, 180 半年内。
        filter_duration: 时长筛选，同 search_works。
        search_range: 搜索范围 0 不限, 1 最近看过, 2 还未看过, 3 关注的人。
        search_id: 上一页返回的下个搜索 ID。
    """
    search_id, guide_words, data = DouyinAPI.search_video_work(
        douyin_auth(), query, offset, str(count), sort_type, publish_time,
        filter_duration, search_range, search_id,
    )
    return {"next_search_id": search_id, "guide_words": guide_words, "data": data}


@read_tool
def search_users_page(
    query: str,
    offset: str = "0",
    num: str = "25",
    fans: str = "",
    user_type: str = "",
) -> dict:
    """按 offset 翻一页用户搜索（需要自己控制分页时用）。

    Args:
        query: 搜索关键词。
        offset: 偏移量，首页传 "0"。
        num: 每页数量，默认 "25"。
        fans: 粉丝数区间，取值同 search_users。
        user_type: 用户类型，取值同 search_users。
    """
    return DouyinAPI.search_user(
        douyin_auth(), query, offset, str(num),
        douyin_user_fans=fans, douyin_user_type=user_type,
    )


@read_tool
def search_lives(query: str, num: int = 15) -> dict:
    """搜索直播间。

    Args:
        query: 搜索关键词。
        num: 需要多少条结果，默认 15。
    """
    return DouyinAPI.search_some_live(douyin_auth(), query, num)
