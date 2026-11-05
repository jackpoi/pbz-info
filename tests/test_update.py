"""版本号与检查更新（app/update.py）。

检查更新不下载、不上报：只读一次 GitHub Releases 的 latest。
"""

from __future__ import annotations

import urllib.error

import pytest

from app import update as update_mod


# ---------------------------------------------------------------- 版本解析

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("v0.2.0", (0, 2, 0)),
        ("0.2.0", (0, 2, 0)),
        ("v1.10.3", (1, 10, 3)),
        ("0.2.0-beta.1", (0, 2, 0)),
        ("", None),
        (None, None),
        ("nightly", None),
    ],
)
def test_parse_version(text, expected):
    assert update_mod.parse_version(text) == expected


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("v0.2.0", "0.1.1", True),
        ("v0.1.1", "0.1.1", False),
        ("v0.1.0", "0.1.1", False),
        ("v0.10.0", "0.9.0", True),
        ("nightly", "0.1.1", False),   # 看不懂就不提示，宁可漏报
        ("v0.2.0", "nightly", False),
        (None, "0.1.1", False),
    ],
)
def test_is_newer(latest, current, expected):
    assert update_mod.is_newer(latest, current) is expected


# ---------------------------------------------------------------- 远端响应

@pytest.fixture(autouse=True)
def _clear_cache():
    update_mod.reset_cache()
    yield
    update_mod.reset_cache()


def _fetcher(payload):
    def fetch(timeout=0):
        return payload
    return fetch


def test_reports_newer_version():
    result = update_mod.check(
        fetch=_fetcher(
            {
                "tag_name": "v0.3.0",
                "html_url": "https://github.com/jackpoi/pbz-info/releases/tag/v0.3.0",
                "published_at": "2026-11-06T01:02:03Z",
            }
        )
    )
    assert result["ok"] is True
    assert result["hasUpdate"] is True
    assert result["latest"] == "v0.3.0"
    assert result["publishedAt"] == "2026-11-06"
    assert result["url"].endswith("/v0.3.0")


def test_reports_up_to_date():
    result = update_mod.check(fetch=_fetcher({"tag_name": f"v{update_mod.__version__}"}))
    assert result["ok"] is True
    assert result["hasUpdate"] is False


def test_missing_html_url_falls_back_to_releases_page():
    result = update_mod.check(fetch=_fetcher({"tag_name": "v9.0.0"}))
    assert result["url"] == update_mod.RELEASES_PAGE


def test_network_failure_is_reported_not_raised():
    def boom(timeout=0):
        raise urllib.error.URLError("no route to host")

    result = update_mod.check(fetch=boom)
    assert result["ok"] is False
    assert result["error"]["code"] == "NETWORK"
    assert result["current"] == update_mod.__version__


def test_rate_limit_is_distinguished():
    def boom(timeout=0):
        raise urllib.error.HTTPError(update_mod.LATEST_API, 403, "rate limit", {}, None)

    result = update_mod.check(fetch=boom)
    assert result["ok"] is False
    assert result["error"]["code"] == "RATE_LIMIT"


def test_result_is_cached_between_clicks():
    calls = []

    def counting(timeout=0):
        calls.append(1)
        return {"tag_name": "v0.3.0"}

    update_mod.check(fetch=counting)
    update_mod.check(fetch=counting)
    assert len(calls) == 1


def test_returns_a_copy_so_callers_cannot_poison_the_cache():
    first = update_mod.check(fetch=_fetcher({"tag_name": "v0.3.0"}))
    first["hasUpdate"] = "mutated"
    second = update_mod.check(fetch=_fetcher({"tag_name": "v0.3.0"}))
    assert second["hasUpdate"] is True
