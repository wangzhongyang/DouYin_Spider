"""本地任务工具：下载媒体、导出 Excel、按用户/关键词批量抓取。

对应 ``main.py`` 里那几条流程和 ``utils/data_util.py`` 的实现，只是把结果路径
作为返回值交给调用方（不再只打印日志）。
"""
from __future__ import annotations

import re

from dy_apis.douyin_api import DouyinAPI
from utils.data_util import download_work as _download_work
from utils.data_util import handle_work_info, save_to_xlsx

from ._common import EXCEL_DIR, MEDIA_DIR, douyin_auth, ensure_dirs, read_tool, write_tool

MAX_WORKS = 200
SAVE_CHOICES = {"media", "media-video", "media-image", "excel", "all"}


def _is_user_url(value: str) -> bool:
    return "/user/" in value


def _safe_name(value: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("_")
    return name[:80] or "douyin"


def _collect(auth, sources: list[str], per_source: int = MAX_WORKS) -> list[dict]:
    infos: list[dict] = []
    for source in sources:
        source = source.strip()
        if not source:
            continue
        if _is_user_url(source):
            user = DouyinAPI.get_user_info(auth, source)
            works = DouyinAPI.get_user_all_work_info(auth, source) or []
            for work in works[:per_source]:
                work.setdefault("author", {}).update(((user or {}).get("user") or {}))
                infos.append(handle_work_info(work))
        else:
            response = DouyinAPI.get_work_info(auth, source)
            infos.append(handle_work_info(response["aweme_detail"]))
    return infos


def _download(infos: list[dict], save_choice: str) -> dict:
    ensure_dirs()
    saved, failed = [], []
    for info in infos:
        try:
            _download_work(info, str(MEDIA_DIR), save_choice)
            saved.append(info.get("work_url") or info.get("work_id"))
        except Exception as exc:  # 单个作品失败不影响整批，和 main.py 一致
            failed.append({"work": info.get("work_url") or info.get("work_id"), "error": str(exc)[:200]})
    return {"saved": saved, "failed": failed, "media_dir": str(MEDIA_DIR)}


def _excel(infos: list[dict], name: str) -> str:
    ensure_dirs()
    file_path = EXCEL_DIR / f"{_safe_name(name)}.xlsx"
    save_to_xlsx(infos, str(file_path))
    return str(file_path)


def _save(infos: list[dict], save_choice: str, excel_name: str) -> dict:
    """按 CLI 的 save_choice 语义落盘：media* 下媒体，excel/all 额外导出表格。"""
    choice = str(save_choice or "media").strip()
    if choice not in SAVE_CHOICES:
        raise ValueError(f"save_choice 只能是 {', '.join(sorted(SAVE_CHOICES))}")
    if choice in {"excel", "all"} and not excel_name:
        raise ValueError("save_choice 为 excel/all 时必须给 excel_name")
    result: dict = {"count": len(infos)}
    if choice in {"media", "media-video", "media-image", "all"}:
        result.update(_download(infos, choice))
    if choice in {"excel", "all"}:
        result["excel"] = _excel(infos, excel_name)
    return result


@write_tool
def download_work(url: str, save_choice: str = "media", excel_name: str = "") -> dict:
    """下载单个作品的媒体文件到服务端 datas/media_datas（也可只导出 Excel）。

    Args:
        url: 作品链接。
        save_choice: media 视频+图片, media-video 只下视频, media-image 只下图片,
            excel 只导出表格, all 下载媒体并导出表格。
        excel_name: 导出 Excel 的文件名；save_choice 为 excel/all 时必填。
    """
    auth = douyin_auth()
    info = handle_work_info(DouyinAPI.get_work_info(auth, url)["aweme_detail"])
    return _save([info], save_choice, excel_name)


@write_tool
def download_works(urls: list[str], save_choice: str = "media", excel_name: str = "") -> dict:
    """批量下载多个作品（作品链接或用户主页链接混在一起都行）。

    Args:
        urls: 作品链接 / 用户主页链接列表；用户链接会展开为其全部作品（每个最多 200 条）。
        save_choice: 同 download_work。
        excel_name: 导出 Excel 的文件名；save_choice 为 excel/all 时必填。
    """
    if not urls:
        raise ValueError("urls 不能为空")
    auth = douyin_auth()
    infos = _collect(auth, urls)
    return _save(infos, save_choice, excel_name)


@write_tool
def export_excel(sources: list[str], name: str = "douyin_export") -> dict:
    """把若干作品/用户的数据导出成 Excel（存到服务端 datas/excel_datas）。

    Args:
        sources: 作品链接或用户主页链接的列表；用户链接会展开为其全部作品。
        name: 文件名（不含 .xlsx）。
    """
    auth = douyin_auth()
    infos = _collect(auth, sources)
    path = _excel(infos, name)
    return {"count": len(infos), "excel": path}


@write_tool
def crawl_user(user_url: str, download: bool = False, excel_name: str = "") -> dict:
    """抓取某个用户的全部作品，可选下载媒体并导出 Excel。

    Args:
        user_url: 用户主页链接。
        download: 是否把视频/图片下载到服务端。
        excel_name: 导出 Excel 的文件名；留空则不导出。
    """
    auth = douyin_auth()
    infos = _collect(auth, [user_url])
    result: dict = {"user_url": user_url, "count": len(infos)}
    if download:
        result["download"] = _download(infos, "media")
    if excel_name:
        result["excel"] = _excel(infos, excel_name)
    return result


@write_tool
def crawl_search(
    query: str,
    num: int = 20,
    sort_type: str = "0",
    publish_time: str = "0",
    filter_duration: str = "",
    search_range: str = "",
    content_type: str = "",
    download: bool = False,
    excel_name: str = "",
) -> dict:
    """按关键词搜索并抓取作品，可选下载媒体并导出 Excel。

    Args:
        query: 搜索关键词。
        num: 抓取多少条，默认 20。
        sort_type: 0 综合, 1 最多点赞, 2 最新发布。
        publish_time: 0 不限, 1 一天内, 7 一周内, 180 半年内。
        filter_duration: 时长筛选，同 search_works。
        search_range: 搜索范围，同 search_works。
        content_type: 0 不限, 1 视频, 2 图文。
        download: 是否下载媒体。
        excel_name: 导出 Excel 的文件名；留空则不导出。
    """
    auth = douyin_auth()
    works = DouyinAPI.search_some_general_work(
        auth, query, num, sort_type, publish_time, filter_duration, search_range, content_type
    ) or []
    infos = [handle_work_info(item["aweme_info"]) for item in works if item.get("aweme_info")]
    result: dict = {"query": query, "count": len(infos)}
    if download:
        result["download"] = _download(infos, "media")
    if excel_name:
        result["excel"] = _excel(infos, excel_name)
    return result
