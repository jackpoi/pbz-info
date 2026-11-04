"""从游戏主程序派生 AES 密钥，并缓存。

密钥是 build 级常量，不是账号级：同一个游戏版本的所有存档共用一把密钥。
游戏更新后锚点可能移动，因此必须动态搜索，固定偏移只作兜底。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

#: PBZ.exe 中密钥材料的定位锚点（UTF-16LE）
ANCHOR = "sealed but block is PLAINTEXT".encode("utf-16le")

#: 锚点之后还要跳过的字节数
SKIP_AFTER_ANCHOR = 8

#: 密钥材料长度：前 32 字节与后 32 字节 XOR
MATERIAL_LEN = 64

#: 当前 build (26266538) 的兜底偏移；锚点搜索失败时使用
FALLBACK_KEY_OFFSET = 203_193_128


class KeyError_(Exception):
    """派生失败。命名加下划线是为了避开内建 KeyError。"""


def derive_key(exe: Path) -> bytes:
    """从 PBZ.exe 派生 32 字节 AES 密钥。"""
    exe = Path(exe)
    try:
        data = exe.read_bytes()
    except OSError as exc:
        raise KeyError_(f"无法读取 {exe}: {exc}") from exc

    at = data.find(ANCHOR)
    if at >= 0:
        offset = at + len(ANCHOR) + SKIP_AFTER_ANCHOR
    else:
        offset = FALLBACK_KEY_OFFSET

    material = data[offset:offset + MATERIAL_LEN]
    if len(material) != MATERIAL_LEN:
        raise KeyError_(f"密钥材料越界：{exe}，offset={offset}")

    return bytes(a ^ b for a, b in zip(material[:32], material[32:]))


def _fingerprint(exe: Path) -> dict:
    st = exe.stat()
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}


def load_key(exe: Path, cache: Path | None = None, *, force: bool = False) -> bytes:
    """带缓存的密钥加载。

    缓存有效性由 (exe 大小, exe mtime) 判定；任何一项变化都重新派生。
    缓存里存的就是密钥本身——它可以从玩家自己的游戏文件推导出来，
    不是额外的秘密，但也不应该出现在日志里。
    """
    exe = Path(exe)
    fingerprint = _fingerprint(exe)

    if cache is not None and not force:
        for entry in _entries(Path(cache)):
            if entry.get("fingerprint") == fingerprint:
                return bytes.fromhex(entry["key"])

    key = derive_key(exe)

    if cache is not None:
        _remember(Path(cache), fingerprint, str(exe), key)

    return key


def load_cached(cache: Path | None) -> bytes | None:
    """只从缓存取最新的一把密钥，不校验 exe。

    用于"机器上没有游戏、但之前派生过"的场景。
    """
    keys = keys_from_cache(cache)
    return keys[0] if keys else None


def keys_from_cache(cache: Path | None) -> list[bytes]:
    """缓存里的所有密钥，最近使用的在前。

    保留多把是因为：换 exe、换存档来源、或误选了别的 build 时，
    旧密钥仍然可能是对的——解析层挨个试，而不是一错就报"版本不兼容"。
    """
    if cache is None:
        return []
    keys: list[bytes] = []
    for entry in _entries(Path(cache)):
        try:
            key = bytes.fromhex(entry["key"])
        except (TypeError, ValueError, KeyError):
            continue
        if key not in keys:
            keys.append(key)
    return keys


def _entries(path: Path) -> list[dict]:
    """读缓存条目，兼容早期的单密钥格式。"""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []

    if isinstance(data.get("keys"), list):
        return [e for e in data["keys"] if isinstance(e, dict) and e.get("key")]

    # 旧格式 {fingerprint, key, ...}
    if data.get("key") and data.get("fingerprint"):
        return [data]
    return []


def _remember(path: Path, fingerprint: dict, exe: str, key: bytes) -> None:
    entries = _entries(path)
    entries = [e for e in entries if e.get("fingerprint") != fingerprint]
    entries.insert(
        0,
        {
            "fingerprint": fingerprint,
            "exe": exe,
            "key": key.hex(),
            "key_id": hashlib.sha256(key).hexdigest()[:16],
        },
    )
    _write_cache(path, {"version": 2, "keys": entries[:8]})


def _write_cache(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)
