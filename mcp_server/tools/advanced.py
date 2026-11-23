"""兜底工具：把没单独做成工具的公开接口按名字直接调用。

曲线是给"高级用法"留的口子（分页细节、非主流程参数），所以：
- 只允许白名单里的方法，禁止 ``_`` 开头的内部实现；
- 参数必须是 JSON 对象，``auth`` / ``proxies`` 等由服务端自己决定；
- 写方法要求 ``douyin.write`` scope。
"""
from __future__ import annotations

from dy_apis.douyin_api import DouyinAPI
from dy_apis.douyin_creator_api import DouyinCreatorAPI

from ..config import SCOPE_WRITE
from ._common import active_runtime, douyin_auth, read_tool, require_scope

READ_METHODS = {
    "get_user_work_info": DouyinAPI,
    "get_work_out_comment": DouyinAPI,
    "get_work_inner_comment": DouyinAPI,
    "get_work_all_inner_comment": DouyinAPI,
    "get_live_production_detail": DouyinAPI,
    "get_product_comments": DouyinAPI,
    "get_product_comment_counter": DouyinAPI,
    "get_rank_list": DouyinAPI,
    "get_live_pk_contribution_rank": DouyinAPI,
    "get_live_linkmic_list": DouyinAPI,
    "search_general_work": DouyinAPI,
    "search_video_work": DouyinAPI,
    "search_user": DouyinAPI,
    "search_live": DouyinAPI,
    "get_conversation_list": DouyinAPI,
    "create_conversation": DouyinAPI,
    "resolve_user_uid": DouyinAPI,
    "get_user_conversation_list": DouyinAPI,
    "get_conversation_ticket": DouyinAPI,
    "get_identity_security_token": DouyinAPI,
    "get_device_id": DouyinAPI,
    "get_user_follower_list": DouyinAPI,
    "get_user_following_list": DouyinAPI,
    "get_notice_list": DouyinAPI,
    "get_cover_gen_ref": DouyinCreatorAPI,
    "get_creator_media_url": DouyinCreatorAPI,
    "get_preview_video_list": DouyinCreatorAPI,
}

WRITE_METHODS = {
    "send_card": DouyinAPI,
    "send_group_msg": DouyinAPI,
    "send_share_photos": DouyinAPI,
    "send_share_web": DouyinAPI,
    "send_user_card": DouyinAPI,
    "video_enable": DouyinCreatorAPI,
    "video_transend": DouyinCreatorAPI,
}

RESERVED_PARAMS = {"auth", "proxies", "request_context"}


@read_tool(dynamic_write=True)
def douyin_api_call(method: str, params: dict | None = None) -> dict:
    """直接调用白名单里的抖音接口（高级用法，参数原样透传）。

    传 ``params`` 时键名要和接口形参一致，例如
    ``{"query": "...", "num": 10, "sort_type": "0", "publish_time": "0"}``。
    白名单外的接口、``_`` 开头的内部方法一律拒绝；写接口需要 douyin.write scope，
    并和专用写工具一样受服务端频率限制（``MCP_ENABLE_WRITE=off`` 时直接拒绝）。

    Args:
        method: 接口方法名，如 get_user_work_info / search_video_work。
        params: 关键字参数字典，不能包含 auth / proxies / request_context。
    """
    owner = READ_METHODS.get(method) or WRITE_METHODS.get(method)
    if owner is None:
        allowed = ", ".join(sorted({*READ_METHODS, *WRITE_METHODS}))
        raise ValueError(f"不支持的方法 {method!r}；白名单：{allowed}")

    payload = dict(params or {})
    blocked = RESERVED_PARAMS & set(payload)
    if blocked:
        raise ValueError(f"参数里不能出现：{', '.join(sorted(blocked))}")

    if method in WRITE_METHODS:
        # 运行时才知道这次是不是写：开关/scope/限流都在这里补齐，
        # 不能依赖装饰器（它按只读注册，好让 MCP_ENABLE_WRITE=off 时读透传仍可用）。
        runtime = active_runtime()
        if runtime is None:
            raise RuntimeError("服务尚未完成工具注册，拒绝执行写操作")
        config, limiter = runtime
        if not config.enable_write:
            raise RuntimeError("服务端已关闭写操作（MCP_ENABLE_WRITE=off）")
        require_scope(SCOPE_WRITE)
        limiter.check()

    creator_only = owner is DouyinCreatorAPI
    auth = douyin_auth(bootstrap_creator=creator_only)
    return getattr(owner, method)(auth, **payload)
