"""通过 Steam 的注册表 / 库配置定位游戏与存档目录。

    注册表 HKCU\\Software\\Valve\\Steam\\SteamPath
      → <Steam>\\steamapps\\libraryfolders.vdf
      → <库>\\steamapps\\appmanifest_<appid>.acf
      → <库>\\steamapps\\common\\<installdir>\\

存档在游戏安装目录内（不是 %LOCALAPPDATA%）：
    <install>\\ProjectPBZ\\Saved\\SaveGames\\Steam\\<17 位 SteamID>\\
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

APP_ID = "4115450"
INSTALL_DIR_NAME = "PBZ"
SAVE_SUBDIR = Path("ProjectPBZ") / "Saved" / "SaveGames" / "Steam"
MAIN_SAVE = "PBZSaveGame.sav"
STEAM_ID_RE = re.compile(r"^\d{17}$")


class DiscoveryError(Exception):
    pass


# --------------------------------------------------------------------------- VDF

def parse_vdf(text: str) -> dict:
    """极简 KeyValues 解析器：够读 libraryfolders.vdf 和 appmanifest_*.acf。"""
    tokens = _tokenize(text)
    value, _ = _parse_block(tokens, 0)
    return value


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in " \t\r\n":
            i += 1
        elif ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif ch in "{}":
            out.append(ch)
            i += 1
        elif ch == '"':
            i += 1
            buf: list[str] = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                else:
                    buf.append(text[i])
                    i += 1
            out.append("".join(buf))
            i += 1
        else:  # 裸 token（少数 vdf 允许）
            start = i
            while i < n and text[i] not in ' \t\r\n{}"':
                i += 1
            out.append(text[start:i])
    return out


def _parse_block(tokens: list[str], i: int) -> tuple[dict, int]:
    out: dict = {}
    while i < len(tokens):
        token = tokens[i]
        if token == "}":
            return out, i + 1
        if i + 1 < len(tokens) and tokens[i + 1] == "{":
            child, i = _parse_block(tokens, i + 2)
            _assign(out, token, child)
        else:
            value = tokens[i + 1] if i + 1 < len(tokens) else ""
            _assign(out, token, value)
            i += 2
    return out, i


def _assign(target: dict, key: str, value) -> None:
    """重复键（多库时会出现）收集成列表。"""
    if key in target:
        existing = target[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            target[key] = [existing, value]
    else:
        target[key] = value


def library_paths(vdf_text: str) -> list[Path]:
    """从 libraryfolders.vdf 里取出所有库路径。"""
    tree = parse_vdf(vdf_text)
    root = tree.get("libraryfolders", tree)
    found: list[Path] = []

    def collect(node) -> None:
        if isinstance(node, dict):
            path = node.get("path")
            if isinstance(path, str) and path:
                found.append(Path(path))
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(root)
    return found


# ------------------------------------------------------------------------ 注册表

def steam_install() -> Path | None:
    if os.name != "nt":
        return None
    import winreg

    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as handle:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        value, _ = winreg.QueryValueEx(handle, name)
                    except OSError:
                        continue
                    if value:
                        return Path(value)
        except OSError:
            continue
    return None


# ----------------------------------------------------------------------- 发现链

def candidate_libraries(steam: Path | None) -> list[Path]:
    roots: list[Path] = []
    if steam is not None:
        roots.append(Path(steam))
        vdf = Path(steam) / "steamapps" / "libraryfolders.vdf"
        try:
            roots.extend(library_paths(vdf.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def find_install(libraries: list[Path], app_id: str = APP_ID) -> Path | None:
    for library in libraries:
        acf = Path(library) / "steamapps" / f"appmanifest_{app_id}.acf"
        try:
            text = acf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        state = parse_vdf(text).get("AppState", {})
        install_dir = state.get("installdir") or INSTALL_DIR_NAME
        install = Path(library) / "steamapps" / "common" / install_dir
        if install.is_dir():
            return install
    return None


def key_exe(install: Path) -> Path:
    """密钥在 platform/steam/PBZ.exe；根目录下的 steam/PBZ.exe 是另一个小文件。"""
    return Path(install) / "platform" / "steam" / "PBZ.exe"


def save_root(install: Path) -> Path:
    return Path(install) / SAVE_SUBDIR


# -------------------------------------------------------------------------- 账号

@dataclass(frozen=True)
class Account:
    steam_id: str
    save_dir: Path

    @property
    def main_save(self) -> Path:
        return self.save_dir / MAIN_SAVE

    @property
    def has_main(self) -> bool:
        return self.main_save.is_file()

    @property
    def mtime_ns(self) -> int:
        try:
            return self.main_save.stat().st_mtime_ns
        except OSError:
            return 0


def list_accounts(root: Path) -> list[Account]:
    """枚举 SaveGames/Steam/<17 位>/，按主存档 mtime 从新到旧。"""
    root = Path(root)
    if not root.is_dir():
        return []
    accounts = [
        Account(child.name, child)
        for child in root.iterdir()
        if child.is_dir() and STEAM_ID_RE.match(child.name)
    ]
    accounts.sort(key=lambda a: a.mtime_ns, reverse=True)
    return accounts


def discover() -> tuple[Path, Path, list[Account]]:
    """返回 (install, exe, accounts)。失败抛 DiscoveryError。"""
    steam = steam_install()
    if steam is None:
        raise DiscoveryError("没有找到 Steam 安装路径")

    libraries = candidate_libraries(steam)
    install = find_install(libraries)
    if install is None:
        raise DiscoveryError("没有在 Steam 库中找到《影之刃零》（appmanifest 缺失）")

    exe = key_exe(install)
    if not exe.is_file():
        raise DiscoveryError(f"没有找到 {exe}")

    accounts = list_accounts(save_root(install))
    if not accounts:
        raise DiscoveryError(f"{save_root(install)} 下没有存档账号目录")

    return install, exe, accounts
