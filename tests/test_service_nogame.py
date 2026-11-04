"""没有安装游戏时也能用：手动指定存档、只手上有密钥缓存、密钥不匹配等路径。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app import service as service_mod
from app.pbz import key as key_mod
from support import STEAM_ID, TEST_KEY, seed_key_cache, write_fake_exe


@pytest.fixture()
def save_only(tmp_path, sample_save, monkeypatch) -> Path:
    """只有存档、没有任何游戏文件的目录。"""
    target = tmp_path / "somewhere" / STEAM_ID
    target.mkdir(parents=True)
    shutil.copy2(sample_save, target / "PBZSaveGame.sav")
    # 这台"机器"上没有 Steam、没有 PBZ.exe
    monkeypatch.setattr(
        service_mod.Service,
        "_exe_from_save_dir",
        staticmethod(lambda _dir: None),
    )
    return target


def test_without_any_key_asks_for_exe(tmp_path, save_only):
    svc = service_mod.Service(cache_dir=tmp_path / "cache")
    view = svc.refresh(save_dir=save_only)

    assert view["ok"] is False
    assert view["error"]["code"] == service_mod.ERROR_NEED_EXE
    assert view["cycle"] is None


def test_cached_key_is_enough_without_game(tmp_path, save_only):
    cache = seed_key_cache(tmp_path / "cache")
    svc = service_mod.Service(cache_dir=cache)
    view = svc.refresh(save_dir=save_only)

    assert view["ok"] is True
    assert view["totals"]["deaths"] == 33
    assert view["meta"]["steamId"] == STEAM_ID


def test_user_supplied_exe_unblocks(tmp_path, save_only):
    svc = service_mod.Service(cache_dir=tmp_path / "cache")
    assert svc.refresh(save_dir=save_only)["error"]["code"] == service_mod.ERROR_NEED_EXE

    svc.set_exe(write_fake_exe(tmp_path / "game" / "PBZ.exe"))
    view = svc.refresh(save_dir=save_only)
    assert view["ok"] is True
    assert view["totals"]["deaths"] == 33
    # 派生结果已落盘，下次没有 exe 也能用
    assert (tmp_path / "cache" / "key.cache").is_file()


def test_wrong_exe_does_not_break_cached_key(tmp_path, save_only):
    """先有正确密钥，再被塞一个派生不出正确密钥的 exe，仍然能读。"""
    cache = tmp_path / "cache"
    svc = service_mod.Service(cache_dir=cache)
    svc.set_exe(write_fake_exe(tmp_path / "game" / "PBZ.exe"))
    assert svc.refresh(save_dir=save_only)["ok"] is True

    bogus = tmp_path / "PBZ.exe"
    bogus.write_bytes(b"MZ" + b"\x00" * 4096)  # 没有锚点，会走兜底偏移
    svc.set_exe(bogus)
    view = svc.refresh(save_dir=save_only, force=True)
    assert view["ok"] is True
    assert view["totals"]["deaths"] == 33


def test_two_keys_are_kept(tmp_path):
    cache = tmp_path / "key.cache"
    key_mod._remember(cache, {"size": 1, "mtime_ns": 1}, "a", TEST_KEY)
    key_mod._remember(cache, {"size": 2, "mtime_ns": 2}, "b", b"\x01" * 32)

    keys = key_mod.keys_from_cache(cache)
    assert keys[0] == b"\x01" * 32  # 最近使用的在前
    assert TEST_KEY in keys


def test_legacy_cache_format_is_readable(tmp_path):
    """早期单密钥格式仍然能读。"""
    import json

    cache = tmp_path / "key.cache"
    cache.write_text(
        json.dumps({"fingerprint": {"size": 1, "mtime_ns": 1}, "key": TEST_KEY.hex()}),
        encoding="utf-8",
    )
    assert len(key_mod.keys_from_cache(cache)) == 1


def test_picking_a_file_instead_of_folder(tmp_path, sample_save):
    """用户直接选了 .sav 文件时，按它的父目录处理。"""
    target = tmp_path / "Steam" / STEAM_ID
    target.mkdir(parents=True)
    shutil.copy2(sample_save, target / "PBZSaveGame.sav")

    svc = service_mod.Service(cache_dir=seed_key_cache(tmp_path / "cache"))
    view = svc.refresh(save_dir=target / "PBZSaveGame.sav")
    assert view["ok"] is True
    assert view["totals"]["deaths"] == 33
