"""只读工具：登录态自检。"""
from __future__ import annotations

from dy_apis.douyin_api import DouyinAPI

from ._common import douyin_auth, read_tool


def _safe(fn) -> dict:
    try:
        return {"ok": True, "value": fn()}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


@read_tool
def auth_status() -> dict:
    """检查服务端持有的抖音登录态是否可用。

    返回我的 uid / sec_uid、cookie 里是否带了风控必需的 UIFID、以及 DouyinAuth 的
    能力自检（cookie 来源、ticket/msToken/dtrait 是否就绪）。工具报错时先调它定位。
    """
    auth = douyin_auth()
    report: dict = {}
    try:
        report = auth.capability_report()
    except Exception as exc:
        report = {"error": f"{type(exc).__name__}: {exc}"[:300]}
    cookie_names = sorted(getattr(auth, "cookie", {}) or {})
    return {
        "uid": _safe(lambda: DouyinAPI.get_my_uid(auth)),
        "sec_uid": _safe(lambda: DouyinAPI.get_my_sec_uid(auth)),
        "has_uifid": "UIFID" in cookie_names,
        "cookie_fields": cookie_names,
        "capability": report,
    }


@read_tool
def my_security_token(force: bool = False) -> dict:
    """取当前登录态的 PC IM 身份安全令牌和设备 ID（排障用）。

    该令牌不是 Cookie，只用于私信发送的 protobuf 头，约 240 秒有效且与当前 ticket/dtrait
    会话绑定；默认走缓存，``force=True`` 强制重新获取。

    Args:
        force: 是否跳过缓存强制刷新，默认 False。
    """
    token, device_id = DouyinAPI.get_identity_security_token(douyin_auth(), force=bool(force))
    return {"identity_security_token": token, "device_id": device_id}


@read_tool
def device_id() -> dict:
    """获取当前登录态的设备 ID（/aweme/v1/web/query/user 返回的 id）。"""
    return {"device_id": DouyinAPI.get_device_id(douyin_auth())}
