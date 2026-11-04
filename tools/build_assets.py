"""生成打包资源：build/app.ico 与 build/splash.png。

    python tools/build_assets.py

图标用 PowerShell + System.Drawing 画（无中文字符串，避免脚本编码问题），
启动图用一份 HTML 交给 Edge/Chrome 无头截图——字体和界面完全一致。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_browser() -> str | None:
    for path in EDGE_CANDIDATES:
        if Path(path).is_file():
            return path
    return shutil.which("msedge") or shutil.which("chrome")


def make_icon() -> None:
    script = BUILD / "make_icon.ps1"
    subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        check=True,
        cwd=str(BUILD),
    )


def make_splash() -> None:
    browser = find_browser()
    if browser is None:
        raise SystemExit("找不到 Edge/Chrome，无法渲染 build/splash.html")

    target = BUILD / "splash.png"
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--screenshot={target}",
            "--window-size=560,320",
            (BUILD / "splash.html").as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    if not target.is_file():
        raise SystemExit("启动图渲染失败")


def main() -> int:
    make_icon()
    make_splash()
    for name in ("app.ico", "splash.png"):
        path = BUILD / name
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
