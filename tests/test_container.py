"""容器解析：解密 + 解压 + 目录结构回归。

合成容器用固定测试密钥 + zlib，不需要游戏；真实 Oodle 存档的回归
只在设置了 ``PBZ_TEST_SAVE``（并装了游戏）的机器上跑。
"""

from __future__ import annotations

import json

import pytest

from app.pbz import codec as codec_mod
from app.pbz import container, key as key_mod
from support import sample_records


# ----------------------------------------------------------------- 回归

@pytest.fixture(scope="module")
def codec() -> codec_mod.Codec:
    return codec_mod.Codec()


def test_derive_key_is_32_bytes(game_exe):
    assert len(key_mod.derive_key(game_exe)) == 32


def test_directory_layout(sample_save, key):
    raw = sample_save.read_bytes()
    records = container.list_records(raw, key)
    expected = list(sample_records().values())

    assert [r.name for r in records] == list(sample_records())
    assert all(r.alg == container.ALG_ZLIB for r in records)
    assert [r.raw_size for r in records] == [
        len(json.dumps(value, ensure_ascii=False).encode("utf-8")) for value in expected
    ]

    # 第一个块紧接目录块，后续块首尾相接，最后一块正好到文件尾
    _version, _flags, _count, dir_size = container.read_header(raw)
    assert records[0].offset == container.HEADER.size + dir_size
    for previous, current in zip(records, records[1:]):
        assert current.offset == previous.offset + previous.block_size
    assert records[-1].offset + records[-1].block_size == len(raw)


def test_every_record_decodes_to_fixture_json(sample_save, key, codec, dec_records):
    raw = sample_save.read_bytes()
    parsed = container.parse_container(raw, key, codec)

    assert set(parsed) == set(dec_records)
    for name, expected in dec_records.items():
        assert parsed[name] == expected, f"{name} 与合成基准不一致"


def test_only_filters_records(sample_save, key, codec):
    raw = sample_save.read_bytes()
    parsed = container.parse_container(raw, key, codec, only={"__Advanced__"})
    assert set(parsed) == {"__Advanced__"}


def test_wrong_key_raises(sample_save):
    raw = sample_save.read_bytes()
    with pytest.raises(container.ContainerError, match="GCM"):
        container.list_records(raw, b"\x00" * 32)


def test_truncated_file_raises(sample_save, key):
    raw = sample_save.read_bytes()[:64]
    with pytest.raises(container.ContainerError):
        container.list_records(raw, key)


def test_bad_magic_raises():
    with pytest.raises(container.ContainerError, match="容器标识"):
        container.read_header(b"NOPE" + b"\x03" + b"\x01" + b"\x00\x00" + b"\x00" * 4)


# --------------------------------------------------------- 合成容器（不依赖游戏）

def test_synthetic_container_roundtrip():
    key = b"k" * 32
    payloads = {"__Advanced__": b'{"a": 1}', "AutoSave0": b'{"b": [1,2,3]}'}
    raw = container.build_container(payloads, key)

    assert container.list_records(raw, key)[0].name == "__Advanced__"
    parsed = container.parse_container(raw, key)
    assert parsed == {"__Advanced__": {"a": 1}, "AutoSave0": {"b": [1, 2, 3]}}


def test_synthetic_oodle_requires_codec():
    key = b"k" * 32
    raw = container.build_container({"AutoSave0": b"{}"}, key, container.ALG_OODLE)
    with pytest.raises(container.ContainerError, match="Oodle"):
        container.parse_container(raw, key)


def test_json_error_is_reported():
    key = b"k" * 32
    raw = container.build_container({"AutoSave0": b"{not json"}, key)
    with pytest.raises(container.ContainerError, match="JSON"):
        container.parse_container(raw, key)


# --------------------------------------------------- 真实存档（可选，不进仓库）

def test_real_save_decodes(real_save, game_exe, codec):
    """真实 Oodle 流只有装了游戏的机器能覆盖；只断言结构，不比对具体数值。"""
    raw = real_save.read_bytes()
    parsed = container.parse_container(raw, key_mod.derive_key(game_exe), codec)

    assert parsed, "真实存档里没有任何记录"
    assert all(isinstance(value, dict) for value in parsed.values())
