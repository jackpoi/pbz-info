# 影之刃零 · 生涯战绩面板

读取《影之刃零》的本地存档，统计**当前周目**的 Boss 战绩：每个 Boss 的死亡数、击杀状态、最快击杀用时，以及本周目时长与总死亡。

- 需求 / 设计：本地维护，不随源码发布

## 当前进度

| 里程碑 | 状态 |
|---|---|
| M1 读取层 + 回归测试 | ✅ 完成 |
| M2 窗口 + 界面（pywebview + Vue） | ✅ 完成 |
| M3 打包（PyInstaller onefile） | ✅ 完成 |

打包产物 `dist/pbz-info.exe`（16.7 MB，单文件，无控制台），冷启动到窗口约 0.9 秒。

## 构建

需要 Windows x64、Python 3.11+、Node 18+。

```powershell
python -m pip install -r requirements-dev.txt
cd web; npm ci; cd ..
powershell -ExecutionPolicy Bypass -File build.ps1
```

## 发布

推送 `v*` 标签后，GitHub Actions 会在 Windows 上跑测试、构建，并创建 Release：

```powershell
git tag -a v0.1.0 -m "pbz-info v0.1.0"
git push origin master --tags
```

工作流见 `.github/workflows/release.yml`：`master` 推送只跑测试与构建并上传 artifact；`v*` 标签才创建 Release，附件是 `pbz-info.exe` 和 `SHA256SUMS.txt`。

## 开发

```powershell
python run.py                      # 启动窗口（需要先构建前端）
python -m pytest tests -q          # 79 项回归测试（2 项需真实游戏资源，默认跳过）
python tools\dump.py               # 打印当前存档归一化后的 JSON
python tools\dump.py --save-dir "D:\...\Steam\<SteamID>"
```

界面回归（Boss 很多时才看得出的问题）：

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

## 数据口径（摘要）

| 指标 | 来源 |
|---|---|
| 本周目时长 | `CurrentCycleGameTime` |
| 总死亡 | `DiedTimes - CycleStartDiedTimes` |
| Boss 死亡 | `max(0, AttemptCount - KillCount)` |
| 击杀用时 | `BestTimeMs` |
| 出现顺序 | `BossRecord` 键的书写顺序 |

统计范围固定为**当前周目 + 当前难度**；跨周目/难度合并没有意义。

## 只读保证

不写存档、不改游戏文件、不联网。Boss 名称来自 `data/bosses.json`（可在 `%LOCALAPPDATA%\pbz-info\bosses.override.json` 里覆盖）。

## 第三方

`native/pbz_codec.dll` 来自 [PBZ-Editor](https://github.com/qry6868/PBZ-Editor) 构建的 MIT 开源解码器 oozextract，见 `THIRD-PARTY.md`。
