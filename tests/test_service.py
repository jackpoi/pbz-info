"""Service 端到端：合成存档 + 固定密钥，覆盖正常、缓存、失败、降级四条路径。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from app import service as service_mod
from support import STEAM_ID, seed_key_cache


@pytest.fixture()
def cache(tmp_path) -> Path:
    return seed_key_cache(tmp_path / "cache")


@pytest.fixture()
def svc(cache) -> service_mod.Service:
    return service_mod.Service(cache_dir=cache)


@pytest.fixture()
def save_dir(tmp_path, sample_save, monkeypatch) -> Path:
    """把合成存档放进临时账号目录，并断开对真实游戏的依赖。"""
    target = tmp_path / "Steam" / STEAM_ID
    target.mkdir(parents=True)
    shutil.copy2(sample_save, target / "PBZSaveGame.sav")
    monkeypatch.setattr(
        service_mod.Service,
        "_exe_from_save_dir",
        staticmethod(lambda _dir: None),
    )
    return target


def test_refresh_matches_sample(svc, save_dir):
    view = svc.refresh(save_dir=save_dir)

    assert view["ok"] is True
    assert view["meta"]["slot"] == "AutoSave0"
    assert view["meta"]["fileName"] == "PBZSaveGame.sav"
    assert view["meta"]["steamId"] == STEAM_ID
    assert view["totals"] == view["totals"] | {
        "deaths": 33,
        "bossDeaths": 30,
        "killed": 8,
    }
    assert len(view["bosses"]) == 10


def test_second_refresh_is_cached(svc, save_dir):
    first = svc.refresh(save_dir=save_dir)
    second = svc.refresh(save_dir=save_dir)
    assert second is first  # 内容未变，不重新解析

    forced = svc.refresh(save_dir=save_dir, force=True)
    assert forced is not first
    assert forced["totals"] == first["totals"]


def test_key_is_cached_to_disk(svc, save_dir, tmp_path):
    svc.refresh(save_dir=save_dir)
    cache = tmp_path / "cache" / "key.cache"
    assert cache.is_file()

    # 第二次实例直接命中缓存，不再扫描 exe
    fresh = service_mod.Service(cache_dir=tmp_path / "cache")
    started = time.perf_counter()
    view = fresh.refresh(save_dir=save_dir)
    elapsed = time.perf_counter() - started
    assert view["ok"] is True
    assert elapsed < 1.0, f"缓存命中后仍耗时 {elapsed:.3f}s"


def test_bad_dir_reports_bad_dir(svc, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    view = svc.refresh(save_dir=empty)
    assert view["ok"] is False
    assert view["error"]["code"] == service_mod.ERROR_BAD_DIR


def test_truncated_save_keeps_last_good_data(svc, save_dir):
    good = svc.refresh(save_dir=save_dir)
    assert good["ok"] is True

    target = save_dir / "PBZSaveGame.sav"
    raw = target.read_bytes()
    target.write_bytes(raw[:100])
    time.sleep(0.01)

    broken = svc.refresh(save_dir=save_dir)
    assert broken["ok"] is False
    assert broken["error"]["code"] == service_mod.ERROR_PARSE_FAIL
    assert broken["meta"]["stale"] is True
    assert broken["totals"]["deaths"] == 33  # 上一次成功的数据仍在


def test_falls_back_to_realtime_snapshot(svc, save_dir):
    target = save_dir / "PBZSaveGame.sav"
    raw = target.read_bytes()
    target.write_bytes(raw[:100])  # 主存档不可读

    snapshot = save_dir / "1RealTime" / "20250101-120000-000.sav"
    snapshot.parent.mkdir()
    snapshot.write_bytes(raw)

    view = svc.refresh(save_dir=save_dir)
    assert view["ok"] is True
    assert view["meta"]["source"] == "snapshot"
    assert view["meta"]["fileName"].endswith(".sav")
    assert view["totals"]["deaths"] == 33


def test_locate_without_game(monkeypatch, svc):
    from app import discovery

    def boom():
        raise discovery.DiscoveryError("没有找到 Steam 安装路径")

    monkeypatch.setattr(discovery, "discover", boom)
    view = svc.refresh()
    assert view["error"]["code"] == service_mod.ERROR_NO_GAME


def test_locate_auto_uses_real_install(svc):
    """本机装了游戏时，自动发现应能找到存档；没有游戏则跳过。"""
    from app import discovery

    try:
        _install, _exe, _accounts = discovery.discover()
    except discovery.DiscoveryError as exc:
        pytest.skip(str(exc))

    view = svc.refresh()
    assert view["ok"] is True, view.get("error")
    assert Path(view["meta"]["savePath"]).name == "PBZSaveGame.sav"
