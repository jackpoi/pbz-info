"""生成打包资源：build/app.ico 与 build/splash.png。

    python tools/build_assets.py

图标直接用 web/src/assets/app-icon.png（透明背景）生成多尺寸 ICO；
启动图用一份 HTML 交给 Edge/Chrome 无头截图——字体和界面完全一致。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

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
    """exe 图标带深色圆角底板。

    源图是白笔触 + 透明底，直接做 exe 图标时，浅色任务栏/资源管理器里几乎看不见，
    所以给图标垫一块与界面同色的深底，只用于 exe/ICO；应用内仍用透明底的原图。
    """
    source = ROOT / "web" / "src" / "assets" / "app-icon.png"
    if not source.is_file():
        raise SystemExit(f"缺少图标源文件：{source}")

    size = 256
    plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=56, fill=(22, 20, 17, 255))

    glyph = Image.open(source).convert("RGBA")
    inner = size - 36  # 四周留白，避免笔触贴边
    plate.alpha_composite(glyph.resize((inner, inner), Image.LANCZOS), (18, 18))

    plate.save(
        BUILD / "app.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
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
