# Phantom Blade Zero · Career Stats

**English** · [简体中文](README.md)

> A read-only dashboard for *Phantom Blade Zero* saves: per-boss deaths, kill status, kill difficulty and best clear time for the **current cycle**, plus playtime and total deaths.
>
> 读取《影之刃零》的本地存档，按**当前周目**统计每个 Boss 的死亡数、击杀状态、击杀难度与最快击杀用时，以及本周目时长和总死亡。

[![Release](https://img.shields.io/github/v/release/jackpoi/pbz-info?style=flat-square)](https://github.com/jackpoi/pbz-info/releases/latest)
[![CI](https://github.com/jackpoi/pbz-info/actions/workflows/release.yml/badge.svg)](https://github.com/jackpoi/pbz-info/actions/workflows/release.yml)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D6?style=flat-square&logo=windows)](https://github.com/jackpoi/pbz-info/releases/latest)

## Download

Download `pbz-info.exe` from [Releases](https://github.com/jackpoi/pbz-info/releases/latest) and run it. Windows x64 single file, no Python installation required.

The game does not need to be running. If no key is cached yet, select the game's `PBZ.exe` once (usually `...\PBZ\platform\steam\PBZ.exe`); it is remembered afterwards.

## Features

| Feature | Description |
|---|---|
| Current-cycle scope | Current cycle only; the boss list spans difficulties, and a boss never repeats across them |
| Boss records | Deaths, kill status, kill difficulty and best clear time for every boss |
| Run overview | Cycle playtime, total deaths and bosses defeated |
| Auto refresh | Re-reads after the save changes; keeps the last good snapshot if reading fails |
| Manual selection | Choose a `.sav` file or a folder containing `PBZSaveGame.sav` when auto-detection fails |
| Read-only, offline | Never writes saves or game files |
| Single executable | PyInstaller onefile build; double-click to run |

## Usage

1. Launch `pbz-info.exe`.
2. The app auto-detects the Steam library and save directory. If it cannot, select a `.sav` file or a save folder manually.
3. If prompted for a key, select the game's `PBZ.exe` once.
4. Use “刷新” (Refresh) to force a re-read, and “切换存档” (Switch save) to choose another save.

## Build

Requires Windows x64, Python 3.11+ and Node 18+.

```powershell
python -m pip install -r requirements-dev.txt
cd web; npm ci; cd ..
powershell -ExecutionPolicy Bypass -File build.ps1
```

The output is `dist/pbz-info.exe`.

## Development

```powershell
python run.py                      # launch the window
python -m pytest tests -q          # regression tests
python tools\dump.py               # print normalized save JSON
python tools\dump.py --save-dir "D:\...\Steam\<SteamID>"
```

UI regression:

```powershell
python tools\make_fake_save.py --bosses 100        # generate a fake save with 100 bosses
python run.py --save-dir "%TEMP%\pbz-fake\<SteamID>"
node tools\check-scroll.mjs 100 1180 820           # headless assertions for scrolling and sticky header
node tools\check-scroll.mjs 40 1000 700            # minimum window size
```

Frontend:

```powershell
cd web
npm install
npm run dev                        # browser-only development with mock data
npm run build                      # emits web/dist/index.html (single file, used by the build)
```

Most tests use synthetic saves and require no game installation. Real Oodle-stream regressions need
`PBZ_TEST_EXE` (game executable) and `PBZ_TEST_SAVE` (real save path); they are skipped when unset.
**The app itself does not require the game**: when auto-detection fails, pick a save file or folder directly.

## Project layout

```text
app/          Python backend: discovery, key derivation, container parsing, stats, bridge
  pbz/        PBZS container, AES-GCM, Oodle decoder binding
web/          Vue 3 + Vite frontend (single-file build)
data/         Built-in boss mapping
native/       pbz_codec.dll + SHA-256 manifest
tools/        Dev utilities (dump, fake save, scroll check, screenshots)
tests/        Regression tests and synthetic save builders
build/        PyInstaller spec and packaging assets
.github/      CI and release workflow
```

## Read-only guarantee

Never writes saves or modifies game files.

## License

[MIT](LICENSE). `native/pbz_codec.dll` and its upstream components remain under their own licenses; see [THIRD-PARTY.md](THIRD-PARTY.md).

## Third-party

`native/pbz_codec.dll` is built from [PBZ-Editor](https://github.com/qry6868/PBZ-Editor)'s MIT-licensed oozextract decoder. See [THIRD-PARTY.md](THIRD-PARTY.md).
