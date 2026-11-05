"""生成打包资源：build/app.ico、build/splash.png、build/version_info.txt。

    python tools/build_assets.py

图标直接用 web/src/assets/app-icon.png（透明背景）生成多尺寸 ICO；
启动图用一份 HTML 交给 Edge/Chrome 无头截图——字体和界面完全一致；
版本资源从 app/__init__.py 的 __version__ 派生，不手写第二份。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
APP_INIT = ROOT / "app" / "__init__.py"

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


def read_version() -> str:
    text = APP_INIT.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        raise SystemExit(f"读不到版本号：{APP_INIT}")
    return match.group(1)


def make_version_info(version: str) -> Path:
    """PyInstaller 的版本资源：资源管理器「属性 → 详细信息」里能看到版本号。

    公司名/产品名都填 pbz-info，不借用游戏厂商名字，避免被当成官方工具。
    """
    parts = re.findall(r"\d+", version)[:4]
    numbers = [int(p) for p in parts] + [0] * (4 - len(parts))
    quad = ", ".join(str(n) for n in numbers)
    target = BUILD / "version_info.txt"
    target.write_text(
        f"""# 由 tools/build_assets.py 生成，不要手改
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}),
    prodvers=({quad}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'pbz-info'),
         StringStruct('FileDescription', '影之刃零 · 生涯战绩面板'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'pbz-info'),
         StringStruct('OriginalFilename', 'pbz-info.exe'),
         StringStruct('ProductName', 'pbz-info'),
         StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return target


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
    version = read_version()
    make_version_info(version)
    make_icon()
    make_splash()
    for name in ("app.ico", "splash.png", "version_info.txt"):
        path = BUILD / name
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size} B")
    print(f"version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
