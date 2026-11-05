"""把解析出来的原始存档记录归一化成界面用的视图模型。

所有口径只在这里算一次：前端不再做二次推导。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .mapping import Mapping

SLOT_PREFIXES = ("AutoSave", "ManualSave")
DATETIME_FORMAT = "%Y.%m.%d-%H.%M.%S"


class StatsError(Exception):
    pass


def parse_saved_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError:
        return None


def format_saved_at(value: Any) -> str:
    parsed = parse_saved_at(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else (value or "")


def pick_slot(records: dict[str, Any]) -> str:
    """优先 __Advanced__.LastContinueSlot，否则取内部存档时间最新的槽。"""
    slots = {
        name: value
        for name, value in records.items()
        if name.startswith(SLOT_PREFIXES) and isinstance(value, dict)
    }
    if not slots:
        raise StatsError("存档里没有可用的存档槽（可能是残缺备份）")

    advanced = records.get("__Advanced__") or {}
    preferred = advanced.get("LastContinueSlot")
    if isinstance(preferred, str) and preferred in slots:
        return preferred

    def sort_key(name: str) -> datetime:
        game = (slots[name].get("PBZGameSystem") or {})
        return parse_saved_at(game.get("DateTimeString")) or datetime.min

    return max(slots, key=sort_key)


def _records_of(container: Any, boss_id: str) -> dict:
    entry = (container or {}).get(boss_id)
    if not isinstance(entry, dict):
        return {}
    recs = entry.get("Records")
    return recs if isinstance(recs, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _advanced_difficulty(key: Any) -> int | None:
    """账号级 Records 的键就是难度，例如 "3"。"""
    text = str(key)
    return int(text) if text.isdigit() else None


def _slot_difficulty(key: Any, cycle: int) -> int | None:
    """槽位 Records 的键是 "<cycle>_<difficulty>"，例如 "0_3"。"""
    parts = str(key).split("_", 1)
    if len(parts) != 2 or parts[0] != str(cycle) or not parts[1].isdigit():
        return None
    return int(parts[1])


def is_first_try(attempt: int, kill: int) -> bool:
    """一命通关：只进入战斗一次就击杀。

    AttemptCount 是"进入战斗"的次数，因此 attempt == 1 意味着没有任何失败尝试。
    """
    return attempt == 1 and kill > 0


def _collect_bosses(
    records: dict[str, Any],
    slot: str,
    cycle: int,
    mapping: Mapping,
) -> list[dict]:
    advanced_bosses = ((records.get("__Advanced__") or {}).get("BossRecord") or {})
    slot_bosses = ((records.get(slot) or {}).get("BossRecord") or {})
    if not isinstance(advanced_bosses, dict):
        advanced_bosses = {}
    if not isinstance(slot_bosses, dict):
        slot_bosses = {}

    # 出现顺序 = 键的书写顺序；账号级优先，只在槽位出现的追加在后
    order: list[str] = []
    for boss_id in list(advanced_bosses) + list(slot_bosses):
        if boss_id not in order:
            order.append(boss_id)

    out: list[dict] = []
    for idx, boss_id in enumerate(order):
        # 同一个 Boss 只会在击杀时的那个难度留下记录；难度不能按当前
        # DifficultModeByte 过滤，否则切换难度后旧难度的战绩会消失。
        by_difficulty: dict[int, dict] = {}

        # 槽位先放，账号级同难度覆盖（账号级可能比槽位新 1 次事件）
        for key, record in _records_of(slot_bosses, boss_id).items():
            if not isinstance(record, dict):
                continue
            diff = _slot_difficulty(key, cycle)
            if diff is not None:
                by_difficulty[diff] = record

        for key, record in _records_of(advanced_bosses, boss_id).items():
            if not isinstance(record, dict):
                continue
            diff = _advanced_difficulty(key)
            if diff is None:
                continue
            if "Cycle" in record and _int(record.get("Cycle")) != cycle:
                continue  # 账号级记的是别的周目，退回槽位
            by_difficulty[diff] = record

        if not by_difficulty:
            continue

        # 防御性选择：理论上一个周目只有一条记录；若有异常的多条，
        # 优先有击杀的，其次难度更高者，保证结果稳定。
        difficulty, record = max(
            by_difficulty.items(),
            key=lambda item: (_int(item[1].get("KillCount")) > 0, item[0]),
        )

        attempt = _int(record.get("AttemptCount"))
        kill = _int(record.get("KillCount"))
        best = _int(record.get("BestTimeMs"))
        out.append(
            {
                "id": boss_id,
                "name": mapping.boss_name(boss_id),
                "idx": idx,
                "attempt": attempt,
                "kill": kill,
                "deaths": max(0, attempt - kill),
                # 0 表示"没有可用的击杀时长"，界面显示破折号而不是 0:00.000
                "bestMs": best if best > 0 else None,
                "firstTry": is_first_try(attempt, kill),
                "difficulty": difficulty,
                "difficultyName": mapping.difficulty_name(difficulty),
            }
        )
    return out


def build_view(records: dict[str, Any], mapping: Mapping, meta: dict | None = None) -> dict:
    """records 是 {记录名: 解析后的 JSON}，至少需要 __Advanced__ 和一个存档槽。"""
    slot = pick_slot(records)
    save = records.get(slot) or {}
    advanced = records.get("__Advanced__") or {}
    game = save.get("PBZGameSystem") or {}
    player = save.get("Player") or {}
    death_meta = save.get("PBZDeathMeta") or {}

    cycle = _int(game.get("CycleCount"))
    difficulty = _int(game.get("DifficultModeByte"))
    died_times = _int(death_meta.get("DiedTimes"))
    cycle_start_died = _int(game.get("CycleStartDiedTimes"))

    bosses = _collect_bosses(records, slot, cycle, mapping)
    boss_deaths = sum(b["deaths"] for b in bosses)
    killed = sum(1 for b in bosses if b["kill"] > 0)

    worst = None
    for boss in bosses:
        # 死亡数并列时取更晚遭遇的（idx 更大），保证结果稳定
        if worst is None or (boss["deaths"], boss["idx"]) > (worst["deaths"], worst["idx"]):
            worst = boss

    steam_id = (meta or {}).get("steamId")
    scope = advanced.get("EntitlementRecordScope")
    if not steam_id and isinstance(scope, str) and "/" in scope:
        steam_id = scope.split("/", 1)[1]

    payload_meta = {
        "source": "main",
        "savePath": None,
        "fileName": None,
        "steamId": steam_id,
        "slot": slot,
        "savedAt": format_saved_at(game.get("DateTimeString")),
        "readAt": None,
        "unmapped": sum(1 for b in bosses if b["name"] is None),
        "stale": False,
    }
    payload_meta.update(meta or {})

    return {
        "ok": True,
        "meta": payload_meta,
        "cycle": {
            "index": cycle + 1,
            "difficulty": difficulty,
            "difficultyName": mapping.difficulty_name(difficulty),
            "finished": bool(game.get("bIsFinishGame")),
            "level": game.get("CurrentLevelName"),
            "bell": game.get("LastSaveActorID"),
            "remainingDays": _int(player.get("RemainingDays")),
            "cycleTime": _int(game.get("CurrentCycleGameTime")),
            "totalTime": _int(game.get("HasGameTime")),
        },
        "totals": {
            "deaths": max(0, died_times - cycle_start_died),
            "bossDeaths": boss_deaths,
            "killed": killed,
            "worst": (
                {"id": worst["id"], "name": worst["name"], "deaths": worst["deaths"]}
                if worst
                else None
            ),
        },
        "bosses": bosses,
    }
