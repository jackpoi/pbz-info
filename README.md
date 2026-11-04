# 影之刃零 · 生涯战绩面板

读取《影之刃零》的本地存档，统计**当前周目**的 Boss 战绩：每个 Boss 的死亡数、击杀状态、最快击杀用时，以及本周目时长与总死亡。

- 需求：`docs/requirements.md`
- 设计：`docs/design.md`
- 界面原型：`docs/prototype/index.html`（可直接用浏览器打开）

## 当前进度

| 里程碑 | 状态 |
|---|---|
| M1 读取层 + 回归测试 | ✅ 完成 |
| M2 窗口 + 界面（pywebview + Vue） | ✅ 完成 |
| M3 打包（PyInstaller onefile） | ✅ 完成 |

打包产物 `dist/pbz-info.exe`（16.7 MB，单文件，无控制台），冷启动到窗口约 0.9 秒。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

## 开发

```powershell
python run.py                      # 启动窗口（需要先构建前端）
python -m pytest tests -q          # 73 项回归测试
python tools\dump.py               # 打印当前存档归一化后的 JSON
python tools\dump.py --save-dir "D:\...\Steam\<SteamID>"
```

改前端：

```powershell
cd web
npm install
npm run dev                        # 浏览器里调样式（无 pywebview 时用样本数据）
npm run build                      # 产出 web/dist/index.html（单文件，打包用）
```

测试需要本机装有游戏（`PBZ.exe` 提供解密密钥）；可用环境变量 `PBZ_TEST_EXE` 指定路径。
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
