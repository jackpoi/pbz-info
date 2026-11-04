"""程序入口：单实例 → 配置 → 首次解析 → 开窗 → 1 秒轮询（由前端发起）。

    python -m app.main            # 正常启动
    python -m app.main --debug    # 打开 devtools
    python -m app.main --save-dir "D:\\...\\<SteamID>"
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

import webview

from . import bridge as bridge_mod
from . import config as config_mod
from . import service as service_mod

APP_NAME = "pbz-info"
WINDOW_TITLE = "生涯战绩 · 影之刃零"
DEFAULT_SIZE = (1180, 820)
MIN_SIZE = (1000, 700)


def single_instance() -> object | None:
    """命名互斥量；已存在第二个实例时返回 None。

    必须用 use_last_error=True + ctypes.get_last_error()：直接调 kernel32.GetLastError
    会被 ctypes 自己的调用清掉，导致第二个实例误以为自己是第一个。
    """
    if sys.platform != "win32":
        return object()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, 0, f"Local\\{APP_NAME}")
    if not handle:
        return object()
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return None
    return handle


def web_root() -> Path:
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "web"
    return Path(__file__).resolve().parents[1] / "web"


def index_url() -> str:
    index = web_root() / "dist" / "index.html"
    if not index.is_file():
        raise SystemExit(
            f"找不到 {index}\n先构建前端：cd web; npm install; npm run build"
        )
    return index.as_uri()


def apply_dark_titlebar(title: str) -> None:
    """Windows 10/11：把系统标题栏切成深色，别让深色应用顶着一根白条。"""
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        dwmapi = ctypes.windll.dwmapi
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE（20 是 2004+）
            if dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
            ) == 0:
                break
    except Exception:  # noqa: BLE001 - 纯粹是外观，失败不影响功能
        pass


def close_splash() -> None:
    """打包时的启动图：窗口一出现就收掉。

    只有在 PyInstaller 的 splash 真正启用时（bootloader 会设置 _PYI_SPLASH_IPC）
    才去 import pyi_splash，否则那个模块会因为拿不到 IPC 句柄而抛异常。
    """
    if not os.environ.get("_PYI_SPLASH_IPC"):
        return
    try:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="影之刃零 · 生涯战绩面板")
    ap.add_argument("--debug", action="store_true", help="打开开发者工具")
    ap.add_argument("--save-dir", type=Path, default=None, help="指定存档目录（临时覆盖配置）")
    ap.add_argument("--config", type=Path, default=None, help="指定配置文件路径")
    args = ap.parse_args(argv)

    if single_instance() is None:
        return 0  # 已经有一个在跑，安静退出

    config_path = args.config or config_mod.default_path()
    config = config_mod.load(config_path)
    if args.save_dir:
        config["saveDir"] = str(args.save_dir)

    cache_dir = config_mod.default_dir()
    service = service_mod.Service(cache_dir=cache_dir, exe_path=config.get("exePath"))
    bridge = bridge_mod.Bridge(service, config, config_path=config_path)

    geometry = config.get("window") or {}
    window = webview.create_window(
        WINDOW_TITLE,
        url=index_url(),
        js_api=bridge,
        width=geometry.get("width") or DEFAULT_SIZE[0],
        height=geometry.get("height") or DEFAULT_SIZE[1],
        x=geometry.get("x"),
        y=geometry.get("y"),
        min_size=MIN_SIZE,
        resizable=True,
        background_color="#0a0908",
    )
    bridge.attach_window(window)  # 文件对话框与退出需要窗口句柄

    def persist_geometry() -> None:
        try:
            config.setdefault("window", {})
            config["window"].update(
                {
                    "width": window.width,
                    "height": window.height,
                    "x": window.x,
                    "y": window.y,
                }
            )
            config_mod.save(config, config_path)
        except Exception:  # noqa: BLE001 - 关闭时不该抛
            pass

    window.events.closing += persist_geometry
    window.events.shown += lambda: (apply_dark_titlebar(WINDOW_TITLE), close_splash())

    try:
        webview.start(debug=args.debug)
    except Exception as exc:  # noqa: BLE001 - 窗口版没有控制台，必须弹出来
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(
                None,
                f"启动失败：{type(exc).__name__}: {exc}\n\n"
                "如果提示缺少 WebView2，请安装 Microsoft Edge WebView2 Runtime 后重试。",
                WINDOW_TITLE,
                0x10,  # MB_ICONERROR
            )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
