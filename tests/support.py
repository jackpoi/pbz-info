"""测试用的合成存档与密钥工具。

这里的数据全部是虚构的：不含任何真实 SteamID、游玩记录或本机路径，
也不依赖安装游戏。容器用 PBZS v3 + zlib，密钥是固定常量；
真实 Oodle 流的回归只在设置了 ``PBZ_TEST_SAVE`` 的机器上跑。
"""

from __future__ import annotations

import json
from pathlib import Path

from app.pbz import container
from app.pbz import key as key_mod

#: 固定测试密钥：同一个仓库里所有合成容器都用它
TEST_KEY = bytes(range(32))

#: 虚构账号，测试断言统一引用这两个常量
STEAM_ID = "12345678901234567"
OTHER_STEAM_ID = "12345678901234568"

#: 虚构存档时间，格式与游戏一致
SAVED_AT = "2025.01.01-12.00.00"

DIFFICULTY = 3
CYCLE = 0
DIED_TIMES = 38
CYCLE_START_DIED = 5

#: (BossID, AttemptCount, KillCount, BestTimeMs)
BOSS_ROWS: list[tuple[str, int, int, int | None]] = [
    ("BP_Monster_ZuoShang", 2, 1, 180000),
    ("BP_Monster_HookMan_HorseCartCombat", 1, 1, 45000),
    ("BP_Monster_YuCong_FirstTime", 1, 0, None),
    ("BP_Monster_MobMan_Elite_Sword", 3, 1, 120000),
    ("BP_Monster_PengMeng_Axe", 3, 1, 150000),
    ("BP_Monster_AHua_GuiTouDao", 5, 1, 200000),
    ("BP_Monster_HookMan", 2, 1, 100000),
    ("BP_Monster_HookMan_P2", 4, 1, 160000),
    ("BP_Monster_MoTian_LongZhu_01", 11, 1, 300000),
    ("BP_Monster_HuaQianXIao", 6, 0, None),
]


def sample_records() -> dict[str, dict]:
    """合成存档的解码结果：{记录名: JSON 对象}。"""
    boss_record: dict[str, dict] = {}
    for boss_id, attempt, kill, best in BOSS_ROWS:
        record: dict = {"Cycle": CYCLE, "AttemptCount": attempt, "KillCount": kill}
        if best is not None:
            record["BestTimeMs"] = best
        boss_record[boss_id] = {"Records": {str(DIFFICULTY): record}}

    advanced = {
        "EntitlementRecordScope": f"Steam/{STEAM_ID}",
        "LastContinueSlot": "AutoSave0",
        "BossRecord": boss_record,
    }
    auto_save_0 = {
        "PBZGameSystem": {
            "CycleCount": CYCLE,
            "DifficultModeByte": DIFFICULTY,
            "CycleStartDiedTimes": CYCLE_START_DIED,
            "CurrentCycleGameTime": 12345,
            "HasGameTime": 12345,
            "bIsFinishGame": False,
            "CurrentLevelName": "PBZ_Fujizhilin_WP",
            "LastSaveActorID": "Bell_LZSJ_003",
            "DateTimeString": SAVED_AT,
        },
        "PBZDeathMeta": {"DiedTimes": DIED_TIMES},
        "Player": {"RemainingDays": 42},
    }
    auto_save_1 = {
        "PBZGameSystem": {
            "CycleCount": CYCLE,
            "DifficultModeByte": DIFFICULTY,
            "DateTimeString": "2024.12.31-10.00.00",
        }
    }
    auto_save_2 = {
        "PBZGameSystem": {
            "CycleCount": CYCLE,
            "DifficultModeByte": DIFFICULTY,
            "DateTimeString": "2024.12.30-10.00.00",
        }
    }
    achievements = {"UnlockedTags": [], "ViewedArt": [], "ViewedMusic": []}
    return {
        "__Advanced__": advanced,
        "AutoSave0": auto_save_0,
        "__Achievements__": achievements,
        "AutoSave1": auto_save_1,
        "AutoSave2": auto_save_2,
    }


def record_bytes(records: dict[str, dict] | None = None) -> dict[str, bytes]:
    """把记录对象编码成容器里的原始 JSON 字节。"""
    source = sample_records() if records is None else records
    return {
        name: json.dumps(value, ensure_ascii=False).encode("utf-8")
        for name, value in source.items()
    }


def sample_save_bytes(records: dict[str, dict] | None = None) -> bytes:
    """合成一份可直接被 container.parse_container 读出的存档。"""
    return container.build_container(record_bytes(records), TEST_KEY, container.ALG_ZLIB)


def seed_key_cache(cache_dir: Path, key: bytes = TEST_KEY) -> Path:
    """在临时目录里放好密钥缓存，测试不必再依赖 PBZ.exe。"""
    cache_dir = Path(cache_dir)
    key_mod._remember(cache_dir / "key.cache", {"size": 0, "mtime_ns": 0}, "test", key)
    return cache_dir


def write_fake_exe(path: Path, key: bytes = TEST_KEY) -> Path:
    """造一个能派生指定密钥的假 PBZ.exe（带锚点，不需要 511 MB）。"""
    path = Path(path)
    first = bytes(range(32))
    second = bytes(a ^ b for a, b in zip(first, key))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"MZ"
        + b"\x00" * 64
        + key_mod.ANCHOR
        + b"\x00" * key_mod.SKIP_AFTER_ANCHOR
        + first
        + second
        + b"\x00" * 64
    )
    return path
