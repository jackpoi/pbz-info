"""检查更新：只读一次 GitHub Releases 的 latest，不下载、不上报任何信息。

设计取舍见 docs/design.md「版本与更新」：
- 只有用户点“检查更新”才会调用 check()，启动时不联网；
- 结果在进程内缓存 60 秒，连点不会连着打 API；
- 任何失败都退化成“打不开”，由前端引导用户去发布页手动下载。
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from . import __version__
from . import logs

log = logs.get("update")

REPO = "jackpoi/pbz-info"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = f"pbz-info/{__version__} (+{RELEASES_PAGE})"
TIMEOUT = 8.0
CACHE_SECONDS = 60.0

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")

_cache: tuple[float, dict] | None = None


def parse_version(text: str | None) -> tuple[int, int, int] | None:
    """把 `v0.2.0` / `0.2.0` / `0.2.0-beta.1` 解析成三元组；不认识就返回 None。

    只取主版本三段：预发布号不参与比较，避免"最新版是 rc 却被判成更新"这类误报。
    """
    if not text:
        return None
    match = _VERSION_RE.match(str(text).strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer(latest: str | None, current: str | None) -> bool:
    new = parse_version(latest)
    old = parse_version(current)
    if new is None or old is None:
        return False  # 看不懂就不提示，宁可漏报也不要误报
    return new > old


def _fetch_latest(timeout: float = TIMEOUT) -> dict:
    request = urllib.request.Request(
        LATEST_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - 固定 https 地址
        return json.loads(response.read().decode("utf-8"))


def check(*, fetch=None, timeout: float = TIMEOUT) -> dict:
    """返回给前端的结构。永远返回 dict，不抛异常。"""
    global _cache

    now = time.monotonic()
    if _cache and now - _cache[0] < CACHE_SECONDS:
        return dict(_cache[1])

    fetcher = fetch or _fetch_latest
    try:
        release = fetcher(timeout=timeout)
    except urllib.error.HTTPError as exc:
        code = "RATE_LIMIT" if exc.code == 403 else "HTTP"
        log.warning("检查更新失败 · HTTP %s · %s", exc.code, "限流" if code == "RATE_LIMIT" else "状态码异常")
        result = {
            "ok": False,
            "current": __version__,
            "error": {"code": code, "message": f"GitHub 返回 {exc.code}，稍后再试或直接去发布页"},
        }
        _cache = (now, result)
        return dict(result)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        log.warning("检查更新失败 · 连不上 GitHub · %s", exc)
        result = {
            "ok": False,
            "current": __version__,
            "error": {"code": "NETWORK", "message": f"连不上 GitHub：{exc}"},
        }
        _cache = (now, result)
        return dict(result)
    except ValueError as exc:  # JSON 解析失败
        log.warning("检查更新失败 · 返回内容无法解析 · %s", exc)
        result = {
            "ok": False,
            "current": __version__,
            "error": {"code": "BAD_RESPONSE", "message": f"返回内容无法解析：{exc}"},
        }
        _cache = (now, result)
        return dict(result)

    if not isinstance(release, dict):
        return {"ok": False, "current": __version__, "error": {"code": "BAD_RESPONSE", "message": "返回内容为空"}}

    tag = release.get("tag_name")
    result = {
        "ok": True,
        "current": __version__,
        "latest": tag,
        "hasUpdate": is_newer(tag, __version__),
        "url": release.get("html_url") or RELEASES_PAGE,
        "publishedAt": (release.get("published_at") or "")[:10],
    }
    log.info(
        "检查更新 · 本地 %s · 发布页 %s · %s",
        __version__,
        tag,
        "有更新" if result["hasUpdate"] else "无需更新",
    )
    _cache = (now, result)
    return dict(result)


def reset_cache() -> None:
    """测试用：清掉缓存，避免用例之间互相污染。"""
    global _cache
    _cache = None
