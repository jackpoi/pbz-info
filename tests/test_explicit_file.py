"""用户直接选了一个 .sav 文件：就读那个文件，不替换成同目录的主存档。"""

from __future__ import annotations

import json
import shutil

import pytest

from app import service as service_mod
from app.pbz import container
from support import STEAM_ID, TEST_KEY, seed_key_cache

ADVANCED = {
    "LastContinueSlot": "AutoSave0",
    "BossRecord": {
        "BP_Monster_TestOne": {"Records": {"2": {"Cycle": 0, "AttemptCount": 9, "KillCount": 1, "BestTimeMs": 60000}}},
        "BP_Monster_TestTwo": {"Records": {"2": {"Cycle": 0, "AttemptCount": 3, "KillCount": 0, "BestTimeMs": 0}}},
    },
}
SLOT = {
    "PBZGameSystem": {
        "DifficultModeByte": 2,
        "CycleCount": 0,
        "CycleStartDiedTimes": 0,
        "CurrentCycleGameTime": 3600,
        "HasGameTime": 3600,
        "bIsFinishGame": False,
        "CurrentLevelName": "PBZ_Test",
        "LastSaveActorID": "Bell_Test",
        "DateTimeString": "2025.06.01-19.18.08",
    },
    "PBZDeathMeta": {"DiedTimes": 12},
    "Player": {"RemainingDays": 7},
}


@pytest.fixture(scope="module")
def key() -> bytes:
    return TEST_KEY


@pytest.fixture()
def cache(tmp_path):
    return seed_key_cache(tmp_path / "cache")


@pytest.fixture()
def snapshot(tmp_path, key):
    """在 <dir>/1RealTime 下造一个"旧快照"，内容与主存档明显不同。"""
    root = tmp_path / "save" / STEAM_ID
    realtime = root / "1RealTime"
    realtime.mkdir(parents=True)

    raw = container.build_container(
        {
            "__Advanced__": json.dumps(ADVANCED).encode(),
            "AutoSave0": json.dumps(SLOT).encode(),
        },
        key,
    )
    path = realtime / "20250601-191808-204.sav"
    path.write_bytes(raw)
    return path


@pytest.fixture()
def svc(cache):
    return service_mod.Service(cache_dir=cache)


def test_explicit_snapshot_keeps_the_account_id(snapshot, svc):
    view = svc.refresh(save_path=snapshot)
    assert view["meta"]["steamId"] == STEAM_ID


def test_explicit_file_is_read_instead_of_main_save(snapshot, svc):
    view = svc.refresh(save_path=snapshot)

    assert view["ok"] is True, view.get("error")
    assert view["meta"]["fileName"] == "20250601-191808-204.sav"
    assert view["meta"]["source"] == "file"
    assert view["meta"]["slot"] == "AutoSave0"
    assert view["totals"]["deaths"] == 12
    assert view["cycle"]["difficulty"] == 2
    assert [b["id"] for b in view["bosses"]] == ["BP_Monster_TestOne", "BP_Monster_TestTwo"]
    assert view["bosses"][0]["name"] is None  # 未映射，原样显示内部 ID
    assert view["bosses"][0]["deaths"] == 8


def test_switching_between_files_changes_numbers(snapshot, svc, sample_save):
    first = svc.refresh(save_path=sample_save)
    assert first["totals"]["deaths"] == 33

    second = svc.refresh(save_path=snapshot)
    assert second["totals"]["deaths"] == 12

    back = svc.refresh(save_path=sample_save)
    assert back["totals"]["deaths"] == 33


def test_broken_explicit_file_does_not_silently_use_main_save(tmp_path, snapshot, svc):
    """指定的文件坏了就报错，绝不能悄悄换成同目录的主存档。"""
    broken = snapshot.with_name("broken.sav")
    broken.write_bytes(b"not a container")

    view = svc.refresh(save_path=broken)
    assert view["ok"] is False
    assert view["error"]["code"] == service_mod.ERROR_PARSE_FAIL
    assert view["meta"].get("fileName") != service_mod.MAIN_SAVE


def test_bridge_remembers_explicit_file(tmp_path, snapshot, cache):
    from app import bridge as bridge_mod
    from app import config as config_mod

    config_path = tmp_path / "config.json"
    config = config_mod.load(config_path)
    svc = service_mod.Service(cache_dir=cache)
    bridge = bridge_mod.Bridge(svc, config, config_path=config_path)

    state = bridge.set_save_dir(str(snapshot))
    assert state["ok"] is True
    assert state["meta"]["fileName"] == snapshot.name

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["savePath"] == str(snapshot)
    assert saved["saveDir"] == str(snapshot.parent)

    # 重启后仍然读这个文件
    config2 = config_mod.load(config_path)
    svc2 = service_mod.Service(cache_dir=cache)
    bridge2 = bridge_mod.Bridge(svc2, config2, config_path=config_path)
    assert bridge2.get_state()["meta"]["fileName"] == snapshot.name


def test_back_to_main_save(tmp_path, snapshot, sample_save, cache):
    from app import bridge as bridge_mod
    from app import config as config_mod

    account = tmp_path / "save" / STEAM_ID
    shutil.copy2(sample_save, account / service_mod.MAIN_SAVE)

    config_path = tmp_path / "config.json"
    config = config_mod.load(config_path)
    svc = service_mod.Service(cache_dir=cache)
    bridge = bridge_mod.Bridge(svc, config, config_path=config_path)

    bridge.set_save_dir(str(snapshot))
    assert bridge.get_state()["meta"]["source"] == "file"

    state = bridge.use_main_save()
    assert state["ok"] is True
    assert state["meta"]["source"] == "main"
    assert state["meta"]["fileName"] == service_mod.MAIN_SAVE
    assert state["totals"]["deaths"] == 33


def test_main_save_still_falls_back_to_snapshot(tmp_path, snapshot, svc):
    """主存档坏了仍然可以降级到快照——这是"读主存档"路径专有的兜底。"""
    main = snapshot.parent.parent / service_mod.MAIN_SAVE
    main.write_bytes(b"half written")

    view = svc.refresh(save_path=main)
    assert view["ok"] is True
    assert view["meta"]["source"] == "snapshot"
    assert view["totals"]["deaths"] == 12
