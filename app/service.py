"""读取编排：定位 → 密钥 → 解析 → 归一化，并缓存上一次成功的结果。

界面只跟这个类打交道：拿到的永远是"当前最可信的一份数据"，
失败时返回上一次成功的结果 + 错误码，而不是清空界面。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import discovery, mapping as mapping_mod, stats
from .pbz import codec as codec_mod
from .pbz import container, key as key_mod, savefile

ERROR_NO_GAME = "NO_GAME"
ERROR_NO_SAVE = "NO_SAVE"
ERROR_NEED_EXE = "NEED_EXE"
ERROR_KEY_FAIL = "KEY_FAIL"
ERROR_PARSE_FAIL = "PARSE_FAIL"
ERROR_IO_BUSY = "IO_BUSY"
ERROR_BAD_DIR = "BAD_DIR"


class ServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Location:
    """一次解析所需的全部路径。exe_path 可能为 None（没装游戏、也没缓存密钥）。"""

    save_path: Path
    exe_path: Path | None
    save_dir: Path
    steam_id: str | None


class Service:
    def __init__(
        self,
        *,
        cache_dir: Path | None = None,
        mapping: mapping_mod.Mapping | None = None,
        exe_path: Path | str | None = None,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self._mapping = mapping or mapping_mod.load(self._cache_dir / "bosses.override.json")
        self._key: bytes | None = None
        self._codec: codec_mod.Codec | None = None
        self._last: dict | None = None
        self._signature: tuple[int, int] | None = None
        self._exe_override: Path | None = Path(exe_path) if exe_path else None

    def set_exe(self, exe_path: Path | str | None) -> None:
        """记住用户手动指定的 PBZ.exe；换 exe 时清掉已缓存的密钥。"""
        new = Path(exe_path) if exe_path else None
        if new != self._exe_override:
            self._key = None
            self._signature = None
        self._exe_override = new

    # ------------------------------------------------------------------ 定位

    def locate(self, save_dir: Path | str | None = None, save_path: Path | str | None = None) -> Location:
        """定位要读的文件。

        save_path 优先：用户明确选了一个 .sav，就老老实实读那个文件
        （可能是 1RealTime 里的快照、别人的存档、或备份）。
        """
        if save_path:
            path = Path(save_path)
            if path.is_dir():
                return self.locate(save_dir=path)
            if not path.is_file():
                raise ServiceError(ERROR_BAD_DIR, f"文件不存在：{path}")
            directory = path.parent
            exe = self._exe_override or self._exe_from_save_dir(directory)
            return Location(path, exe, directory, _steam_id_of(directory))

        if save_dir:
            directory = resolve_save_dir(save_dir)
            if not (directory / MAIN_SAVE).is_file():
                raise ServiceError(ERROR_BAD_DIR, f"{directory} 里没有 {MAIN_SAVE}")
            save_path = directory / MAIN_SAVE
            exe = self._exe_override or self._exe_from_save_dir(directory)
            return Location(save_path, exe, directory, directory.name)

        try:
            install, exe, accounts = discovery.discover()
        except discovery.DiscoveryError as exc:
            raise ServiceError(ERROR_NO_GAME, str(exc)) from exc

        account = next((a for a in accounts if a.has_main), None)
        if account is None:
            raise ServiceError(ERROR_NO_SAVE, "存档账号目录里没有 PBZSaveGame.sav")
        return Location(account.main_save, self._exe_override or exe, account.save_dir, account.steam_id)

    @staticmethod
    def _exe_from_save_dir(save_dir: Path) -> Path | None:
        """手动指定存档目录时，向上找游戏根目录下的 platform/steam/PBZ.exe。"""
        for parent in save_dir.parents:
            candidate = parent / "platform" / "steam" / "PBZ.exe"
            if candidate.is_file():
                return candidate
        try:
            _install, exe, _accounts = discovery.discover()
            return exe
        except discovery.DiscoveryError:
            return None

    # ------------------------------------------------------------------ 解析

    def _ensure_codec(self) -> codec_mod.Codec:
        if self._codec is None:
            try:
                self._codec = codec_mod.Codec()
            except codec_mod.CodecError as exc:
                raise ServiceError(ERROR_KEY_FAIL, str(exc)) from exc
        return self._codec

    def refresh(
        self,
        *,
        save_dir: Path | str | None = None,
        save_path: Path | str | None = None,
        force: bool = False,
    ) -> dict:
        """返回界面数据。失败时保留上一次成功的结果。"""
        try:
            location = self.locate(save_dir, save_path)
            signature = savefile.stat_signature(location.save_path)
            if not force and signature is not None and signature == self._signature and self._last:
                return self._last
        except ServiceError as exc:
            return self._failure(exc.code, exc.message)

        try:
            view = self._parse(location)
        except ServiceError as exc:
            return self._failure(exc.code, exc.message)
        except savefile.ReadError as exc:
            return self._failure(ERROR_IO_BUSY, str(exc))
        except container.ContainerError as exc:
            return self._failure(ERROR_PARSE_FAIL, str(exc))
        except Exception as exc:  # noqa: BLE001 - 读档失败不该让界面崩掉
            return self._failure(ERROR_PARSE_FAIL, f"{type(exc).__name__}: {exc}")

        self._signature = signature
        self._last = view
        return view

    def _candidate_keys(self, location: Location) -> list[bytes]:
        """按可信度排序的候选密钥：本次已成功的 → 已知 exe 派生 → 缓存里的其余密钥。"""
        cache = self._cache_dir / "key.cache"
        keys: list[bytes] = []

        def add(key: bytes | None) -> None:
            if key is not None and key not in keys:
                keys.append(key)

        add(self._key)
        for candidate in (self._exe_override, location.exe_path):
            if candidate is None or not Path(candidate).is_file():
                continue
            try:
                add(key_mod.load_key(Path(candidate), cache))
            except key_mod.KeyError_:
                continue  # 这个 exe 派生不出来就算了，还有缓存兜底
        for key in key_mod.keys_from_cache(cache):
            add(key)

        if not keys:
            raise ServiceError(
                ERROR_NEED_EXE,
                "这个存档需要一个密钥。请选择游戏的 PBZ.exe（每台机器只需一次）。",
            )
        return keys

    def _try_parse(self, raw: bytes, keys: list[bytes]) -> tuple[dict, bytes]:
        last: Exception | None = None
        for key in keys:
            try:
                return container.parse_container(raw, key, self._ensure_codec()), key
            except container.ContainerError as exc:
                last = exc
        raise last  # type: ignore[misc]

    def _parse(self, location: Location) -> dict:
        keys = self._candidate_keys(location)
        raw = savefile.read_bytes(location.save_path)
        is_main = location.save_path.name.lower() == MAIN_SAVE.lower()

        try:
            records, key = self._try_parse(raw, keys)
        except container.ContainerError:
            # 只有"读的是主存档"时才去翻实时快照；
            # 用户明确指定了某个文件，就如实报错，不要偷偷换成别的文件。
            fallback = self._newest_snapshot(location.save_dir) if is_main else None
            if fallback is None:
                raise
            records, key = self._try_parse(savefile.read_bytes(fallback), keys)
            self._key = key
            view = stats.build_view(records, self._mapping, self._meta(location, fallback))
            view["meta"]["source"] = "snapshot"
            return view

        self._key = key
        return stats.build_view(records, self._mapping, self._meta(location, location.save_path))

    @staticmethod
    def _newest_snapshot(save_dir: Path) -> Path | None:
        folder = Path(save_dir) / "1RealTime"
        try:
            files = sorted(p for p in folder.glob("*.sav") if p.is_file())
        except OSError:
            return None
        return files[-1] if files else None

    @staticmethod
    def _meta(location: Location, used: Path) -> dict:
        source = "main" if used.name.lower() == MAIN_SAVE.lower() else "file"
        return {
            "source": source,
            "savePath": str(location.save_path),
            "saveDir": str(location.save_dir),
            "fileName": used.name,
            "steamId": location.steam_id,
            "readAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stale": False,
        }

    def _failure(self, code: str, message: str) -> dict:
        payload = dict(self._last) if self._last else {"ok": False, "meta": {}, "cycle": None,
                                                       "totals": None, "bosses": []}
        payload["ok"] = False
        payload["error"] = {"code": code, "message": message}
        if self._last:
            payload["stale"] = True
            payload["meta"] = dict(self._last["meta"], stale=True)
        return payload


MAIN_SAVE = discovery.MAIN_SAVE


def resolve_save_dir(path: Path | str) -> Path:
    """用户可能选的是目录，也可能直接选了 .sav 文件。"""
    resolved = Path(path)
    if resolved.is_file() and resolved.suffix.lower() == ".sav":
        return resolved.parent
    return resolved


def _steam_id_of(directory: Path) -> str | None:
    """存档文件所在目录往上找 17 位数字目录（1RealTime 里的快照也能认出账号）。"""
    for candidate in (directory, *list(directory.parents)[:2]):
        name = candidate.name
        if len(name) == 17 and name.isdigit():
            return name
    return None


def default_cache_dir() -> Path:
    base = Path.home() / "AppData" / "Local"
    if sys.platform != "win32":
        base = Path.home() / ".local" / "share"
    return base / "pbz-info"
