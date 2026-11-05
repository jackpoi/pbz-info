# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包脚本（onefile + splash）。

    python tools/build_assets.py                      # 生成 app.ico / splash.png
    cd web; npm run build                             # 生成 web/dist/index.html
    python -m PyInstaller build/pbz-info.spec --noconfirm

产物：dist/pbz-info.exe（单文件，无控制台）
"""

from pathlib import Path
import os

ROOT = Path(SPECPATH).parent

# 这台机器的 Python 是精简发行版，没有 tkinter，而 PyInstaller 的 splash 依赖它。
# 用 PBZ_SPLASH=1 才引入启动图；否则打成普通 onefile。
USE_SPLASH = os.environ.get("PBZ_SPLASH") == "1"
# 排障用：PBZ_CONSOLE=1 打成控制台版本，能看到 traceback
CONSOLE = os.environ.get("PBZ_CONSOLE") == "1"

# 运行时会用 sys._MEIPASS / native 找它
BINARIES = [(str(ROOT / "native" / "pbz_codec.dll"), "native")]

DATAS = [
    (str(ROOT / "native" / "manifest.json"), "native"),
    (str(ROOT / "web" / "dist"), "web/dist"),
    (str(ROOT / "data"), "data"),
]

HIDDEN = [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "clr_loader",
    "pythonnet",
]

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

splash = None
if USE_SPLASH:
    splash = Splash(
        str(ROOT / "build" / "splash.png"),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        always_on_top=True,
    )

extra = [splash, splash.binaries] if splash else []

exe = EXE(
    pyz,
    a.scripts,
    *extra,
    a.binaries,
    a.datas,
    [],
    name="pbz-info",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "build" / "app.ico"),
    version=str(ROOT / "build" / "version_info.txt"),
)
