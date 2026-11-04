"""PBZS v3 加密容器的解析。

    header  : "PBZS" | u8 version | u8 flags | u16 recordCount | u32 dirSize
    block   : "PBZS" | u32 01 01 00 00 | nonce(12) | tag(16) | ciphertext
    entry   : u16 nameLen | name(utf-8) | u8 alg | u8 flag |
              u32 rawSize | u32 relOffset | u32 blockSize

两个容易踩的细节：
  1. GCM tag 在密文**前面**，解密时要重排成 ciphertext || tag；
  2. 目录块解密后的明文以 12 字节头的副本开头，目录项从偏移 12 开始。
"""

from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HEADER = struct.Struct("<4sBBHI")
ENTRY_FIXED = struct.Struct("<BBIII")  # alg, flag, rawSize, relOffset, blockSize
BLOCK_MAGIC = b"PBZS"
BLOCK_PREFIX_LEN = 8  # magic(4) + 01 01 00 00
NONCE_LEN = 12
TAG_LEN = 16

ALG_RAW = 0
ALG_ZLIB = 1
ALG_OODLE = 2


class ContainerError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    name: str
    alg: int
    raw_size: int
    offset: int
    block_size: int


class Decompressor(Protocol):
    def decompress(self, data: bytes, size: int) -> bytes: ...


def _unseal(key: bytes, block: bytes) -> bytes:
    if len(block) < BLOCK_PREFIX_LEN + NONCE_LEN + TAG_LEN:
        raise ContainerError("块太短，可能读到了不完整的文件")
    if block[:4] != BLOCK_MAGIC:
        raise ContainerError(f"块标识错误：{block[:4]!r}")
    nonce = block[8:8 + NONCE_LEN]
    tag = block[8 + NONCE_LEN:8 + NONCE_LEN + TAG_LEN]
    ciphertext = block[8 + NONCE_LEN + TAG_LEN:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext + tag, None)
    except InvalidTag as exc:
        raise ContainerError("GCM 校验失败（密钥不对，或文件正在写入）") from exc


def read_header(raw: bytes) -> tuple[int, int, int, int]:
    if len(raw) < HEADER.size:
        raise ContainerError("文件太短，不是 PBZS 容器")
    magic, version, flags, count, dir_size = HEADER.unpack_from(raw, 0)
    if magic != BLOCK_MAGIC:
        raise ContainerError(f"容器标识错误：{magic!r}")
    if version != 3:
        raise ContainerError(f"不支持的容器版本：{version}")
    return version, flags, count, dir_size


def parse_directory(plain: bytes, base: int, count: int) -> list[Record]:
    records: list[Record] = []
    off = HEADER.size  # 明文开头是 12 字节头的副本
    for _ in range(count):
        if off + 2 > len(plain):
            raise ContainerError("目录块被截断")
        (name_len,) = struct.unpack_from("<H", plain, off)
        off += 2
        if off + name_len + ENTRY_FIXED.size > len(plain):
            raise ContainerError("目录项被截断")
        name = plain[off:off + name_len].decode("utf-8")
        off += name_len
        alg, _flag, raw_size, rel_offset, block_size = ENTRY_FIXED.unpack_from(plain, off)
        off += ENTRY_FIXED.size
        records.append(Record(name, alg, raw_size, base + rel_offset, block_size))
    return records


def decompress(record: Record, payload: bytes, codec: Decompressor | None) -> bytes:
    if record.alg == ALG_RAW:
        return payload
    if record.alg == ALG_ZLIB:
        return zlib.decompress(payload)
    if record.alg == ALG_OODLE:
        if codec is None:
            raise ContainerError(f"{record.name}: 需要 Oodle 解码器")
        return codec.decompress(payload, record.raw_size)
    raise ContainerError(f"{record.name}: 未知压缩算法 {record.alg}")


def list_records(raw: bytes, key: bytes) -> list[Record]:
    _version, _flags, count, dir_size = read_header(raw)
    directory = _unseal(key, raw[HEADER.size:HEADER.size + dir_size])
    return parse_directory(directory, HEADER.size + dir_size, count)


def parse_container(
    raw: bytes,
    key: bytes,
    codec: Decompressor | None = None,
    *,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """解出所有记录为 JSON 对象。only 用于只解关心的记录，省掉无谓的解压。"""
    out: dict[str, Any] = {}
    for record in list_records(raw, key):
        if only is not None and record.name not in only:
            continue
        block = raw[record.offset:record.offset + record.block_size]
        if len(block) != record.block_size:
            raise ContainerError(f"{record.name}: 块越界")
        payload = decompress(record, _unseal(key, block), codec)
        try:
            out[record.name] = json.loads(payload)
        except ValueError as exc:
            raise ContainerError(f"{record.name}: JSON 解析失败") from exc
    return out
