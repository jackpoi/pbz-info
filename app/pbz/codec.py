"""Oodle Kraken 解码器（native/pbz_codec.dll）的加载与校验。

DLL 来自 PBZ-Editor 构建的 oozextract（MIT），不是 Epic 的 oo2core。
打包成 onefile 后它位于 sys._MEIPASS，开发时位于仓库根的 native/。
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import sys
from pathlib import Path

DLL_NAME = "pbz_codec.dll"
MANIFEST_NAME = "manifest.json"
EXPECTED_ABI = 1


class CodecError(Exception):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def native_dir() -> Path:
    """DLL 所在目录：onefile 下是解压目录，否则是仓库的 native/。"""
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        candidate = Path(bundle) / "native"
        if candidate.is_dir():
            return candidate
    return repo_root() / "native"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_dll(dll: Path, manifest: Path) -> dict:
    """比对 manifest 里的 sha256，防止 DLL 被替换。"""
    try:
        meta = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CodecError(f"无法读取 {manifest}: {exc}") from exc

    expected = meta.get("sha256")
    if not expected:
        raise CodecError(f"{manifest} 缺少 sha256")

    actual = _sha256(dll)
    if actual.lower() != expected.lower():
        raise CodecError(f"{dll.name} 校验失败：{actual} != {expected}")
    return meta


class Codec:
    """pbz_decode 的薄包装。"""

    def __init__(self, dll: Path | None = None, *, verify: bool = True) -> None:
        base = native_dir()
        dll = Path(dll) if dll else base / DLL_NAME
        if not dll.is_file():
            raise CodecError(f"找不到解码器 {dll}")

        if verify:
            verify_dll(dll, dll.with_name(MANIFEST_NAME))

        try:
            lib = ctypes.CDLL(str(dll))
        except OSError as exc:
            raise CodecError(f"无法加载 {dll.name}: {exc}") from exc

        lib.pbz_codec_version.restype = ctypes.c_uint32
        version = lib.pbz_codec_version()
        if version != EXPECTED_ABI:
            raise CodecError(f"ABI 不匹配：{version} != {EXPECTED_ABI}")

        self._fn = lib.pbz_decode
        self._fn.restype = ctypes.c_ssize_t
        self._fn.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        # 让 lib 生命周期跟随实例，避免被 GC
        self._lib = lib

    def decompress(self, data: bytes, size: int) -> bytes:
        out = ctypes.create_string_buffer(size)
        written = self._fn(data, len(data), out, size)
        if written != size:
            raise CodecError(f"解压失败：返回 {written}，期望 {size}")
        return out.raw
