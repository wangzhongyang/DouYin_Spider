"""创作者中心工具：发布图集 / 视频，以及发布前的预览与合规声明建议。

发布链路比较重（上传 → 检测 → 提交），一次调用可能几十秒到几分钟，
客户端超时要给足；创作者会话由 ``bootstrap_creator=True`` 单独补一次。
"""
from __future__ import annotations

from dy_apis.douyin_creator_api import DouyinCreatorAPI

from ._common import douyin_auth, read_tool, write_tool


def _poi(value: dict | None) -> dict | None:
    """位置必须是 poi 对象（不是名字字符串）：接口会直接读 poi_id / poi_name。"""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('poi 必须是对象，形如 {"poi_id": "713...", "poi_name": "上海"}')
    if not str(value.get("poi_id") or "").strip():
        raise ValueError('poi.poi_id 不能为空（poi_name 只用于展示）')
    return value


@read_tool
def creator_preview_videos(current_aweme_id: str = "") -> dict:
    """获取创作者中心的近期作品（发布页的"选择视频"列表）。

    Args:
        current_aweme_id: 当前作品 id，可空。
    """
    return DouyinCreatorAPI.get_preview_video_list(
        douyin_auth(bootstrap_creator=True), current_aweme_id=current_aweme_id or ""
    )


@read_tool
def creator_declaration_suggestion(creation_id: str, item_type: str = "video") -> dict:
    """获取某次创作的"自主声明"建议（AI 生成内容等合规声明）。

    Args:
        creation_id: 创作流水号。
        item_type: video 或 image。
    """
    return DouyinCreatorAPI.get_user_declaration_suggestion(
        douyin_auth(bootstrap_creator=True), creation_id, item_type=item_type
    )


@write_tool
def creator_publish_images(
    images: list[str],
    title: str = "",
    desc: str = "",
    visibility: int = 1,
    allow_download: bool = True,
    timing: int | None = None,
    cover_index: int = 0,
    cover_uri: str | None = None,
    poi: dict | None = None,
    challenges: list[str] | None = None,
    mentions: list[str] | None = None,
    activity: list[dict] | None = None,
    mix_id: str | None = None,
    hot_spot: dict | None = None,
    creation_id: str | None = None,
) -> dict:
    """发布图文作品（自动上传图片并提交）。

    Args:
        images: 本地图片路径或 http(s) 地址列表，至少一张。
        title: 标题（不超过 20 字）。
        desc: 正文描述（可内嵌 #话题 @好友 纯文本）。
        visibility: 谁可以看 0 公开 / 1 仅自己可见 / 2 好友可见（接口默认 1，即仅自己可见）。
        allow_download: 是否允许他人下载。
        timing: 定时发布时间戳（秒），空则立即发布。
        cover_index: 用第几张图当封面（从 0 开始）。
        cover_uri: 显式封面的 creator uri（优先于 cover_index）。
        poi: 位置对象 {"poi_id": "...", "poi_name": "..."}；不接受纯名称字符串。
        challenges: 话题列表（不带 #）。
        mentions: @ 的用户名列表。
        activity: 官方活动列表（原始活动对象）。
        mix_id: 合集 ID。
        hot_spot: 关联热点对象（builder 读取 hot_spot["word"]）。
        creation_id: 前端 creationId，留空自动生成。
    """
    if not images:
        raise ValueError("images 不能为空")
    return DouyinCreatorAPI.post_images(
        douyin_auth(bootstrap_creator=True),
        images,
        title=title,
        desc=desc,
        visibility=int(visibility),
        allow_download=bool(allow_download),
        timing=timing,
        cover_index=int(cover_index),
        cover_uri=cover_uri,
        poi=_poi(poi),
        challenges=challenges,
        mentions=mentions,
        activity=activity,
        mix_id=mix_id,
        hot_spot=hot_spot,
        creation_id=creation_id,
    )


@write_tool
def creator_publish_video(
    video: str,
    title: str = "",
    desc: str = "",
    visibility: int = 1,
    allow_download: bool = True,
    cover: str | None = None,
    cover_delay: int = 0,
    timing: int | None = None,
    poi: dict | None = None,
    challenges: list[str] | None = None,
    mentions: list[str] | None = None,
    activity: list[dict] | None = None,
    mix_id: str | None = None,
    hot_spot: dict | None = None,
    chapter: dict | None = None,
    creation_id: str | None = None,
) -> dict:
    """发布视频作品（自动分片上传、生成封面并提交，耗时可能较长）。

    Args:
        video: 本地视频路径或 http(s) 地址。
        title: 标题（不超过 20 字）。
        desc: 正文描述（可内嵌 #话题 @好友 纯文本）。
        visibility: 谁可以看 0 公开 / 1 仅自己可见 / 2 好友可见（接口默认 1，即仅自己可见）。
        allow_download: 是否允许他人下载。
        cover: 自定义封面图片路径/地址，或 creator 的 tos- uri；空则自动取帧。
        cover_delay: 取封面的时间点（秒），默认 0。
        timing: 定时发布时间戳（秒），空则立即发布。
        poi: 位置对象 {"poi_id": "...", "poi_name": "..."}；不接受纯名称字符串。
        challenges: 话题列表（不带 #）。
        mentions: @ 的用户名列表。
        activity: 官方活动列表（原始活动对象）。
        mix_id: 合集 ID。
        hot_spot: 关联热点对象（builder 读取 hot_spot["word"]）。
        chapter: 章节对象（键集合与 PC 端一致，无章节留空）。
        creation_id: 前端 creationId，留空自动生成。
    """
    return DouyinCreatorAPI.post_video(
        douyin_auth(bootstrap_creator=True),
        video,
        title=title,
        desc=desc,
        visibility=int(visibility),
        allow_download=bool(allow_download),
        cover=cover,
        cover_delay=int(cover_delay),
        timing=timing,
        poi=_poi(poi),
        challenges=challenges,
        mentions=mentions,
        activity=activity,
        mix_id=mix_id,
        hot_spot=hot_spot,
        chapter=chapter,
        creation_id=creation_id,
    )


@read_tool
def creator_cover_gen_ref(creation_id: str) -> dict:
    """获取某次创作的封面生成参考数据（cover/gen/ref）。

    Args:
        creation_id: 创作流水号。
    """
    return DouyinCreatorAPI.get_cover_gen_ref(douyin_auth(bootstrap_creator=True), creation_id)


@read_tool
def creator_media_url(uri: str) -> dict:
    """把创作者素材的 uri 换成可访问的 URL（creator/get/url）。

    Args:
        uri: creator 素材 uri，例如 tos-... 开头的封面/视频 uri。
    """
    return {"url": DouyinCreatorAPI.get_creator_media_url(douyin_auth(bootstrap_creator=True), uri)}


@write_tool
def creator_video_enable(video_id: str) -> dict:
    """向创作者中心发送视频 enable 信号（部分上传/发布流程需要）。

    Args:
        video_id: 创作者中心的视频 ID（vid 或 video_id）。
    """
    return DouyinCreatorAPI.video_enable(douyin_auth(bootstrap_creator=True), video_id)


@write_tool
def creator_video_transend(video_id: str) -> dict:
    """向创作者中心发送视频 transend（转码结束）信号。

    Args:
        video_id: 创作者中心的视频 ID（vid 或 video_id）。
    """
    return DouyinCreatorAPI.video_transend(douyin_auth(bootstrap_creator=True), video_id)
