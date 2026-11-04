"""映射表：内置表完整性、名称解析、用户覆盖合并。"""

from __future__ import annotations

import json

import pytest

from app import mapping as mapping_mod


@pytest.fixture()
def builtin() -> mapping_mod.Mapping:
    return mapping_mod.load()


def test_builtin_loads(builtin):
    assert len(builtin.names) > 150
    assert builtin.boss_name("BP_Monster_HuaQianXIao") == "剑痴：花千笑"
    assert builtin.is_known("BP_Monster_ZuoShang") is True


def test_unknown_id_is_none(builtin):
    assert builtin.boss_name("BP_Monster_DoesNotExist") is None
    assert builtin.is_known("BP_Monster_DoesNotExist") is False


def test_difficulty_names(builtin):
    assert builtin.difficulty_name(1) == "入阵者"
    assert builtin.difficulty_name(2) == "破局者"
    assert builtin.difficulty_name(3) == "逆天者"
    assert builtin.difficulty_name(4) == "六十六天"
    assert builtin.difficulty_name(9) is None
    assert builtin.difficulty_name("3") == "逆天者"


def test_data_file_shape():
    data = json.loads((mapping_mod.data_dir() / "bosses.json").read_text(encoding="utf-8"))
    assert data["schema"] == 1
    assert isinstance(data["bosses"], dict)
    for boss_id, entry in data["bosses"].items():
        assert boss_id.startswith("BP_"), boss_id
        assert entry.get("zh"), f"{boss_id} 缺少中文名"
        assert "en" in entry


def test_override_merges(tmp_path):
    override = tmp_path / "bosses.override.json"
    override.write_text(
        json.dumps(
            {
                "difficulties": {"9": "自定义"},
                "bosses": {
                    "BP_Monster_HuaQianXIao": {"zh": "花千笑（改）", "en": "Hua"},
                    "BP_Monster_NewOne": {"zh": "新 Boss", "en": ""},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    merged = mapping_mod.load(override)

    assert merged.boss_name("BP_Monster_HuaQianXIao") == "花千笑（改）"
    assert merged.english["BP_Monster_HuaQianXIao"] == "Hua"
    assert merged.boss_name("BP_Monster_NewOne") == "新 Boss"
    assert merged.difficulty_name(9) == "自定义"
    # 未被覆盖的条目保留
    assert merged.boss_name("BP_Monster_ZuoShang") == "组织冥主：左殇"


def test_missing_override_is_ignored(tmp_path):
    mapping = mapping_mod.load(tmp_path / "nope.json")
    assert mapping.boss_name("BP_Monster_ZuoShang") == "组织冥主：左殇"


def test_broken_override_is_ignored(tmp_path):
    override = tmp_path / "bosses.override.json"
    override.write_text("{ 这不是 json", encoding="utf-8")
    mapping = mapping_mod.load(override)
    assert mapping.boss_name("BP_Monster_ZuoShang") == "组织冥主：左殇"
