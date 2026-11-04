"""生成一份"假存档"，用来测试很多 Boss、空数据、未映射 ID 等边界情况。

    python tools/make_fake_save.py --bosses 40 --out "%TEMP%\\pbz-fake"

产物是一个完整的存档目录（含 1RealTime 里的一份快照），可以：
    python run.py --save-dir "%TEMP%\\pbz-fake\\<SteamID>"

密钥从本机 PBZ.exe 派生（必需，因为容器要真的加密）；没有游戏时用 --key-from
指向任意能派生密钥的 exe。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pbz import container  # noqa: E402
from app.pbz import key as key_mod  # noqa: E402

STEAM_ID = "12345678901234567"
DEFAULT_EXE = os.environ.get("PBZ_TEST_EXE")


def load_boss_ids(mapping_path: Path) -> list[str]:
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    return list(data["bosses"])


def build_save(key: bytes, boss_ids: list[str], difficulty: int, boss_count: int) -> dict:
    """造出 boss_count 个 Boss 的记录；前几个保持 0 死亡，用于验证排序与空态。"""
    bosses: dict[str, dict] = {}
    for index, boss_id in enumerate(boss_ids[:boss_count]):
        attempts = (index * 7) % 23 + (0 if index % 5 else 0)
        killed = 1 if attempts and index % 4 != 3 else 0
        record = {
            "Cycle": 0,
            "AttemptCount": attempts,
            "KillCount": killed,
            "BestTimeMs": (index + 1) * 37_000 % 900_000 if killed else 0,
        }
        bosses[boss_id] = {"Records": {str(difficulty): record}}

    advanced = {
        "LastContinueSlot": "AutoSave0",
        "BossRecord": bosses,
        "EntitlementRecordScope": f"Steam/{STEAM_ID}",
    }
    slot = {
        "PBZGameSystem": {
            "DifficultModeByte": difficulty,
            "CycleCount": 0,
            "CycleStartDiedTimes": 0,
            "CurrentCycleGameTime": 9 * 3600 + 12 * 60,
            "HasGameTime": 9 * 3600 + 12 * 60,
            "bIsFinishGame": False,
            "CurrentLevelName": "PBZ_Test_Level",
            "LastSaveActorID": "Bell_Test_003",
            "DateTimeString": datetime.now().strftime("%Y.%m.%d-%H.%M.%S"),
        },
        "PBZDeathMeta": {"DiedTimes": sum(b["Records"][str(difficulty)]["AttemptCount"] for b in bosses.values()) + 5},
        "Player": {"RemainingDays": 42},
    }
    return {"__Advanced__": advanced, "AutoSave0": slot}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成用于测试的假存档目录")
    parser.add_argument("--bosses", type=int, default=40, help="Boss 记录条数")
    parser.add_argument("--difficulty", type=int, default=3, help="难度字节")
    parser.add_argument("--out", default=str(Path.home() / "AppData/Local/Temp/pbz-fake"), help="输出根目录")
    parser.add_argument("--exe", default=DEFAULT_EXE, help="派生密钥用的 PBZ.exe（也可用 PBZ_TEST_EXE）")
    args = parser.parse_args()

    if not args.exe:
        print("需要 --exe 或环境变量 PBZ_TEST_EXE 指定游戏 exe", file=sys.stderr)
        return 2
    exe = Path(args.exe)
    if not exe.is_file():
        print(f"找不到 {exe}（用 --exe 指定）", file=sys.stderr)
        return 2

    key = key_mod.derive_key(exe)
    boss_ids = load_boss_ids(ROOT / "data" / "bosses.json")
    records = build_save(key, boss_ids, args.difficulty, args.bosses)

    raw = container.build_container(
        {name: json.dumps(value, ensure_ascii=False).encode("utf-8") for name, value in records.items()},
        key,
    )

    account = Path(args.out) / STEAM_ID
    (account / "1RealTime").mkdir(parents=True, exist_ok=True)
    (account / "PBZSaveGame.sav").write_bytes(raw)
    (account / "1RealTime" / "20260101-120000-000.sav").write_bytes(raw)

    print(f"生成了 {len(records['__Advanced__']['BossRecord'])} 个 Boss 的假存档：")
    print(f"  {account}")
    print("用这个启动：")
    print(f'  python run.py --save-dir "{account}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
