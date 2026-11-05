# 影之刃零 · 生涯战绩面板

**简体中文** · [English](README.en.md)

> 读取《影之刃零》的本地存档，按**当前周目**统计每个 Boss 的死亡数、击杀状态、击杀难度与最快击杀用时，以及本周目时长和总死亡。
>
> A read-only dashboard for *Phantom Blade Zero* saves: per-boss deaths, kill status, kill difficulty and best clear time, plus playtime and total deaths for the current cycle.

[![Release](https://img.shields.io/github/v/release/jackpoi/pbz-info?style=flat-square)](https://github.com/jackpoi/pbz-info/releases/latest)
[![CI](https://github.com/jackpoi/pbz-info/actions/workflows/release.yml/badge.svg)](https://github.com/jackpoi/pbz-info/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D6?style=flat-square&logo=windows)](https://github.com/jackpoi/pbz-info/releases/latest)

## 下载

从 [Releases](https://github.com/jackpoi/pbz-info/releases/latest) 下载 `pbz-info.exe`，双击运行。Windows x64 单文件，不需要安装 Python。

游戏不需要保持运行。首次使用若没有密钥缓存，选择一次游戏的 `PBZ.exe`（通常在 `...\PBZ\platform\steam\PBZ.exe`），之后会记住。

## 特性

| 特性 | 说明 |
|---|---|
| 当前周目口径 | 只统计当前周目；Boss 列表跨难度读取，同一 Boss 不会跨难度重复 |
| Boss 战绩 | 每个 Boss 的死亡数、击杀状态、击杀难度、最快击杀用时 |
| 生涯概览 | 本周目时长、总死亡、已击败 Boss 数 |
| 自动刷新 | 存档变化后自动重读；读取失败时保留上一次结果 |
| 手动指定 | 找不到游戏时，直接选 `.sav` 文件或包含 `PBZSaveGame.sav` 的目录 |
| 只读离线 | 不写存档、不改游戏文件 |
| 关于 / 检查更新 | 弹窗显示版本号与项目地址；点“检查更新”只读一次 GitHub Releases，有新版本时给出发布页入口 |
| 单文件 | PyInstaller onefile，双击即用 |

## 使用

1. 启动 `pbz-info.exe`。
2. 应用会自动定位 Steam 库和存档目录；找不到时手动选择 `.sav` 文件或存档目录。
3. 提示缺少密钥时，选择一次游戏的 `PBZ.exe`。
4. 窗口内点击“刷新”可强制重读；需要换存档时点击“切换存档”。

## 构建

需要 Windows x64、Python 3.11+、Node 18+。

```powershell
python -m pip install -r requirements-dev.txt
cd web; npm ci; cd ..
powershell -ExecutionPolicy Bypass -File build.ps1
```

产物是 `dist/pbz-info.exe`。

## 开发

```powershell
python run.py                      # 启动窗口（需要先构建前端）
python -m pytest tests -q          # 110 项回归测试（2 项需真实游戏资源，默认跳过）
python tools\dump.py               # 打印当前存档归一化后的 JSON
python tools\dump.py --save-dir "D:\...\Steam\<SteamID>"
```

界面回归：

```powershell
python tools\make_fake_save.py --bosses 100        # 造一份 100 个 Boss 的假存档
python run.py --save-dir "%TEMP%\pbz-fake\<SteamID>"
node tools\check-scroll.mjs 100 1180 820           # 无头浏览器断言滚动与吸顶
node tools\check-scroll.mjs 40 1000 700            # 最小窗口尺寸
```

改前端：

```powershell
cd web
npm install
npm run dev                        # 浏览器里调样式（无 pywebview 时用样本数据）
npm run build                      # 产出 web/dist/index.html（单文件，打包用）
```

常规测试用合成存档，不需要安装游戏；真实存档（Oodle 流）的回归需要设置
`PBZ_TEST_EXE`（游戏 exe）和 `PBZ_TEST_SAVE`（真实存档路径），未设置时自动跳过。
**应用本身不要求安装游戏**：找不到游戏时，直接选一个存档文件或目录即可。

## 项目结构

```text
app/          Python 后端：发现、密钥派生、容器解析、统计、桥接
  pbz/        PBZS 容器、AES-GCM、Oodle 解码器绑定
web/          Vue 3 + Vite 前端（单文件构建）
data/         内置 Boss 映射
native/       pbz_codec.dll + SHA-256 清单
tools/        开发工具（dump、假存档、滚动检查、截图）
tests/        回归测试与合成存档构造器
build/        PyInstaller spec 与打包资源
.github/      CI / 发布工作流
```

## 只读保证

不写存档、不改游戏文件。除你主动点击“检查更新”（只读一次 GitHub Releases 的 latest）外不联网。

## 许可证

[MIT](LICENSE)。`native/pbz_codec.dll` 及其上游组件按各自许可分发，见 [THIRD-PARTY.md](THIRD-PARTY.md)。

## 第三方

`native/pbz_codec.dll` 来自 [PBZ-Editor](https://github.com/qry6868/PBZ-Editor) 构建的 MIT 开源解码器 oozextract，见 [THIRD-PARTY.md](THIRD-PARTY.md)。
