"""测试公用：把仓库根与 tests/ 加入 sys.path，并提供合成存档与可选的真实资源。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
for entry in (ROOT, TESTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from support import TEST_KEY, sample_records, sample_save_bytes  # noqa: E402

#: 真实游戏资源只在显式指定时使用，仓库里不保留任何本机路径。
GAME_EXE = Path(os.environ["PBZ_TEST_EXE"]) if os.environ.get("PBZ_TEST_EXE") else None
REAL_SAVE = Path(os.environ["PBZ_TEST_SAVE"]) if os.environ.get("PBZ_TEST_SAVE") else None


@pytest.fixture(scope="session")
def dec_records() -> dict:
    """合成存档的解码结果，作为口径回归的基准。"""
    return sample_records()


@pytest.fixture(scope="session")
def sample_save(tmp_path_factory) -> Path:
    """运行时生成的合成存档（zlib 容器，不含任何真实数据）。"""
    path = tmp_path_factory.mktemp("fixtures") / "PBZSaveGame.sav"
    path.write_bytes(sample_save_bytes())
    return path


@pytest.fixture(scope="session")
def key() -> bytes:
    """合成容器使用的固定测试密钥。"""
    return TEST_KEY


@pytest.fixture(scope="session")
def game_exe() -> Path:
    if GAME_EXE is None or not GAME_EXE.is_file():
        pytest.skip("没有设置 PBZ_TEST_EXE（真实游戏 exe 路径）")
    return GAME_EXE


@pytest.fixture(scope="session")
def real_save() -> Path:
    if REAL_SAVE is None or not REAL_SAVE.is_file():
        pytest.skip("没有设置 PBZ_TEST_SAVE（真实存档路径）")
    return REAL_SAVE
