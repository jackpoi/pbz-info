"""配置读写与桥接层（不启动窗口的部分）。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app import bridge as bridge_mod
from app import config as config_mod
from app import service as service_mod
from support import STEAM_ID, seed_key_cache, write_fake_exe


# ------------------------------------------------------------------ 配置

def test_defaults_when_missing(tmp_path):
    config = config_mod.load(tmp_path / "nope.json")
    assert config["window"]["width"] == 1180
    assert config["view"]["sort"] == "idx"
    assert config["saveDir"] is None


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = config_mod.load(path)
    config["saveDir"] = r"D:\save"
    config["window"]["width"] = 1280
    config_mod.save(config, path)

    again = config_mod.load(path)
    assert again["saveDir"] == r"D:\save"
    assert again["window"]["width"] == 1280


def test_partial_file_is_merged_with_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"window": {"height": 900}}), encoding="utf-8")
    config = config_mod.load(path)
    assert config["window"] == {"width": 1180, "height": 900, "x": None, "y": None}


def test_unknown_keys_are_dropped(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"bogus": 1, "window": {"nope": 2}}), encoding="utf-8")
    config = config_mod.load(path)
    assert "bogus" not in config
    assert "nope" not in config["window"]


def test_broken_file_falls_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ nope", encoding="utf-8")
    assert config_mod.load(path)["schema"] == 1


# ------------------------------------------------------------------ 桥接

@pytest.fixture()
def env(tmp_path, sample_save, monkeypatch):
    """一个只有存档、没有游戏的"机器"，密钥来自测试缓存。"""
    save_dir = tmp_path / "save" / STEAM_ID
    save_dir.mkdir(parents=True)
    shutil.copy2(sample_save, save_dir / "PBZSaveGame.sav")

    monkeypatch.setattr(
        service_mod.Service, "_exe_from_save_dir", staticmethod(lambda _d: None)
    )
    cache = seed_key_cache(tmp_path / "cache")
    config_path = tmp_path / "config.json"
    config = config_mod.load(config_path)
    svc = service_mod.Service(cache_dir=cache)
    bridge = bridge_mod.Bridge(svc, config, config_path=config_path)
    return bridge, config_path, save_dir


def test_get_state_without_any_location_is_an_error(env, monkeypatch):
    from app import discovery

    def boom():
        raise discovery.DiscoveryError("没有找到 Steam")

    monkeypatch.setattr(discovery, "discover", boom)
    bridge, _path, _save = env
    state = bridge.get_state()
    assert state["ok"] is False
    assert state["error"]["code"] == service_mod.ERROR_NO_GAME


def test_set_save_dir_switches_and_persists(env):
    bridge, config_path, save_dir = env
    state = bridge.set_save_dir(str(save_dir))
    assert state["ok"] is True
    assert state["totals"]["deaths"] == 33
    assert json.loads(config_path.read_text(encoding="utf-8"))["saveDir"] == str(save_dir)


def test_set_save_dir_accepts_a_sav_file(env):
    bridge, _path, save_dir = env
    state = bridge.set_save_dir(str(save_dir / "PBZSaveGame.sav"))
    assert state["ok"] is True


def test_bad_save_dir_is_rejected_without_persisting(env, tmp_path):
    bridge, config_path, _save = env
    empty = tmp_path / "empty"
    empty.mkdir()
    state = bridge.set_save_dir(str(empty))
    assert state["ok"] is False
    assert state["error"]["code"] == service_mod.ERROR_BAD_DIR
    assert not config_path.exists() or config_mod.load(config_path)["saveDir"] is None


def test_set_exe_records_path(env, tmp_path):
    bridge, config_path, save_dir = env
    bridge.set_save_dir(str(save_dir))
    fake_exe = write_fake_exe(tmp_path / "PBZ.exe")
    state = bridge.set_exe(str(fake_exe))
    assert state["ok"] is True
    assert config_mod.load(config_path)["exePath"] == str(fake_exe)


def test_set_exe_rejects_missing_file(env, tmp_path):
    bridge, _path, _save = env
    state = bridge.set_exe(str(tmp_path / "nope.exe"))
    assert state["ok"] is False


def test_view_preferences_persist(env):
    bridge, config_path, _save = env
    bridge.set_view("deaths", 1)
    view = config_mod.load(config_path)["view"]
    assert view == {"sort": "deaths", "dir": 1}


def test_list_accounts_without_steam_is_empty(env, monkeypatch):
    from app import discovery

    def boom():
        raise discovery.DiscoveryError("no steam")

    monkeypatch.setattr(discovery, "discover", boom)
    assert bridge_mod.Bridge.list_accounts(env[0]) == []


# ------------------------------------------------------------------ 版本 / 外链

def test_get_version_matches_module(env):
    from app import __version__

    info = env[0].get_version()
    assert info["version"] == __version__
    assert info["repo"] == "jackpoi/pbz-info"
    assert info["releasesPage"].endswith("/releases")


def test_open_url_rejects_foreign_links(env, monkeypatch):
    """桥接层只放行本项目地址，不接受任意 URL（哪怕是 https）。"""
    import app.bridge as bridge_module

    opened = []
    monkeypatch.setattr(bridge_module, "_open_url", lambda url: opened.append(url) or True)
    bridge = env[0]

    assert bridge.open_url("https://example.com")["ok"] is False
    assert bridge.open_url("file:///C:/Windows/System32/calc.exe")["ok"] is False
    assert bridge.open_url(None)["ok"] is False
    assert opened == []


def test_open_url_allows_project_links(env, monkeypatch):
    import app.bridge as bridge_module

    opened = []
    monkeypatch.setattr(bridge_module, "_open_url", lambda url: opened.append(url) or True)
    bridge = env[0]

    assert bridge.open_url("https://github.com/jackpoi/pbz-info")["ok"] is True
    assert bridge.open_url("https://github.com/jackpoi/pbz-info/releases/tag/v1.0.0")["ok"] is True
    assert len(opened) == 2


def test_check_update_never_raises(env, monkeypatch):
    """检查更新失败也只是返回 {ok:false}，不能把界面打崩。"""
    import app.update as update_module

    def boom():
        raise RuntimeError("network stack exploded")

    monkeypatch.setattr(update_module, "check", boom)
    result = env[0].check_update()
    assert result["ok"] is False
    assert result["error"]["code"] == "UNEXPECTED"
    assert result["current"]
