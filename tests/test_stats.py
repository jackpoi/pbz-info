"""口径回归：所有界面数字都来自 build_view，测试直接对着运行时生成的合成数据跑。"""

from __future__ import annotations

import copy

import pytest

from app import mapping as mapping_mod, stats

EXPECTED_BOSSES = [
    # (id, attempt, kill, deaths, bestMs)
    ("BP_Monster_ZuoShang", 2, 1, 1, 180000),
    ("BP_Monster_HookMan_HorseCartCombat", 1, 1, 0, 45000),
    ("BP_Monster_YuCong_FirstTime", 1, 0, 1, None),
    ("BP_Monster_MobMan_Elite_Sword", 3, 1, 2, 120000),
    ("BP_Monster_PengMeng_Axe", 3, 1, 2, 150000),
    ("BP_Monster_AHua_GuiTouDao", 5, 1, 4, 200000),
    ("BP_Monster_HookMan", 2, 1, 1, 100000),
    ("BP_Monster_HookMan_P2", 4, 1, 3, 160000),
    ("BP_Monster_MoTian_LongZhu_01", 11, 1, 10, 300000),
    ("BP_Monster_HuaQianXIao", 6, 0, 6, None),
]


@pytest.fixture()
def mapping() -> mapping_mod.Mapping:
    return mapping_mod.load()


@pytest.fixture()
def view(dec_records, mapping) -> dict:
    return stats.build_view(dec_records, mapping)


# ------------------------------------------------------------------ 样本数值

def test_meta(view):
    assert view["ok"] is True
    assert view["meta"]["slot"] == "AutoSave0"
    assert view["meta"]["savedAt"] == "2025-01-01 12:00:00"
    assert view["meta"]["steamId"] == "12345678901234567"
    assert view["meta"]["unmapped"] == 0


def test_cycle(view):
    assert view["cycle"] == {
        "index": 1,
        "difficulty": 3,
        "difficultyName": "逆天者",
        "finished": False,
        "level": "PBZ_Fujizhilin_WP",
        "bell": "Bell_LZSJ_003",
        "remainingDays": 42,
        "cycleTime": 12345,
        "totalTime": 12345,
    }


def test_totals(view):
    assert view["totals"]["deaths"] == 33
    assert view["totals"]["bossDeaths"] == 30
    assert view["totals"]["killed"] == 8
    assert view["totals"]["worst"] == {
        "id": "BP_Monster_MoTian_LongZhu_01",
        "name": "金面具黑衣人",
        "deaths": 10,
    }


def test_boss_rows(view):
    got = [(b["id"], b["attempt"], b["kill"], b["deaths"], b["bestMs"]) for b in view["bosses"]]
    assert got == EXPECTED_BOSSES


def test_boss_order_follows_record_order(view):
    """出现顺序 = BossRecord 的键顺序，不能被重新排序。"""
    assert [b["idx"] for b in view["bosses"]] == list(range(len(EXPECTED_BOSSES)))


def test_boss_names_resolve(view):
    names = {b["id"]: b["name"] for b in view["bosses"]}
    assert names["BP_Monster_HuaQianXIao"] == "剑痴：花千笑"
    assert names["BP_Monster_MoTian_LongZhu_01"] == "金面具黑衣人"
    assert all(name for name in names.values())


def test_boss_deaths_sum_matches_totals(view):
    assert sum(b["deaths"] for b in view["bosses"]) == view["totals"]["bossDeaths"]
    assert view["totals"]["bossDeaths"] < view["totals"]["deaths"]  # 差额是小怪/地形死亡


# ------------------------------------------------------------------ 口径随字段变化

def test_deaths_use_cycle_offset(dec_records, mapping):
    records = copy.deepcopy(dec_records)
    records["AutoSave0"]["PBZDeathMeta"]["DiedTimes"] = 80
    records["AutoSave0"]["PBZGameSystem"]["CycleStartDiedTimes"] = 5
    assert stats.build_view(records, mapping)["totals"]["deaths"] == 75


def test_missing_killcount_counts_as_zero(dec_records, mapping):
    records = copy.deepcopy(dec_records)
    record = records["__Advanced__"]["BossRecord"]["BP_Monster_HuaQianXIao"]["Records"]["3"]
    record.pop("KillCount", None)
    boss = next(b for b in stats.build_view(records, mapping)["bosses"]
                if b["id"] == "BP_Monster_HuaQianXIao")
    assert boss["kill"] == 0
    assert boss["deaths"] == 6


def test_kill_reduces_deaths(dec_records, mapping):
    records = copy.deepcopy(dec_records)
    record = records["__Advanced__"]["BossRecord"]["BP_Monster_HuaQianXIao"]["Records"]["3"]
    record["KillCount"] = 1
    record["BestTimeMs"] = 1234
    view = stats.build_view(records, mapping)
    boss = next(b for b in view["bosses"] if b["id"] == "BP_Monster_HuaQianXIao")
    assert (boss["kill"], boss["deaths"], boss["bestMs"]) == (1, 5, 1234)
    assert view["totals"]["killed"] == 9


def test_other_cycle_falls_back_to_slot_records(dec_records, mapping):
    """账号级记录写的是别的周目时，应退回槽位的 <cycle>_<difficulty> 键。"""
    records = copy.deepcopy(dec_records)
    records["AutoSave0"]["PBZGameSystem"]["CycleCount"] = 1
    for entry in records["__Advanced__"]["BossRecord"].values():
        entry["Records"]["3"]["Cycle"] = 0
        entry["Records"]["3"]["AttemptCount"] = 999
    # 槽位里没有 1_3 的键 -> 该难度本周目没有任何记录
    assert stats.build_view(records, mapping)["bosses"] == []


def test_unknown_difficulty_has_name_none(dec_records, mapping):
    records = copy.deepcopy(dec_records)
    records["AutoSave0"]["PBZGameSystem"]["DifficultModeByte"] = 9
    view = stats.build_view(records, mapping)
    assert view["cycle"]["difficultyName"] is None
    assert view["bosses"] == []


# ------------------------------------------------------------------ 槽位选择

def test_pick_slot_prefers_continue_slot(dec_records):
    assert stats.pick_slot(dec_records) == "AutoSave0"


def test_pick_slot_falls_back_to_newest(dec_records):
    records = copy.deepcopy(dec_records)
    records["__Advanced__"].pop("LastContinueSlot", None)
    assert stats.pick_slot(records) == "AutoSave0"

    records["AutoSave2"]["PBZGameSystem"]["DateTimeString"] = "2027.01.01-00.00.00"
    assert stats.pick_slot(records) == "AutoSave2"


def test_pick_slot_without_slots_raises(mapping):
    with pytest.raises(stats.StatsError):
        stats.build_view({"__Advanced__": {}}, mapping)


def test_saved_at_formatting():
    assert stats.format_saved_at("2025.01.01-12.00.00") == "2025-01-01 12:00:00"
    assert stats.format_saved_at("不是时间") == "不是时间"
    assert stats.format_saved_at(None) == ""
